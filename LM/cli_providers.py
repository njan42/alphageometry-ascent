import json
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
from time import perf_counter

PROVIDERS = ("codex", "antigravity", "claude", "copilot")


class AgentError(RuntimeError):
    pass


class EventLog:
    def __init__(self, path=None):
        self.path = Path(path) if path else None

    def write(self, event, **data):
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps({"event": event, **data}, ensure_ascii=False) + "\n")


class CLIProvider:
    def __init__(self, name, *, model=None, timeout=120, log=None, executable=None):
        if name not in PROVIDERS:
            raise ValueError(f"Unknown provider: {name}")
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Agent timeout must be finite and positive")
        self.name, self.model, self.timeout = name, model, timeout
        self.last_metrics = {}
        self.log = log or EventLog()
        binary = "agy" if name == "antigravity" else name
        self.executable = shutil.which(executable or binary)
        if not self.executable:
            raise AgentError(f"{name} CLI is not installed or is not on PATH")

    def arguments(self, output, prompt=None):
        if self.name == "codex":
            args = ["exec", "--sandbox", "read-only", "--ephemeral", "--skip-git-repo-check",
                    "--output-last-message", str(output), "-"]
        elif self.name == "antigravity":
            args = ["--output-format", "json", "--disable-slash-commands"]
            if not self.model:
                args += ["--effort", "low"]
        elif self.name == "claude":
            args = ["--print", "--output-format", "json", "--tools", "",
                    "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
                    "--no-session-persistence"]
        else:
            args = ["--silent", "--no-ask-user", "--disable-builtin-mcps", "--available-tools=",
                    "--deny-tool", "shell", "--deny-tool", "write", "--deny-tool", "url",
                    "--prompt", prompt]
        if self.model:
            args += ["--model", self.model]
        if self.name == "antigravity":
            # agy takes the entire one-shot prompt as an argument. Close stdin
            # rather than leaving it available for an interactive input loop.
            args += ["--print", prompt]
        return [self.executable, *args]

    def decode(self, stdout, output):
        if self.name == "codex":
            if not output.is_file():
                raise AgentError("Codex did not produce a final response file")
            return output.read_text(encoding="utf-8").strip()
        if self.name in ("antigravity", "claude"):
            try:
                data = json.loads(stdout)
            except json.JSONDecodeError as error:
                raise AgentError(f"{self.name} returned invalid JSON") from error
            if not isinstance(data, dict):
                raise AgentError(f"{self.name} returned an unexpected JSON envelope")
            if data.get("is_error") or data.get("error"):
                raise AgentError(f"{self.name} reported failure: {data.get('error') or data.get('result')}")
            if self.name == "antigravity" and data.get("status") != "SUCCESS":
                raise AgentError(f"Antigravity did not complete successfully: {data.get('status')}")
            if self.name == "antigravity":
                duration = data.get("duration_seconds")
                if isinstance(duration, (int, float)) and math.isfinite(duration) and duration >= 0:
                    self.last_metrics["reported_agent_seconds"] = duration
                    self.last_metrics["outside_reported_agent_seconds"] = max(
                        0, self.last_metrics.get("subprocess_seconds", duration) - duration)
                usage = data.get("usage", {})
                for key in ("input_tokens", "output_tokens", "thinking_tokens", "cache_read_tokens"):
                    if isinstance(usage.get(key), (int, float)):
                        self.last_metrics[key] = usage[key]
            response = data.get("response" if self.name == "antigravity" else "result")
            if not isinstance(response, str):
                raise AgentError(f"{self.name} response has no final text")
            return response.strip()
        return stdout.strip()

    def generate(self, prompt):
        self.last_metrics = {}
        with tempfile.TemporaryDirectory(prefix="geometry-agent-") as directory:
            output = Path(directory) / "response.txt"
            args = self.arguments(output, prompt)
            started = perf_counter()
            self.log.write("agent_request", provider=self.name, model=self.model, prompt=prompt,
                           requested_effort="low" if self.name == "antigravity" and not self.model else None)
            try:
                process = subprocess.Popen(
                    args, stdin=subprocess.DEVNULL if self.name in ("antigravity", "copilot") else subprocess.PIPE,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, cwd=directory, start_new_session=True,
                )
                try:
                    stdout, stderr = process.communicate(None if self.name in ("antigravity", "copilot") else prompt, timeout=self.timeout)
                except (subprocess.TimeoutExpired, KeyboardInterrupt):
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    stdout, stderr = process.communicate()
                    self.log.write("agent_interrupted", provider=self.name,
                                   elapsed=perf_counter() - started, stdout=stdout, stderr=stderr)
                    raise
                elapsed = perf_counter() - started
                self.last_metrics["subprocess_seconds"] = elapsed
                self.log.write("agent_response", provider=self.name, exit_code=process.returncode,
                               elapsed=elapsed, stdout=stdout, stderr=stderr,
                               final_response=output.read_text() if output.is_file() else None)
                if process.returncode:
                    raise AgentError(f"{self.name} exited {process.returncode}: {(stderr or stdout)[-2000:]}")
                response = self.decode(stdout, output)
                if not response:
                    raise AgentError(f"{self.name} returned an empty response")
                self.log.write("agent_metrics", provider=self.name, **self.last_metrics)
                return response
            except subprocess.TimeoutExpired as error:
                self.log.write("agent_error", error="timeout", seconds=self.timeout)
                diagnostic = stderr.strip()[-500:]
                detail = f" Last diagnostic: {diagnostic}" if diagnostic else ""
                raise AgentError(f"{self.name} timed out after {self.timeout:g}s.{detail}") from error
            except OSError as error:
                raise AgentError(f"Could not run {self.name}: {error}") from error
