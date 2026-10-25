"""Deduction module using Ascent datalog database."""

from python.ascent_py import DeductiveDatabase
from relations import Point, Predicate, Deduction
import relations
import inspect


def _build_predicate_registry():
    """
    Automatically build a registry of predicate classes from relations.py.
    Returns a dict mapping lowercase predicate names to (class, arity, db_method) tuples.
    """
    registry = {}

    # Get all classes from the relations module
    for name, obj in inspect.getmembers(relations, inspect.isclass):
        # Only include classes that are subclasses of Predicate
        if issubclass(obj, Predicate) and obj is not Predicate:
            if getattr(obj, "ar_only", False):
                continue
            # Get the __init__ signature to determine arity
            sig = inspect.signature(obj.__init__)
            # Count parameters excluding 'self'
            params = [p for p in sig.parameters.values() if p.name != "self"]
            arity = len(params)

            registry[name.lower()] = (obj, arity, name.lower())

    return registry


_PREDICATE_REGISTRY = _build_predicate_registry()


class DD:
    """
    Manages the Ascent datalog deductive database for geometric reasoning.
    Maintains correspondence between Point objects and their string names.
    """

    def __init__(
        self, points: set[Point] = set(), initial_predicates: set[Predicate] = set()
    ):
        """
        Initialize the deductive database with points and initial predicates.

        Args:
            points: Set of Point objects in the geometry
            initial_predicates: Set of initial Predicate facts
        """
        self.db = DeductiveDatabase()
        self.predicates: set[Predicate] = set()

        self.point_by_name: dict[str, Point] = {}
        self.name_by_point: dict[Point, str] = {}

        self._extracted_predicates: set[Predicate] = set()
        self._fact_id_to_predicate: dict[str, Predicate] = {}

        for point in points:
            self.add_point(point)

        for predicate in initial_predicates:
            self.add_predicate(predicate)

        self.db.run()

    def add_point(self, point: Point):
        """Add a point to the database and maintain mappings."""
        if point not in self.name_by_point:
            self.db.add_point(point.x, point.y, point.name)
            self.point_by_name[point.name] = point
            self.name_by_point[point] = point.name

    def add_predicate(self, predicate: Predicate):
        """
        Add a predicate to the deductive database.
        Must call run() after adding predicates to deduce new facts.
        """
        if predicate in self.predicates:
            return
        else:
            self.predicates.add(predicate)

        if not predicate._init_args:
            return

        pred_type = type(predicate).__name__.lower()

        if pred_type not in _PREDICATE_REGISTRY:
            return

        _, expected_arity, db_method = _PREDICATE_REGISTRY[pred_type]

        if len(predicate._init_args) == expected_arity:
            # Keep scalar parameters (for example Aconst m/n) unchanged.
            point_names = [pt.name if isinstance(pt, Point) else pt for pt in predicate._init_args]
            # Get the database method (e.g., db.add_collinear)
            method = getattr(self.db, f"add_{db_method}")
            method(*point_names)

            # Store the fact_id mapping
            fact_id = self._make_fact_id(pred_type, point_names)
            self._fact_id_to_predicate[fact_id] = predicate

    def run(self):
        """Run the datalog deduction engine."""
        self.db.run()

    def _make_fact_id(self, pred_type: str, point_names: list[str]) -> str:
        """Create a fact ID string matching the Rust implementation."""
        return f"{pred_type}({','.join(map(str, point_names))})"

    def get_new_deductions(self) -> set[Deduction]:
        """
        Extract newly deduced predicates from the database with provenance.
        Creates a separate Deduction for each derivation path.

        Returns:
            Set of newly deduced Deduction objects (one per derivation path)
        """
        records = []
        for pred_name, (pred_class, _, db_method) in _PREDICATE_REGISTRY.items():
            for *args, derivations in getattr(self.db, f"get_{db_method}")():
                pred = self._extract_predicate(pred_class, tuple(args))
                identifier = self._make_fact_id(pred_name, args)
                self._fact_id_to_predicate[identifier] = pred
                records.append((pred, derivations))

        deductions = set()
        previously_extracted = set(self._extracted_predicates)
        for pred, paths in records:
            if pred in previously_extracted:
                continue
            for rule, parents in paths:
                if rule != "axiom":
                    deductions.add(Deduction(pred, {self._fact_id_to_predicate[p] for p in parents}, rule))
        self._extracted_predicates.update(pred for pred, _ in records)
        return deductions

    def _extract_predicate(
        self, pred_class: type, point_names: tuple[str, ...]
    ) -> Predicate:
        """
        Extract a predicate from database results.

        Args:
            pred_class: The Predicate class to instantiate
            point_names: Tuple of point names from database

        Returns:
            Instantiated Predicate object
        """
        points = [self.point_by_name[arg] if isinstance(arg, str) else arg for arg in point_names]
        return pred_class(*points)

    def _build_parent_predicates(
        self, derivations: list[tuple[str, list[str]]]
    ) -> set[Predicate]:
        """
        Build the set of parent predicates from derivation information.

        Args:
            derivations: List of (rule_name, parent_fact_ids) tuples

        Returns:
            Set of parent Predicate objects
        """
        parent_predicates = set()

        for rule_name, parent_fact_ids in derivations:
            for parent_fact_id in parent_fact_ids:
                if parent_fact_id in self._fact_id_to_predicate:
                    parent_predicates.add(self._fact_id_to_predicate[parent_fact_id])
                else:
                    print(
                        f"Warning: Missing parent fact {parent_fact_id} for rule {rule_name}"
                    )

        return parent_predicates


def deduce_from_datalog(problem) -> None:
    """
    Run the datalog deductive database and return all newly deduced predicates.

    This is the main deduction function called by the solver.

    Args:
        problem: Problem instance with a dd attribute

    Returns:
        Set of newly deduced Predicate objects
    """
    # Run the deduction engine
    problem.dd.run()

    # Extract and return new deductions
    deductions = problem.dd.get_new_deductions()

    for deduction in deductions:
        problem._add_predicate(
            deduction.predicate, deduction.parent_predicates, deduction.rule_name
        )

    return


# Export the deduction functions list for the solver
functions = [deduce_from_datalog]
