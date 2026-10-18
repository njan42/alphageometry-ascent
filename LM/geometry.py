import inspect
import re
from pathlib import Path

import rabbit
from LM.facts import serialize_facts, useful_for_prompt
from problem import Problem
from relations import Point


def list_constructions():
    return [rabbit.describe(function) for function in rabbit.rabbits]


def apply_construction(problem, command):
    """Validate a single construction command."""
    if not isinstance(command, str) or not re.fullmatch(
        r"[A-Za-z_][A-Za-z_0-9]*(?:[ \t]+[A-Za-z][A-Za-z0-9]*)+", command.strip()
    ):
        raise ValueError("Expected one construction followed by existing point names")
    name, *names = command.split()
    functions = {f.__name__: f for f in rabbit.rabbits}
    if name not in functions:
        raise ValueError(f"Unknown construction: {name}")
    function = functions[name]
    arity = len(inspect.signature(function).parameters) - 1
    if len(names) != arity:
        raise ValueError(f"{name} needs {arity} input points, got {len(names)}")
    points = {p.name: p for p in problem.points}
    if set(names) - points.keys():
        raise ValueError(f"Unknown points: {sorted(set(names) - points.keys())}")
    if len(set(names)) != len(names):
        raise ValueError("Construction input points must be distinct")
    if not function(problem, *(points[name] for name in names)):
        raise ValueError("Construction is degenerate, coincident, or numerically invalid")


def clone_problem(problem):
    """Copy the symbolic state while preserving derivations."""
    state = Problem(set(), set(problem.goals), set(problem.points))
    state.possible_relations = set(problem.possible_relations)
    state.impossible_relations = set(problem.impossible_relations)
    for fact, derivations in problem.predicates.items():
        for deduction in derivations:
            state._add_predicate(fact, set(deduction.parent_predicates), deduction.rule_name)
    return state


def state_dict(problem):
    return {
        "points": [{"name": p.name, "x": p.x, "y": p.y}
                   for p in sorted(problem.points, key=lambda p: p.name)],
        "known_predicates": serialize_facts(problem.predicates),
        "goals": serialize_facts(problem.goals),
        "missing_goals": serialize_facts(problem.goals - problem.predicates.keys()),
        "solved": problem.is_solved(),
    }


def try_construction(problem, command):
    """Return a separate saturated branch and its delta as a copy."""
    branch = clone_problem(problem)
    before = set(problem.predicates)
    old_points = set(problem.points)
    try:
        apply_construction(branch, command)
    except ValueError as error:
        return None, {"command": command, "accepted": False, "error": str(error)}
    direct = set(branch.predicates) - before
    branch.run_ddar(stop_when_solved=False)
    added = set(branch.predicates) - before
    result = {
        "command": command,
        "accepted": True,
        "solved": branch.is_solved(),
        "new_points": sorted(p.name for p in branch.points - old_points),
        "construction_predicates": serialize_facts(direct),
        "new_predicates": serialize_facts(added),
        "new_predicates_on_existing_points": serialize_facts(
            p for p in added if useful_for_prompt(p) and p._init_args is not None
            and {a for a in p._init_args if isinstance(a, Point)} <= old_points
        ),
    }
    return branch, result


def load_problem(directory):
    # Lazy import keeps the engine usable independently of plotting/file input.
    from solve import construct_problem
    directory = Path(directory).expanduser().resolve()
    problem = construct_problem(
        str(directory / "problem.ggb"), str(directory / "problem.txt")
    )
    if not problem.goals:
        raise ValueError("The problem must contain at least one goal")
    problem.run_ddar(stop_when_solved=False)
    return problem
