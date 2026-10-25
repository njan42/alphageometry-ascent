"""Serialize known DDAR facts and simplify them."""
from relations import Eqpoint, Sameclock, Cong, Para, Eqangle, Eqratio, Simtri1, Contri1


def serialize_facts(facts):
    return sorted(str(fact) for fact in facts)


def useful_for_prompt(fact):
    """Omit irrelevant identities."""
    if isinstance(fact, Eqpoint) and len(fact.data) == 1:
        return False
    if isinstance(fact, Sameclock):
        return False
    if isinstance(fact, (Cong, Para, Eqangle, Eqratio)) and len(fact.data) == 1:
        return False
    if isinstance(fact, Eqratio) and all(a == b for a, b in fact.data):
        return False
    if isinstance(fact, (Simtri1, Contri1)):
        args = fact._init_args
        if args[:3] == args[3:]:
            return False
    return True

