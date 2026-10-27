from __future__ import annotations  # unneeded in python 3.11+
from dataclasses import dataclass, field
from typing import Generic, Optional, TypeVar, Callable, Iterator
import functools
import itertools
import inspect
from math import atan2, pi, isclose, remainder, log, fsum, isfinite, nextafter, inf
from fractions import Fraction

# Absolute tolerance in radians for angle predicates.
ANGLE_ATOM = 1e-2

def str_init_args(init):
    """
    Decorator that captures initialization arguments for custom __str__ methods.

    This decorator wraps an __init__ method to store the original arguments
    passed during initialization. These stored arguments can later be used
    in the __str__ method to display predicates in a more readable format.
    """

    @functools.wraps(init)
    def wrapper(self, *args, **kwargs):
        self._init_args = args
        return init(self, *args, **kwargs)

    return wrapper


T = TypeVar("T")


@dataclass
class Point:
    x: float
    y: float
    name: str = ""

    def __hash__(self):
        return hash((self.x, self.y, self.name))

    def __eq__(self, other):
        if not isinstance(other, Point):
            return False
        return (self.x, self.y, self.name) == (other.x, other.y, other.name)

    def __str__(self):
        # We only care about the name of the point when printing in a human-readable manner.
        return self.name


def distance(p: Point, q: Point) -> float:
    return ((q.x - p.x) ** 2 + (q.y - p.y) ** 2) ** 0.5


def angle_of_line(p: Point, q: Point) -> float:
    return atan2(q.y - p.y, q.x - p.x)


def angle_between(p: Point, q: Point, r: Point) -> float:
    angle1 = angle_of_line(p, q)
    angle2 = angle_of_line(q, r)
    angle = angle2 - angle1
    if angle < 0:
        angle += 2 * pi
    return angle


def same_orientation(l1: list[Point], l2: list[Point]) -> bool:
    assert len(l1) == len(l2), "must be same size"

    def edge_length(p, q):
        return (q.x - p.x) * (q.y + p.y)

    area1 = 0
    for i in range(len(l1)):
        area1 += edge_length(l1[i], (l1[(i + 1) % len(l1)]))

    area2 = 0
    for i in range(len(l1)):
        area2 += edge_length(l2[i], (l2[(i + 1) % len(l2)]))

    return (area1 * area2) > 0


Row = TypeVar("Row")


@dataclass
class AngleRow:
    predicate: Predicate
    constant: Fraction = Fraction(0)  # constant coefficient
    data: dict[frozenset[Point], Fraction] = field(default_factory=dict)

    def __str__(self) -> str:
        res = []
        for line, value in self.data.items():
            if not value:
                continue
            line_str = "".join(sorted([str(p) for p in list(line)]))
            res.append(str(value) + " " + line_str)
        return str(self.constant) + " = " + "\t+ ".join(res)

    @property
    def is_zero_row(self) -> bool:
        return all(value == 0 for value in self.data.values()) and isclose(
            self.constant, 0.0
        )


@dataclass
class RatioRow:
    predicate: Predicate
    data: dict[frozenset[Point], Fraction] = field(default_factory=dict)

    constant: Fraction = Fraction(0)  # RHS in log space, like AngleRow

    def __str__(self) -> str:
        res = []
        for line, value in self.data.items():
            if not value:
                continue
            line_str = "".join(sorted([str(p) for p in list(line)]))
            res.append(str(value) + " " + line_str)
        return str(self.constant) + " = " + "\t+ ".join(res)

    @property
    def is_zero_row(self) -> bool:
        return all(value == 0 for value in self.data.values()) and self.constant == 0


def collect_rows(
    data: frozenset[Predicate],
    cls: type[Predicate],
    row_func: Callable[[Predicate], Optional[list[Row]]],
) -> list[Row]:
    """Collect and merge rows from subpredicates of a given class."""
    result: list[Row] = []
    for pred in data:
        if isinstance(pred, cls):
            if rows := row_func(pred):
                result.extend(rows)
    return result


@dataclass
class Deduction:
    predicate: Predicate
    parent_predicates: set[Predicate]
    rule_name: str = "unknown"

    def __hash__(self):
        return hash((self.predicate, frozenset(self.parent_predicates), self.rule_name))


class Predicate(Generic[T]):
    data: T
    _init_args: Optional[tuple] = None

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return self.data == other.data

    def __hash__(self):
        return hash((self.__class__.__name__, self.data))

    def __str__(self):
        predicate = self.__class__.__name__.lower()
        if self._init_args is not None:
            args_str = " ".join(str(arg) for arg in self._init_args)
            return f"{predicate} {args_str}"
        else:
            return f"{predicate}({self.data})"

    def to_sub_data(self) -> set[Deduction]:
        if not isinstance(self.data, frozenset):
            return set()

        deductions: set[Deduction] = set()

        for pred in self.data:
            if not isinstance(pred, Predicate):
                continue

            deductions.add(Deduction(pred, {self}, "subpredicate"))
            deductions |= pred.to_sub_data()

        return deductions

    def to_angle_rows(self) -> list[AngleRow]:
        return []

    def to_ratio_rows(self) -> list[RatioRow]:
        return []

    def is_valid(self) -> bool:
        if not isinstance(self.data, frozenset):
            return True

        for pred in self.data:
            if not isinstance(pred, Predicate):
                continue

            if not pred.is_valid():
                return False
        return True

    @classmethod
    def generate(cls, points: set[Point]) -> Iterator[Predicate]:
        """
        Generate all possible instances of this predicate from given points.
        Uses inspect to determine the signature and generate appropriate combinations.
        """
        sig = inspect.signature(cls.__init__)
        params = [
            p
            for p in sig.parameters.values()
            if p.name not in ("self", "args", "kwargs")
        ]

        point_params = [p for p in params if p.annotation == Point]
        nonpoint_params = any(p for p in params if p.annotation != Point)

        if not nonpoint_params:
            for point_combo in itertools.permutations(points, len(point_params)):
                yield cls(*point_combo)
        else:
            raise NotImplementedError(
                f"{cls.__name__} has non-Point parameters requiring custom generation"
            )


class Eqpoint(Predicate):
    """Two named points coincide; numerical agreement only validates a proof."""

    @str_init_args
    def __init__(self, a: Point, b: Point):
        self.data = frozenset({a, b})

    def is_valid(self):
        a, b = self._init_args
        return distance(a, b) <= 1e-10


class Distinct(Predicate):
    """A and B have distinct positions."""

    @str_init_args
    def __init__(self, a: Point, b: Point):
        self.data = frozenset({a, b})

    def is_valid(self):
        a, b = self._init_args
        length = distance(a, b)
        return isfinite(length) and length > 1e-10


class Nonparallel(Predicate):
    """The nonzero lines AB and CD have different directions."""

    @str_init_args
    def __init__(self, a: Point, b: Point, c: Point, d: Point):
        self.data = frozenset({frozenset({a, b}), frozenset({c, d})})

    def is_valid(self):
        a, b, c, d = self._init_args
        if not Distinct(a, b).is_valid() or not Distinct(c, d).is_valid():
            return False
        ux, uy, vx, vy = b.x - a.x, b.y - a.y, d.x - c.x, d.y - c.y
        scale = distance(a, b) * distance(c, d)
        return isfinite(scale) and abs(ux * vy - uy * vx) > 1e-10 * scale


class Noncollinear(Predicate):
    """A, B, C form a nondegenerate triangle."""

    @str_init_args
    def __init__(self, a: Point, b: Point, c: Point):
        self.data = frozenset({a, b, c})

    def is_valid(self):
        a, b, c = self._init_args
        return Nonparallel(a, b, a, c).is_valid()


class Col(Predicate):
    """A B C are collinear"""

    data: frozenset[Predicate]

    @str_init_args
    def __init__(self, a: Point, b: Point, c: Point):
        self.data = frozenset([Para(a, b, b, c), Para(a, b, a, c), Para(b, c, a, c)])

    def to_angle_rows(self) -> list[AngleRow]:
        return collect_rows(self.data, Para, lambda p: p.to_angle_rows())

    def is_valid(self):
        a, b, c = sorted(self._init_args, key=lambda p: (p.x, p.y))
        b, c = c, b
        ux, uy, vx, vy = b.x - a.x, b.y - a.y, c.x - a.x, c.y - a.y
        scale = (ux * ux + uy * uy) ** 0.5 * (vx * vx + vy * vy) ** 0.5
        return isfinite(scale) and abs(ux * vy - uy * vx) <= 1e-7 * max(scale, ux * ux + uy * uy)

    @classmethod
    def generate(cls, points: set[Point]) -> Iterator[Col]:
        for point_combo in itertools.combinations(points, 3):
            yield cls(*point_combo)


class Perp(Predicate):
    """A B ⊥ C D"""

    data: frozenset[frozenset[Point]]

    @str_init_args
    def __init__(self, a: Point, b: Point, c: Point, d: Point):
        self.data = frozenset([frozenset({a, b}), frozenset({c, d})])

    def to_angle_rows(self) -> list[AngleRow]:
        return [
            AngleRow(
                predicate=self,
                data={list(self.data)[0]: Fraction(1), list(self.data)[1]: Fraction(-1)},
                constant=Fraction(1, 2),
            )
        ]

    def is_valid(self) -> bool:
        lines = list(self.data)
        if len(lines) != 2:
            return False
        line1, line2 = lines
        if line1 == line2:
            return False
        if len(set(line1)) == 1 or len(set(line2)) == 1:
            return False
        if distance(*line1) <= 1e-10 or distance(*line2) <= 1e-10:
            return False
        if not isclose(
            abs(angle_of_line(*line1) - angle_of_line(*line2)) % pi,
            pi / 2,
            abs_tol=ANGLE_ATOM,
            rel_tol=0,
        ):
            return False
        return True

    @classmethod
    def generate(cls, points: set[Point]) -> Iterator[Perp]:
        for p1, p2 in itertools.combinations(itertools.combinations(points, 2), 2):
            predicate = cls(*p1, *p2)
            if predicate.is_valid():
                yield predicate


class Cong(Predicate):
    """A B ≅ C D"""

    data: frozenset[frozenset[Point]]

    @str_init_args
    def __init__(self, a: Point, b: Point, c: Point, d: Point):
        self.data = frozenset([frozenset({a, b}), frozenset({c, d})])

    def to_ratio_rows(self) -> list[RatioRow]:
        if len(self.data) != 2:
            return [RatioRow(predicate=self, data={})]
        return [
            RatioRow(
                predicate=self, data={list(self.data)[0]: Fraction(1), list(self.data)[1]: Fraction(-1)}
            )
        ]

    def is_valid(self) -> bool:
        lines = list(self.data)
        if any(len(line) != 2 or distance(*line) <= 1e-10 for line in lines):
            return False
        if len(lines) < 2:
            return True
        line1, line2 = lines
        if not isclose(distance(*line1), distance(*line2)):
            return False
        return True

    @classmethod
    def generate(cls, points: set[Point]) -> Iterator[Cong]:
        for p1, p2 in itertools.combinations(itertools.combinations(points, 2), 2):
            predicate = cls(*p1, *p2)
            if predicate.is_valid():
                yield predicate


class Simtri1(Predicate):
    """△ABC ~ △DEF"""

    data: frozenset[Predicate]

    @str_init_args
    def __init__(self, a: Point, b: Point, c: Point, d: Point, e: Point, f: Point):
        self.data = frozenset(
            [
                Eqangle(a, b, c, d, e, f),
                Eqangle(b, c, a, e, f, d),
                Eqangle(c, a, b, f, d, e),
                Eqratio(a, c, b, c, d, f, e, f),
                Eqratio(a, c, b, a, d, f, e, d),
                Eqratio(b, c, a, b, e, f, d, e),
                Eqratio(a, c, d, f, b, c, e, f),
                Eqratio(b, c, e, f, b, a, e, d),
                Eqratio(b, a, e, d, a, c, d, f),
            ]
        )

    def to_angle_rows(self) -> list[AngleRow]:
        return collect_rows(self.data, Eqangle, lambda p: p.to_angle_rows())

    def to_ratio_rows(self) -> list[RatioRow]:
        return collect_rows(self.data, Eqratio, lambda p: p.to_ratio_rows())

    @classmethod
    def generate(cls, points: set[Point]) -> Iterator[Simtri1]:
        for t1, t2 in itertools.combinations(itertools.permutations(points, 3), 2):
            yield cls(*t1, *t2)


class Simtri2(Predicate):
    """△ABC ~ △DEF with mirror symmetry"""

    data: frozenset[Predicate]

    @str_init_args
    def __init__(self, a: Point, b: Point, c: Point, d: Point, e: Point, f: Point):
        self.data = frozenset(
            [
                Eqangle(a, b, c, f, e, d),
                Eqangle(b, c, a, d, f, e),
                Eqangle(c, a, b, e, d, f),
                Eqratio(a, c, a, b, d, f, d, e),
                Eqratio(a, b, b, c, d, e, e, f),
            ]
        )

    def to_angle_rows(self) -> list[AngleRow]:
        return collect_rows(self.data, Eqangle, lambda p: p.to_angle_rows())

    def to_ratio_rows(self) -> list[RatioRow]:
        return collect_rows(self.data, Eqratio, lambda p: p.to_ratio_rows())

    @classmethod
    def generate(cls, points: set[Point]) -> Iterator[Simtri2]:
        for t1, t2 in itertools.combinations(itertools.permutations(points, 3), 2):
            yield cls(*t1, *t2)


class Eqangle(Predicate):
    """∠ABC = ∠DEF"""

    data: frozenset[tuple[Point, Point, Point]]

    @str_init_args
    def __init__(self, a: Point, b: Point, c: Point, d: Point, e: Point, f: Point):
        self.data = frozenset([(a, b, c), (d, e, f)])

    def to_angle_rows(self) -> list[AngleRow]:
        if len(self.data) != 2:
            return [AngleRow(predicate=self, data={})]
        l0a = frozenset(list(self.data)[0][:2])
        l0b = frozenset(list(self.data)[0][1:])
        l1a = frozenset(list(self.data)[1][:2])
        l1b = frozenset(list(self.data)[1][1:])

        data = {}
        data[l0a] = data.get(l0a, 0) + 1
        data[l0b] = data.get(l0b, 0) - 1
        data[l1a] = data.get(l1a, 0) - 1
        data[l1b] = data.get(l1b, 0) + 1
        return [AngleRow(predicate=self, data=data)]

    def is_valid(self) -> bool:
        angles = list(self.data)
        if any(distance(a, b) <= 1e-10 or distance(b, c) <= 1e-10 for a, b, c in angles):
            return False
        if len(set(angles)) > 2:
            return False
        if len(set(angles)) == 1:
            if len(set(angles[0])) != 3:
                return False
            return True
        for angle in self.data:
            if isclose(abs(pi - (angle_between(*angle) % pi)) % pi, 0):
                return False
        a1, b1, c1 = angles[0]
        a2, b2, c2 = angles[1]
        if len({a1, b1, c1}) != 3:
            return False
        if len({a2, b2, c2}) != 3:
            return False
        difference = remainder(angle_between(a1, b1, c1) - angle_between(a2, b2, c2), pi)
        if not isclose(difference, 0, rel_tol=0, abs_tol=ANGLE_ATOM):
            return False
        return True

    @classmethod
    def generate(cls, points: set[Point]) -> Iterator[Eqangle]:
        # Sort angles before pairing them.
        from bisect import bisect_left, bisect_right
        angles = sorted(
            ((angle_between(*triple) % pi, tuple(p.name for p in triple), triple)
             for triple in itertools.permutations(points, 3)
             if distance(triple[0], triple[1]) > 1e-10
             and distance(triple[1], triple[2]) > 1e-10),
            key=lambda item: (item[0], item[1]),
        )
        values = [item[0] for item in angles]
        for i, (value, _, first) in enumerate(angles):
            nearby_end = bisect_right(values, nextafter(value + ANGLE_ATOM, inf), i + 1)
            wrap_start = max(nearby_end, bisect_left(
                values, nextafter(value + pi - ANGLE_ATOM, -inf), i + 1))
            for j in itertools.chain(range(i + 1, nearby_end), range(wrap_start, len(angles))):
                predicate = cls(*first, *angles[j][2])
                if predicate.is_valid():
                    yield predicate


class Para(Predicate):
    """A B || C D"""

    data: frozenset[frozenset[Point]]

    @str_init_args
    def __init__(self, a: Point, b: Point, c: Point, d: Point):
        self.data = frozenset([frozenset({a, b}), frozenset({c, d})])

    def to_angle_rows(self) -> list[AngleRow]:
        if len(self.data) != 2:
            return [AngleRow(predicate=self, data={})]
        return [
            AngleRow(
                predicate=self, data={list(self.data)[0]: Fraction(1), list(self.data)[1]: Fraction(-1)}
            )
        ]

    def is_valid(self) -> bool:
        lines = list(self.data)
        if len(lines) < 2:
            return True
        line1, line2 = lines
        if line1 == line2:
            return False
        if len(set(line1)) == 1 or len(set(line2)) == 1:
            return False
        if distance(*line1) <= 1e-10 or distance(*line2) <= 1e-10:
            return False
        if not isclose(remainder(angle_of_line(*line1) - angle_of_line(*line2), pi), 0, abs_tol=1e-7):
            return False
        return True

    @classmethod
    def generate(cls, points: set[Point]) -> Iterator[Para]:
        for p1, p2 in itertools.combinations(itertools.combinations(points, 2), 2):
            predicate = cls(*p1, *p2)
            if predicate.is_valid():
                yield predicate


class Contri1(Predicate):
    """△ABC ≅ △DEF"""

    data: frozenset[Predicate]

    @str_init_args
    def __init__(self, a: Point, b: Point, c: Point, d: Point, e: Point, f: Point):
        self.data = frozenset(
            [
                Eqangle(a, b, c, d, e, f),
                Eqangle(b, c, a, e, f, d),
                Eqangle(c, a, b, f, d, e),
                Cong(a, b, d, e),
                Cong(b, c, e, f),
                Cong(c, a, f, d),
            ]
        )

    def to_angle_rows(self) -> list[AngleRow]:
        return collect_rows(self.data, Eqangle, lambda p: p.to_angle_rows())

    def to_ratio_rows(self) -> list[RatioRow]:
        return collect_rows(self.data, Cong, lambda p: p.to_ratio_rows())

    @classmethod
    def generate(cls, points: set[Point]) -> Iterator[Contri1]:
        for t1, t2 in itertools.combinations(itertools.permutations(points, 3), 2):
            yield cls(*t1, *t2)


class Contri2(Predicate):
    """△ABC ≅ △DEF with mirror symmetry"""

    data: frozenset[Predicate]

    @str_init_args
    def __init__(self, a: Point, b: Point, c: Point, d: Point, e: Point, f: Point):
        self.data = frozenset(
            [
                Eqangle(c, a, b, e, d, f),
                Eqangle(b, c, a, d, f, e),
                Eqangle(a, b, c, f, e, d),
                Cong(a, b, d, e),
                Cong(b, c, e, f),
                Cong(a, c, d, f),
            ]
        )

    def to_angle_rows(self) -> list[AngleRow]:
        return collect_rows(self.data, Eqangle, lambda p: p.to_angle_rows())

    def to_ratio_rows(self) -> list[RatioRow]:
        return collect_rows(self.data, Cong, lambda p: p.to_ratio_rows())

    @classmethod
    def generate(cls, points: set[Point]) -> Iterator[Contri2]:
        for t1, t2 in itertools.combinations(itertools.permutations(points, 3), 2):
            yield cls(*t1, *t2)


class Cyclic(Predicate):
    """A B C D lie on a circle"""

    data: frozenset[Predicate]

    @str_init_args
    def __init__(self, a: Point, b: Point, c: Point, d: Point):
        self.data = frozenset(
            [
                Eqangle(b, a, c, b, d, c),
                Eqangle(d, a, c, d, b, c),
                Eqangle(b, d, a, b, c, a),
                Eqangle(d, b, a, d, c, a),
            ]
        )

    def to_angle_rows(self) -> list[AngleRow]:
        return collect_rows(self.data, Eqangle, lambda p: p.to_angle_rows())

    @classmethod
    def generate(cls, points: set[Point]) -> Iterator[Cyclic]:
        for p in itertools.permutations(points, 4):
            yield cls(*p)


class Sameclock(Predicate):
    """A B C D are in the same clockwise order"""

    data: frozenset[tuple[Point, Point, Point]]

    @str_init_args
    def __init__(self, a: Point, b: Point, c: Point, d: Point, e: Point, f: Point):
        self.data = frozenset([(a, b, c), (d, e, f)])

    def is_valid(self) -> bool:
        angles = list(self.data)
        l1 = angles[0]
        l2 = angles[-1]
        return same_orientation(list(l1), list(l2))

    @classmethod
    def generate(cls, points: set[Point]) -> Iterator[Sameclock]:
        for t1, t2 in itertools.combinations(itertools.permutations(points, 3), 2):
            yield cls(*t1, *t2)


class Midp(Predicate):
    """M is the midpoint of A B"""

    data: frozenset[Predicate]

    @str_init_args
    def __init__(self, m: Point, a: Point, b: Point):
        self.data = frozenset([Col(m, a, b), Cong(a, m, m, b)])

    def to_angle_rows(self) -> list[AngleRow]:
        return collect_rows(self.data, Col, lambda p: p.to_angle_rows())

    def to_ratio_rows(self) -> list[RatioRow]:
        return collect_rows(self.data, Cong, lambda p: p.to_ratio_rows())

    def is_valid(self):
        _, a, b = self._init_args
        return distance(a, b) > 1e-10 and super().is_valid()

    @classmethod
    def generate(cls, points: set[Point]) -> Iterator[Midp]:
        for p in itertools.permutations(points, 3):
            yield cls(*p)


class Eqratio(Predicate):
    """AB/CD = EF/GH"""

    data: frozenset[tuple[frozenset[Point], frozenset[Point]]]

    @str_init_args
    def __init__(
        self,
        a: Point,
        b: Point,
        c: Point,
        d: Point,
        e: Point,
        f: Point,
        g: Point,
        h: Point,
    ):
        self.data = frozenset(
            [
                (frozenset({a, b}), frozenset({c, d})),
                (frozenset({e, f}), frozenset({g, h})),
            ]
        )

    def to_ratio_rows(self) -> list[RatioRow]:
        if len(self.data) != 2:
            return []
        l0a, l0b = list(self.data)[0]
        l1a, l1b = list(self.data)[1]
        if l0a == l0b and l1a == l1b:
            return []

        data = {}
        data[l0a] = data.get(l0a, 0) + 1
        data[l0b] = data.get(l0b, 0) - 1
        data[l1a] = data.get(l1a, 0) - 1
        data[l1b] = data.get(l1b, 0) + 1
        return [
            RatioRow(
                predicate=self,
                data=data,
            )
        ]

    def is_valid(self) -> bool:
        values = []
        for numerator, denominator in self.data:
            if len(numerator) != 2 or len(denominator) != 2:
                return False
            numerator_length = distance(*numerator)
            denominator_length = distance(*denominator)
            if numerator_length == 0 or denominator_length == 0:
                return False
            values.append(numerator_length / denominator_length)
        return all(isclose(value, values[0]) for value in values[1:])

    @classmethod
    def generate(cls, points: set[Point]) -> Iterator[Eqratio]:
        lengths = {pair: distance(*pair) for pair in itertools.combinations(points, 2)}
        segments = [(pair, length) for pair, length in lengths.items()
                    if isfinite(length) and length > 0]
        ratios = sorted(
            ((nl / dl, numerator, denominator)
             for (numerator, nl), (denominator, dl) in itertools.product(segments, repeat=2)),
            key=lambda item: item[0],
        )
        for i, (value, ab, cd) in enumerate(ratios):
            for j in range(i + 1, len(ratios)):
                other, ef, gh = ratios[j]
                if not isclose(value, other):
                    break
                yield cls(*ab, *cd, *ef, *gh)


class Aconst(Predicate):
    """∠ABC = mπ/n"""

    data: tuple[Point, Point, Point, int, int]

    @str_init_args
    def __init__(self, a: Point, b: Point, c: Point, m: int, n: int):
        self.data = (a, b, c, m, n)

    def to_angle_rows(self) -> list[AngleRow]:
        lines = (
            frozenset({self.data[0], self.data[1]}),
            frozenset({self.data[1], self.data[2]}),
        )
        return [
            AngleRow(
                predicate=self,
                data={lines[0]: Fraction(1), lines[1]: Fraction(-1)},
                constant=Fraction(self.data[3], self.data[4]),
            )
        ]

    def is_valid(self) -> bool:
        a, b, c, m, n = self.data
        angle = angle_between(a, b, c)
        if not isclose(angle, (m * pi) / n):
            return False
        return True

    @classmethod
    def generate(cls, points: set[Point]) -> Iterator[Aconst]:
        # Common angle constants: 0, π/6, π/4, π/3, π/2, 2π/3, 3π/4, 5π/6, π
        angle_constants = [
            (0, 1),
            (1, 6),
            (1, 4),
            (1, 3),
            (1, 2),
            (2, 3),
            (3, 4),
            (5, 6),
            (1, 1),
        ]
        for point_combo in itertools.permutations(points, 3):
            for m, n in angle_constants:
                yield cls(*point_combo, m, n)


class _WeightedEquation:
    variable_arity = True
    ar_only = True

    @classmethod
    def point_arg_count(cls, count):
        n, remainder = (count - 1) // 3, (count - 1) % 3
        if n < 1 or remainder:
            raise ValueError(f"{cls.__name__} expects 2n points, n coefficients, and a constant")
        return 2 * n

    def __init__(self, *args):
        count = self.point_arg_count(len(args))
        points = args[:count]
        coefficients = tuple(Fraction(str(c)) for c in args[count:])

        self._init_args = (*points, *coefficients)
        self.terms = {}
        for a, b, c in zip(points[::2], points[1::2], coefficients[:-1]):
            pair = frozenset({a, b})
            self.terms[pair] = self.terms.get(pair, Fraction(0)) + c
        self.terms = {pair: c for pair, c in self.terms.items() if c}
        self.constant = coefficients[-1]
        self.data = (frozenset(self.terms.items()), self.constant)

    def _valid_equation(self, measure, period=None):
        points = self._init_args[:self.point_arg_count(len(self._init_args))]
        try:
            lengths = [distance(a, b) for a, b in zip(points[::2], points[1::2])]
            if any(not isfinite(length) or length <= 0 for length in lengths):
                return False
            values = [float(c) * measure(*pair) for pair, c in self.terms.items()]
            values.append(float(self.constant))
            if not all(isfinite(value) for value in values):
                return False
            total = fsum(values)
            return isclose(remainder(total, period) if period else total, 0, abs_tol=1e-8)
        except (ValueError, OverflowError):
            return False


class Angeq(_WeightedEquation, Predicate):
    """Σ t_i direction(A_i B_i) + yπ = 0 mod π."""

    def to_angle_rows(self):
        return [AngleRow(self, constant=-self.constant, data=dict(self.terms))]

    def is_valid(self):
        return self._valid_equation(lambda a, b: (angle_of_line(a, b) / pi) % 1, period=1)


class Distmeq(_WeightedEquation, Predicate):
    """Σ t_i log(|A_i B_i|) + y = 0."""

    def to_ratio_rows(self):
        return [RatioRow(self, data=dict(self.terms), constant=-self.constant)]

    def is_valid(self):
        return self._valid_equation(lambda a, b: log(distance(a, b)))



class Inter(Predicate):
    """X is the unique intersection of the nonparallel lines AB and CD."""

    @str_init_args
    def __init__(self, x: Point, a: Point, b: Point, c: Point, d: Point):
        self.data = frozenset({Col(x, a, b), Col(x, c, d)})

    def to_angle_rows(self):
        return collect_rows(self.data, Col, lambda p: p.to_angle_rows())

    def is_valid(self):
        _, a, b, c, d = self._init_args
        ux, uy, vx, vy = b.x - a.x, b.y - a.y, d.x - c.x, d.y - c.y
        scale = distance(a, b) * distance(c, d)
        return (isfinite(scale) and distance(a, b) > 1e-10 and distance(c, d) > 1e-10
                and abs(ux * vy - uy * vx) > 1e-10 * scale
                and all(fact.is_valid() for fact in self.data))


class Acompute(Predicate):
    """Request a symbolically determined angle between two lines (mod π)."""
    ar_only = True

    @str_init_args
    def __init__(self, a: Point, b: Point, c: Point, d: Point):
        self.data = (frozenset({a, b}), frozenset({c, d}))

    def is_valid(self):
        return all(len(pair) == 2 and distance(*pair) > 1e-10 for pair in self.data)


class Distseq(_WeightedEquation, Predicate):
    """Σ t_i |A_i B_i| = 0 (AG2 additive, not logarithmic, lengths)."""

    @classmethod
    def point_arg_count(cls, count):
        n, remainder = divmod(count, 3)
        if n < 1 or remainder:
            raise ValueError("Distseq expects 2n points and n coefficients")
        return 2 * n

    def __init__(self, *args):
        count = self.point_arg_count(len(args))
        self._init_args = (*args[:count], *(Fraction(str(c)) for c in args[count:]))
        self.terms = {}
        for a, b, c in zip(args[:count:2], args[1:count:2], self._init_args[count:]):
            pair = frozenset({a, b})
            self.terms[pair] = self.terms.get(pair, Fraction(0)) + c
        self.terms = {pair: c for pair, c in self.terms.items() if c}
        self.constant = Fraction(0)
        self.data = frozenset(self.terms.items())

    def is_valid(self):
        return self._valid_equation(distance)
