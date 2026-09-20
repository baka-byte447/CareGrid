# CareGrid-RL: Rule-Based Allocation Baseline 

Deterministic bed allocation logic used before any RL model exists.
Implemented in `simulator/hospital/allocation_rules.py::decide_bed()`.

## 1. Hard constraints (checked before acuity)

A patient is **not admitted** — regardless of acuity — unless both hold:

| Requirement | Rule |
|---|---|
| Isolation required | Candidate bed must have `isolation_capable = YES` |
| Ventilator required | At least one `VENTILATOR` equipment record must be `AVAILABLE`, and it is reserved (`IN_USE`) at the moment of admission |

If a hard constraint fails, the patient stays `WAITING` even if a plain bed is free — the bed is never "wasted" on a patient it can't actually support.

## 2. Acuity → ward tier, with escalation

| Acuity | Preferred tier | Falls back to |
|---|---|---|
| 5 (Critical) | ICU | — (no fallback) |
| 4 | ICU | STEP_DOWN |
| 3 | STEP_DOWN | WARD |
| 1–2 | WARD | — (no fallback) |

## 3. Tie-break among equally valid beds

Lowest `bed_id` wins. Deterministic and auditable — given the same hospital state and patient, the decision is always reproducible.

## 4. Re-queueing

Patients who can't be admitted on arrival join `waiting_queue` (FIFO by arrival time). Every time a bed finishes cleaning (`BED_RELEASE`), the engine retries the *entire* waiting queue, oldest-first, looping until a full pass makes no further admissions.

## 5. Known capacity constraint (Phase 4 finding)

The synthetic bed roster allocates isolation-capable beds mostly to ICU (4 per ward) and STEP_DOWN (3 per ward), but only **2 isolation-capable WARD beds** exist in the entire 50-bed WARD tier (`Medical-North` only; `Medical-South`, `Surgical-East`, `Surgical-West` have none). Because acuity 1–2 patients never escalate above WARD, isolation-required low-acuity patients can queue for a very long time under this rule set whenever those 2 beds are occupied — even while ICU/STEP_DOWN isolation beds sit free. This is the rules behaving correctly, not a bug: it's a genuine capacity bottleneck the baseline exposes, and a concrete example for "why not just use rules?" — a smarter policy (or a rule update allowing controlled escalation) could route around it.

## 6. Viva-ready answers

- **"Why not just use rules?"** → point at §5: rigid tier boundaries create an isolation-bed bottleneck a rules engine won't route around on its own, even when capacity technically exists elsewhere.
- **"How do you guarantee safety?"** → hard constraints (§1) are checked unconditionally before any placement decision, independent of acuity logic.
- **"Is the outcome reproducible?"** → yes — no randomness in `decide_bed()`; the tie-break (§3) is deterministic.
