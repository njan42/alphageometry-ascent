from math import e

from relations import (
    Predicate,
    Deduction,
    AngleRow,
    RatioRow,
    Point,
)

from elimination import (
    ElimLHS,
    ElimRHS,
    LinComb,
    ElimAngle,
    ElimDistMul,
    FormalAngle,
    DistMul,
    angle_unit,
    ATOM
)


class LineVar:
    """
    Registers a canonical ElimLHS per unordered pair of points (a "line direction").
    """
    _registry: dict[frozenset[Point], ElimLHS] = {}

    @classmethod
    def get(cls, line: frozenset[Point], numeric_direction: float) -> ElimLHS:
        if line not in cls._registry:
            name = "".join(sorted(p.name for p in line))
            cls._registry[line] = ElimLHS(numeric_direction, f"σ({name})")
        return cls._registry[line]

    @classmethod
    def reset(cls):
        cls._registry.clear()


class SegVar:
    """
    Registers a canonical ElimLHS per unordered pair of points (a "segment length").
    """
    _registry: dict[frozenset[Point], ElimLHS] = {}

    @classmethod
    def get(cls, seg: frozenset[Point], numeric_length: float) -> ElimLHS:
        if seg not in cls._registry:
            name = "".join(sorted(p.name for p in seg))
            cls._registry[seg] = ElimLHS(numeric_length, f"|{name}|")
        return cls._registry[seg]

    @classmethod
    def reset(cls):
        cls._registry.clear()


def _numeric_direction(line: frozenset[Point]) -> float:
    """Direction of a line (pair of points) in [0,1)."""
    pts = list(line)
    if len(pts) < 2:
        return 0.0
    a, b = pts[0], pts[1]
    import math as _math
    return (_math.atan2(b.y - a.y, b.x - a.x) / _math.pi) % 1.0


def _numeric_length(seg: frozenset[Point]) -> float:
    pts = list(seg)
    if len(pts) < 2:
        return 0.0
    a, b = pts[0], pts[1]
    return ((b.x - a.x)**2 + (b.y - a.y)**2) ** 0.5


def _angle_row_to_formal(row: AngleRow) -> FormalAngle:
    comb = LinComb.zero()
    for line, coef in row.data.items():
        num_dir = _numeric_direction(line)
        var = LineVar.get(line, num_dir)
        comb.iadd_mul(LinComb.singleton(var), coef)
    if row.constant:
        comb.iadd_mul(LinComb.singleton(angle_unit), -row.constant)
    return FormalAngle(comb)


_log_unit = ElimRHS(e, "e")


def _ratio_row_to_formal(row: RatioRow) -> DistMul:
    comb = LinComb.zero()
    for seg, coef in row.data.items():
        num_len = _numeric_length(seg)
        var = SegVar.get(seg, num_len)
        comb.iadd_mul(LinComb.singleton(var), coef)
    if row.constant:
        comb.iadd_mul(LinComb.singleton(_log_unit), -row.constant)
    return DistMul(comb)


class ElimAngleAR:
    def __init__(self):
        self.elim = ElimAngle()
        # track which predicates we have already forced
        self._forced: set[int] = set()

    def add_predicate(self, predicate: Predicate) -> None:
        rows: list[AngleRow] = predicate.to_angle_rows()
        for row in rows:
            if not row.data or any(_numeric_length(pair) <= 1e-10 for pair in row.data):
                continue
            angle = _angle_row_to_formal(row)
            # Check numerical validity before forcing with Cyclic
            if abs((angle.value + 0.5) % 1 - 0.5) ** 2 >= ATOM:
                continue
            # force_zero asserts this combination equals zero (mod π)
            self.elim.force_zero(angle, sources={predicate})

    def try_deduce(self, predicate: Predicate) -> set[Deduction]:
        rows: list[AngleRow] = predicate.to_angle_rows()
        if not rows or any(_numeric_length(pair) <= 1e-10 for row in rows for pair in row.data):
            return set()

        # implicit: row has no data (always zero) → trivially true
        implicit = set()
        for row in rows:
            if not row.data:
                implicit.add(Deduction(row.predicate, set(), "AR_implicit"))
        if implicit:
            return implicit

        deductions = set()
        all_sources: set[Predicate] = set()
        is_deduced = True
        for row in rows:
            if not row.data or any(_numeric_length(pair) <= 1e-10 for pair in row.data):
                continue
            angle = _angle_row_to_formal(row)
            simplified, sources = self.elim.simplify(angle)
            is_deduced &= simplified.is_zero()
            all_sources |= sources
        if is_deduced:
            deductions.add(Deduction(predicate, all_sources, "AR"))

        return deductions

    def __str__(self) -> str:
        lines = ["\n<AngleAR>"]
        core = self.elim.core
        if not core.instantiated:
            lines.append("(empty)")
        else:
            for pivot_var, full_row in core.instantiated.items():
                rhs = LinComb({
                    v: c
                    for v, c in full_row.d.items()
                    if v is not pivot_var
                })
                sources = core.row_sources.get(pivot_var, set())
                src_str = ", ".join(str(s) for s in sources)
                lines.append(f"  {pivot_var} = {rhs}  [{src_str}]")
        return "\n".join(lines)


class ElimRatioAR:
    def __init__(self):
        self.elim = ElimDistMul()

    def add_predicate(self, predicate: Predicate) -> None:
        rows: list[RatioRow] = predicate.to_ratio_rows()
        for row in rows:
            if not row.data or any(_numeric_length(pair) <= 1e-10 for pair in row.data):
                continue
            dist = _ratio_row_to_formal(row)
            # force_one: the product (in ratio space) equals 1
            try:
                self.elim.force_one(dist, sources={predicate})
            except AssertionError:
                # numerical mismatch
                pass

    def try_deduce(self, predicate: Predicate) -> set[Deduction]:
        rows: list[RatioRow] = predicate.to_ratio_rows()
        if not rows or any(_numeric_length(pair) <= 1e-10 for row in rows for pair in row.data):
            return set()

        implicit = set()
        for row in rows:
            if not row.data:
                implicit.add(Deduction(row.predicate, set(), "AR_implicit"))
        if implicit:
            return implicit

        deductions = set()
        all_sources: set[Predicate] = set()
        is_deduced = True
        for row in rows:
            if not row.data or any(_numeric_length(pair) <= 1e-10 for pair in row.data):
                continue
            dist = _ratio_row_to_formal(row)
            simplified, sources = self.elim.simplify(dist)
            is_deduced &= simplified.is_one()
            all_sources |= sources
        if is_deduced:
            deductions.add(Deduction(predicate, all_sources, "AR"))

        return deductions

    def __str__(self) -> str:
        lines = ["\n<RatioAR>"]
        core = self.elim.core
        if not core.instantiated:
            lines.append("(empty)")
        else:
            for pivot_var, full_row in core.instantiated.items():
                rhs = LinComb({
                    v: c
                    for v, c in full_row.d.items()
                    if v is not pivot_var
                })
                sources = core.row_sources.get(pivot_var, set())
                src_str = ", ".join(str(s) for s in sources)
                lines.append(f"  {pivot_var} = {rhs}  [{src_str}]")
        return "\n".join(lines)


class AR:
    def __init__(self):
        self.angle_elim = ElimAngleAR()
        self.ratio_elim = ElimRatioAR()

    def add_predicate(self, predicate: Predicate) -> None:
        self.angle_elim.add_predicate(predicate)
        self.ratio_elim.add_predicate(predicate)

    def try_deduce(self, predicate: Predicate) -> set[Deduction]:
        if getattr(predicate, "ar_only", False) and not predicate.is_valid():
            return set()
        return (
            self.angle_elim.try_deduce(predicate)
            | self.ratio_elim.try_deduce(predicate)
        )

    def __str__(self) -> str:
        return str(self.angle_elim) + "\n" + str(self.ratio_elim)
