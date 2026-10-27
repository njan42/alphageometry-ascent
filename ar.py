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
    ElimDistAdd,
    DistAdd,
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
            name = ",".join(sorted(p.name for p in line))
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
            name = ",".join(sorted(p.name for p in seg))
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

        deductions = set()
        all_sources: set[Predicate] = set()
        is_deduced = True
        for row in rows:
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

        deductions = set()
        all_sources: set[Predicate] = set()
        is_deduced = True
        for row in rows:
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


class ElimAdditiveAR:
    """Linear lengths, kept separate from logarithmic segment variables."""
    def __init__(self):
        self.elim = ElimDistAdd()
        self.variables = {}

    def formal(self, terms):
        comb = LinComb.zero()
        for pair, coefficient in terms.items():
            if pair not in self.variables:
                self.variables[pair] = ElimLHS(_numeric_length(pair), "L(" + ",".join(sorted(p.name for p in pair)) + ")")
            comb.iadd_mul(LinComb.singleton(self.variables[pair]), coefficient)
        return DistAdd(comb)

    def terms(self, predicate):
        from relations import Distseq, Cong, Col, distance
        if isinstance(predicate, Distseq):
            return predicate.terms
        if isinstance(predicate, Cong):
            return predicate.to_ratio_rows()[0].data if predicate.to_ratio_rows() else {}
        if isinstance(predicate, Col):
            a, b, c = sorted(predicate._init_args, key=lambda p: (p.x, p.y))
            if min(distance(a,b), distance(b,c)) <= 1e-10:
                return {}
            return {frozenset({a,b}): 1, frozenset({b,c}): 1, frozenset({a,c}): -1}
        return {}

    def add_predicate(self, predicate):
        terms = self.terms(predicate)
        if terms and all(_numeric_length(pair) > 1e-10 for pair in terms):
            formal = self.formal(terms)
            if abs(formal.value) ** 2 < ATOM:
                self.elim.force_zero(formal, sources={predicate})

    def try_deduce(self, predicate):
        from relations import Distseq, Cong
        if not isinstance(predicate, (Distseq, Cong)):
            return set()
        terms = self.terms(predicate)
        if not terms or any(_numeric_length(pair) <= 1e-10 for pair in terms):
            return set()
        reduced, sources = self.elim.simplify(self.formal(terms))
        return {Deduction(predicate, sources, "AR_length")} if reduced.is_zero() else set()


class AR:
    def __init__(self):
        self.angle_elim = ElimAngleAR()
        self.ratio_elim = ElimRatioAR()
        self.additive_elim = ElimAdditiveAR()

    @property
    def revision(self):
        return (len(self.angle_elim.elim.core.instantiated),
                len(self.ratio_elim.elim.core.instantiated),
                len(self.additive_elim.elim.core.instantiated))

    def add_predicate(self, predicate: Predicate) -> None:
        self.angle_elim.add_predicate(predicate)
        self.ratio_elim.add_predicate(predicate)
        self.additive_elim.add_predicate(predicate)

    def transfer_lengths(self, points):
        import itertools
        additive, multiplicative = {}, {}
        for a, b in itertools.combinations(points, 2):
            pair = frozenset({a, b})
            if _numeric_length(pair) <= 1e-10:
                continue
            add, add_sources = self.additive_elim.elim.simplify(self.additive_elim.formal({pair: 1}))
            mul, mul_sources = self.ratio_elim.elim.simplify(
                _ratio_row_to_formal(RatioRow(None, data={pair: 1})))
            if add.is_zero():
                continue
            add_normal, add_coefficient = add.normalize()
            mul_normal, mul_coefficient = mul.normalize()
            # Matching reduced forms are symbolic equalities. Coordinates
            # played no part in choosing which forms match.
            if add_normal in additive:
                other_mul, sources = additive[add_normal]
                self.ratio_elim.elim.force_one(other_mul / (mul / add_coefficient),
                                               sources=sources | add_sources | mul_sources)
            else:
                additive[add_normal] = (mul / add_coefficient, add_sources | mul_sources)
            if mul_normal in multiplicative:
                other_add, sources = multiplicative[mul_normal]
                self.additive_elim.elim.force_zero(other_add - add / mul_coefficient,
                                                  sources=sources | add_sources | mul_sources)
            else:
                multiplicative[mul_normal] = (add / mul_coefficient, add_sources | mul_sources)

    def try_deduce(self, predicate: Predicate) -> set[Deduction]:
        if getattr(predicate, "ar_only", False) and not predicate.is_valid():
            return set()
        from relations import Acompute
        if isinstance(predicate, Acompute):
            first, second = predicate.data
            terms = {}
            for pair, coefficient in ((first, 1), (second, -1)):
                terms[pair] = terms.get(pair, 0) + coefficient
            angle = _angle_row_to_formal(AngleRow(predicate, data=terms))
            reduced, sources = self.angle_elim.elim.simplify(angle)
            if all(var is angle_unit for var in reduced.comb.d):
                from fractions import Fraction
                predicate.computed_degrees = (reduced.comb.d.get(angle_unit, Fraction(0)) % 1) * 180
                return {Deduction(predicate, sources, "AR_compute")}
            return set()
        deductions = (self.angle_elim.try_deduce(predicate)
                      | self.ratio_elim.try_deduce(predicate))
        return deductions or self.additive_elim.try_deduce(predicate)

    def __str__(self) -> str:
        return str(self.angle_elim) + "\n" + str(self.ratio_elim)
