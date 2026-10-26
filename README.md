# Alpha Geometry DDAR with Ascent

This repository contains an implementation of Alpha Geometry, a system for developing proofs in geometry using a deductive database, algebraic reasoning, and a LLM in order to prove geometric theorems.

This implementation uses [Ascent](https://github.com/s-arash/ascent/tree/master), a logic programming language (similar to Datalog) embedded in Rust, for the deductive database component.

## Quick Links:

- [Example Problem](#example-problem)
- [Getting Started](#getting-started)
- [Deductive Database](#deductive-database-(dd))
    - [Basic Rule Example](#basic-rule-example)
    - [Generating from Point Existence](#generating-from-point-existence)
    - [Complex Rule Example](#complex-rule-example)
    - [Double Points](#double-points)
- [Algebraic Reasoning](#algebraic-reasoning-(ar))
- [LLM Rabbit Generation](#llm-rabbit-generation)
    - [Straight prompt](#straight-prompt)
    - [As an MCP server](#as-an-mcp-server)

## Example Problem

```bash
❯ python solve.py problems/contri_sas
Initial Predicates:
  cong C A I G
  eqangle C A B F D E
  cong A B G H
  cong C A F D
  eqangle C A B H G I
  cong A B D E

Goals:
  contri2 A B C G H I
  contri1 A B C D E F

=== Iteration 1 ===
Predicates known: 6 / Goals Known: 0 / Goals: 2
Missing Goals:  contri2 A B C G H I contri1 A B C D E F
Found: contri1 D E F A B C via sas_cong
Found: contri2 A B C G H I via sas_cong
Added 2020 new predicates

============================================================
[1] cong C A I G                | axiom
[2] eqangle C A B F D E         | axiom
[3] cong A B G H                | axiom
[4] cong C A F D                | axiom
[5] eqangle C A B H G I         | axiom
[6] cong A B D E                | axiom
[7] eqangle B A C E D F         | sym [2]
[8] eqangle B A C I G H         | sym [5]
[9] contri1 A C B D F E         | sas_cong [2],[4],[6]
[10] contri2 G H I A B C        | sas_cong [3],[5],[1]
[11] contri1 D E F A B C        | sas_cong [7],[4],[6]
[12] contri2 A B C G H I        | sas_cong [3],[1],[8]
Solved!
```

## Getting Started

This repo uses [`uv`](https://docs.astral.sh/uv/getting-started/installation/) to manage the environment. You'll also need a [Rust toolchain](https://rust-lang.org/tools/install/) to build the Ascent extension. After cloning the repo and installing `uv` and `rust`, run the following to get set up.

```bash
uv sync
source .venv/bin/activate
uv run --with maturin maturin develop
```

You can then run `python solve.py problems/contri_sas` to solve the example problem above.

To try all the problems that only require DDAR (no rabbits) run:

```bash
find problems -mindepth 1 -maxdepth 1 -type d ! -name 'rabbit*' | sort | xargs -n1 -I{} bash -c 'echo -e "\n\n==> {}" && uv run python solve.py "{}"'
```

To run all the problems in this repository run:

```bash
find problems -mindepth 1 -maxdepth 1 -type d | sort | xargs -n1 -I{} bash -c 'echo -e "\n\n==> {}" && uv run python solve.py --rabbit agent --agent-provider YOUR_AGENT_PROVIDER "{}"'
```
> Note that this requires an LLM agent provider to be set up. See the [LLM Rabbit Generation](#llm-rabbit-generation) section for more details.

## Deductive Database (DD)

Each geometric fact (`col`, `para`, etc.) is represented as a relation in Ascent, containing the fact and provenance lattice i.e. how it was derived. 

The provenance uses Ascent's `Set<Derivation>` lattice to store all derivations for a fact:

- `axiom()` → a starting fact
- `proof()` → a fact derived from other facts and a rule

Lattices allow combining multiple derivations so that we can keep track of all the ways a fact was derived. We only search for the actual derivation used in the proof when we trace the proof in `problem.py`.

### Basic Rule Example

Here's the symmetry rule for collinearity. `col(c, b, a)` is derived from `col(a, b, c)` using the symmetry property which is recorded in the provenance `proof("sym", vec![fact_id("col", [a, b, c])])`. We only need to keep track of 1 step at a time, so we don't care how `col(a, b, c)` was derived, so we have the notation `?_prov` to ignore its provenance.

```rust
col(c, b, a, proof("sym", vec![fact_id("col", [a, b, c])]))
    <-- col(a, b, c, ?_prov);
```

### Generating from Point Existence

Distinct points give a nonzero segment, so congruence with itself has no provenance other than the rule name.

```rust
cong(a, b, a, b, proof("rfl", vec![])) <--
    distinct(a, b);
```

### Complex Rule Example

Here's the rule for ASA congruence. `contri1` requires triangles `ABC` and `DEF` to have the same orientation (both clockwise or both counterclockwise). The `same_orientation!` macro checks this using the diagram's coordinates.

```rust
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
```

### Double Points

Two names can refer to the same geometric point. DDAR can prove `eqpoint X Y` from intersection uniqueness or equal division ratios, then substitute either name into known facts. Equal coordinates alone don't prove equality i.e. we don't naively rely on the diagram. Run `uv run python solve.py problems/double_points` for an example.

## Algebraic Reasoning (AR)

The AR component uses Gaussian elimination to check whether angle or distance facts follow algebraically from known facts.

Angles and log-distances are represented as linear combinations over a set of free variables (one per line direction or segment length). Known facts are fed in as constraints via `force_zero` / `force_one`; a candidate relation is checked by simplifying its linear combination and testing whether it reduces to zero / one in linear / log space.

This implementation uses a mostly unchanged [elimination.py](https://github.com/google-deepmind/alphageometry2/blob/main/elimination.py) from [AlphaGeometry 2](https://www.jmlr.org/papers/v26/25-1654.html).
See that file for the original copyright notice (Google LLC, Apache 2.0).

The file `ar.py` in this repo bridges the predicate's algebraic representations to the `ElimAngle` and `ElimDistMul` in `elimination.py`. Note that the AR component using the elimination module can't give a complete proof trace.

## LLM Rabbit Generation

### Straight prompt

Install and sign in to a CLI agent (`codex`, `claude`, `antigravity`, or `copilot`), then select it with `--agent-provider`. When DDAR stalls, the solver asks the agent for constructions and checks each suggestion with DDAR.

Example: solve Ceva's theorem with [Antigravity](https://antigravity.google/download#antigravity-cli):

```bash
uv run python solve.py problems/rabbit_ceva --rabbit agent --agent-provider antigravity
```

To run all the `rabbit*` examples:

```bash
find problems -mindepth 1 -maxdepth 1 -type d -name 'rabbit*' | sort | xargs -n1 -I{} bash -c 'echo -e "\n\n==> {}" && uv run python solve.py --rabbit agent --agent-provider YOUR_AGENT_PROVIDER "{}"'
```

There are multiple parameters that you can use:

- `--agent-model`: model name passed to the selected CLI
- `--agent-timeout`: seconds per CLI call
- `--agent-attempts`: total construction trials
- `--agent-batch-size`: constructions requested per CLI call
- `--agent-beam-width`: branches retained per search depth (default: 1).
- `--agent-log`: JSONL event log path; defaults to a new file in `LM/logs`.

In terms of the free tier agent providers (Copilot, Antigravity), Antigravity tended to have better results.

### As an MCP server

With MCP, the agent controls the search by calling tools to inspect facts, try constructions on separate branches, and retrieve proofs. For example, to register the server with Antigravity, run from the repository root:

```bash
uv sync --extra mcp
agy mcp add alphageometry -- uv --directory "$PWD" run --extra mcp python -m LM.mcp_server
```

Start a new agent session and ask:

> Use the alphageometry MCP tools to load the built-in ceva problem. Inspect
> its known predicates and available constructions. Try auxiliary constructions
> until DDAR proves the goal, then show me the proof. Keep the original diagram
> available while exploring alternative branches.

See [LM/MCP.md](LM/MCP.md) for more details
