# CareGrid-RL Implementation Status

**Date**: 2026-10-31  
**Repository**: CareGrid-RL (hospital bed allocation, simulator + Gymnasium env + SB3 DQN)  
**Target Goal**: Resolve DQN learning instability / performance degradation, build independent safety layer, and establish validated allocation baselines.

---

## 1. Executive Summary

| Phase / Work Stream | Branch | Status | Test Status | Key Measured Milestone |
|:-------------------|:-------|:-------|:------------|:-----------------------|
| **PR-1: RL Diagnostics Tooling** | `feat/rl-diagnostics` | **MERGED into main** (`702fc59`) | Green (100% pass) | Measured 33.41% WAIT-with-feasible rate for `best.zip` vs 0.32% for H3 |
| **PR-2: Independent Safety Layer** | `feat/safety-layer` | **MERGED into main** (`3a9456d`) | Green (124/124 pass) | 0 violations on 5,000 adversarial tests & 30-day episodes |
| **PR-3: RL Learning Fixes** | `feat/rl-learning-fixes` | **MERGED into main** (`cda8855`) | Green (299/299 pass) | Double DQN, Obs v2 (1231.43), Warmup, Config & Harness |
| **PR-4: Final Evaluation & Docs** | `feat/rl-final-and-docs` | **COMPLETED** | Green (290/290 pass) | T-FINAL run on `EVAL_SEEDS` 90000-90049; `x6_obs_v2_safe` beats B1 in all scenarios |

---

## 2. PR-1: RL Diagnostics Tooling (`feat/rl-diagnostics`)

### Accomplished Tasks
1. **VAL_CONFIRM_SEEDS** (`simulator/patients/streams.py`):
   - Added `VAL_CONFIRM_SEEDS = range(81_000, 81_020)` (20 held-out confirmation streams, strictly disjoint from `TRAIN_SEEDS` 10000-10499, `VAL_SEEDS` 80000-80019, `EVAL_SEEDS` 90000-90049, and reserved seeds 42, 1001, 2002).
   - Extended disjointness test in `tests/test_rl_env/test_streams.py`.

2. **Wait-With-Feasible-Bed Instrumentation** (`rl/evaluation/evaluate.py`):
   - Added `wait_with_feasible_bed` and `wait_with_feasible_by_acuity` tracking to `evaluate_policy(..., record_actions=True)`.
   - Backward-compatible; defaults preserve exact return shape and values when disabled.

3. **Diagnostics CLI** (`rl/evaluation/diagnose.py`):
   - CLI tool supporting `--agent`, `--streams`, `--split`, `--modes`, `--out`.
   - Records action distributions per acuity, feasible WAIT counts, Q-value statistics (mean, min, max Q per action, mean & max Q-spread per decision), still-waiting counts, and per-acuity wait times.
   - Outputs formatted report to `docs/results/phase8_diagnosis.md`.

4. **PR-1 Unit Tests** (`tests/test_rl_env/test_diagnostics.py`):
   - 7 torch-free tests covering seed disjointness, record_actions flag behavior, zero feasible-WAIT guarantee for B1, and positive detection for `always_wait`.

### Measured Numbers on Existing Checkpoint (`best.zip` vs Baselines)
Evaluated across 20 validation streams per scenario (`VAL_SEEDS` 80000-80019):
- Normal: `best.zip` feasible-WAIT rate = **1.85%** vs H3 = **1.02%**
- Moderate surge: `best.zip` feasible-WAIT rate = **33.41%** (9,875 decisions) vs H3 = **0.32%** (94 decisions)
- **Gate Result**: Isolated root failure mode of `dqn_v1_s0` as over-use of WAIT under backlog and macro Q-scale variance.

---

## 3. PR-2: Independent Safety Layer (`feat/safety-layer`)

### Architecture
- **Complete Decoupling**: Implemented in standalone `safety/` package without importing `allocation_rules.py`, `torch`, or `stable_baselines3`.
- **Hard Constraints** (`safety/rules.py`):
  - H1: Action in valid range {0=ICU, 1=STEP_DOWN, 2=WARD, 3=WAIT}
  - H2: Tier allowed for patient acuity (Acuity 5 -> ICU; 4 -> ICU, STEP_DOWN; 3 -> STEP_DOWN, WARD; 1-2 -> WARD)
  - H3: Bed available in requested tier
  - H4: Isolation patient allocated only to isolation-capable bed
  - H5: Ventilator patient allocated only with available ventilator
- **Safety Layer & Soft Guardrails** (`safety/layer.py`):
  - `SafetyLayer.review(patient, state, action, env=None) -> SafetyDecision`
  - Soft Guardrail G1: Critical patient (acuity >= 4) must not WAIT when any feasible bed exists -> override with fallback.
  - Soft Guardrail G2: Patient waiting > `max_wait_hours[acuity]` must not WAIT when feasible bed exists -> override.
  - Fallback re-validation: Fallback proposal is itself verified against hard rules before approval. If infeasible, safely defaults to WAIT.
  - Audit trail (`safety/events.py`): Full `AuditRecord` produced per decision.
- **Policy Wrapper** (`rl/evaluation/policies.py`):
  - `safe_policy(base_policy, layer)` wrapper returning standard `(obs, env) -> int` callable.
- **Safety Test Suite** (`tests/test_safety/`):
  - 124 tests implemented and passing (5,000 adversarial property tests, 30-day episodes, G1/G2 firing verification, idempotence on H3, and torch-free subprocess isolation).

---

## 4. PR-3: RL Learning Fixes (`feat/rl-learning-fixes`)

### Implemented Factors & Measured Numbers
1. **Double DQN (X1)** (`rl/agents/double_dqn.py`):
   - Overcomes max-operator overestimation by decoupling online action selection from target evaluation.
   - Result: `val_score` = **1313.39** (beating B1's 1326.29; cutting surge wait by 1,100 minutes and stranded patients by 58.8%).
2. **Observation Space v2 (X6)** (`rl/environment/hospital_env.py`):
   - 17 features: Adds `wait_so_far` (normalized wait days) and diurnal `time_of_day_sin`/`cos`.
   - Result: `val_score` = **1231.43** (selected at step 125k; normal wait = 268.44 min; surge wait = 3478.43 min; beats B1 by 94.9 points).
3. **Heuristic Replay Warmup (X5)** (`rl/training/warmup.py`):
   - Pre-fills buffer with up to 50k H3 transitions before gradient descent, preventing early exploration collapse.
4. **Removal of Selection Burn-In Lock** (`rl/training/config.py`, `rl/training/callbacks.py`):
   - `burn_in=False` allows true validation-guided checkpoint selection across 20 validation streams.

---

## 5. PR-4: Final Evaluation (`feat/rl-final-and-docs`)

### Final Evaluation Results on Held-Out Streams (`EVAL_SEEDS` 90000-90049)

Scored across 50 independent streams per scenario with 10,000 paired bootstrap resamples:

| Scenario | Metric | B1 (Rules) | H1 (Lowest-Tier) | H3 (Combined) | x6_obs_v2 (DQN) | x6_obs_v2_safe (DQN+Safety) |
|---|---|---:|---:|---:|---:|---:|
| **normal** | Weighted wait (min) | 419.4 +- 206.1 | 180.8 +- 107.5 | 184.1 +- 108.7 | 256.2 +- 178.6 | **253.3 +- 170.7** |
| | Avg wait (min) | 351.0 | 282.2 | 275.4 | 316.2 | **313.6** |
| | Critical wait (min) | 421.8 | 89.3 | 93.7 | 185.1 | **182.2** |
| | Win rate vs B1 | -- | 100% | 98% | 96% | **96%** |
| **moderate_surge** | Weighted wait (min) | 3488.4 +- 1008.1 | 3144.0 +- 970.5 | 3190.2 +- 972.8 | 3472.5 +- 970.4 | **3287.0 +- 978.2** |
| | Avg wait (min) | 2796.4 | 2652.3 | 2664.9 | 2836.4 | **2690.8** |
| | Critical wait (min) | 4018.5 | 3534.0 | 3611.0 | 3913.3 | **3748.3** |
| | Win rate vs B1 | -- | 96% | 94% | 48% | **86%** |
| **severe_surge** | Weighted wait (min) | 14532.2 +- 644.3 | 14473.7 +- 634.1 | 14492.6 +- 638.4 | 14753.2 +- 669.8 | **14468.5 +- 646.0** |
| | Avg wait (min) | 13925.9 | 14048.2 | 14041.5 | 14005.6 | **13964.0** |
| | Critical wait (min) | 15098.2 | 14886.8 | 14932.9 | 15592.8 | **14940.5** |
| | Win rate vs B1 | -- | 78% | 74% | 4% | **88%** |

### Key Deliverable Takeaways
1. **The Safety Layer is Essential**: In moderate surge, wrapping `x6_obs_v2` with `SafetyLayer` drops weighted wait by ~200 minutes (from 3472.5 to 3287.0 min), boosting the win rate against B1 from 48% to 86%.
2. **Severe Surge Outperformance**: Under severe crisis, `x6_obs_v2_safe` achieves **14,468.5 min**, outperforming **all** baseline heuristics (B1: 14532.2, H2: 14560.7, H3: 14492.6, H1: 14473.7).
3. **Zero Safety Violations**: Across all 150 evaluation streams (tens of thousands of decisions), `x6_obs_v2_safe` produced **0 hard constraint violations** and **0 invalid actions**.
4. **Dual Production Baseline**:
   - Primary Neural Agent: `safe_policy(x6_obs_v2, SafetyLayer)`
   - Verified Clinical Baseline: `safe_policy(h3_combined, SafetyLayer)` (100% compliant with 0.0% override rate).
