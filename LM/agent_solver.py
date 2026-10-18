import json
from pathlib import Path

from LM.facts import serialize_facts, useful_for_prompt
from LM.cli_providers import EventLog
from LM.geometry import list_constructions, state_dict, try_construction


class AgentSolver:
    def __init__(self, provider, *, attempts=10, batch_size=3, log=None):
        if attempts < 1 or batch_size < 1:
            raise ValueError("Agent attempts and batch size must be positive")
        self.provider, self.attempts, self.batch_size = provider, attempts, batch_size
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
                "Do not use tools, edit files, or delegate. Do not repeat previous attempts.")

    def record_timing(self, stage, seconds, **details):
        self.log.write("timing", stage=stage, seconds=seconds, **details)

    def solve(self, problem, *, initial_saturated=False):
        if not initial_saturated:
            problem.run_ddar()
        self.log.write("initial_state", state=state_dict(problem))
        feedback, tried = [], set()
        attempts = 0
        while not problem.is_solved() and attempts < self.attempts:
            count = min(self.batch_size, self.attempts - attempts)
            print(f"DDAR stalled; asking {getattr(self.provider, 'name', 'agent')} for {count} constructions", flush=True)
            prompt = self.prompt(problem, feedback, count)
            response = self.provider.generate(prompt)
            proposals = [line.strip() for line in response.splitlines() if line.strip()] or [""]
            retained = None
            for proposal in proposals[:count]:
                attempts += 1
                if proposal in tried:
                    result = {"command": proposal, "accepted": False, "error": "Already tried"}
                    branch = None
                else:
                    tried.add(proposal)
                    branch, result = try_construction(problem, proposal)
                print(f"Agent attempt {attempts}/{self.attempts}: {proposal}; "
                      f"{result.get('error') or ('solved' if result['solved'] else 'DDAR stalled')}", flush=True)
                self.log.write("construction_result", **result)
                feedback.append({key: value for key, value in result.items()
                                 if key in {"command", "accepted", "error", "solved", "new_points",
                                            "new_predicates_on_existing_points"}})
                if branch is not None:
                    if branch.is_solved():
                        problem = branch
                        retained = None
                        break
                    if retained is None or len(result['new_predicates_on_existing_points']) > retained[2]:
                        retained = (branch, proposal, len(result['new_predicates_on_existing_points']))
            if retained is not None:
                problem, command, _ = retained
                # Point names changed, so allow commands to be reconsidered on
                # the next state only if their input tuple has not been tried.
                feedback.append({"retained_construction": command,
                                 "note": "Only this branch was retained; other trials used the prior state."})
                self.log.write("branch_retained", command=command, state=state_dict(problem))
        proof = str(problem) if problem.is_solved() else None
        self.log.write("finished", attempts=attempts, state=state_dict(problem), proof=proof)
        return problem
