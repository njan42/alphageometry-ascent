use ascent::ascent_run;
use ascent::lattice::set::Set;
use pyo3::prelude::*;
use pyo3::{types::PyModule, Bound};
use std::collections::{BTreeSet, HashMap, HashSet};

fn same_orientation(coords: &Coordinates, left: &[&str; 3], right: &[&str; 3]) -> bool {
    let area = |names: &[&str; 3]| -> Option<f64> {
        let &(ax, ay) = coords.get(names[0])?;
        let &(bx, by) = coords.get(names[1])?;
        let &(cx, cy) = coords.get(names[2])?;
        Some((bx - ax) * (cy - ay) - (by - ay) * (cx - ax))
    };
    match (area(left), area(right)) {
        (Some(a), Some(b)) => a != 0.0 && b != 0.0 && a.is_sign_positive() == b.is_sign_positive(),
        _ => false,
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Hash, PartialOrd, Ord)]
struct Derivation {
    rule: String,
    parents: BTreeSet<String>,
}

impl Derivation {
    fn axiom() -> Self {
        Derivation {
            rule: "axiom".to_string(),
            parents: BTreeSet::new(),
        }
    }

    fn new(rule: &str, parents: Vec<String>) -> Self {
        Derivation {
            rule: rule.to_string(),
            parents: parents.into_iter().collect(),
        }
    }
}

// Provenance helps to track all ways a fact was derived
type Provenance = Set<Derivation>;

fn axiom() -> Provenance {
    Set::singleton(Derivation::axiom())
}

fn proof(rule: &str, parents: Vec<String>) -> Provenance {
    Set::singleton(Derivation::new(rule, parents))
}

fn fact_id(pred_type: &str, args: impl IntoIterator<Item = impl AsRef<str>>) -> String {
    let args_str: Vec<String> = args.into_iter().map(|s| s.as_ref().to_string()).collect();
    format!("{}({})", pred_type, args_str.join(","))
}

// Coordinates to only check nondegeneracy
type Coordinates = HashMap<String, (f64, f64)>;

fn numerically_distinct(coords: &Coordinates, a: &str, b: &str) -> bool {
    match (coords.get(a), coords.get(b)) {
        (Some(&(ax, ay)), Some(&(bx, by))) => (ax - bx).hypot(ay - by) > 1e-10,
        _ => false,
    }
}

fn numerically_nonparallel(coords: &Coordinates, a: &str, b: &str, c: &str, d: &str) -> bool {
    let Some(&(ax, ay)) = coords.get(a) else {
        return false;
    };
    let Some(&(bx, by)) = coords.get(b) else {
        return false;
    };
    let Some(&(cx, cy)) = coords.get(c) else {
        return false;
    };
    let Some(&(dx, dy)) = coords.get(d) else {
        return false;
    };
    if !numerically_distinct(coords, a, b) || !numerically_distinct(coords, c, d) {
        return false;
    }
    let (ux, uy, vx, vy) = (bx - ax, by - ay, dx - cx, dy - cy);
    let scale = ux.hypot(uy) * vx.hypot(vy);
    scale > 0.0 && (ux * vy - uy * vx).abs() > 1e-10 * scale
}

/// Generates an equality-substitution rule for each point argument,
/// replacing the original point with an equal point, given that the
/// guard holds for the replacement.
///
/// ```ignore
/// substitution_source! { substitution {
///     para(a, b, c, d) where [distinct(a, b), distinct(c, d)];
/// }}
/// ```
/// transforms to
/// ```ignore
/// substitution:
///     para(a, b, c, d, proof(...)) <--
///         para(original, b, c, d, ?_prov),
///         eqpoint(original, a, ?_equality),
///         distinct(a, b),
///         distinct(c, d),
///         if original != a;
///
///     para(a, original, c, d, proof(...)) <--
///         para(a, original, c, d, ?_prov),
///         eqpoint(original, b, ?_equality),
///         distinct(a, b),
///         distinct(c, d),
///         if original != b;
///
///     // And likewise for c and d.
/// ```
macro_rules! substitution_source {
    ($name:ident { $($relations:tt)* }) => {
        substitution_source!(@relations $name [] $($relations)*);
    };

    (@relations $name:ident [$($rules:tt)*]) => {
        ascent::ascent_source! { $name: $($rules)* }
    };

    (@relations $name:ident [$($rules:tt)*]
        $relation:ident ($($points:ident),+ $(; $($params:ident),+)? )
        $(where [$($guard:ident($($guard_args:tt)*)),* $(,)?])? ; $($rest:tt)*
    ) => {
        substitution_source!(@positions $name [$($rules)*]
            $relation [] [$($points),+] [$($($params),+)?]
            [$($($guard($($guard_args)*),)*)?] [$($rest)*]);
    };

    (@positions $name:ident [$($rules:tt)*]
        $relation:ident [$($before:ident),*] [] [$($params:ident),*]
        [$($guards:tt)*] [$($rest:tt)*]
    ) => {
        substitution_source!(@relations $name [$($rules)*] $($rest)*);
    };

    // Name the replacement `$point` so the guards apply to the result.
    (@positions $name:ident [$($rules:tt)*]
        $relation:ident [$($before:ident),*] [$point:ident $(, $after:ident)*]
        [$($params:ident),*] [$($guards:tt)*] [$($rest:tt)*]
    ) => {
        substitution_source!(@positions $name [
            $($rules)*
            $relation($($before,)* $point $(, $after)* $(, $params)*,
                proof("point_sub", vec![
                    fact_id(stringify!($relation), [
                        $($before.to_string(),)* original.to_string(),
                        $($after.to_string(),)* $($params.to_string(),)*
                    ]),
                    fact_id("eqpoint", [original, $point])
                ])
            ) <--
                $relation($($before,)* original $(, $after)* $(, $params)*, ?_prov),
                eqpoint(original, $point, ?_equality),
                $($guards)*
                if original != $point;
        ] $relation [$($before,)* $point] [$($after),*]
            [$($params),*] [$($guards)*] [$($rest)*]);
    };
}

mod rules {
    ascent::ascent_source! { nondegeneracy:
        distinct(a, b) <--
            point(a), point(b),
            numerically_distinct!(a, b);

        nonparallel(a, b, c, d) <--
            distinct(a, b), distinct(c, d),
            numerically_nonparallel!(a, b, c, d);

        noncollinear(a, b, c) <--
            nonparallel(a, b, a_prime, c), if a == a_prime;
    }

    ascent::ascent_source! { equality:

        // Equal point is a equivalence relation
        eqpoint(b, a, proof("sym", vec![fact_id("eqpoint", [a, b])]))
            <-- eqpoint(a, b, ?_p), if a != b;
        eqpoint(a, a, proof("rfl", vec![])) <-- point(a);
        eqpoint(a, c, proof("trans", vec![
            fact_id("eqpoint", [a, b]),
            fact_id("eqpoint", [b, c])
        ])) <--
            eqpoint(a, b, ?_p), eqpoint(b, c, ?_q),
            if a != b && b != c && a != c;

        // Intersection point is collinear with each line
        col(x, a, b, proof("inter_incid", vec![fact_id("inter", [x, a, b, c, d])])),
        col(x, c, d, proof("inter_incid", vec![fact_id("inter", [x, a, b, c, d])]))
            <-- inter(x, a, b, c, d, ?_p);

        // Intersection point is unique to the two lines
        inter(x, a, b, c, d, proof("inter", vec![
            fact_id("col", [x, a, b]),
            fact_id("col", [x, c, d])
        ])) <--
            col(x, a, b, ?_p), col(x, c, d, ?_q),
            nonparallel(a, b, c, d);
        eqpoint(x, y, proof("inter_unique", vec![
            fact_id("inter", [x, a, b, c, d]),
            fact_id("col", [y, a, b]),
            fact_id("col", [y, c, d])
        ])) <--
            inter(x, a, b, c, d, ?_p),
            col(y, a, b, ?_q), col(y, c, d, ?_r), if x != y,
            nonparallel(a, b, c, d);

        // Equal division ratios imply a double point. Orientation distinguishes
        // whether it's in the internal or external region.
        eqpoint(x, y, proof("ratio_unique", vec![
            fact_id("col", [a, x, b]), fact_id("col", [a, y, b]),
            fact_id("eqratio", [a, x, x_prime, b, a_prime, y, y_prime, b_prime])
        ])) <--
            col(a, x, b, ?_p), col(a, y, b, ?_q),
            eqratio(a, x, x_prime, b, a_prime, y, y_prime, b_prime, ?_ratio),
            if a == a_prime && b == b_prime && x == x_prime && y == y_prime && x != y,
            noncollinear(a, b, o),
            same_orientation!(a, x, o, a, y, o),
            same_orientation!(x, b, o, y, b, o);
    }

    substitution_source! { substitution {
        col(a, b, c);
        para(a, b, c, d) where [distinct(a, b), distinct(c, d)];
        perp(a, b, c, d) where [distinct(a, b), distinct(c, d)];
        cong(a, b, c, d) where [distinct(a, b), distinct(c, d)];

        eqangle(a, b, c, d, e, f) where [noncollinear(a, b, c), noncollinear(d, e, f)];
        cyclic(a, b, c, d) where [
            noncollinear(a, b, c), distinct(a, d), distinct(b, d), distinct(c, d),
        ];
        sameclock(a, b, c, d, e, f) where [noncollinear(a, b, c), noncollinear(d, e, f)];
        midp(a, b, c) where [distinct(a, b), distinct(a, c), distinct(b, c)];
        contri1(a, b, c, d, e, f) where [noncollinear(a, b, c), noncollinear(d, e, f)];
        contri2(a, b, c, d, e, f) where [noncollinear(a, b, c), noncollinear(d, e, f)];
        simtri1(a, b, c, d, e, f) where [noncollinear(a, b, c), noncollinear(d, e, f)];
        simtri2(a, b, c, d, e, f) where [noncollinear(a, b, c), noncollinear(d, e, f)];
        eqratio(a, b, c, d, e, f, g, h) where [
            distinct(a, b), distinct(c, d), distinct(e, f), distinct(g, h),
        ];
        inter(x, a, b, c, d) where [nonparallel(a, b, c, d)];

        aconst(a, b, c; m, n) where [distinct(a, b), distinct(b, c)];
    }}

    ascent::ascent_source! { geometry:
        // ----------------------------------------------------------------
        // Relation Properties (Symmetries)
        // ----------------------------------------------------------------

        col(c, b, a, proof("sym", vec![fact_id("col", [a, b, c])]))
            <-- col(a, b, c, ?_prov);
        col(a, c, b, proof("sym", vec![fact_id("col", [a, b, c])]))
            <-- col(a, b, c, ?_prov);

        para(c, d, a, b, proof("sym", vec![fact_id("para", [a, b, c, d])]))
            <-- para(a, b, c, d, ?_prov);
        para(b, a, c, d, proof("sym", vec![fact_id("para", [a, b, c, d])]))
            <-- para(a, b, c, d, ?_prov);
        para(a, b, d, c, proof("sym", vec![fact_id("para", [a, b, c, d])]))
            <-- para(a, b, c, d, ?_prov);

        perp(c, d, a, b, proof("sym", vec![fact_id("perp", [a, b, c, d])]))
            <-- perp(a, b, c, d, ?_prov);
        perp(b, a, c, d, proof("sym", vec![fact_id("perp", [a, b, c, d])]))
            <-- perp(a, b, c, d, ?_prov);
        perp(a, b, d, c, proof("sym", vec![fact_id("perp", [a, b, c, d])]))
            <-- perp(a, b, c, d, ?_prov);

        cong(c, d, a, b, proof("sym", vec![fact_id("cong", [a, b, c, d])]))
            <-- cong(a, b, c, d, ?_prov);
        cong(b, a, c, d, proof("sym", vec![fact_id("cong", [a, b, c, d])]))
            <-- cong(a, b, c, d, ?_prov);
        cong(a, b, d, c, proof("sym", vec![fact_id("cong", [a, b, c, d])]))
            <-- cong(a, b, c, d, ?_prov);

        eqangle(d, e, f, a, b, c, proof("sym", vec![fact_id("eqangle", [a, b, c, d, e, f])]))
            <-- eqangle(a, b, c, d, e, f, ?_prov);
        eqangle(c, b, a, f, e, d, proof("sym", vec![fact_id("eqangle", [a, b, c, d, e, f])]))
            <-- eqangle(a, b, c, d, e, f, ?_prov);

        cyclic(b, c, d, a, proof("sym", vec![fact_id("cyclic", [a, b, c, d])]))
            <-- cyclic(a, b, c, d, ?_prov);
        cyclic(a, c, b, d, proof("sym", vec![fact_id("cyclic", [a, b, c, d])]))
            <-- cyclic(a, b, c, d, ?_prov);

        sameclock(d, e, f, a, b, c, proof("sym", vec![fact_id("sameclock", [a, b, c, d, e, f])]))
            <-- sameclock(a, b, c, d, e, f, ?_prov);
        sameclock(a, b, c, f, d, e, proof("sym", vec![fact_id("sameclock", [a, b, c, d, e, f])]))
            <-- sameclock(a, b, c, d, e, f, ?_prov);
        sameclock(c, b, a, f, e, d, proof("sym", vec![fact_id("sameclock", [a, b, c, d, e, f])]))
            <-- sameclock(a, b, c, d, e, f, ?_prov);

        eqratio(b, a, c, d, e, f, g, h, proof("sym", vec![fact_id("eqratio", [a, b, c, d, e, f, g, h])]))
            <-- eqratio(a, b, c, d, e, f, g, h, ?_prov);
        eqratio(e, f, g, h, a, b, c, d, proof("sym", vec![fact_id("eqratio", [a, b, c, d, e, f, g, h])]))
            <-- eqratio(a, b, c, d, e, f, g, h, ?_prov);
        eqratio(c, d, a, b, g, h, e, f, proof("sym", vec![fact_id("eqratio", [a, b, c, d, e, f, g, h])]))
            <-- eqratio(a, b, c, d, e, f, g, h, ?_prov);
        eqratio(a, b, e, f, c, d, g, h, proof("sym", vec![fact_id("eqratio", [a, b, c, d, e, f, g, h])]))
            <-- eqratio(a, b, c, d, e, f, g, h, ?_prov);

        // ----------------------------------------------------------------
        // Trivial Statements
        // ----------------------------------------------------------------

        cong(a, b, a, b, proof("rfl", vec![])) <--
            distinct(a, b);

        para(a, b, a, b, proof("rfl", vec![])) <--
            distinct(a, b);

        eqangle(a, b, c, a, b, c, proof("rfl", vec![])) <--
            distinct(a, b), distinct(a, c), distinct(b, c);

        // ----------------------------------------------------------------
        // Deductive Rules
        // ----------------------------------------------------------------

        // Two distinct points determine lines
        col(a, c, d, proof("trans", vec![
            fact_id("col", [a, b, c]),
            fact_id("col", [a, b, d])
        ])) <--
            col(a, b, c, ?_prov1), col(a, b, d, ?_prov2),
            distinct(a, b), distinct(a, c),
            distinct(a, d), distinct(b, c),
            distinct(b, d), distinct(c, d);

        // Right Angle Equal
        eqangle(c, b, a, b, e, a, proof("right_angle_eq", vec![
            fact_id("perp", [a, b, b_prime, c]),
            fact_id("perp", [a, e, e_prime, b])
        ])) <--
            perp(a, b, b_prime, c, ?_prov1),
            perp(a, e, e_prime, b, ?_prov2),
            distinct(a, b), distinct(a, c),
            distinct(a, e), distinct(b, c),
            distinct(b, e), distinct(c, e),
            if b == b_prime && e == e_prime;

        // AA Similarity
        simtri1(a, b, c, d, e, f, proof("aa_sim", vec![
            fact_id("eqangle", [b, a, c, e, d, f]),
            fact_id("eqangle", [b, c, a, e, f, d])
        ])) <--
            eqangle(b, a, c, e, d, f, ?_prov1),
            eqangle(b, c, a, e, f, d, ?_prov2),
            point(a), point(b), point(c),
            point(d), point(e), point(f),
            same_orientation!(a, b, c, d, e, f);

        simtri2(a, b, c, d, e, f, proof("aa_sim", vec![
            fact_id("eqangle", [b, a, c, f, d, e]),
            fact_id("eqangle", [b, c, a, d, f, e])
        ])) <--
            eqangle(b, a, c, f, d, e, ?_prov1),
            eqangle(b, c, a, d, f, e, ?_prov2),
            point(a), point(b), point(c),
            point(d), point(e), point(f),
            same_orientation!(a, b, c, f, e, d);

        // ASA Congruence
        contri1(a, b, c, d, e, f, proof("asa_cong", vec![
            fact_id("eqangle", [b, a, c, e, d, f]),
            fact_id("eqangle", [c, b, a, f, e, d]),
            fact_id("cong", [a, b, d, e])
        ])) <--
            eqangle(b, a, c, e, d, f, ?_prov1),
            eqangle(c, b, a, f, e, d, ?_prov2),
            cong(a, b, d, e, ?_prov3),
            point(a), point(b), point(c),
            point(d), point(e), point(f),
            same_orientation!(a, b, c, d, e, f);

        contri2(a, b, c, d, e, f, proof("asa_cong", vec![
            fact_id("eqangle", [b, a, c, f, d, e]),
            fact_id("eqangle", [c, b, a, d, e, f]),
            fact_id("cong", [a, b, d, e])
        ])) <--
            eqangle(b, a, c, f, d, e, ?_prov1),
            eqangle(c, b, a, d, e, f, ?_prov2),
            cong(a, b, d, e, ?_prov3),
            point(a), point(b), point(c),
            point(d), point(e), point(f),
            same_orientation!(a, b, c, f, e, d);

        // SAS Congruence
        contri1(a, b, c, d, e, f, proof("sas_cong", vec![
            fact_id("eqangle", [b, a, c, e, d, f]),
            fact_id("cong", [a, c, d, f]),
            fact_id("cong", [a, b, d, e])
        ])) <--
            eqangle(b, a, c, e, d, f, ?_prov1),
            cong(a, c, d, f, ?_prov2),
            cong(a, b, d, e, ?_prov3),
            point(a), point(b), point(c),
            point(d), point(e), point(f),
            same_orientation!(a, b, c, d, e, f);

        contri2(a, b, c, d, e, f, proof("sas_cong", vec![
            fact_id("eqangle", [b, a, c, f, d, e]),
            fact_id("cong", [a, c, d, f]),
            fact_id("cong", [a, b, d, e])
        ])) <--
            eqangle(b, a, c, f, d, e, ?_prov1),
            cong(a, c, d, f, ?_prov2),
            cong(a, b, d, e, ?_prov3),
            point(a), point(b), point(c),
            point(d), point(e), point(f),
            same_orientation!(a, b, c, f, e, d);

        // SSS Congruence
        contri1(a, b, c, d, e, f, proof("sss_cong", vec![
            fact_id("cong", [a, c, d, f]),
            fact_id("cong", [a, b, d, e]),
            fact_id("cong", [c, b, f, e])
        ])) <--
            cong(a, c, d, f, ?_prov1),
            cong(a, b, d, e, ?_prov2),
            cong(c, b, f, e, ?_prov3),
            point(a), point(b), point(c),
            point(d), point(e), point(f),
            same_orientation!(a, b, c, d, e, f);

        contri2(a, b, c, d, e, f, proof("sss_cong", vec![
            fact_id("cong", [a, c, d, f]),
            fact_id("cong", [a, b, d, e]),
            fact_id("cong", [c, b, f, e])
        ])) <--
            cong(a, c, d, f, ?_prov1),
            cong(a, b, d, e, ?_prov2),
            cong(c, b, f, e, ?_prov3),
            point(a), point(b), point(c),
            point(d), point(e), point(f),
            same_orientation!(a, b, c, f, e, d);

        // Right SSA Congruence
        contri1(a, b, c, d, e, f, proof("ssa_right_cong", vec![
            fact_id("perp", [a, b, a_prime, c]),
            fact_id("perp", [d, e, d_prime, f]),
            fact_id("cong", [a, b, d, e]),
            fact_id("cong", [b, c, e, f])
        ])) <--
            perp(a, b, a_prime, c, ?_prov1),
            perp(d, e, d_prime, f, ?_prov2),
            cong(a, b, d, e, ?_prov3),
            cong(b, c, e, f, ?_prov4),
            point(a), point(b), point(c),
            point(d), point(e), point(f),
            same_orientation!(a, b, c, d, e, f), if a == a_prime && d == d_prime;

        contri2(a, b, c, d, e, f, proof("ssa_right_cong", vec![
            fact_id("perp", [a, b, a_prime, c]),
            fact_id("perp", [d, e, d_prime, f]),
            fact_id("cong", [a, b, d, e]),
            fact_id("cong", [b, c, e, f])
        ])) <--
            perp(a, b, a_prime, c, ?_prov1),
            perp(d, e, d_prime, f, ?_prov2),
            cong(a, b, d, e, ?_prov3),
            cong(b, c, e, f, ?_prov4),
            point(a), point(b), point(c),
            point(d), point(e), point(f),
            same_orientation!(a, b, c, f, e, d), if a == a_prime && d == d_prime;

        // Inscribed Angle Theorem
        eqangle(a, b, c, c, b, d, proof("inscribed_angle_thm", vec![
            fact_id("cong", [o, a, o_prime, b]),
            fact_id("cong", [o, c, o_prime, b]),
            fact_id("cong", [o, c, o_prime, a]),
            fact_id("perp", [o, b, b_prime, d]),
            fact_id("eqangle", [a, o, c, c_prime, o, b])
        ])) <--
            cong(o, a, o_prime, b, ?_prov1),
            cong(o, c, o_prime, b, ?_prov2),
            cong(o, c, o_prime, a, ?_prov3),
            perp(o, b, b_prime, d, ?_prov4),
            eqangle(a, o, c, c_prime, o, b, ?_prov5),
            distinct(a, b), distinct(a, c),
            distinct(a, d), distinct(b, c),
            distinct(b, d), distinct(c, d),
            if o == o_prime && b == b_prime && c == c_prime;

        // Thales's theorem
        perp(b, r, r, d, proof("thales_thm", vec![
            fact_id("cyclic", [b, r, y, d]),
            fact_id("cong", [b, o, r, o_prime]),
            fact_id("cong", [r, o, d, o_prime]),
            fact_id("col", [b, o, d])
        ])) <--
            cyclic(b, r, y, d, ?_prov1),
            cong(b, o, r, o_prime, ?_prov2),
            cong(r, o, d, o_prime, ?_prov3),
            col(b, o, d, ?_prov4),
            distinct(b, r), distinct(b, y),
            distinct(b, d), distinct(r, y),
            distinct(r, d), distinct(y, d),
            if o == o_prime;

        // Eqratio is Additive
        eqratio(a, m, b, n, m, c, n, d, proof("eqratio_additive", vec![
            fact_id("eqratio", [a, c, m, c, b, d, n, d]),
            fact_id("col", [a, m, c]),
            fact_id("col", [b, n, d])
        ])) <--
            eqratio(a, c, m, c_prime, b, d, n, d_prime, ?_prov1),
            col(a, m, c, ?_prov2),
            col(b, n, d, ?_prov3),
            distinct(a, m), distinct(a, c),
            distinct(m, c), distinct(b, n),
            distinct(b, d), distinct(n, d),
            if c == c_prime && d == d_prime;

        eqratio(a, c, m, c, b, d, n, d, proof("eqratio_additive", vec![
            fact_id("eqratio", [a, m, b, n, m, c, n, d]),
            fact_id("col", [a, m, c]),
            fact_id("col", [b, n, d])
        ])) <--
            eqratio(a, m, b, n, m_prime, c, n_prime, d, ?_prov1),
            col(a, m, c, ?_prov2),
            col(b, n, d, ?_prov3),
            distinct(a, m), distinct(a, c),
            distinct(m, c), distinct(b, n),
            distinct(b, d), distinct(n, d),
            if m == m_prime && n == n_prime;
    }
}

#[pyclass]
struct DeductiveDatabase {
    // Input facts
    points: Vec<(String,)>,
    coordinates: Coordinates,
    distinct_facts: Vec<(String, String)>,
    nonparallel_facts: Vec<(String, String, String, String)>,
    noncollinear_facts: Vec<(String, String, String)>,
    eqpoint_facts: Vec<(String, String)>,
    inter_facts: Vec<(String, String, String, String, String)>,
    col_facts: Vec<(String, String, String)>,
    para_facts: Vec<(String, String, String, String)>,
    perp_facts: Vec<(String, String, String, String)>,
    cong_facts: Vec<(String, String, String, String)>,
    eqangle_facts: Vec<(String, String, String, String, String, String)>,
    cyclic_facts: Vec<(String, String, String, String)>,
    sameclock_facts: Vec<(String, String, String, String, String, String)>,
    midp_facts: Vec<(String, String, String)>,
    contri1_facts: Vec<(String, String, String, String, String, String)>,
    contri2_facts: Vec<(String, String, String, String, String, String)>,
    simtri1_facts: Vec<(String, String, String, String, String, String)>,
    simtri2_facts: Vec<(String, String, String, String, String, String)>,
    eqratio_facts: Vec<(
        String,
        String,
        String,
        String,
        String,
        String,
        String,
        String,
    )>,
    aconst_facts: Vec<(String, String, String, i32, i32)>,

    // Derived results with provenance
    derived_distinct: Vec<(String, String)>,
    derived_nonparallel: Vec<(String, String, String, String)>,
    derived_noncollinear: Vec<(String, String, String)>,
    derived_eqpoint: Vec<(String, String, Provenance)>,
    derived_inter: Vec<(String, String, String, String, String, Provenance)>,
    derived_col: Vec<(String, String, String, Provenance)>,
    derived_para: Vec<(String, String, String, String, Provenance)>,
    derived_perp: Vec<(String, String, String, String, Provenance)>,
    derived_cong: Vec<(String, String, String, String, Provenance)>,
    derived_eqangle: Vec<(String, String, String, String, String, String, Provenance)>,
    derived_cyclic: Vec<(String, String, String, String, Provenance)>,
    derived_sameclock: Vec<(String, String, String, String, String, String, Provenance)>,
    derived_midp: Vec<(String, String, String, Provenance)>,
    derived_contri1: Vec<(String, String, String, String, String, String, Provenance)>,
    derived_contri2: Vec<(String, String, String, String, String, String, Provenance)>,
    derived_simtri1: Vec<(String, String, String, String, String, String, Provenance)>,
    derived_simtri2: Vec<(String, String, String, String, String, String, Provenance)>,
    derived_eqratio: Vec<(
        String,
        String,
        String,
        String,
        String,
        String,
        String,
        String,
        Provenance,
    )>,
    derived_aconst: Vec<(String, String, String, i32, i32, Provenance)>,
}

#[pymethods]
impl DeductiveDatabase {
    #[new]
    fn new() -> Self {
        DeductiveDatabase {
            points: Vec::new(),
            coordinates: HashMap::new(),
            distinct_facts: Vec::new(),
            nonparallel_facts: Vec::new(),
            noncollinear_facts: Vec::new(),
            eqpoint_facts: Vec::new(),
            inter_facts: Vec::new(),
            derived_distinct: Vec::new(),
            derived_nonparallel: Vec::new(),
            derived_noncollinear: Vec::new(),
            derived_eqpoint: Vec::new(),
            derived_inter: Vec::new(),
            col_facts: Vec::new(),
            para_facts: Vec::new(),
            perp_facts: Vec::new(),
            cong_facts: Vec::new(),
            eqangle_facts: Vec::new(),
            cyclic_facts: Vec::new(),
            sameclock_facts: Vec::new(),
            midp_facts: Vec::new(),
            contri1_facts: Vec::new(),
            contri2_facts: Vec::new(),
            simtri1_facts: Vec::new(),
            simtri2_facts: Vec::new(),
            eqratio_facts: Vec::new(),
            aconst_facts: Vec::new(),

            derived_col: Vec::new(),
            derived_para: Vec::new(),
            derived_perp: Vec::new(),
            derived_cong: Vec::new(),
            derived_eqangle: Vec::new(),
            derived_cyclic: Vec::new(),
            derived_sameclock: Vec::new(),
            derived_midp: Vec::new(),
            derived_contri1: Vec::new(),
            derived_contri2: Vec::new(),
            derived_simtri1: Vec::new(),
            derived_simtri2: Vec::new(),
            derived_eqratio: Vec::new(),
            derived_aconst: Vec::new(),
        }
    }

    fn add_point(&mut self, x: f64, y: f64, name: String) -> PyResult<()> {
        if !x.is_finite() || !y.is_finite() {
            return Err(pyo3::exceptions::PyValueError::new_err(
                "Point coordinates must be finite",
            ));
        }
        if let Some(old) = self.coordinates.get(&name) {
            if *old != (x, y) {
                return Err(pyo3::exceptions::PyValueError::new_err(
                    "Point name already has different coordinates",
                ));
            }
            return Ok(());
        }
        self.coordinates.insert(name.clone(), (x, y));
        self.points.push((name,));
        Ok(())
    }

    fn add_distinct(&mut self, a: String, b: String) {
        self.distinct_facts.push((a, b));
    }

    fn add_nonparallel(&mut self, a: String, b: String, c: String, d: String) {
        self.nonparallel_facts.push((a, b, c, d));
    }

    fn add_noncollinear(&mut self, a: String, b: String, c: String) {
        self.noncollinear_facts.push((a, b, c));
    }

    fn add_eqpoint(&mut self, a: String, b: String) {
        self.eqpoint_facts.push((a, b));
    }

    fn add_inter(&mut self, x: String, a: String, b: String, c: String, d: String) {
        self.inter_facts.push((x, a, b, c, d));
    }

    fn add_col(&mut self, a: String, b: String, c: String) {
        self.col_facts.push((a, b, c));
    }

    fn add_para(&mut self, a: String, b: String, c: String, d: String) {
        self.para_facts.push((a, b, c, d));
    }

    fn add_perp(&mut self, a: String, b: String, c: String, d: String) {
        self.perp_facts.push((a, b, c, d));
    }

    fn add_cong(&mut self, a: String, b: String, c: String, d: String) {
        self.cong_facts.push((a, b, c, d));
    }

    fn add_eqangle(&mut self, a: String, b: String, c: String, d: String, e: String, f: String) {
        self.eqangle_facts.push((a, b, c, d, e, f));
    }

    fn add_cyclic(&mut self, a: String, b: String, c: String, d: String) {
        self.cyclic_facts.push((a, b, c, d));
    }

    fn add_sameclock(&mut self, a: String, b: String, c: String, d: String, e: String, f: String) {
        self.sameclock_facts.push((a, b, c, d, e, f));
    }

    fn add_midp(&mut self, a: String, b: String, c: String) {
        self.midp_facts.push((a, b, c));
    }

    fn add_contri1(&mut self, a: String, b: String, c: String, d: String, e: String, f: String) {
        self.contri1_facts.push((a, b, c, d, e, f));
    }

    fn add_contri2(&mut self, a: String, b: String, c: String, d: String, e: String, f: String) {
        self.contri2_facts.push((a, b, c, d, e, f));
    }

    fn add_simtri1(&mut self, a: String, b: String, c: String, d: String, e: String, f: String) {
        self.simtri1_facts.push((a, b, c, d, e, f));
    }

    fn add_simtri2(&mut self, a: String, b: String, c: String, d: String, e: String, f: String) {
        self.simtri2_facts.push((a, b, c, d, e, f));
    }

    fn add_eqratio(
        &mut self,
        a: String,
        b: String,
        c: String,
        d: String,
        e: String,
        f: String,
        g: String,
        h: String,
    ) {
        self.eqratio_facts.push((a, b, c, d, e, f, g, h));
    }

    fn add_aconst(&mut self, a: String, b: String, c: String, m: i32, n: i32) {
        self.aconst_facts.push((a, b, c, m, n));
    }

    fn run(&mut self) {
        let points = self.points.clone();
        let coordinates = self.coordinates.clone();
        let distinct_facts = self.distinct_facts.clone();
        let nonparallel_facts = self.nonparallel_facts.clone();
        let noncollinear_facts = self.noncollinear_facts.clone();
        let eqpoint_facts = self.eqpoint_facts.clone();
        let inter_facts = self.inter_facts.clone();

        let col_facts = self.col_facts.clone();
        let para_facts = self.para_facts.clone();
        let perp_facts = self.perp_facts.clone();
        let cong_facts = self.cong_facts.clone();
        let eqangle_facts = self.eqangle_facts.clone();
        let cyclic_facts = self.cyclic_facts.clone();
        let sameclock_facts = self.sameclock_facts.clone();
        let midp_facts = self.midp_facts.clone();
        let contri1_facts = self.contri1_facts.clone();
        let contri2_facts = self.contri2_facts.clone();
        let simtri1_facts = self.simtri1_facts.clone();
        let simtri2_facts = self.simtri2_facts.clone();
        let eqratio_facts = self.eqratio_facts.clone();
        let aconst_facts = self.aconst_facts.clone();

        let prog = ascent_run! {

            relation point(String) = points;
            relation distinct(String, String) = distinct_facts;
            relation nonparallel(String, String, String, String) = nonparallel_facts;
            relation noncollinear(String, String, String) = noncollinear_facts;

            lattice col(String, String, String, Provenance) = col_facts
                .into_iter()
                .map(|(a, b, c)| (a, b, c, axiom()))
                .collect();
            lattice para(String, String, String, String, Provenance) = para_facts
                .into_iter()
                .map(|(a, b, c, d)| (a, b, c, d, axiom()))
                .collect();
            lattice perp(String, String, String, String, Provenance) = perp_facts
                .into_iter()
                .map(|(a, b, c, d)| (a, b, c, d, axiom()))
                .collect();
            lattice cong(String, String, String, String, Provenance) = cong_facts
                .into_iter()
                .map(|(a, b, c, d)| (a, b, c, d, axiom()))
                .collect();
            lattice eqangle(String, String, String, String, String, String, Provenance) = eqangle_facts
                .into_iter()
                .map(|(a, b, c, d, e, f)| (a, b, c, d, e, f, axiom()))
                .collect();
            lattice cyclic(String, String, String, String, Provenance) = cyclic_facts
                .into_iter()
                .map(|(a, b, c, d)| (a, b, c, d, axiom()))
                .collect();
            lattice sameclock(String, String, String, String, String, String, Provenance) = sameclock_facts
                .into_iter()
                .map(|(a, b, c, d, e, f)| (a, b, c, d, e, f, axiom()))
                .collect();
            lattice eqratio(String, String, String, String, String, String, String, String, Provenance) = eqratio_facts
                .into_iter()
                .map(|(a, b, c, d, e, f, g, h)| (a, b, c, d, e, f, g, h, axiom()))
                .collect();
            lattice midp(String, String, String, Provenance) = midp_facts
                .into_iter()
                .map(|(a, b, c)| (a, b, c, axiom()))
                .collect();
            lattice contri1(String, String, String, String, String, String, Provenance) = contri1_facts
                .into_iter()
                .map(|(a, b, c, d, e, f)| (a, b, c, d, e, f, axiom()))
                .collect();
            lattice contri2(String, String, String, String, String, String, Provenance) = contri2_facts
                .into_iter()
                .map(|(a, b, c, d, e, f)| (a, b, c, d, e, f, axiom()))
                .collect();
            lattice simtri1(String, String, String, String, String, String, Provenance) = simtri1_facts
                .into_iter()
                .map(|(a, b, c, d, e, f)| (a, b, c, d, e, f, axiom()))
                .collect();
            lattice simtri2(String, String, String, String, String, String, Provenance) = simtri2_facts
                .into_iter()
                .map(|(a, b, c, d, e, f)| (a, b, c, d, e, f, axiom()))
                .collect();
            lattice aconst(String, String, String, i32, i32, Provenance) = aconst_facts
                .into_iter()
                .map(|(a, b, c, m, n)| (a, b, c, m, n, axiom()))
                .collect();

            lattice eqpoint(String, String, Provenance) = eqpoint_facts
                .into_iter()
                .map(|(a, b)| (a, b, axiom()))
                .collect();
            lattice inter(String, String, String, String, String, Provenance) = inter_facts
                .into_iter()
                .map(|(x, a, b, c, d)| (x, a, b, c, d, axiom()))
                .collect();

            // Define guards here to capture this run's coordinate map.
            macro numerically_distinct($a: expr, $b: expr) {
                if numerically_distinct(&coordinates, $a, $b)
            }
            macro numerically_nonparallel($a: expr, $b: expr, $c: expr, $d: expr) {
                if numerically_nonparallel(&coordinates, $a, $b, $c, $d)
            }
            macro same_orientation($a: expr, $b: expr, $c: expr, $d: expr, $e: expr, $f: expr) {
                if same_orientation(&coordinates, &[$a, $b, $c], &[$d, $e, $f])
            }

            include_source!(rules::nondegeneracy);
            include_source!(rules::equality);
            include_source!(rules::substitution);
            include_source!(rules::geometry);
        };

        // Extract derived results
        self.derived_distinct = prog.distinct;
        self.derived_nonparallel = prog.nonparallel;
        self.derived_noncollinear = prog.noncollinear;
        self.derived_eqpoint = prog.eqpoint;
        self.derived_inter = prog.inter;
        self.derived_col = prog.col;
        self.derived_para = prog.para;
        self.derived_perp = prog.perp;
        self.derived_cong = prog.cong;
        self.derived_eqangle = prog.eqangle;
        self.derived_cyclic = prog.cyclic;
        self.derived_sameclock = prog.sameclock;
        self.derived_midp = prog.midp;
        self.derived_contri1 = prog.contri1;
        self.derived_contri2 = prog.contri2;
        self.derived_simtri1 = prog.simtri1;
        self.derived_simtri2 = prog.simtri2;
        self.derived_eqratio = prog.eqratio;
        self.derived_aconst = prog.aconst;
    }

    // Output methods
    fn get_points(&self) -> Vec<(f64, f64, String)> {
        self.points
            .iter()
            .map(|(name,)| {
                let &(x, y) = &self.coordinates[name];
                (x, y, name.clone())
            })
            .collect()
    }

    fn get_distinct(&self) -> Vec<(String, String, Vec<(String, Vec<String>)>)> {
        let inputs: HashSet<_> = self.distinct_facts.iter().cloned().collect();
        self.derived_distinct
            .iter()
            .map(|(a, b)| {
                let paths = if inputs.contains(&(a.clone(), b.clone())) {
                    vec![("axiom".to_string(), vec![])]
                } else {
                    vec![("numerical".to_string(), vec![])]
                };
                (a.clone(), b.clone(), paths)
            })
            .collect()
    }

    fn get_nonparallel(&self) -> Vec<(String, String, String, String, Vec<(String, Vec<String>)>)> {
        let inputs: HashSet<_> = self.nonparallel_facts.iter().cloned().collect();
        self.derived_nonparallel
            .iter()
            .map(|(a, b, c, d)| {
                let paths = if inputs.contains(&(a.clone(), b.clone(), c.clone(), d.clone())) {
                    vec![("axiom".to_string(), vec![])]
                } else {
                    vec![("numerical".to_string(), vec![])]
                };
                (a.clone(), b.clone(), c.clone(), d.clone(), paths)
            })
            .collect()
    }

    fn get_noncollinear(&self) -> Vec<(String, String, String, Vec<(String, Vec<String>)>)> {
        let inputs: HashSet<_> = self.noncollinear_facts.iter().cloned().collect();
        self.derived_noncollinear
            .iter()
            .map(|(a, b, c)| {
                let paths = if inputs.contains(&(a.clone(), b.clone(), c.clone())) {
                    vec![("axiom".to_string(), vec![])]
                } else {
                    vec![(
                        "noncollinear".to_string(),
                        vec![fact_id("nonparallel", [a, b, a, c])],
                    )]
                };
                (a.clone(), b.clone(), c.clone(), paths)
            })
            .collect()
    }

    fn get_eqpoint(&self) -> Vec<(String, String, Vec<(String, Vec<String>)>)> {
        self.derived_eqpoint
            .iter()
            .map(|(a, b, prov)| {
                let ds = prov
                    .iter()
                    .map(|d| (d.rule.clone(), d.parents.iter().cloned().collect()))
                    .collect();
                (a.clone(), b.clone(), ds)
            })
            .collect()
    }

    fn get_inter(
        &self,
    ) -> Vec<(
        String,
        String,
        String,
        String,
        String,
        Vec<(String, Vec<String>)>,
    )> {
        self.derived_inter
            .iter()
            .map(|(a, b, c, d, e, prov)| {
                let ds = prov
                    .iter()
                    .map(|d| (d.rule.clone(), d.parents.iter().cloned().collect()))
                    .collect();
                (a.clone(), b.clone(), c.clone(), d.clone(), e.clone(), ds)
            })
            .collect()
    }

    fn get_col(&self) -> Vec<(String, String, String, Vec<(String, Vec<String>)>)> {
        self.derived_col
            .iter()
            .map(|(a, b, c, prov)| {
                let derivations = prov
                    .iter()
                    .map(|d| (d.rule.clone(), d.parents.iter().cloned().collect()))
                    .collect();
                (a.clone(), b.clone(), c.clone(), derivations)
            })
            .collect()
    }

    fn get_para(&self) -> Vec<(String, String, String, String, Vec<(String, Vec<String>)>)> {
        self.derived_para
            .iter()
            .map(|(a, b, c, d, prov)| {
                let derivations = prov
                    .iter()
                    .map(|d| (d.rule.clone(), d.parents.iter().cloned().collect()))
                    .collect();
                (a.clone(), b.clone(), c.clone(), d.clone(), derivations)
            })
            .collect()
    }

    fn get_perp(&self) -> Vec<(String, String, String, String, Vec<(String, Vec<String>)>)> {
        self.derived_perp
            .iter()
            .map(|(a, b, c, d, prov)| {
                let derivations = prov
                    .iter()
                    .map(|d| (d.rule.clone(), d.parents.iter().cloned().collect()))
                    .collect();
                (a.clone(), b.clone(), c.clone(), d.clone(), derivations)
            })
            .collect()
    }

    fn get_cong(&self) -> Vec<(String, String, String, String, Vec<(String, Vec<String>)>)> {
        self.derived_cong
            .iter()
            .map(|(a, b, c, d, prov)| {
                let derivations = prov
                    .iter()
                    .map(|d| (d.rule.clone(), d.parents.iter().cloned().collect()))
                    .collect();
                (a.clone(), b.clone(), c.clone(), d.clone(), derivations)
            })
            .collect()
    }

    fn get_eqangle(
        &self,
    ) -> Vec<(
        String,
        String,
        String,
        String,
        String,
        String,
        Vec<(String, Vec<String>)>,
    )> {
        self.derived_eqangle
            .iter()
            .map(|(a, b, c, d, e, f, prov)| {
                let derivations = prov
                    .iter()
                    .map(|d| (d.rule.clone(), d.parents.iter().cloned().collect()))
                    .collect();
                (
                    a.clone(),
                    b.clone(),
                    c.clone(),
                    d.clone(),
                    e.clone(),
                    f.clone(),
                    derivations,
                )
            })
            .collect()
    }

    fn get_cyclic(&self) -> Vec<(String, String, String, String, Vec<(String, Vec<String>)>)> {
        self.derived_cyclic
            .iter()
            .map(|(a, b, c, d, prov)| {
                let derivations = prov
                    .iter()
                    .map(|d| (d.rule.clone(), d.parents.iter().cloned().collect()))
                    .collect();
                (a.clone(), b.clone(), c.clone(), d.clone(), derivations)
            })
            .collect()
    }

    fn get_sameclock(
        &self,
    ) -> Vec<(
        String,
        String,
        String,
        String,
        String,
        String,
        Vec<(String, Vec<String>)>,
    )> {
        self.derived_sameclock
            .iter()
            .map(|(a, b, c, d, e, f, prov)| {
                let derivations = prov
                    .iter()
                    .map(|d| (d.rule.clone(), d.parents.iter().cloned().collect()))
                    .collect();
                (
                    a.clone(),
                    b.clone(),
                    c.clone(),
                    d.clone(),
                    e.clone(),
                    f.clone(),
                    derivations,
                )
            })
            .collect()
    }

    fn get_midp(&self) -> Vec<(String, String, String, Vec<(String, Vec<String>)>)> {
        self.derived_midp
            .iter()
            .map(|(a, b, c, prov)| {
                let derivations = prov
                    .iter()
                    .map(|d| (d.rule.clone(), d.parents.iter().cloned().collect()))
                    .collect();
                (a.clone(), b.clone(), c.clone(), derivations)
            })
            .collect()
    }

    fn get_contri1(
        &self,
    ) -> Vec<(
        String,
        String,
        String,
        String,
        String,
        String,
        Vec<(String, Vec<String>)>,
    )> {
        self.derived_contri1
            .iter()
            .map(|(a, b, c, d, e, f, prov)| {
                let derivations = prov
                    .iter()
                    .map(|d| (d.rule.clone(), d.parents.iter().cloned().collect()))
                    .collect();
                (
                    a.clone(),
                    b.clone(),
                    c.clone(),
                    d.clone(),
                    e.clone(),
                    f.clone(),
                    derivations,
                )
            })
            .collect()
    }

    fn get_contri2(
        &self,
    ) -> Vec<(
        String,
        String,
        String,
        String,
        String,
        String,
        Vec<(String, Vec<String>)>,
    )> {
        self.derived_contri2
            .iter()
            .map(|(a, b, c, d, e, f, prov)| {
                let derivations = prov
                    .iter()
                    .map(|d| (d.rule.clone(), d.parents.iter().cloned().collect()))
                    .collect();
                (
                    a.clone(),
                    b.clone(),
                    c.clone(),
                    d.clone(),
                    e.clone(),
                    f.clone(),
                    derivations,
                )
            })
            .collect()
    }

    fn get_simtri1(
        &self,
    ) -> Vec<(
        String,
        String,
        String,
        String,
        String,
        String,
        Vec<(String, Vec<String>)>,
    )> {
        self.derived_simtri1
            .iter()
            .map(|(a, b, c, d, e, f, prov)| {
                let derivations = prov
                    .iter()
                    .map(|d| (d.rule.clone(), d.parents.iter().cloned().collect()))
                    .collect();
                (
                    a.clone(),
                    b.clone(),
                    c.clone(),
                    d.clone(),
                    e.clone(),
                    f.clone(),
                    derivations,
                )
            })
            .collect()
    }

    fn get_simtri2(
        &self,
    ) -> Vec<(
        String,
        String,
        String,
        String,
        String,
        String,
        Vec<(String, Vec<String>)>,
    )> {
        self.derived_simtri2
            .iter()
            .map(|(a, b, c, d, e, f, prov)| {
                let derivations = prov
                    .iter()
                    .map(|d| (d.rule.clone(), d.parents.iter().cloned().collect()))
                    .collect();
                (
                    a.clone(),
                    b.clone(),
                    c.clone(),
                    d.clone(),
                    e.clone(),
                    f.clone(),
                    derivations,
                )
            })
            .collect()
    }

    fn get_eqratio(
        &self,
    ) -> Vec<(
        String,
        String,
        String,
        String,
        String,
        String,
        String,
        String,
        Vec<(String, Vec<String>)>,
    )> {
        self.derived_eqratio
            .iter()
            .map(|(a, b, c, d, e, f, g, h, prov)| {
                let derivations = prov
                    .iter()
                    .map(|d| (d.rule.clone(), d.parents.iter().cloned().collect()))
                    .collect();
                (
                    a.clone(),
                    b.clone(),
                    c.clone(),
                    d.clone(),
                    e.clone(),
                    f.clone(),
                    g.clone(),
                    h.clone(),
                    derivations,
                )
            })
            .collect()
    }

    fn get_aconst(&self) -> Vec<(String, String, String, i32, i32, Vec<(String, Vec<String>)>)> {
        self.derived_aconst
            .iter()
            .map(|(a, b, c, m, n, prov)| {
                let derivations = prov
                    .iter()
                    .map(|d| (d.rule.clone(), d.parents.iter().cloned().collect()))
                    .collect();
                (a.clone(), b.clone(), c.clone(), *m, *n, derivations)
            })
            .collect()
    }
}

#[pymodule]
fn ascent_py(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<DeductiveDatabase>()?;
    Ok(())
}
