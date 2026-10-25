import ast
from functools import wraps
import inspect
import itertools
import math
import random
from types import SimpleNamespace

from relations import Point, Deduction, Col, Cong
from problem import Problem

_name_counter = {}


def next_name(prefix="P", *, problem=None):
    """Generate a unique label like P1, P2, P3…"""
    used = {p.name for p in problem.points} if problem is not None else set()
    while True:
        _name_counter[prefix] = _name_counter.get(prefix, 0) + 1
        name = f"{prefix}{_name_counter[prefix]}"
        if name not in used:
            return name


def describe(function):
    """Describe inputs and possible deductions directly from the constructor."""
    source = ast.parse(inspect.getsource(inspect.unwrap(function)))
    deductions = [
        ast.unparse(node.args[0]) for node in ast.walk(source)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        and node.func.id == "Deduction" and node.args
    ]
    return {
        "signature": function.__name__ + " " + " ".join(list(inspect.signature(function).parameters)[1:]),
        "doc": inspect.getdoc(function),
        "possible_deductions": deductions,
    }


def construction(function):
    """Validate a construction before registering its points and facts in DDAR."""
    @wraps(function)
    def apply(problem, *args):
        deductions = []
        staged = SimpleNamespace(points=set(problem.points), add_deduction=deductions.append)
        if not function(staged, *args):
            return False
        new_points = staged.points - problem.points
        if not new_points or not deductions:
            return False
        used_names = {p.name for p in problem.points}
        for point in sorted(new_points, key=lambda p: p.name):
            if not (math.isfinite(point.x) and math.isfinite(point.y)):
                return False
            if not point.name or point.name in used_names:
                return False
            used_names.add(point.name)
        if not all(problem.is_valid(d.predicate) for d in deductions):
            return False
        # Register every name before facts can reach Ascent or be extracted.
        for point in new_points:
            problem.points.add(point)
            problem.dd.add_point(point)
        for deduction in deductions:
            deduction.rule_name = f"rabbit:{function.__name__}"
            problem.add_deduction(deduction)
        problem.flush_deductions()
        return True
    return apply


@construction
def angle_bisector(problem: Problem, a: Point, b: Point, c: Point) -> bool:
    """Construct X at intersection of the internal angle bisector of ∠ABC with line AC."""
    import math
    from relations import distance

    # Reject degenerate cases
    if Col(a, b, c).is_valid():
        return False
    if distance(a, b) < 1e-10 or distance(b, c) < 1e-10:
        return False

    # Compute normalized direction vectors BA and BC
    bax = a.x - b.x
    bay = a.y - b.y
    bcx = c.x - b.x
    bcy = c.y - b.y

    len_ba = math.hypot(bax, bay)
    len_bc = math.hypot(bcx, bcy)

    if len_ba < 1e-12 or len_bc < 1e-12:
        return False

    bax /= len_ba
    bay /= len_ba
    bcx /= len_bc
    bcy /= len_bc

    # Bisector direction = normalized average of vectors BA and BC
    bis_x = bax + bcx
    bis_y = bay + bcy
    bis_len = math.hypot(bis_x, bis_y)

    if bis_len < 1e-12:
        # This happens only when angle is 180°, no bisector intersection
        return False

    bis_x /= bis_len
    bis_y /= bis_len

    # Line AC direction
    ac_dx = c.x - a.x
    ac_dy = c.y - a.y

    # Solve intersection of:
    #  B + t * (bis_x, bis_y)
    #  A + s * (ac_dx, ac_dy)
    det = bis_x * ac_dy - bis_y * ac_dx
    if abs(det) < 1e-12:
        return False  # Parallel (should not happen unless geometry degenerate)

    s = ((b.y - a.y) * bis_x - (b.x - a.x) * bis_y) / det

    x = a.x + s * ac_dx
    y = a.y + s * ac_dy

    name = next_name("X", problem=problem)
    X = Point(x=x, y=y, name=name)
    problem.points.add(X)

    # Add deductions: X lies on AC, and BX bisects ∠ABC
    from relations import Eqangle

    problem.add_deduction(Deduction(Col(a, X, c), set()))
    problem.add_deduction(Deduction(Eqangle(a, b, X, X, b, c), set()))

    return True


@construction
def circle(problem: Problem, a: Point, b: Point, c: Point) -> bool:
    """Construct the circumcenter of triangle ABC."""
    col = Col(a, b, c)
    if col.is_valid():
        return False

    # Compute circumcenter coordinates
    x1, y1 = a.x, a.y
    x2, y2 = b.x, b.y
    x3, y3 = c.x, c.y

    D = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
    if D == 0:
        return False  # Degenerate case (collinear)

    x = ((x1**2 + y1**2) * (y2 - y3) + (x2**2 + y2**2) * (y3 - y1) +
         (x3**2 + y3**2) * (y1 - y2)) / D

    y = ((x1**2 + y1**2) * (x3 - x2) + (x2**2 + y2**2) * (x1 - x3) +
         (x3**2 + y3**2) * (x2 - x1)) / D

    name = next_name("X", problem=problem)
    X = Point(x=x, y=y, name=name)
    problem.points.add(X)

    problem.add_deduction(Deduction(Cong(X, a, X, b), set()))
    problem.add_deduction(Deduction(Cong(X, a, X, c), set()))

    # TODO: When Problem has circles and lines dictionary (from constructions), should add corresponding elements there...
    # This is so the diagram can be drawn later on (diagram requires knowledge of lines and circles in addition to just points).

    return True


@construction
def foot(problem: Problem, a: Point, b: Point, c: Point) -> bool:
    """Construct the foot of the perpendicular from A to line BC."""
    # Check if B and C are collinear (same point would make line undefined)
    col = Col(a, b, c)
    if col.is_valid():
        return False  # A, B, C are collinear, no unique perpendicular

    # Line BC has direction vector (dx, dy) = (c.x - b.x, c.y - b.y)
    dx = c.x - b.x
    dy = c.y - b.y

    if dx == 0 and dy == 0:
        return False  # B and C are the same point

    # Perpendicular from A to line BC
    # Line BC can be parameterized as: P = B + t * (C - B)
    # We want AP ⊥ BC, so (P - A) · (C - B) = 0
    # (B + t*(C-B) - A) · (C-B) = 0
    # (B - A) · (C - B) + t * |C - B|^2 = 0
    # t = -((B - A) · (C - B)) / |C - B|^2

    dot_product = (b.x - a.x) * dx + (b.y - a.y) * dy
    length_squared = dx * dx + dy * dy

    t = -dot_product / length_squared

    # Foot point X = B + t * (C - B)
    x = b.x + t * dx
    y = b.y + t * dy

    name = next_name("X", problem=problem)
    X = Point(x=x, y=y, name=name)
    problem.points.add(X)

    # Add deductions: X is on BC and AX ⊥ BC
    from relations import Perp

    problem.add_deduction(Deduction(Col(b, X, c), set()))
    problem.add_deduction(Deduction(Perp(a, X, b, c), set()))

    return True


@construction
def incenter(problem: Problem, a: Point, b: Point, c: Point) -> bool:
    """Construct the incenter I of triangle ABC with angle bisector properties."""
    col = Col(a, b, c)
    if col.is_valid():
        return False  # Degenerate triangle

    # Calculate side lengths
    from relations import distance

    side_a = distance(b, c)  # opposite to vertex A
    side_b = distance(a, c)  # opposite to vertex B
    side_c = distance(a, b)  # opposite to vertex C

    if side_a == 0 or side_b == 0 or side_c == 0:
        return False  # Degenerate triangle

    # Incenter is weighted average of vertices by opposite side lengths
    perimeter = side_a + side_b + side_c
    x = (side_a * a.x + side_b * b.x + side_c * c.x) / perimeter
    y = (side_a * a.y + side_b * b.y + side_c * c.y) / perimeter

    name = next_name("X", problem=problem)
    I = Point(x=x, y=y, name=name)
    problem.points.add(I)

    # Add angle bisector deductions: I lies on all three angle bisectors
    from relations import Eqangle

    problem.add_deduction(Deduction(Eqangle(a, b, I, I, b, c),
                                    set()))  # I bisects ∠ABC
    problem.add_deduction(Deduction(Eqangle(b, c, I, I, c, a),
                                    set()))  # I bisects ∠BCA
    problem.add_deduction(Deduction(Eqangle(c, a, I, I, a, b),
                                    set()))  # I bisects ∠CAB

    return True


@construction
def incenter2(problem: Problem, a: Point, b: Point, c: Point) -> bool:
    """Construct incenter I with tangency points X, Y, Z where incircle touches sides."""
    col = Col(a, b, c)
    if col.is_valid():
        return False  # Degenerate triangle

    from relations import distance

    side_a = distance(b, c)
    side_b = distance(a, c)
    side_c = distance(a, b)

    if side_a == 0 or side_b == 0 or side_c == 0:
        return False

    # Compute incenter
    perimeter = side_a + side_b + side_c
    ix = (side_a * a.x + side_b * b.x + side_c * c.x) / perimeter
    iy = (side_a * a.y + side_b * b.y + side_c * c.y) / perimeter

    name_i = next_name("X", problem=problem)
    I = Point(x=ix, y=iy, name=name_i)
    problem.points.add(I)

    # Add angle bisector deductions
    from relations import Eqangle, Perp

    problem.add_deduction(Deduction(Eqangle(a, b, I, I, b, c), set()))
    problem.add_deduction(Deduction(Eqangle(b, c, I, I, c, a), set()))
    problem.add_deduction(Deduction(Eqangle(c, a, I, I, a, b), set()))

    # Create tangency points (feet of perpendiculars from I to each side)
    # X on BC
    dx_bc = c.x - b.x
    dy_bc = c.y - b.y
    len_bc_sq = dx_bc * dx_bc + dy_bc * dy_bc
    if len_bc_sq > 1e-10:
        t_x = -((b.x - ix) * dx_bc + (b.y - iy) * dy_bc) / len_bc_sq
        x_x = b.x + t_x * dx_bc
        x_y = b.y + t_x * dy_bc
        X = Point(x=x_x, y=x_y, name=next_name("X", problem=problem))
        problem.points.add(X)
        problem.add_deduction(Deduction(Perp(I, X, b, c), set()))
        problem.add_deduction(Deduction(Col(b, X, c), set()))

    # Y on AC
    dx_ac = c.x - a.x
    dy_ac = c.y - a.y
    len_ac_sq = dx_ac * dx_ac + dy_ac * dy_ac
    if len_ac_sq > 1e-10:
        t_y = -((a.x - ix) * dx_ac + (a.y - iy) * dy_ac) / len_ac_sq
        y_x = a.x + t_y * dx_ac
        y_y = a.y + t_y * dy_ac
        Y = Point(x=y_x, y=y_y, name=next_name("X", problem=problem))
        problem.points.add(Y)
        problem.add_deduction(Deduction(Perp(I, Y, a, c), set()))
        problem.add_deduction(Deduction(Col(a, Y, c), set()))

    # Z on AB
    dx_ab = b.x - a.x
    dy_ab = b.y - a.y
    len_ab_sq = dx_ab * dx_ab + dy_ab * dy_ab
    if len_ab_sq > 1e-10:
        t_z = -((a.x - ix) * dx_ab + (a.y - iy) * dy_ab) / len_ab_sq
        z_x = a.x + t_z * dx_ab
        z_y = a.y + t_z * dy_ab
        Z = Point(x=z_x, y=z_y, name=next_name("X", problem=problem))
        problem.points.add(Z)
        problem.add_deduction(Deduction(Perp(I, Z, a, b), set()))
        problem.add_deduction(Deduction(Col(a, Z, b), set()))

    return True


@construction
def excenter(problem: Problem, a: Point, b: Point, c: Point) -> bool:
    """Construct excenter J with respect to vertex A (internal bisector at A, external at B and C)."""
    col = Col(a, b, c)
    if col.is_valid():
        return False  # Degenerate triangle

    from relations import distance

    side_a = distance(b, c)
    side_b = distance(a, c)
    side_c = distance(a, b)

    if side_a == 0 or side_b == 0 or side_c == 0:
        return False

    # Excenter I_A (opposite to A)
    x = (-side_a * a.x + side_b * b.x + side_c * c.x) / (-side_a + side_b +
                                                         side_c)
    y = (-side_a * a.y + side_b * b.y + side_c * c.y) / (-side_a + side_b +
                                                         side_c)

    name = next_name("X", problem=problem)
    J = Point(x=x, y=y, name=name)
    problem.points.add(J)

    # Add angle bisector deductions
    # J lies on internal bisector of ∠BAC and external bisectors of ∠ABC and ∠ACB
    from relations import Eqangle

    problem.add_deduction(Deduction(Eqangle(b, a, J, J, a, c),
                                    set()))  # internal bisector at A

    return True


@construction
def excenter2(problem: Problem, a: Point, b: Point, c: Point) -> bool:
    """Construct excenter J with tangency points X, Y, Z where excircle touches sides."""
    col = Col(a, b, c)
    if col.is_valid():
        return False

    from relations import distance, Eqangle, Perp

    side_a = distance(b, c)
    side_b = distance(a, c)
    side_c = distance(a, b)

    if side_a == 0 or side_b == 0 or side_c == 0:
        return False

    # Excenter I_A (opposite to A)
    jx = (-side_a * a.x + side_b * b.x + side_c * c.x) / (-side_a + side_b +
                                                          side_c)
    jy = (-side_a * a.y + side_b * b.y + side_c * c.y) / (-side_a + side_b +
                                                          side_c)

    name = next_name("X", problem=problem)
    J = Point(x=jx, y=jy, name=name)
    problem.points.add(J)

    # Add angle bisector deduction
    problem.add_deduction(Deduction(Eqangle(b, a, J, J, a, c), set()))

    # Create tangency points (feet of perpendiculars from J to each side/extension)
    # X on BC
    dx_bc = c.x - b.x
    dy_bc = c.y - b.y
    len_bc_sq = dx_bc * dx_bc + dy_bc * dy_bc
    if len_bc_sq > 1e-10:
        t_x = -((b.x - jx) * dx_bc + (b.y - jy) * dy_bc) / len_bc_sq
        x_x = b.x + t_x * dx_bc
        x_y = b.y + t_x * dy_bc
        X = Point(x=x_x, y=x_y, name=next_name("X", problem=problem))
        problem.points.add(X)
        problem.add_deduction(Deduction(Perp(J, X, b, c), set()))
        problem.add_deduction(Deduction(Col(b, X, c), set()))

    # Y on AC
    dx_ac = c.x - a.x
    dy_ac = c.y - a.y
    len_ac_sq = dx_ac * dx_ac + dy_ac * dy_ac
    if len_ac_sq > 1e-10:
        t_y = -((a.x - jx) * dx_ac + (a.y - jy) * dy_ac) / len_ac_sq
        y_x = a.x + t_y * dx_ac
        y_y = a.y + t_y * dy_ac
        Y = Point(x=y_x, y=y_y, name=next_name("X", problem=problem))
        problem.points.add(Y)
        problem.add_deduction(Deduction(Perp(J, Y, a, c), set()))
        problem.add_deduction(Deduction(Col(a, Y, c), set()))

    # Z on AB
    dx_ab = b.x - a.x
    dy_ab = b.y - a.y
    len_ab_sq = dx_ab * dx_ab + dy_ab * dy_ab
    if len_ab_sq > 1e-10:
        t_z = -((a.x - jx) * dx_ab + (a.y - jy) * dy_ab) / len_ab_sq
        z_x = a.x + t_z * dx_ab
        z_y = a.y + t_z * dy_ab
        Z = Point(x=z_x, y=z_y, name=next_name("X", problem=problem))
        problem.points.add(Z)
        problem.add_deduction(Deduction(Perp(J, Z, a, b), set()))
        problem.add_deduction(Deduction(Col(a, Z, b), set()))

    return True


@construction
def centroid(problem: Problem, a: Point, b: Point, c: Point) -> bool:
    """Construct centroid G with midpoints X, Y, Z of sides BC, AC, AB."""
    col = Col(a, b, c)
    if col.is_valid():
        return False  # Degenerate triangle

    # Centroid is the average of the three vertices
    gx = (a.x + b.x + c.x) / 3
    gy = (a.y + b.y + c.y) / 3

    name_g = next_name("X", problem=problem)
    G = Point(x=gx, y=gy, name=name_g)
    problem.points.add(G)

    # Create midpoints of the three sides
    # X = midpoint of BC
    x_bc = (b.x + c.x) / 2
    y_bc = (b.y + c.y) / 2
    X = Point(x=x_bc, y=y_bc, name=next_name("X", problem=problem))
    problem.points.add(X)

    # Y = midpoint of AC
    x_ac = (a.x + c.x) / 2
    y_ac = (a.y + c.y) / 2
    Y = Point(x=x_ac, y=y_ac, name=next_name("X", problem=problem))
    problem.points.add(Y)

    # Z = midpoint of AB
    x_ab = (a.x + b.x) / 2
    y_ab = (a.y + b.y) / 2
    Z = Point(x=x_ab, y=y_ab, name=next_name("X", problem=problem))
    problem.points.add(Z)

    # Add deductions: midpoint relations and collinearity of medians
    from relations import Midp

    problem.add_deduction(Deduction(Midp(X, b, c), set()))
    problem.add_deduction(Deduction(Midp(Y, a, c), set()))
    problem.add_deduction(Deduction(Midp(Z, a, b), set()))

    # G lies on each median
    problem.add_deduction(Deduction(Col(a, G, X), set()))
    problem.add_deduction(Deduction(Col(b, G, Y), set()))
    problem.add_deduction(Deduction(Col(c, G, Z), set()))

    return True


@construction
def tangent_2arg(problem: Problem, o: Point, a: Point) -> bool:
    """Construct X such that OA ⊥ AX (tangent perpendicular to radius at A)."""
    from relations import distance
    import math

    dist = distance(o, a)
    if dist < 1e-10:
        return False

    # Direction from O to A
    dx = a.x - o.x
    dy = a.y - o.y

    # Perpendicular direction to OA
    perp_x = -dy / dist
    perp_y = dx / dist

    # Place X at unit distance from A in perpendicular direction
    x = a.x + perp_x
    y = a.y + perp_y

    name = next_name("X", problem=problem)
    X = Point(x=x, y=y, name=name)
    problem.points.add(X)

    # Add perpendicularity deduction: OA ⊥ AX
    from relations import Perp

    problem.add_deduction(Deduction(Perp(o, a, a, X), set()))

    return True


@construction
def midpoint(problem: Problem, a: Point, b: Point) -> bool:
    """Construct the midpoint M of segment AB."""
    # Calculate midpoint coordinates
    x = (a.x + b.x) / 2
    y = (a.y + b.y) / 2

    name = next_name("X", problem=problem)
    M = Point(x=x, y=y, name=name)

    # Add deductions: M is midpoint of AB
    from relations import Midp

    problem.add_deduction(Deduction(Midp(M, a, b), set()))

    problem.points.add(M)

    return True


@construction
def mirror(problem: Problem, a: Point, b: Point) -> bool:
    """Construct the reflection of point A across point B."""
    # Mirror point: B is midpoint of A and A'
    # So A' = 2B - A
    x = 2 * b.x - a.x
    y = 2 * b.y - a.y

    name = next_name("X", problem=problem)
    A_prime = Point(x=x, y=y, name=name)
    problem.points.add(A_prime)

    # Add deductions: B is midpoint of A and A'
    from relations import Midp

    problem.add_deduction(Deduction(Midp(b, a, A_prime), set()))

    return True


@construction
def orthocenter(problem: Problem, a: Point, b: Point, c: Point) -> bool:
    """Construct the orthocenter of triangle ABC (intersection of altitudes)."""
    col = Col(a, b, c)
    if col.is_valid():
        return False  # Degenerate triangle

    # Find intersection of two altitudes
    # Altitude from A perpendicular to BC
    # Altitude from B perpendicular to AC

    # Line BC direction: (c.x - b.x, c.y - b.y)
    # Perpendicular direction: (-(c.y - b.y), c.x - b.x)
    dx_bc = c.x - b.x
    dy_bc = c.y - b.y

    # Line AC direction: (c.x - a.x, c.y - a.y)
    # Perpendicular direction: (-(c.y - a.y), c.x - a.x)
    dx_ac = c.x - a.x
    dy_ac = c.y - a.y

    # Altitude from A: point = A + t1 * perpendicular_to_BC
    # perpendicular_to_BC = (-dy_bc, dx_bc)
    # Altitude from B: point = B + t2 * perpendicular_to_AC
    # perpendicular_to_AC = (-dy_ac, dx_ac)

    # Solve for intersection:
    # a.x + t1 * (-dy_bc) = b.x + t2 * (-dy_ac)
    # a.y + t1 * (dx_bc) = b.y + t2 * (dx_ac)

    # Rearranging:
    # -dy_bc * t1 + dy_ac * t2 = b.x - a.x
    # dx_bc * t1 - dx_ac * t2 = b.y - a.y

    det = -dy_bc * (-dx_ac) - dy_ac * dx_bc
    if abs(det) < 1e-10:
        return (
            False  # Lines are parallel (shouldn't happen for non-degenerate triangle)
        )

    rhs1 = b.x - a.x
    rhs2 = b.y - a.y

    t1 = (rhs1 * (-dx_ac) - rhs2 * dy_ac) / det

    x = a.x + t1 * (-dy_bc)
    y = a.y + t1 * dx_bc

    name = next_name("X", problem=problem)
    H = Point(x=x, y=y, name=name)
    problem.points.add(H)

    # Add deductions: H lies on altitudes
    from relations import Perp

    problem.add_deduction(Deduction(Perp(a, H, b, c), set()))
    problem.add_deduction(Deduction(Perp(b, H, a, c), set()))
    problem.add_deduction(Deduction(Perp(c, H, a, b), set()))

    return True


@construction
def orthocenter2(problem: Problem, a: Point, b: Point, c: Point) -> bool:
    """Construct orthocenter H with feet X, Y, Z on opposite sides."""
    col = Col(a, b, c)
    if col.is_valid():
        return False  # Degenerate triangle

    from relations import distance, Perp

    # Find orthocenter (same as orthocenter function)
    dx_bc = c.x - b.x
    dy_bc = c.y - b.y
    dx_ac = c.x - a.x
    dy_ac = c.y - a.y

    det = -dy_bc * (-dx_ac) - dy_ac * dx_bc
    if abs(det) < 1e-10:
        return False

    rhs1 = b.x - a.x
    rhs2 = b.y - a.y
    t1 = (rhs1 * (-dx_ac) - rhs2 * dy_ac) / det

    hx = a.x + t1 * (-dy_bc)
    hy = a.y + t1 * dx_bc

    name_h = next_name("X", problem=problem)
    H = Point(x=hx, y=hy, name=name_h)
    problem.points.add(H)

    # Add deductions for orthocenter
    problem.add_deduction(Deduction(Perp(a, H, b, c), set()))
    problem.add_deduction(Deduction(Perp(b, H, a, c), set()))
    problem.add_deduction(Deduction(Perp(c, H, a, b), set()))

    # Create feet of altitudes (intersection points with opposite sides)
    # X = foot from A to BC
    len_bc_sq = dx_bc * dx_bc + dy_bc * dy_bc
    if len_bc_sq > 1e-10:
        t_x = -((b.x - a.x) * dx_bc + (b.y - a.y) * dy_bc) / len_bc_sq
        x_x = b.x + t_x * dx_bc
        x_y = b.y + t_x * dy_bc
        X = Point(x=x_x, y=x_y, name=next_name("X", problem=problem))
        problem.points.add(X)
        problem.add_deduction(Deduction(Col(b, X, c), set()))
        problem.add_deduction(Deduction(Col(a, X, H), set()))

    # Y = foot from B to AC
    len_ac_sq = dx_ac * dx_ac + dy_ac * dy_ac
    if len_ac_sq > 1e-10:
        t_y = -((a.x - b.x) * dx_ac + (a.y - b.y) * dy_ac) / len_ac_sq
        y_x = a.x + t_y * dx_ac
        y_y = a.y + t_y * dy_ac
        Y = Point(x=y_x, y=y_y, name=next_name("X", problem=problem))
        problem.points.add(Y)
        problem.add_deduction(Deduction(Col(a, Y, c), set()))
        problem.add_deduction(Deduction(Col(b, Y, H), set()))

    # Z = foot from C to AB
    dx_ab = b.x - a.x
    dy_ab = b.y - a.y
    len_ab_sq = dx_ab * dx_ab + dy_ab * dy_ab
    if len_ab_sq > 1e-10:
        t_z = -((a.x - c.x) * dx_ab + (a.y - c.y) * dy_ab) / len_ab_sq
        z_x = a.x + t_z * dx_ab
        z_y = a.y + t_z * dy_ab
        Z = Point(x=z_x, y=z_y, name=next_name("X", problem=problem))
        problem.points.add(Z)
        problem.add_deduction(Deduction(Col(a, Z, b), set()))
        problem.add_deduction(Deduction(Col(c, Z, H), set()))

    return True


@construction
def reflect(problem: Problem, a: Point, b: Point, c: Point) -> bool:
    """Construct the reflection of point A across line BC."""
    col = Col(a, b, c)
    if col.is_valid():
        return False  # A is already on line BC

    # First find the foot of perpendicular from A to BC
    dx = c.x - b.x
    dy = c.y - b.y

    if dx == 0 and dy == 0:
        return False  # B and C are the same point

    dot_product = (b.x - a.x) * dx + (b.y - a.y) * dy
    length_squared = dx * dx + dy * dy
    t = -dot_product / length_squared

    # Foot point F
    foot_x = b.x + t * dx
    foot_y = b.y + t * dy

    # Reflection A' = 2*F - A
    x = 2 * foot_x - a.x
    y = 2 * foot_y - a.y

    name = next_name("X", problem=problem)
    A_prime = Point(x=x, y=y, name=name)
    problem.points.add(A_prime)

    # Add deductions: A' is reflection of A across BC
    # This means the midpoint of AA' lies on BC and AA' ⊥ BC
    F = Point(x=foot_x, y=foot_y, name=next_name("F", problem=problem))
    problem.points.add(F)
    from relations import Midp, Perp

    problem.add_deduction(Deduction(Midp(F, a, A_prime), set()))
    problem.add_deduction(Deduction(Col(b, F, c), set()))
    problem.add_deduction(Deduction(Perp(a, A_prime, b, c), set()))

    return True


@construction
def on_dia(problem: Problem, a: Point, b: Point) -> bool:
    """Construct X such that ∠AXB = 90° (X on circle with diameter AB)."""
    from relations import distance, Perp
    import math

    # Create a point X such that AX ⊥ XB
    # Place X at a perpendicular position from the midpoint of AB

    # Midpoint (center of circle)
    cx = (a.x + b.x) / 2
    cy = (a.y + b.y) / 2

    # Direction from A to B
    dx = b.x - a.x
    dy = b.y - a.y
    dist_ab = distance(a, b)

    if dist_ab < 1e-10:
        return False

    # Perpendicular direction
    perp_x = -dy / dist_ab
    perp_y = dx / dist_ab

    # Place X at distance radius from center, perpendicular to AB
    radius = dist_ab / 2
    x = cx + radius * perp_x
    y = cy + radius * perp_y

    name = next_name("X", problem=problem)
    X = Point(x=x, y=y, name=name)
    problem.points.add(X)

    # Add deduction: ∠AXB = 90°
    problem.add_deduction(Deduction(Perp(a, X, X, b), set()))

    return True


@construction
def tangent(problem: Problem, a: Point, o: Point, b: Point) -> bool:
    """Construct both tangent points X and Y from A to circle centered at O with radius |OB|."""
    from relations import distance, Perp
    import math

    radius = distance(o, b)
    dist_ao = distance(a, o)

    if dist_ao <= radius:
        return False  # A is inside or on the circle, no external tangent

    # Tangent point satisfies: OT ⊥ AT and |OT| = radius
    tangent_length_sq = dist_ao * dist_ao - radius * radius
    if tangent_length_sq < 0:
        return False

    tangent_length = math.sqrt(tangent_length_sq)

    # Direction from O to A
    dx = a.x - o.x
    dy = a.y - o.y

    # Unit vector from O to A
    ux = dx / dist_ao
    uy = dy / dist_ao

    # Perpendicular unit vectors
    perp_x = -uy
    perp_y = ux

    cos_alpha = radius / dist_ao
    sin_alpha = tangent_length / dist_ao

    # First tangent point X
    x1 = o.x + radius * (ux * cos_alpha + perp_x * sin_alpha)
    y1 = o.y + radius * (uy * cos_alpha + perp_y * sin_alpha)

    name_x = next_name("X", problem=problem)
    X = Point(x=x1, y=y1, name=name_x)
    problem.points.add(X)

    # Add deductions for X
    problem.add_deduction(Deduction(Cong(o, X, o, b), set()))  # X on circle
    problem.add_deduction(Deduction(Perp(a, X, o, X),
                                    set()))  # tangent condition

    # Second tangent point Y (using negative perpendicular)
    x2 = o.x + radius * (ux * cos_alpha - perp_x * sin_alpha)
    y2 = o.y + radius * (uy * cos_alpha - perp_y * sin_alpha)

    name_y = next_name("X", problem=problem)
    Y = Point(x=x2, y=y2, name=name_y)
    problem.points.add(Y)

    # Add deductions for Y
    problem.add_deduction(Deduction(Cong(o, Y, o, b), set()))  # Y on circle
    problem.add_deduction(Deduction(Perp(a, Y, o, Y),
                                    set()))  # tangent condition

    return True


@construction
def intersect_lines(problem: Problem, a: Point, o: Point, b: Point,
                    d: Point) -> bool:
    """Construct the intersection point of line AO and line BD."""
    from relations import Inter
    # Line AO direction
    dx1 = o.x - a.x
    dy1 = o.y - a.y

    # Line BD direction
    dx2 = d.x - b.x
    dy2 = d.y - b.y

    # Check if lines are parallel
    det = dx1 * dy2 - dy1 * dx2
    if abs(det) < 1e-10:
        return False  # Lines are parallel or coincident

    # Solve for intersection:
    # a.x + t1 * dx1 = b.x + t2 * dx2
    # a.y + t1 * dy1 = b.y + t2 * dy2

    # Rearranging:
    # dx1 * t1 - dx2 * t2 = b.x - a.x
    # dy1 * t1 - dy2 * t2 = b.y - a.y

    rhs1 = b.x - a.x
    rhs2 = b.y - a.y

    t1 = (rhs1 * dy2 - rhs2 * dx2) / det

    x = a.x + t1 * dx1
    y = a.y + t1 * dy1

    name = next_name("X", problem=problem)
    X = Point(x=x, y=y, name=name)
    problem.points.add(X)

    # Add deductions: X is on both lines
    problem.add_deduction(Deduction(Inter(X, a, o, b, d), set()))

    return True


@construction
def parallel_intersection(problem: Problem, a: Point, b: Point, c: Point,
                          d: Point, e: Point) -> bool:
    """Intersect DE with the line through A parallel to BC."""
    from relations import Para

    ux, uy = c.x - b.x, c.y - b.y
    vx, vy = e.x - d.x, e.y - d.y
    det = ux * vy - uy * vx
    if abs(det) < 1e-10:
        return False
    t = ((d.x - a.x) * vy - (d.y - a.y) * vx) / det
    X = Point(a.x + t * ux, a.y + t * uy, next_name("X", problem=problem))
    problem.points.add(X)
    problem.add_deduction(Deduction(Para(a, X, b, c), set()))
    problem.add_deduction(Deduction(Col(d, X, e), set()))
    return True


rabbits = [
    angle_bisector,
    circle,
    foot,
    incenter,
    incenter2,
    excenter,
    excenter2,
    centroid,
    tangent_2arg,
    midpoint,
    mirror,
    orthocenter,
    orthocenter2,
    reflect,
    on_dia,
    tangent,
    intersect_lines,
    parallel_intersection,
]


def add_random_rabbit(problem: Problem) -> bool:
    """Try randomized constructions/point tuples until one valid rabbit is added."""
    candidates = list(rabbits)
    random.shuffle(candidates)
    points = sorted(problem.points, key=lambda p: p.name)
    random.shuffle(points)
    for function in candidates:
        arity = len(inspect.signature(function).parameters) - 1
        for args in itertools.permutations(points, arity):
            if function(problem, *args):
                print(f"Rabbit: {function.__name__}({', '.join(p.name for p in args)})")
                return True
    return False


def midpoint_theorem_problem():
    """D and E are midpoints of AB and AC; prove DE is parallel to BC."""
    from relations import Midp, Para

    a = Point(0, 4, "A")
    b = Point(-4, 0, "B")
    c = Point(4, 0, "C")
    d = Point(-2, 2, "D")
    e = Point(2, 2, "E")
    original_points = {a, b, c, d, e}
    goal = Para(d, e, b, c)
    return Problem(
        {Midp(d, a, b), Midp(e, a, c)}, {goal}, set(original_points)
    )


def test_mirror_unlocks_triangle_midpoint_theorem():
    """DDAR needs a mirror rabbit to prove the triangle midpoint theorem."""
    from relations import Midp

    problem = midpoint_theorem_problem()
    original_points = set(problem.points)
    by_name = {p.name: p for p in original_points}
    d, e = by_name["D"], by_name["E"]
    goal, = problem.goals
    problem.run_ddar()
    assert not problem.is_solved(), "DDAR should not solve without the rabbit"
    assert goal not in problem.predicates

    # Add the mirror rabbit to unlock the proof for DDAR
    assert mirror(problem, e, d)
    x, = problem.points - original_points
    assert Midp(d, e, x) in problem.predicates
    assert not problem.is_solved(), "The rabbit should not directly add the goal"

    problem.run_ddar()
    assert problem.is_solved(), "DDAR must solve with the rabbit"
    assert problem.predicates[goal]
    proof = str(problem)
    assert "rabbit:mirror" in proof
    print(proof)
    print("Passed: DDAR stalls alone but solves with the mirror rabbit.")


def test_parallel_rabbits_unlock_ceva():
    """The two intersections of A's parallel to BC give the usual Ceva proof."""
    from pathlib import Path
    from LM.geometry import load_problem

    problem = load_problem(Path(__file__).parent / "problems" / "ceva")
    assert not problem.is_solved(), "DDAR should not solve without the rabbits"
    points = {p.name: p for p in problem.points}
    a, b, c, d, e, f = (points[n] for n in "ABCDEF")
    # U = BE ∩ (parallel to BC through A), V = CF ∩ the same parallel.
    assert parallel_intersection(problem, a, d, c, b, e)
    assert parallel_intersection(problem, a, b, d, c, f)
    assert not problem.is_solved(), "The rabbit should not directly add the goal"
    problem.run_ddar()
    assert problem.is_solved(), "DDAR must solve with the rabbits"
    proof = str(problem)
    assert "rabbit:parallel_intersection" in proof
    assert "trans" in proof
    print(proof)
    print("Passed: DDAR stalls alone but solves with the intersection rabbits.")
    return problem


def test_double_point_rabbits_unlock_ceva_converse():
    """Intersect CO with AB, apply the forward construction, and identify it with F."""
    from pathlib import Path
    from LM.geometry import load_problem
    from relations import Eqpoint

    problem = load_problem(Path(__file__).parent / "problems" / "ceva_converse")
    assert not problem.is_solved(), "DDAR should not solve without the rabbits"
    points = {p.name: p for p in problem.points}
    a, b, c, d, e, f, o = (points[n] for n in "ABCDEFO")
    before = set(problem.points)
    assert intersect_lines(problem, a, b, c, o)
    x, = problem.points - before
    assert parallel_intersection(problem, a, d, c, b, e)
    assert parallel_intersection(problem, a, b, d, c, x)
    assert not problem.is_solved(), "The rabbits should not directly add the goal"
    problem.run_ddar()
    assert problem.is_solved(), "DDAR must solve with the rabbits"
    assert Eqpoint(f, x) in problem.predicates
    proof = str(problem)
    assert "ratio_unique" in proof
    assert "point_sub" in proof
    assert "rabbit:intersect_lines" in proof
    print(proof)
    print("Passed: Ceva's converse identifies the constructed double point.")
    return problem


def test_parallel_rabbit_unlocks_menelaus():
    """A's parallel to BC gives the two similar triangles in Menelaus's proof."""
    from pathlib import Path
    from LM.geometry import load_problem

    problem = load_problem(Path(__file__).parent / "problems" / "menelaus")
    assert not problem.is_solved(), "DDAR should not solve without the rabbit"
    points = {p.name: p for p in problem.points}
    a, b, c, d, e = (points[n] for n in "ABCDE")
    assert parallel_intersection(problem, a, b, c, d, e)
    assert not problem.is_solved(), "The rabbit should not directly add the goal"
    problem.run_ddar()
    assert problem.is_solved(), "DDAR must solve with the rabbit"
    proof = str(problem)
    assert "rabbit:parallel_intersection" in proof
    print(proof)
    print("Passed: DDAR stalls alone but solves with the intersection rabbit.")
    return problem


def test_double_point_rabbits_unlock_menelaus_converse():
    """Intersect EF with BC, prove its division ratio, and identify it with D."""
    from pathlib import Path
    from LM.geometry import load_problem
    from relations import Eqpoint

    problem = load_problem(Path(__file__).parent / "problems" / "menelaus_converse")
    assert not problem.is_solved(), "DDAR should not solve without the rabbits"
    points = {p.name: p for p in problem.points}
    a, b, c, d, e, f = (points[n] for n in "ABCDEF")
    before = set(problem.points)
    assert intersect_lines(problem, e, f, b, c)
    x, = problem.points - before
    assert parallel_intersection(problem, a, b, c, e, f)
    assert not problem.is_solved(), "The rabbits should not directly add the goal"
    problem.run_ddar()
    assert problem.is_solved(), "DDAR must solve with the rabbits"
    assert Eqpoint(d, x) in problem.predicates
    proof = str(problem)
    assert "ratio_unique" in proof
    assert "point_sub" in proof
    assert "rabbit:intersect_lines" in proof
    print(proof)
    print("Passed: Menelaus's converse identifies the constructed double point.")
    return problem


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Test hand-picked rabbit proofs without an agent.")
    tests = {"midpoint": test_mirror_unlocks_triangle_midpoint_theorem,
             "ceva": test_parallel_rabbits_unlock_ceva,
             "ceva-converse": test_double_point_rabbits_unlock_ceva_converse,
             "menelaus": test_parallel_rabbit_unlocks_menelaus,
             "menelaus-converse": test_double_point_rabbits_unlock_menelaus_converse}
    parser.add_argument("--test", choices=(*tests.keys(), "all"), default="all")
    selected = parser.parse_args().test
    for name, test in tests.items():
        if selected in (name, "all"):
            print(f"Running test: {name}")
            test()
            print()
