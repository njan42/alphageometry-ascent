"""Python bindings for Ascent Datalog"""

from .ascent_py import DeductiveDatabase as _DeductiveDatabase
from typing import List, Tuple


class DeductiveDatabase:
    """High-level Python wrapper for geometric deduction queries"""

    def __init__(self):
        self._prog = _DeductiveDatabase()

    # Input methods
    def add_point(self, x: float = 0, y: float = 0, name: str = ""):
        """Add a point to the geometry with coordinates"""
        self._prog.add_point(x, y, name)

    def add_distinct(self, a: str, b: str):
        self._prog.add_distinct(a, b)

    def add_nonparallel(self, a: str, b: str, c: str, d: str):
        self._prog.add_nonparallel(a, b, c, d)

    def add_noncollinear(self, a: str, b: str, c: str):
        self._prog.add_noncollinear(a, b, c)

    def add_eqpoint(self, a: str, b: str):
        self._prog.add_eqpoint(a, b)

    def add_inter(self, x: str, a: str, b: str, c: str, d: str):
        self._prog.add_inter(x, a, b, c, d)

    def add_col(self, a: str, b: str, c: str):
        """Add collinearity fact: points a, b, c are collinear"""
        self._prog.add_col(a, b, c)

    def add_para(self, a: str, b: str, c: str, d: str):
        """Add parallel fact: line AB is parallel to line CD"""
        self._prog.add_para(a, b, c, d)

    def add_perp(self, a: str, b: str, c: str, d: str):
        """Add perpendicular fact: line AB is perpendicular to line CD"""
        self._prog.add_perp(a, b, c, d)

    def add_cong(self, a: str, b: str, c: str, d: str):
        """Add congruence fact: segment AB is congruent to segment CD"""
        self._prog.add_cong(a, b, c, d)

    def add_eqangle(self, a: str, b: str, c: str, d: str, e: str, f: str):
        """Add equal angle fact: angle ABC equals angle DEF"""
        self._prog.add_eqangle(a, b, c, d, e, f)

    def add_cyclic(self, a: str, b: str, c: str, d: str):
        """Add cyclic fact: points A, B, C, D lie on the same circle"""
        self._prog.add_cyclic(a, b, c, d)

    def add_sameclock(self, a: str, b: str, c: str, d: str, e: str, f: str):
        """Add sameclock fact: points A, B, C, D, E, F have the same orientation"""
        self._prog.add_sameclock(a, b, c, d, e, f)

    def add_midp(self, m: str, a: str, b: str):
        """Add midpoint fact: M is the midpoint of segment AB"""
        self._prog.add_midp(m, a, b)

    def add_contri1(self, a: str, b: str, c: str, d: str, e: str, f: str):
        """Add congruent triangles fact (same orientation): triangle ABC ≅ triangle DEF"""
        self._prog.add_contri1(a, b, c, d, e, f)

    def add_contri2(self, a: str, b: str, c: str, d: str, e: str, f: str):
        """Add congruent triangles fact (opposite orientation): triangle ABC ≅ triangle DEF"""
        self._prog.add_contri2(a, b, c, d, e, f)

    def add_simtri1(self, a: str, b: str, c: str, d: str, e: str, f: str):
        """Add similar triangles fact (same orientation): triangle ABC ~ triangle DEF"""
        self._prog.add_simtri1(a, b, c, d, e, f)

    def add_simtri2(self, a: str, b: str, c: str, d: str, e: str, f: str):
        """Add similar triangles fact (opposite orientation): triangle ABC ~ triangle DEF"""
        self._prog.add_simtri2(a, b, c, d, e, f)

    def add_eqratio(
        self, a: str, b: str, c: str, d: str, e: str, f: str, g: str, h: str
    ):
        """Add equal ratios fact: (AB/CD) = (EF/GH)"""
        self._prog.add_eqratio(a, b, c, d, e, f, g, h)

    def add_aconst(self, a: str, b: str, c: str, m: int, n: int):
        """Add constant angle fact: ∠ABC = mπ/n"""
        self._prog.add_aconst(a, b, c, m, n)

    def run(self):
        """Execute the Datalog deduction rules"""
        self._prog.run()

    # Output methods - now return full derivation information
    def get_distinct(self):
        return self._prog.get_distinct()

    def get_nonparallel(self):
        return self._prog.get_nonparallel()

    def get_noncollinear(self):
        return self._prog.get_noncollinear()

    def get_eqpoint(self):
        return self._prog.get_eqpoint()

    def get_inter(self):
        return self._prog.get_inter()

    def get_col(self) -> List[Tuple[str, str, str, List[Tuple[str, List[str]]]]]:
        """
        Get all deduced collinear point sets with full derivation provenance.

        Returns:
            List of (a, b, c, derivations) where derivations is a list of
            (rule_name, parent_fact_ids) tuples
        """
        return self._prog.get_col()

    def get_para(self) -> List[Tuple[str, str, str, str, List[Tuple[str, List[str]]]]]:
        """Get all deduced parallel relationships with full derivation provenance"""
        return self._prog.get_para()

    def get_perp(self) -> List[Tuple[str, str, str, str, List[Tuple[str, List[str]]]]]:
        """Get all deduced perpendicular relationships with full derivation provenance"""
        return self._prog.get_perp()

    def get_cong(self) -> List[Tuple[str, str, str, str, List[Tuple[str, List[str]]]]]:
        """Get all deduced congruent segments with full derivation provenance"""
        return self._prog.get_cong()

    def get_eqangle(
        self,
    ) -> List[Tuple[str, str, str, str, str, str, List[Tuple[str, List[str]]]]]:
        """Get all deduced equal angles with full derivation provenance"""
        return self._prog.get_eqangle()

    def get_cyclic(
        self,
    ) -> List[Tuple[str, str, str, str, List[Tuple[str, List[str]]]]]:
        """Get all deduced cyclic point sets with full derivation provenance"""
        return self._prog.get_cyclic()

    def get_sameclock(
        self,
    ) -> List[Tuple[str, str, str, str, str, str, List[Tuple[str, List[str]]]]]:
        """Get all deduced sameclock relationships with full derivation provenance"""
        return self._prog.get_sameclock()

    def get_midp(self) -> List[Tuple[str, str, str, List[Tuple[str, List[str]]]]]:
        """Get all deduced midpoint relationships with full derivation provenance"""
        return self._prog.get_midp()

    def get_contri1(
        self,
    ) -> List[Tuple[str, str, str, str, str, str, List[Tuple[str, List[str]]]]]:
        """Get all deduced congruent triangles (same orientation) with full derivation provenance"""
        return self._prog.get_contri1()

    def get_contri2(
        self,
    ) -> List[Tuple[str, str, str, str, str, str, List[Tuple[str, List[str]]]]]:
        """Get all deduced congruent triangles (opposite orientation) with full derivation provenance"""
        return self._prog.get_contri2()

    def get_simtri1(
        self,
    ) -> List[Tuple[str, str, str, str, str, str, List[Tuple[str, List[str]]]]]:
        """Get all deduced similar triangles (same orientation) with full derivation provenance"""
        return self._prog.get_simtri1()

    def get_simtri2(
        self,
    ) -> List[Tuple[str, str, str, str, str, str, List[Tuple[str, List[str]]]]]:
        """Get all deduced similar triangles (opposite orientation) with full derivation provenance"""
        return self._prog.get_simtri2()

    def get_eqratio(
        self,
    ) -> List[
        Tuple[str, str, str, str, str, str, str, str, List[Tuple[str, List[str]]]]
    ]:
        """Get all deduced equal ratios with full derivation provenance"""
        return self._prog.get_eqratio()

    def get_aconst(
        self,
    ) -> List[Tuple[str, str, str, int, int, List[Tuple[str, List[str]]]]]:
        """Get all deduced constant angle relationships with full derivation provenance"""
        return self._prog.get_aconst()

    def get_similar_triangles(
        self,
    ) -> List[Tuple[str, str, str, str, str, str, List[Tuple[str, List[str]]]]]:
        """Get all deduced similar triangles (both orientations combined) with full derivation provenance"""
        return self.get_simtri1() + self.get_simtri2()

    def get_congruent_triangles(
        self,
    ) -> List[Tuple[str, str, str, str, str, str, List[Tuple[str, List[str]]]]]:
        """Get all deduced congruent triangles (both orientations combined) with full derivation provenance"""
        return self.get_contri1() + self.get_contri2()

    def __repr__(self):
        parallels = len(self.get_para())
        congruent = len(self.get_cong())
        angles = len(self.get_eqangle())
        contri = len(self.get_contri1()) + len(self.get_contri2())
        simtri = len(self.get_simtri1()) + len(self.get_simtri2())
        return (
            f"<DeductiveDatabase: {parallels} parallels, {congruent} congruences, "
            f"{angles} equal angles, {contri} congruent triangles, {simtri} similar triangles>"
        )
