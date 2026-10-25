from LM.facts import useful_for_prompt
from relations import Point


def axioms(problem):
    return frozenset(p for p, ds in problem.predicates.items()
                     if any(d.rule_name == 'axiom' for d in ds))


class SharedKnowledge:
    def __init__(self, problem):
        self.points = frozenset(problem.points)
        self.axioms = axioms(problem)
        self.facts = {}
        self.proofs = {}

    def check(self, problem):
        if not self.points <= problem.points or axioms(problem) != self.axioms:
            raise ValueError('Shared knowledge requires the same original points and axioms')

    def collect(self, problem):
        self.check(problem)
        added = set()
        for fact, deductions in problem.predicates.items():
            args = fact._init_args
            if (fact not in self.facts and args and useful_for_prompt(fact)
                    and {p for p in args if isinstance(p, Point)} <= self.points):
                self.facts[fact] = list(deductions)
                added.add(fact)
        if added:
            # Keep witnesses for proof printing only; never feed auxiliary facts
            # or points from the discarded branch into the target's DDAR state.
            for graph in (problem.proof_predicates, problem.predicates):
                for fact, ds in graph.items():
                    paths = self.proofs.setdefault(fact, [])
                    paths.extend(d for d in ds if d not in paths)
        return added

    def apply(self, problem):
        self.check(problem)
        added = self.facts.keys() - problem.predicates.keys()
        if added:
            for fact, ds in self.proofs.items():
                paths = problem.proof_predicates.setdefault(fact, [])
                paths.extend(d for d in ds if d not in paths)
            for fact in added:
                for deduction in self.facts[fact]:
                    problem._add_predicate(fact, set(deduction.parent_predicates), deduction.rule_name)
        return added
