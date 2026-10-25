import json
from pathlib import Path

from LM.shared import SharedKnowledge
from LM.facts import serialize_facts, useful_for_prompt
from LM.cli_providers import EventLog
from LM.geometry import list_constructions, state_dict, try_construction


class AgentSolver:
    def __init__(self, provider, *, attempts=10, batch_size=3, beam_width=1, log=None):
        if attempts < 1 or batch_size < 1 or beam_width < 1:
            raise ValueError("Agent attempts, batch size, and beam width must be positive")
        self.provider, self.attempts, self.batch_size = provider, attempts, batch_size
        self.beam_width = beam_width
        self.log = log or EventLog()

    def prompt(self, problem, feedback, count):
        state = state_dict(problem)
        payload = {
            "problem_statement": {
                "premises": serialize_facts(p for p, ds in problem.predicates.items()
                                            if any(d.rule_name == 'axiom' for d in ds)),
                "goals": state["goals"],
            },
            "diagram": state["points"],
            "analysis": {"S1": serialize_facts(p for p in problem.predicates if useful_for_prompt(p))},
            "constructions": list_constructions(),
            "previous_attempts": feedback,
        }
        return (Path(__file__).with_name("prompt.txt").read_text() + json.dumps(payload)
                + f"\nReturn exactly {count} different construction commands, one per line. "
                "Do not use tools, edit files, or delegate. Do not repeat failed commands on the same branch.")

    def record_timing(self, stage, seconds, **details):
        self.log.write("timing", stage=stage, seconds=seconds, **details)

    def solve(self, problem, *, initial_saturated=False):
        if not initial_saturated:
            problem.run_ddar()
        self.log.write("initial_state", state=state_dict(problem))
        shared = SharedKnowledge(problem)
        shared.collect(problem)
        feedback, tried = [], set()
        attempts, depth = 0, 0
        frontier = [problem]
        while not problem.is_solved() and attempts < self.attempts:
            candidates = []
            for node in frontier:
                if shared.apply(node):
                    node.run_ddar()
                if node.is_solved():
                    problem = node
                    break
                if attempts >= self.attempts:
                    break
                count = min(self.batch_size, self.attempts - attempts)
                print(f"DDAR stalled; asking {getattr(self.provider, 'name', 'agent')} for {count} constructions", flush=True)
                response = self.provider.generate(self.prompt(node, feedback, count))
                proposals = [line.strip() for line in response.splitlines() if line.strip()] or [""]
                for proposal in proposals[:count]:
                    attempts += 1
                    # The same command can be useful in a different branch.
                    key = (frozenset(node.points), frozenset(node.predicates), proposal)
                    if key in tried:
                        result = {"command": proposal, "accepted": False, "error": "Already tried"}
                        branch = None
                    else:
                        tried.add(key)
                        branch, result = try_construction(node, proposal)
                    print(f"Agent attempt {attempts}/{self.attempts}: {proposal}; "
                          f"{result.get('error') or ('solved' if result['solved'] else 'DDAR stalled')}", flush=True)
                    self.log.write("construction_result", depth=depth, **result)
                    feedback.append({key: value for key, value in result.items()
                                     if key in {"command", "accepted", "error", "solved", "new_points",
                                                "new_predicates_on_existing_points"}})
                    if branch is not None:
                        shared.collect(branch)
                        candidates.append((branch, proposal, len(result['new_predicates_on_existing_points'])))
                        if branch.is_solved():
                            problem = branch
                            break
                if problem.is_solved():
                    break
            if problem.is_solved():
                break
            if candidates:
                candidates.sort(key=lambda item: item[2], reverse=True)
                retained = candidates[:self.beam_width]
                frontier = [branch for branch, _, _ in retained]
                problem = frontier[0]
                depth += 1
                for branch, command, _ in retained:
                    self.log.write("branch_retained", command=command, depth=depth,
                                   state=state_dict(branch))
                feedback.append({"retained_constructions": [command for _, command, _ in retained],
                                 "note": "Each retained construction is a separate branch."})
            # Even a discarded sibling may have proved a needed lemma.
            for node in frontier:
                if shared.apply(node):
                    node.run_ddar()
                if node.is_solved():
                    problem = node
                    break
        proof = str(problem) if problem.is_solved() else None
        self.log.write("finished", attempts=attempts, state=state_dict(problem), proof=proof)
        return problem
