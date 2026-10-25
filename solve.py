# solve.py
import argparse
import os
import math
import read_in_relations
import geogebra
import rabbit
from problem import Problem
from relations import Point


def construct_problem(
    ggb_file: str = "",
    problem_file: str = "",
    plot: bool = False,
) -> Problem:
    """
    Construct a geometry problem either from:
      - file mode (ggb_file + problem_file), or
      - manual mode (no ggb file -> points + predicates are taken from txt,
        with missing points defaulting to (0,0)).
    """

    use_geogebra = bool(ggb_file) and os.path.isfile(ggb_file)

    if use_geogebra:
        points, lines, circles = geogebra.parse_picture(ggb_file)

        if plot:
            import constructions
            constructions.plot(points, lines, circles)

        with open(problem_file, "r") as f:
            txt = f.read()
        predicates, goals = read_in_relations.parse_string(
            txt, points=points, allow_dummy_points=False
        )

    else:
        # Manual mode
        if not problem_file:
            raise ValueError("No ggb file found and no problem_file specified.")
        with open(problem_file, "r") as f:
            txt = f.read()

        predicates, goals = read_in_relations.parse_string(
            txt, points=None, allow_dummy_points=True
        )
        parsed_points, _ = read_in_relations.parse_points_and_predicates(txt)

        points = dict(parsed_points)
        for pred in list(predicates) + list(goals):
            if not hasattr(pred, "_init_args"):
                continue
            if not pred._init_args:
                continue
            for p in pred._init_args:
                if not isinstance(p, Point):
                    continue
                if p.name not in points:
                    points[p.name] = (0.0, 0.0)

    points_objs = {Point(name=k, x=v[0], y=v[1]) for k, v in points.items()}
    return Problem(set(predicates), set(goals), points_objs)


def prove(
    problem: Problem, rabbit_mode: str = "none", *,
    agent_provider=None, agent_model=None, agent_timeout=120,
    agent_attempts=10, agent_batch_size=3, agent_beam_width=1, agent_log=None
):
    if rabbit_mode not in {"none", "random", "agent"}:
        raise ValueError(f"Unknown rabbit mode: {rabbit_mode}")
    if problem.is_solved():
        print("Already solved!")
        return problem

    changed = True
    iteration = 0
    max_iterations = 10

    print("Initial Predicates:")
    for pred in problem.predicates:
        if any(
            (deduction.rule_name == "axiom") for deduction in problem.predicates[pred]
        ):
            print(f"  {pred}")
    print("\nGoals:")
    for goal in problem.goals:
        print(f"  {goal}")

    while changed and not problem.is_solved() and iteration < max_iterations:
        iteration += 1
        print(f"\n=== Iteration {iteration} ===")
        missing_goals = [
            goal for goal in problem.goals if goal not in problem.predicates
        ]
        print(
            f"Predicates known: {len(problem.predicates)} / Goals Known: {len(problem.goals) - len(missing_goals)} / Goals: {len(problem.goals)}"
        )
        print("Missing Goals: ", " ".join(str(goal) for goal in missing_goals))

        previous_count = len(problem.predicates)

        changed = problem.ddar_step()

        if changed:
            print(f"Added {len(problem.predicates) - previous_count} new predicates")
        elif (
            not problem.is_solved()
            and rabbit_mode != "none"
            and iteration < max_iterations
        ):
            print(f"DDAR is stuck; trying an auxiliary construction ({rabbit_mode})")
            if rabbit_mode == "agent":
                from datetime import datetime
                from uuid import uuid4
                from LM.agent_solver import AgentSolver
                from LM.cli_providers import CLIProvider, EventLog
                log_path = agent_log or f"LM/logs/{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex[:8]}.jsonl"
                print(f"Agent log: {log_path}", flush=True)
                log = EventLog(log_path)
                provider = CLIProvider(agent_provider, model=agent_model,
                                       timeout=agent_timeout, log=log)
                problem = AgentSolver(provider, attempts=agent_attempts,
                                      batch_size=agent_batch_size, beam_width=agent_beam_width, log=log
                                      ).solve(problem, initial_saturated=True)
                break
            changed = rabbit.add_random_rabbit(problem)
            if not changed:
                print("No valid auxiliary construction found")

    print("\n" + "=" * 60)
    if iteration >= max_iterations:
        print(f"Stopped after {max_iterations} iterations")

    print(problem)
    if problem.is_solved():
        print("\x1b[32mSolved!\x1b[0m")
    else:
        print("\x1b[31mCould not solve the problem.\x1b[0m")
        raise SystemExit(1)
    return problem


def main():
    parser = argparse.ArgumentParser(description="Solve a geometry problem with DDAR.")
    parser.add_argument("problem_directory")
    parser.add_argument("--plot", action="store_true")
    parser.add_argument(
        "--rabbit", choices=("none", "random", "agent"), default="none",
        help="auxiliary construction strategy when DDAR gets stuck (default: none)",
    )
    parser.add_argument("--agent-provider", choices=("codex", "antigravity", "claude", "copilot"))
    parser.add_argument("--agent-model", help="model name passed to the selected CLI")
    parser.add_argument("--agent-timeout", type=float, default=120, help="seconds per CLI call")
    parser.add_argument("--agent-attempts", type=int, default=10, help="total construction trials")
    parser.add_argument("--agent-batch-size", type=int, default=3)
    parser.add_argument("--agent-beam-width", type=int, default=1, help="branches retained per search depth")
    parser.add_argument("--agent-log", help="JSONL event log path (default: a new file in LM/logs)")
    args = parser.parse_args()
    if not math.isfinite(args.agent_timeout) or args.agent_timeout <= 0:
        parser.error("--agent-timeout must be finite and positive")
    if args.agent_attempts < 1 or args.agent_batch_size < 1 or args.agent_beam_width < 1:
        parser.error("--agent-attempts, --agent-batch-size, and --agent-beam-width must be positive")
    problem_dir = args.problem_directory
    ggb_file = f"{problem_dir}/problem.ggb"
    problem_file = f"{problem_dir}/problem.txt"

    problem = construct_problem(
        ggb_file=ggb_file, problem_file=problem_file, plot=args.plot
    )

    if args.rabbit == "agent":
        try:
            prove(problem, rabbit_mode="agent", agent_provider=args.agent_provider,
                  agent_model=args.agent_model, agent_timeout=args.agent_timeout,
                  agent_attempts=args.agent_attempts, agent_batch_size=args.agent_batch_size,
                  agent_beam_width=args.agent_beam_width,
                  agent_log=args.agent_log)
        except (ValueError, RuntimeError) as error:
            parser.exit(2, f"Error: {error}\n")
    else:
        prove(problem, rabbit_mode=args.rabbit)


if __name__ == "__main__":
    main()
