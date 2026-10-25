from typing import List, Tuple, Dict, Optional
import re
import inspect
import relations
from relations import Predicate, Point


def _build_predicate_registry():
    """
    Automatically build a registry of predicate classes from relations.py.
    Returns a dict mapping lowercase predicate names to (class, arity) tuples.
    """
    registry = {}

    # Get all classes from the relations module
    for name, obj in inspect.getmembers(relations, inspect.isclass):
        # Only include classes that are subclasses of Predicate (but not Predicate itself or Point)
        if issubclass(obj, Predicate) and obj is not Predicate:
            # Get the __init__ signature to determine arity
            sig = inspect.signature(obj.__init__)
            # Count parameters excluding 'self'
            params = [p for p in sig.parameters.values() if p.name != "self"]
            arity = len(params)

            # Register using lowercase class name
            key = name.lower()
            registry[key] = (obj, arity)

    return registry


_PREDICATE_REGISTRY = _build_predicate_registry()


def _normalize_predicate_name(name: str) -> str:
    return name.strip().lower()


def _instantiate_predicate(
    name: str, args, points: dict, allow_dummy_points: bool
) -> Predicate:
    key = _normalize_predicate_name(name)
    if key not in _PREDICATE_REGISTRY:
        raise ValueError(
            f"Unknown predicate '{name}'. Supported: {sorted(_PREDICATE_REGISTRY.keys())}"
        )

    cls, arity = _PREDICATE_REGISTRY[key]
    arg_list = [a for a in args if a != ""]

    variable = getattr(cls, "variable_arity", False)
    point_count = cls.point_arg_count(len(arg_list)) if variable else arity
    if not variable and len(arg_list) != arity:
        raise ValueError(
            f"Predicate '{name}' expects {arity} arguments, got {len(arg_list)}: {arg_list}"
        )

    pts = []
    for sym in arg_list[:point_count]:
        if sym not in points:
            if allow_dummy_points:
                points[sym] = (0.0, 0.0)
            else:
                raise KeyError(
                    f"Point '{sym}' not found in provided points dictionary."
                )
        x, y = points[sym]
        pts.append(Point(name=sym, x=x, y=y))

    return cls(*pts, *arg_list[point_count:])


# Match a single "point definition" segment: a@x_y = <rest>
_POINT_SEGMENT_RE = re.compile(
    r"""
    ^\s*
    (?P<name>[A-Za-z][A-Za-z0-9]*)      # point name
    @
    (?P<x>[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?) # x coordinate
    _
    (?P<y>[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?) # y coordinate
    \s*
    =
    \s*
    (?P<preds>.*)                       # everything after '=' (may be empty)
    $
""",
    re.VERBOSE,
)


def parse_points_and_predicates(text: str) -> Tuple[Dict[str, tuple], str]:
    """
    Parse text that may contain point definitions like:
        a@-0.52_0.10 = ;
        q@..._... = perp a b ... ? cong e p e q

    The same text can also be on one line separated by ';'.

    Returns:
        points_dict: { "a": (x, y), ... }
        predicates_text: a single string with all predicate fragments
                         (including everything after 'q@... =').
    """
    points: Dict[str, tuple] = {}
    predicate_fragments: List[str] = []

    # First split entire text by ';' to get "segments"
    # This works both with and without newlines.
    segments = [seg.strip() for seg in text.split(";") if seg.strip()]

    for seg in segments:
        m = _POINT_SEGMENT_RE.match(seg)
        if m:
            # This segment defines a point
            name = m.group("name")
            x = float(m.group("x"))
            y = float(m.group("y"))
            points[name] = (x, y)

            # The part after '=' may contain predicate fragments
            preds = m.group("preds").strip()
            if preds:
                # NOTE: do NOT split preds by ';' here; we already split the whole text
                # by ';' above. Just append this fragment as-is.
                predicate_fragments.append(preds)
        else:
            # Pure predicate segment
            predicate_fragments.append(seg)

    predicates_text = "; ".join(predicate_fragments)
    return points, predicates_text


def parse_string(
    problem: str,
    points: Optional[dict] = None,
    allow_dummy_points: bool = False,
) -> Tuple[List[Predicate], List[Predicate]]:
    """
    Parse a problem description into premises and goals.

    If 'points' is None or empty, this function will automatically extract
    points from segments of the form:
        a@-0.52_0.10 = ...
        q@..._... = perp a b ... ? cong e p e q

    It works with both multi-line and single-line inputs.

    If allow_dummy_points is True, any point referenced by a predicate but
    not found in points will be created with coordinates (0.0, 0.0).
    """
    if points:
        local_points = dict(points)
        text = problem
    else:
        local_points, text = parse_points_and_predicates(problem)

    # Now split the predicates/goals text into clauses by ';'
    segments = [seg.strip() for seg in text.split(";") if seg.strip()]
    if not segments:
        if text.strip():
            segments = [text.strip()]
        else:
            raise ValueError("No predicate segments found.")

    premises: List[Predicate] = []
    goals: List[Predicate] = []

    for raw in segments:
        is_goal = raw.startswith("?")
        clause = raw[1:].strip() if is_goal else raw.strip()

        # Allow commas OR whitespace between tokens
        parts = re.split(r"[,\s]+", clause)
        if not parts:
            raise ValueError(f"Empty clause found: '{raw}'")

        name, *args = parts
        pred = _instantiate_predicate(name, args, local_points, allow_dummy_points)

        if is_goal:
            goals.append(pred)
        else:
            premises.append(pred)

    return premises, goals
