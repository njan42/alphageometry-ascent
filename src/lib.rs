use ascent::ascent;
use ascent::Lattice;
use pyo3::prelude::*;
use pyo3::{types::PyModule, Bound};
use std::collections::BTreeSet;

fn same_orientation(l1: Vec<(i64, i64)>, l2: Vec<(i64, i64)>) -> bool {
    let edge_length = |p: (i64, i64), q: (i64, i64)| (q.0 - p.0) * (q.1 + p.1);

    let area1: i64 = (0..l1.len())
        .map(|i| edge_length(l1[i], l1[(i + 1) % l1.len()]))
        .sum();

    let area2: i64 = (0..l2.len())
        .map(|i| edge_length(l2[i], l2[(i + 1) % l2.len()]))
        .sum();

    (area1 * area2) > 0
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

// Provenance lattice to track all ways a fact was derived
#[derive(Clone, Debug, PartialEq, Eq, Hash)]
struct Provenance {
    derivations: BTreeSet<Derivation>,
}

impl Provenance {
    fn axiom() -> Self {
        let mut derivations = BTreeSet::new();
        derivations.insert(Derivation::axiom());
        Provenance { derivations }
    }

    fn from(rule: &str, parents: Vec<String>) -> Self {
        let mut derivations = BTreeSet::new();
        derivations.insert(Derivation::new(rule, parents));
        Provenance { derivations }
    }
}

impl PartialOrd for Provenance {
    fn partial_cmp(&self, other: &Self) -> Option<std::cmp::Ordering> {
        use std::cmp::Ordering;
        if self == other {
            Some(Ordering::Equal)
        } else if self.derivations.is_subset(&other.derivations) {
            Some(Ordering::Less)
        } else if self.derivations.is_superset(&other.derivations) {
            Some(Ordering::Greater)
        } else {
            None
        }
    }
}

impl Lattice for Provenance {
    fn meet_mut(&mut self, other: Self) -> bool {
        let old_len = self.derivations.len();
        self.derivations.retain(|d| other.derivations.contains(d));
        self.derivations.len() != old_len
    }

    fn join_mut(&mut self, other: Self) -> bool {
        let old_len = self.derivations.len();
        self.derivations.extend(other.derivations);
        self.derivations.len() != old_len
    }
}

fn fact_id(pred_type: &str, args: impl IntoIterator<Item = impl AsRef<str>>) -> String {
    let args_str: Vec<String> = args.into_iter().map(|s| s.as_ref().to_string()).collect();
    format!("{}({})", pred_type, args_str.join(","))
}

#[pyclass]
struct DeductiveDatabase {
    // Input facts
    points: Vec<(i64, i64, String)>,
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

    fn add_point(&mut self, x: i64, y: i64, name: String) {
        if self.points.iter().any(|(_, _, n)| n == &name) {
            return;
        }
        self.points.push((x, y, name.clone()));
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

        ascent! {
            struct AscentProgram;

            relation point(i64, i64, String);

            lattice col(String, String, String, Provenance);
            lattice para(String, String, String, String, Provenance);
            lattice perp(String, String, String, String, Provenance);
            lattice cong(String, String, String, String, Provenance);
            lattice eqangle(String, String, String, String, String, String, Provenance);
            lattice cyclic(String, String, String, String, Provenance);
            lattice sameclock(String, String, String, String, String, String, Provenance);
            lattice eqratio(String, String, String, String, String, String, String, String, Provenance);
            lattice midp(String, String, String, Provenance);
            lattice contri1(String, String, String, String, String, String, Provenance);
            lattice contri2(String, String, String, String, String, String, Provenance);
            lattice simtri1(String, String, String, String, String, String, Provenance);
            lattice simtri2(String, String, String, String, String, String, Provenance);
            lattice aconst(String, String, String, i32, i32, Provenance);

            // ----------------------------------------------------------------
            // Relation Properties (Symmetries)
            // ----------------------------------------------------------------

            col(c, b, a, Provenance::from("sym", vec![fact_id("col", [a, b, c])]))
                <-- col(a, b, c, ?_prov);
            col(a, c, b, Provenance::from("sym", vec![fact_id("col", [a, b, c])]))
                <-- col(a, b, c, ?_prov);

            para(c, d, a, b, Provenance::from("sym", vec![fact_id("para", [a, b, c, d])]))
                <-- para(a, b, c, d, ?_prov);
            para(b, a, c, d, Provenance::from("sym", vec![fact_id("para", [a, b, c, d])]))
                <-- para(a, b, c, d, ?_prov);
            para(a, b, d, c, Provenance::from("sym", vec![fact_id("para", [a, b, c, d])]))
                <-- para(a, b, c, d, ?_prov);

            perp(c, d, a, b, Provenance::from("sym", vec![fact_id("perp", [a, b, c, d])]))
                <-- perp(a, b, c, d, ?_prov);
            perp(b, a, c, d, Provenance::from("sym", vec![fact_id("perp", [a, b, c, d])]))
                <-- perp(a, b, c, d, ?_prov);
            perp(a, b, d, c, Provenance::from("sym", vec![fact_id("perp", [a, b, c, d])]))
                <-- perp(a, b, c, d, ?_prov);

            cong(c, d, a, b, Provenance::from("sym", vec![fact_id("cong", [a, b, c, d])]))
                <-- cong(a, b, c, d, ?_prov);
            cong(b, a, c, d, Provenance::from("sym", vec![fact_id("cong", [a, b, c, d])]))
                <-- cong(a, b, c, d, ?_prov);
            cong(a, b, d, c, Provenance::from("sym", vec![fact_id("cong", [a, b, c, d])]))
                <-- cong(a, b, c, d, ?_prov);

            eqangle(d, e, f, a, b, c, Provenance::from("sym", vec![fact_id("eqangle", [a, b, c, d, e, f])]))
                <-- eqangle(a, b, c, d, e, f, ?_prov);
            eqangle(c, b, a, f, e, d, Provenance::from("sym", vec![fact_id("eqangle", [a, b, c, d, e, f])]))
                <-- eqangle(a, b, c, d, e, f, ?_prov);

            cyclic(b, c, d, a, Provenance::from("sym", vec![fact_id("cyclic", [a, b, c, d])]))
                <-- cyclic(a, b, c, d, ?_prov);
            cyclic(a, c, b, d, Provenance::from("sym", vec![fact_id("cyclic", [a, b, c, d])]))
                <-- cyclic(a, b, c, d, ?_prov);

            sameclock(d, e, f, a, b, c, Provenance::from("sym", vec![fact_id("sameclock", [a, b, c, d, e, f])]))
                <-- sameclock(a, b, c, d, e, f, ?_prov);
            sameclock(a, b, c, f, d, e, Provenance::from("sym", vec![fact_id("sameclock", [a, b, c, d, e, f])]))
                <-- sameclock(a, b, c, d, e, f, ?_prov);
            sameclock(c, b, a, f, e, d, Provenance::from("sym", vec![fact_id("sameclock", [a, b, c, d, e, f])]))
                <-- sameclock(a, b, c, d, e, f, ?_prov);

            eqratio(b, a, c, d, e, f, g, h, Provenance::from("sym", vec![fact_id("eqratio", [a, b, c, d, e, f, g, h])]))
                <-- eqratio(a, b, c, d, e, f, g, h, ?_prov);
            eqratio(e, f, g, h, a, b, c, d, Provenance::from("sym", vec![fact_id("eqratio", [a, b, c, d, e, f, g, h])]))
                <-- eqratio(a, b, c, d, e, f, g, h, ?_prov);
            eqratio(c, d, a, b, g, h, e, f, Provenance::from("sym", vec![fact_id("eqratio", [a, b, c, d, e, f, g, h])]))
                <-- eqratio(a, b, c, d, e, f, g, h, ?_prov);
            eqratio(a, b, e, f, c, d, g, h, Provenance::from("sym", vec![fact_id("eqratio", [a, b, c, d, e, f, g, h])]))
                <-- eqratio(a, b, c, d, e, f, g, h, ?_prov);

            // ----------------------------------------------------------------
            // Trivial Statements
            // ----------------------------------------------------------------

            cong(a, b, a, b, Provenance::from("rfl", vec![])) <--
                point(_, _, a), point(_, _, b),
                if a != b;

            para(a, b, a, b, Provenance::from("rfl", vec![])) <--
                point(_, _, a), point(_, _, b),
                if a != b;

            eqangle(a, b, c, a, b, c, Provenance::from("rfl", vec![])) <--
                point(_, _, a), point(_, _, b), point(_, _, c),
                if a != b && a != c && b != c;

            // ----------------------------------------------------------------
            // Deductive Rules
            // ----------------------------------------------------------------

            // Two distinct points determine lines
            col(a, c, d, Provenance::from("trans", vec![
                fact_id("col", [a, b, c]),
                fact_id("col", [a, b, d])
            ])) <--
                col(a, b, c, ?_prov1), col(a, b, d, ?_prov2),
                if a != b && a != c && a != d &&
                   b != c && b != d && c != d;

            // Right Angle Equal
            eqangle(c, b, a, b, e, a, Provenance::from("right_angle_eq", vec![
                fact_id("perp", [a, b, b_prime, c]),
                fact_id("perp", [a, e, e_prime, b])
            ])) <--
                perp(a, b, b_prime, c, ?_prov1),
                perp(a, e, e_prime, b, ?_prov2),
                if b == b_prime && e == e_prime &&
                   a != b && a != c && a != e &&
                   b != c && b != e &&
                   c != e;

            // AA Similarity
            simtri1(a, b, c, d, e, f, Provenance::from("aa_sim", vec![
                fact_id("eqangle", [b, a, c, e, d, f]),
                fact_id("eqangle", [b, c, a, e, f, d])
            ])) <--
                eqangle(b, a, c, e, d, f, ?_prov1),
                eqangle(b, c, a, e, f, d, ?_prov2),
                point(ax, ay, a), point(bx, by, b), point(cx, cy, c),
                point(dx, dy, d), point(ex, ey, e), point(fx, fy, f),
                if same_orientation(
                    vec![(*ax, *ay), (*bx, *by), (*cx, *cy)],
                    vec![(*dx, *dy), (*ex, *ey), (*fx, *fy)]
                );

            simtri2(a, b, c, d, e, f, Provenance::from("aa_sim", vec![
                fact_id("eqangle", [b, a, c, f, d, e]),
                fact_id("eqangle", [b, c, a, d, f, e])
            ])) <--
                eqangle(b, a, c, f, d, e, ?_prov1),
                eqangle(b, c, a, d, f, e, ?_prov2),
                point(ax, ay, a), point(bx, by, b), point(cx, cy, c),
                point(dx, dy, d), point(ex, ey, e), point(fx, fy, f),
                if same_orientation(
                    vec![(*ax, *ay), (*bx, *by), (*cx, *cy)],
                    vec![(*fx, *fy), (*ex, *ey), (*dx, *dy)]
                );

            // ASA Congruence
            contri1(a, b, c, d, e, f, Provenance::from("asa_cong", vec![
                fact_id("eqangle", [b, a, c, e, d, f]),
                fact_id("eqangle", [c, b, a, f, e, d]),
                fact_id("cong", [a, b, d, e])
            ])) <--
                eqangle(b, a, c, e, d, f, ?_prov1),
                eqangle(c, b, a, f, e, d, ?_prov2),
                cong(a, b, d, e, ?_prov3),
                point(ax, ay, a), point(bx, by, b), point(cx, cy, c),
                point(dx, dy, d), point(ex, ey, e), point(fx, fy, f),
                if same_orientation(
                    vec![(*ax, *ay), (*bx, *by), (*cx, *cy)],
                    vec![(*dx, *dy), (*ex, *ey), (*fx, *fy)]
                );

            contri2(a, b, c, d, e, f, Provenance::from("asa_cong", vec![
                fact_id("eqangle", [b, a, c, f, d, e]),
                fact_id("eqangle", [c, b, a, d, e, f]),
                fact_id("cong", [a, b, d, e])
            ])) <--
                eqangle(b, a, c, f, d, e, ?_prov1),
                eqangle(c, b, a, d, e, f, ?_prov2),
                cong(a, b, d, e, ?_prov3),
                point(ax, ay, a), point(bx, by, b), point(cx, cy, c),
                point(dx, dy, d), point(ex, ey, e), point(fx, fy, f),
                if same_orientation(
                    vec![(*ax, *ay), (*bx, *by), (*cx, *cy)],
                    vec![(*fx, *fy), (*ex, *ey), (*dx, *dy)]
                );

            // SAS Congruence
            contri1(a, b, c, d, e, f, Provenance::from("sas_cong", vec![
                fact_id("eqangle", [b, a, c, e, d, f]),
                fact_id("cong", [a, c, d, f]),
                fact_id("cong", [a, b, d, e])
            ])) <--
                eqangle(b, a, c, e, d, f, ?_prov1),
                cong(a, c, d, f, ?_prov2),
                cong(a, b, d, e, ?_prov3),
                point(ax, ay, a), point(bx, by, b), point(cx, cy, c),
                point(dx, dy, d), point(ex, ey, e), point(fx, fy, f),
                if same_orientation(
                    vec![(*ax, *ay), (*bx, *by), (*cx, *cy)],
                    vec![(*dx, *dy), (*ex, *ey), (*fx, *fy)]
                );

            contri2(a, b, c, d, e, f, Provenance::from("sas_cong", vec![
                fact_id("eqangle", [b, a, c, f, d, e]),
                fact_id("cong", [a, c, d, f]),
                fact_id("cong", [a, b, d, e])
            ])) <--
                eqangle(b, a, c, f, d, e, ?_prov1),
                cong(a, c, d, f, ?_prov2),
                cong(a, b, d, e, ?_prov3),
                point(ax, ay, a), point(bx, by, b), point(cx, cy, c),
                point(dx, dy, d), point(ex, ey, e), point(fx, fy, f),
                if same_orientation(
                    vec![(*ax, *ay), (*bx, *by), (*cx, *cy)],
                    vec![(*fx, *fy), (*ex, *ey), (*dx, *dy)]
                );

            // SSS Congruence
            contri1(a, b, c, d, e, f, Provenance::from("sss_cong", vec![
                fact_id("cong", [a, c, d, f]),
                fact_id("cong", [a, b, d, e]),
                fact_id("cong", [c, b, f, e])
            ])) <--
                cong(a, c, d, f, ?_prov1),
                cong(a, b, d, e, ?_prov2),
                cong(c, b, f, e, ?_prov3),
                point(ax, ay, a), point(bx, by, b), point(cx, cy, c),
                point(dx, dy, d), point(ex, ey, e), point(fx, fy, f),
                if same_orientation(
                    vec![(*ax, *ay), (*bx, *by), (*cx, *cy)],
                    vec![(*dx, *dy), (*ex, *ey), (*fx, *fy)]
                );

            contri2(a, b, c, d, e, f, Provenance::from("sss_cong", vec![
                fact_id("cong", [a, c, d, f]),
                fact_id("cong", [a, b, d, e]),
                fact_id("cong", [c, b, f, e])
            ])) <--
                cong(a, c, d, f, ?_prov1),
                cong(a, b, d, e, ?_prov2),
                cong(c, b, f, e, ?_prov3),
                point(ax, ay, a), point(bx, by, b), point(cx, cy, c),
                point(dx, dy, d), point(ex, ey, e), point(fx, fy, f),
                if same_orientation(
                    vec![(*ax, *ay), (*bx, *by), (*cx, *cy)],
                    vec![(*fx, *fy), (*ex, *ey), (*dx, *dy)]
                );

            // Right SSA Congruence
            contri1(a, b, c, d, e, f, Provenance::from("ssa_right_cong", vec![
                fact_id("perp", [a, b, a_prime, c]),
                fact_id("perp", [d, e, d_prime, f]),
                fact_id("cong", [a, b, d, e]),
                fact_id("cong", [b, c, e, f])
            ])) <--
                perp(a, b, a_prime, c, ?_prov1),
                perp(d, e, d_prime, f, ?_prov2),
                cong(a, b, d, e, ?_prov3),
                cong(b, c, e, f, ?_prov4),
                point(ax, ay, a), point(bx, by, b), point(cx, cy, c),
                point(dx, dy, d), point(ex, ey, e), point(fx, fy, f),
                if same_orientation(
                    vec![(*ax, *ay), (*bx, *by), (*cx, *cy)],
                    vec![(*dx, *dy), (*ex, *ey), (*fx, *fy)]
            ) && a == a_prime && d == d_prime;

            contri2(a, b, c, d, e, f, Provenance::from("ssa_right_cong", vec![
                fact_id("perp", [a, b, a_prime, c]),
                fact_id("perp", [d, e, d_prime, f]),
                fact_id("cong", [a, b, d, e]),
                fact_id("cong", [b, c, e, f])
            ])) <--
                perp(a, b, a_prime, c, ?_prov1),
                perp(d, e, d_prime, f, ?_prov2),
                cong(a, b, d, e, ?_prov3),
                cong(b, c, e, f, ?_prov4),
                point(ax, ay, a), point(bx, by, b), point(cx, cy, c),
                point(dx, dy, d), point(ex, ey, e), point(fx, fy, f),
                if same_orientation(
                    vec![(*ax, *ay), (*bx, *by), (*cx, *cy)],
                    vec![(*fx, *fy), (*ex, *ey), (*dx, *dy)]
                ) && a == a_prime && d == d_prime;

            // Inscribed Angle Theorem
            eqangle(a, b, c, c, b, d, Provenance::from("inscribed_angle_thm", vec![
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
                if o == o_prime && b == b_prime && c == c_prime &&
                   a != b && a != c && a != d &&
                   b != c && b != d &&
                   c != d;

            // Thales's theorem
            perp(b, r, r, d, Provenance::from("thales_thm", vec![
                fact_id("cyclic", [b, r, y, d]),
                fact_id("cong", [b, o, r, o_prime]),
                fact_id("cong", [r, o, d, o_prime]),
                fact_id("col", [b, o, d])
            ])) <--
                cyclic(b, r, y, d, ?_prov1),
                cong(b, o, r, o_prime, ?_prov2),
                cong(r, o, d, o_prime, ?_prov3),
                col(b, o, d, ?_prov4),
                if o == o_prime &&
                   b != r && b != y && b != d &&
                   r != y && r != d &&
                   y != d;

            // Eqratio is Additive
            eqratio(a, m, b, n, m, c, n, d, Provenance::from("eqratio_additive", vec![
                fact_id("eqratio", [a, c, m, c, b, d, n, d]),
                fact_id("col", [a, m, c]),
                fact_id("col", [b, n, d])
            ])) <--
                eqratio(a, c, m, c_prime, b, d, n, d_prime, ?_prov1),
                col(a, m, c, ?_prov2),
                col(b, n, d, ?_prov3),
                if a != m && a != c &&
                   m != c &&
                   b != n && b != d &&
                   n != d &&
                   c == c_prime && d == d_prime;

            eqratio(a, c, m, c, b, d, n, d, Provenance::from("eqratio_additive", vec![
                fact_id("eqratio", [a, m, b, n, m, c, n, d]),
                fact_id("col", [a, m, c]),
                fact_id("col", [b, n, d])
            ])) <--
                eqratio(a, m, b, n, m_prime, c, n_prime, d, ?_prov1),
                col(a, m, c, ?_prov2),
                col(b, n, d, ?_prov3),
                if a != m && a != c &&
                   m != c &&
                   b != n && b != d &&
                   n != d &&
                   m == m_prime && n == n_prime;
        }

        let mut prog = AscentProgram::default();

        // Initialize input relations with axiom provenance
        prog.point = points;
        prog.col = col_facts
            .into_iter()
            .map(|(a, b, c)| (a, b, c, Provenance::axiom()))
            .collect();
        prog.para = para_facts
            .into_iter()
            .map(|(a, b, c, d)| (a, b, c, d, Provenance::axiom()))
            .collect();
        prog.perp = perp_facts
            .into_iter()
            .map(|(a, b, c, d)| (a, b, c, d, Provenance::axiom()))
            .collect();
        prog.cong = cong_facts
            .into_iter()
            .map(|(a, b, c, d)| (a, b, c, d, Provenance::axiom()))
            .collect();
        prog.eqangle = eqangle_facts
            .into_iter()
            .map(|(a, b, c, d, e, f)| (a, b, c, d, e, f, Provenance::axiom()))
            .collect();
        prog.cyclic = cyclic_facts
            .into_iter()
            .map(|(a, b, c, d)| (a, b, c, d, Provenance::axiom()))
            .collect();
        prog.sameclock = sameclock_facts
            .into_iter()
            .map(|(a, b, c, d, e, f)| (a, b, c, d, e, f, Provenance::axiom()))
            .collect();
        prog.midp = midp_facts
            .into_iter()
            .map(|(a, b, c)| (a, b, c, Provenance::axiom()))
            .collect();
        prog.contri1 = contri1_facts
            .into_iter()
            .map(|(a, b, c, d, e, f)| (a, b, c, d, e, f, Provenance::axiom()))
            .collect();
        prog.contri2 = contri2_facts
            .into_iter()
            .map(|(a, b, c, d, e, f)| (a, b, c, d, e, f, Provenance::axiom()))
            .collect();
        prog.simtri1 = simtri1_facts
            .into_iter()
            .map(|(a, b, c, d, e, f)| (a, b, c, d, e, f, Provenance::axiom()))
            .collect();
        prog.simtri2 = simtri2_facts
            .into_iter()
            .map(|(a, b, c, d, e, f)| (a, b, c, d, e, f, Provenance::axiom()))
            .collect();
        prog.eqratio = eqratio_facts
            .into_iter()
            .map(|(a, b, c, d, e, f, g, h)| (a, b, c, d, e, f, g, h, Provenance::axiom()))
            .collect();
        prog.aconst = aconst_facts
            .into_iter()
            .map(|(a, b, c, m, n)| (a, b, c, m, n, Provenance::axiom()))
            .collect();

        prog.run();

        // Extract derived results
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
    fn get_points(&self) -> Vec<(i64, i64, String)> {
        self.points.clone()
    }

    fn get_col(&self) -> Vec<(String, String, String, Vec<(String, Vec<String>)>)> {
        self.derived_col
            .iter()
            .map(|(a, b, c, prov)| {
                let derivations = prov
                    .derivations
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
                    .derivations
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
                    .derivations
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
                    .derivations
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
                    .derivations
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
                    .derivations
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
                    .derivations
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
                    .derivations
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
                    .derivations
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
                    .derivations
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
                    .derivations
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
                    .derivations
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
                    .derivations
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
                    .derivations
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
