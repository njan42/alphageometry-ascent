from contextlib import redirect_stdout
import sys
from uuid import uuid4

try:
    from mcp.server import MCPServer
    from mcp.server.mcpserver.exceptions import ToolError
except ImportError as error:
    raise SystemExit("Install the MCP extra first: uv sync --extra mcp") from error

from LM import geometry

server = MCPServer(
    "AlphaGeometry",
    instructions="Use load_problem, get_state, and list_constructions to inspect a problem. "
    "try_construction tests on a separate branch and runs DDAR. Continue with its returned "
    "problem_id to keep the branch, or reuse the previous id to discard it. "
    "Only DDAR establishes proof facts. Use get_proof when solved.",
)
problems = {}


def remember(problem):
    identifier = uuid4().hex
    problems[identifier] = problem
    return {"problem_id": identifier, **geometry.state_dict(problem)}


def lookup(problem_id):
    if problem_id not in problems:
        raise ToolError(f"Unknown problem_id: {problem_id}")
    return problems[problem_id]


@server.tool()
async def load_problem(directory: str = "midpoint") -> dict:
    """Load and saturate a directory containing problem.txt (and optional problem.ggb).

    Use directory='midpoint' for the built-in midpoint theorem example.
    """
    # DDAR prints diagnostics; stdout must contain only MCP protocol messages.
    try:
        with redirect_stdout(sys.stderr):
            if directory == "midpoint":
                import rabbit
                problem = rabbit.midpoint_theorem_problem()
                problem.run_ddar(stop_when_solved=False)
            else:
                problem = geometry.load_problem(directory)
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        raise ToolError(f"Cannot load problem: {error}") from error
    return remember(problem)


@server.tool()
async def get_state(problem_id: str) -> dict:
    """Return points, all known predicates, goals, missing goals, and solved status."""
    return {"problem_id": problem_id, **geometry.state_dict(lookup(problem_id))}


@server.tool()
async def list_constructions() -> list[dict]:
    """Return allowed construction signatures, descriptions, and possible deductions."""
    return geometry.list_constructions()


@server.tool()
async def try_construction(problem_id: str, construction: str, inputs: list[str]) -> dict:
    """Validate a rabbit and saturate a separate branch; preserve the original state.

    Example: construction='mirror', inputs=['E', 'D']. A valid trial returns a
    new problem_id and state. Continue using that id to keep the construction.
    """
    # Do not allow spaces/newlines in structured input fields to smuggle a
    # different command through the text command validator.
    if any(not value or any(c.isspace() for c in value) for value in [construction, *inputs]):
        raise ToolError("Construction and inputs must be individual names")
    with redirect_stdout(sys.stderr):
        branch, result = geometry.try_construction(
            lookup(problem_id), " ".join([construction, *inputs])
        )
    return {**result, **remember(branch)} if branch is not None else {**result, "problem_id": problem_id}


@server.tool()
async def get_proof(problem_id: str) -> dict:
    """Return the symbolic DDAR proof if the goals are solved."""
    problem = lookup(problem_id)
    return {"solved": problem.is_solved(), "proof": str(problem) if problem.is_solved() else None}


@server.tool()
async def discard_problem(problem_id: str) -> dict:
    """Release a problem/branch that is no longer needed."""
    lookup(problem_id)
    del problems[problem_id]
    return {"discarded": problem_id}


if __name__ == "__main__":
    server.run(transport="stdio")
