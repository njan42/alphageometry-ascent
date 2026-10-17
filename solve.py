# solve.py
import argparse
import os
import read_in_relations
import geogebra
import constructions
import dd
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


def prove(problem: Problem, rabbit_mode: str = "none"):
    if problem.is_solved():
        print("Already solved!")
        return

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

        for deduction_fn in dd.functions:
            deduction_fn(problem)

        if not problem.is_solved():
            problem.search_ar()

        problem.flush_deductions()

        changed = len(problem.predicates) > previous_count

        if changed:
            print(f"Added {len(problem.predicates) - previous_count} new predicates")
        elif (
            not problem.is_solved()
            and rabbit_mode == "random"
            and iteration < max_iterations
        ):
            print("DDAR is stuck; trying a random auxiliary construction")
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
        exit(1)


def main():
    parser = argparse.ArgumentParser(description="Solve a geometry problem with DDAR.")
    parser.add_argument("problem_directory")
    parser.add_argument("--plot", action="store_true")
    parser.add_argument(
        "--rabbit", choices=("none", "random"), default="none",
        help="auxiliary construction strategy when DDAR gets stuck (default: none)",
    )
    args = parser.parse_args()
    problem_dir = args.problem_directory
    ggb_file = f"{problem_dir}/problem.ggb"
    problem_file = f"{problem_dir}/problem.txt"

    problem = construct_problem(
        ggb_file=ggb_file, problem_file=problem_file, plot=args.plot
    )

    prove(problem, rabbit_mode=args.rabbit)


if __name__ == "__main__":
    main()
