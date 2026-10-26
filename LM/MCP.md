# MCP

MCP lets an agent call the geometry engine directly. The host (Antigravity,
Codex, Claude Code, or Copilot) launches this repository's local stdio server;
it can inspect facts and try constructions without editing or executing Python.
This is a separate entry point from `solve.py --rabbit agent`, where the Python
solver controls the search and calls a headless CLI for suggestions.

## Install and register

Run from the repository root:

```sh
uv sync --extra mcp
```

Choose the host you want to use. Each registration captures the absolute
checkout directory through `$PWD`, so the server also works when the host
starts from another directory.

### Antigravity

```sh
agy mcp add alphageometry -- uv --directory "$PWD" run --extra mcp python -m LM.mcp_server
```

### Codex

```sh
codex mcp add alphageometry -- uv --directory "$PWD" run --extra mcp python -m LM.mcp_server
```

### Claude Code

```sh
claude mcp add alphageometry -- uv --directory "$PWD" run --extra mcp python -m LM.mcp_server
```

### Copilot

```sh
copilot mcp add alphageometry -- uv --directory "$PWD" run --extra mcp python -m LM.mcp_server
```

Start a new host session after registration. Use its `/mcp` view to check the
connection and tools. The host starts the server; you do not need to start it in
a separate terminal or expose a port. Starting `python -m LM.mcp_server`
manually waits for MCP messages on stdin rather than displaying a prompt.

For hosts configured using JSON, the corresponding entry is:

```json
{
  "mcpServers": {
    "alphageometry": {
      "command": "uv",
      "args": [
        "--directory", "/absolute/path/to/alphageometry-ascent",
        "run", "--extra", "mcp", "python", "-m", "LM.mcp_server"
      ]
    }
  }
}
```

## Ask the agent to solve a problem

Example request:

> Use the alphageometry MCP tools to load the built-in ceva problem. Inspect
> its known predicates and available constructions. Try auxiliary constructions
> until DDAR proves the goal, then show me the proof. Keep the original diagram
> available while exploring alternative branches.

For a file-based problem, give the absolute directory containing `problem.txt`
and, optionally, `problem.ggb`.

The tool flow is:

1. `load_problem({"directory": _})` returns a `problem_id`, point
   coordinates, all known predicates, goals, missing goals, and `solved`.
   Loading runs DDAR; a problem it can solve already needs no construction.
2. `list_constructions({})` lists permitted signatures and descriptions.
3. `get_state({"problem_id": "ORIGINAL_ID"})` inspects a loaded state.
4. `try_construction({"problem_id": "ORIGINAL_ID", "construction": _,
   "inputs": [_, _, ...]})` validates the construction and runs DDAR on a copy.
   It returns the new state under a **new** `problem_id`, direct construction
   facts, and newly deduced predicates, including those on the original points.
5. `get_proof({"problem_id": "NEW_ID"})` returns the symbolic proof when solved.
6. `discard_problem({"problem_id": "UNUSED_ID"})` releases an unused state.

To keep a trial, use its returned id in subsequent calls. To discard its effect,
keep using the original id. Failed constructions return `accepted: false` and
an explanation; the original state is preserved. Bad ids, malformed fields,
and missing input files produce explicit MCP tool errors without killing the
session. Unsolved states return `proof: null`.

States live in memory in one server process. Restarting the host/server loses
its ids; load the problem again. Geometry diagnostics go to stderr, while
stdout carries MCP messages only.

Official host documentation:
[Antigravity MCP](https://antigravity.google/docs/mcp/),
[Codex MCP](https://learn.chatgpt.com/docs/extend/mcp?surface=cli),
[Claude Code MCP](https://code.claude.com/docs/en/mcp), and
[Copilot CLI](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference).
