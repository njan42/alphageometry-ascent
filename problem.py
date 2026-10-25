from relations import (
    Deduction,
    Predicate,
    Point,
    Cong,
    Para,
    Perp,
    Eqangle,
    # Col,
    # Simtri1,
    # Simtri2,
    # Contri1,
    # Contri2,
    # Cyclic,
    # Sameclock,
    # Midp,
    Eqratio,
    # Aconst,
)
from dd import DD
import dd
from ar import AR


class Problem:
    predicates: dict[Predicate, list[Deduction]]
    goals: set[Predicate]
    points: set[Point]
    ar: AR
    dd: DD
    deductions_buffer: list[Deduction]
    possible_relations: set[Predicate]
    impossible_relations: set[Predicate]

    def __init__(
        self, predicates: set[Predicate], goals: set[Predicate], points: set[Point]
    ):
        self.predicates = {}
        self.proof_predicates = {}  # Witnesses for shared lemmas; outside DDAR.
        self.goals = goals
        self.points = points
        self.dd = DD(points, set())
        self.ar = AR()
        self.deductions_buffer = []
        self.possible_relations = set()
        self.impossible_relations = set()

        for predicate in predicates:
            if self.is_valid(predicate):
                self._add_predicate(predicate, set(), "axiom")
            else:
                raise ValueError(f"Invalid initial predicate: {predicate}")

    def add_deduction(self, deduction: Deduction):
        """Add a predicate to the deductions buffer."""
        self.deductions_buffer.append(deduction)

    def is_valid(self, predicate: Predicate) -> bool:
        """Cache numerical validity"""
        if predicate in self.possible_relations:
            return True
        if predicate in self.impossible_relations:
            return False
        if predicate.is_valid():
            self.possible_relations.add(predicate)
            return True
        self.impossible_relations.add(predicate)
        return False

    def fork(self, premises: set[Predicate], goals: set[Predicate]) -> "Problem":
        state = Problem(set(), set(goals), set(self.points))
        state.possible_relations = self.possible_relations
        state.impossible_relations = self.impossible_relations
        for predicate in premises:
            if not state.is_valid(predicate):
                raise ValueError(f"Invalid initial predicate: {predicate}")
            state._add_predicate(predicate, set(), "axiom")
        return state

    def ddar_step(self, *, stop_when_solved: bool = True) -> bool:
        previous_count = len(self.predicates)
        for deduction_fn in dd.functions:
            deduction_fn(self)
        if not stop_when_solved or not self.is_solved():
            self.search_ar()
        self.flush_deductions()
        return len(self.predicates) > previous_count

    def run_ddar(self, *, stop_when_solved: bool = True, max_iterations: int = 50):
        for _ in range(max_iterations):
            if stop_when_solved and self.is_solved():
                return
            changed = self.ddar_step(stop_when_solved=stop_when_solved)
            if not changed or (stop_when_solved and self.is_solved()):
                return
        raise RuntimeError(f"DDAR did not reach a fixed point in {max_iterations} iterations")

    def flush_deductions(self):
        for deduction in self.deductions_buffer:
            self._add_predicate(
                deduction.predicate, deduction.parent_predicates, deduction.rule_name
            )

        self.deductions_buffer.clear()

    def can_deduce(self, predicate: Predicate) -> bool:
        if predicate in self.predicates:
            return True

        if not self.is_valid(predicate):
            return False

        # AR deduction
        ar_deductions = self.ar.try_deduce(predicate)
        for deduction in ar_deductions:
            self.add_deduction(deduction)
        return False

    def _add_predicate(
        self,
        predicate: Predicate,
        parent_predicates: set[Predicate],
        rule_name: str = "unknown",
    ):
        if not self.is_valid(predicate):
            return
        if predicate in self.goals:
            print(f"\x1b[34mFound: {predicate}\x1b[0m via {rule_name}")
        for sub in predicate.to_sub_data():
            if sub.predicate in self.goals:
                print(
                    f"\x1b[34mFound: {sub.predicate}\x1b[0m as part of {predicate} via {rule_name}"
                )
        if predicate not in self.predicates:
            self.predicates[predicate] = []

        # Store this derivation path
        deduction = Deduction(predicate, parent_predicates, rule_name)
        if deduction not in self.predicates[predicate]:
            self.predicates[predicate].append(deduction)
        self.dd.add_predicate(deduction.predicate)
        self.ar.add_predicate(deduction.predicate)

        # Handle sub-predicates
        for sub_deduction in predicate.to_sub_data():
            if not self.is_valid(sub_deduction.predicate):
                continue
            if sub_deduction.predicate not in self.predicates:
                self.predicates[sub_deduction.predicate] = []

            sub_ded = Deduction(
                sub_deduction.predicate,
                sub_deduction.parent_predicates,
                "sub_deduction",
            )
            if sub_ded not in self.predicates[sub_deduction.predicate]:
                self.predicates[sub_deduction.predicate].append(sub_ded)
            self.dd.add_predicate(sub_ded.predicate)

    def is_solved(self) -> bool:
        # We have solved the problem if all goals are in self.predicates
        return all(goal in self.predicates for goal in self.goals)

    def search_ar(self):
        """
        Scans through all predicate types with all point combinations.
        """
        predicate_classes = [
            Cong,
            Para,
            Perp,
            Eqangle,
            # Col,    # omitted for speed
            # Simtri1,
            # Simtri2,
            # Contri1,
            # Contri2,
            # Cyclic,
            # Sameclock,
            # Midp,
            Eqratio,
            # Aconst,
        ]

        # Weighted equations have arbitrary coefficients so query explicit goals.
        for goal in self.goals - self.predicates.keys():
            self.can_deduce(goal)

        for pred_class in predicate_classes:
            for predicate in pred_class.generate(self.points):
                if predicate not in self.predicates:
                    self.can_deduce(predicate)

    def __str__(self) -> str:
        """
        Generate a string version of the solved problem.
        Uses smart derivation selection during topological sort.
        """
        if not self.is_solved():
            return ""

        if not self.goals:
            return "No goals specified"

        predicates = {p: list(ds) for p, ds in self.proof_predicates.items()}
        for p, ds in self.predicates.items():
            predicates.setdefault(p, []).extend(ds)

        RULE_PRIORITY = {
            "axiom": 0,
            "rfl": 1,
            "sub_deduction": 2,
            "AR": 10,
            "sym": 20,
        }

        def get_priority(rule_name: str) -> int:
            return RULE_PRIORITY.get(rule_name, 5)

        def find_reachable_predicates():
            """Find all predicates reachable from goals."""
            reachable = set()
            to_visit = set(self.goals)

            while to_visit:
                current = to_visit.pop()
                if current in reachable:
                    continue

                reachable.add(current)
                if current in predicates:
                    for deduction in predicates[current]:
                        new_parents = deduction.parent_predicates - reachable
                        to_visit.update(new_parents)

            return reachable

        goal_reachable_predicates = find_reachable_predicates()

        # Check for unreachable goals
        unreachable_goals = self.goals - goal_reachable_predicates
        if unreachable_goals:
            return f"Unreachable goals: {' '.join([str(goal) for goal in unreachable_goals])}"

        # Select best derivation for each predicate using topological sort
        selected_derivations: dict[Predicate, Deduction] = {}
        used_predicates = set()
        ordered_predicates: list[tuple[Predicate, Deduction]] = []

        # Start with axioms
        for pred, deductions in predicates.items():
            if pred not in goal_reachable_predicates:
                continue
            axiom_deductions = [d for d in deductions if len(d.parent_predicates) == 0]
            if axiom_deductions:
                best = min(axiom_deductions, key=lambda d: get_priority(d.rule_name))
                selected_derivations[pred] = best
                used_predicates.add(pred)
                ordered_predicates.append((pred, best))

        # Topological sort with smart derivation selection
        prev_used_count = -1
        while any(goal not in used_predicates for goal in self.goals):
            current_count = len(used_predicates)
            if current_count == prev_used_count:
                remaining_goals = [
                    goal for goal in self.goals if goal not in used_predicates
                ]
                raise RuntimeError(
                    f"Cannot complete proof - unreachable goals: {remaining_goals}"
                )
            prev_used_count = current_count

            for predicate, deductions in predicates.items():
                if predicate not in goal_reachable_predicates:
                    continue
                if predicate in used_predicates:
                    continue

                # Find all valid derivations (where all parents are already proven)
                valid_derivations = [
                    d
                    for d in deductions
                    if all(parent in used_predicates for parent in d.parent_predicates)
                ]

                if valid_derivations:
                    # Select best derivation by rule priority
                    best = min(
                        valid_derivations, key=lambda d: get_priority(d.rule_name)
                    )
                    selected_derivations[predicate] = best
                    used_predicates.add(predicate)
                    ordered_predicates.append((predicate, best))

        # Build full output
        numbering: dict[Predicate, int] = {}
        for i, (predicate, _) in enumerate(ordered_predicates):
            numbering[predicate] = i + 1

        def format_line(num: int, predicate, deduction) -> str:
            padded_pred = f"{str(predicate):<25}"
            pred_str = (
                padded_pred
                if predicate not in self.goals
                else f"\x1b[32m{padded_pred}\x1b[0m"
            )
            parents = (
                ""
                if not deduction.parent_predicates
                else ",".join(f"[{numbering[p]}]" for p in deduction.parent_predicates)
            )
            rule = f"{deduction.rule_name}" if deduction.rule_name != "unknown" else ""
            return f"[{num}] {pred_str}\t| {rule} {parents}"

        # Full proof lines (as you already do)
        full_lines = []
        for predicate, deduction in ordered_predicates:
            num = numbering[predicate]
            full_lines.append(format_line(num, predicate, deduction))

        # ---------- Shortened proof construction ----------

        by_num = {numbering[p]: (p, d) for p, d in ordered_predicates}

        def collect_needed_lines_for_goal(goal_pred):
            """
            Starting from goal_pred, walk backwards through selected_derivations
            and collect all line numbers needed for that goal.
            """
            needed = set()
            stack = [goal_pred]

            while stack:
                current = stack.pop()
                if current not in selected_derivations:
                    continue
                if current not in numbering:
                    continue

                line_no = numbering[current]
                if line_no in needed:
                    continue

                needed.add(line_no)

                deduction = selected_derivations[current]
                for parent in deduction.parent_predicates:
                    if parent in numbering:  # has a line
                        stack.append(parent)

            return needed

        # For each goal, build a minimal proof
        short_proofs_sections = []
        for goal in self.goals:
            if goal not in numbering:
                continue

            needed_lines = collect_needed_lines_for_goal(goal)
            ordered_needed = sorted(needed_lines)

            header = f"\n\n=== Proof for goal: {goal} ==="
            lines = [header]
            for ln in ordered_needed:
                predicate, deduction = by_num[ln]
                lines.append(format_line(ln, predicate, deduction))

            short_proofs_sections.append("\n".join(lines))

        output = []
        # output.append("=== Full proof ===")
        # output.append("\n".join(full_lines))
        if short_proofs_sections:
            output.append("\n".join(short_proofs_sections))

        return "\n".join(output)
