# CareGrid-RL Implementation Status

**Date**: 2026-10-30  
**Repository**: CareGrid-RL (hospital bed allocation, simulator + Gymnasium env + SB3 DQN)  
**Target Goal**: Resolve DQN learning instability / performance degradation, build independent safety layer, and establish validated allocation baselines.

---

## 1. Executive Summary

| Phase / Work Stream | Branch | Status | Test Status | Key Measured Milestone |
|:-------------------|:-------|:-------|:------------|:-----------------------|
| **PR-1: RL Diagnostics Tooling** | `feat/rl-diagnostics` | **COMMITTED** (`7c1bf08`) | Green (100% pass) | Measured 33.41% WAIT-with-feasible rate for `best.zip` vs 0.32% for H3 |
| **PR-2: Independent Safety Layer** | `feat/safety-layer` | **COMMITTED** (`687c9c6`) | Green (124/124 pass) | 0 violations on 5,000 adversarial tests & 30-day episodes |
| **PR-3: RL Learning Fixes** | `feat/rl-learning-fixes` | **IMPLEMENTED** | Green (299/299 pass) | Implemented Double DQN, Obs v2, Heuristic Warmup, Config & Harness |
| **PR-4: Final Evaluation & Docs** | `feat/rl-final-and-docs` | **PLANNED** | Pending PR-3 runs | T-FINAL run with `--final`, curated comparison results, doc updates |

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
   - Automatically outputs formatted report to `docs/results/phase8_diagnosis.md`.

4. **PR-1 Unit Tests** (`tests/test_rl_env/test_diagnostics.py`):
   - 7 torch-free tests covering seed disjointness, record_actions flag behavior, zero feasible-WAIT guarantee for B1, and positive detection for `always_wait`.

### Measured Numbers on Existing Checkpoint (`best.zip` vs Baselines)

Evaluated across 20 validation streams per scenario (`VAL_SEEDS` 80000-80019):

| Scenario | Metric | B1 (Strict Rules) | H1 (Lowest Tier) | H3 (Combined) | DQN Agent (`best.zip`) |
|:---|:---|---:|---:|---:|---:|
| **Normal** | Acuity-weighted wait (min) | 440.6 +- 197.6 | 193.1 +- 101.7 | 209.0 +- 121.3 | **272.1 +- 143.8** |
| | Avg wait incl. unadmitted (min) | 404.9 | 323.3 | 338.4 | **336.9** |
| | Still waiting at end | 0.2 | 0.5 | 0.6 | **0.5** |
| | ICU utilization | 88.10% | 57.69% | 57.73% | **78.66%** |
| | **WAIT-with-feasible rate** | **0.0000** | **0.0000** | **0.0102** | **0.0185** |
| **Moderate Surge** | Acuity-weighted wait (min) | 3392.9 +- 987.7 | 3096.2 +- 981.3 | 3121.9 +- 987.1 | **4902.6 +- 1281.6** |
| | Avg wait incl. unadmitted (min) | 2746.7 | 2623.6 | 2630.6 | **4557.2** |
| | **Still waiting at end** | **16.1** | **15.4** | **16.1** | **67.7** |
| | ICU utilization | 95.18% | 88.39% | 88.32% | **86.19%** |
| | **WAIT-with-feasible rate** | **0.0000** | **0.0000** | **0.0032** | **0.3341 (33.4%)** |

### Acceptance Gate Verification
- **PR-1 Gate**: Report WAIT-with-feasible-bed rate of `best.zip` vs H3.
  - Normal: `best.zip` = **1.85%** vs H3 = **1.02%**
  - Moderate surge: `best.zip` = **33.41%** (9,875 decisions) vs H3 = **0.32%** (94 decisions)
  - **GATE PASSED**: Diagnostic tool successfully isolates the root failure mode of `dqn_v1_s0`.

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

### Safety Test Suite (`tests/test_safety/`)
- **124 tests implemented and passing**:
  1. *Property test*: 5,000 random adversarial proposals across randomized hospital states -> **0 hard violations**.
  2. *Full 30-day episodes*: Random and always-ICU policies wrapped by safety layer -> **0 audit violations, 0 invalid actions**.
  3. *Guardrails G1/G2*: Verified firing under backlog and staying dormant when no feasible tier exists.
  4. *Fallback re-validation*: Verified fallback degradation to WAIT when constraints bind.
  5. *Idempotence on H3*: Measured **override_rate = 0.0%** when base policy is H3.
  6. *Subprocess isolation*: Verified `import safety` does NOT import torch or SB3.

---

## 4. PR-3: RL Learning Fixes (`feat/rl-learning-fixes`)

### Implemented Enhancements
1. **Double DQN (X1)** (`rl/agents/double_dqn.py`):
   - Subclasses SB3 `DQN`, decouples online network action selection from target network evaluation.
   - Fully compatible with `MaskedReplayBuffer` for valid-action masking.
2. **Observation Space v2 (X6)** (`rl/environment/hospital_env.py`):
   - Added `observation_version: int = 1` parameter.
   - `observation_version=1`: Standard 14 features (exact original behavior preserved).
   - `observation_version=2`: 17 features, adding `wait_so_far` (normalized wait days capped at 7) and `time_of_day_sin` / `time_of_day_cos` (cyclical time of day). All normalized to [0.0, 1.0].
3. **Heuristic Replay Warmup (X5)** (`rl/training/warmup.py`):
   - `fill_replay_buffer_with_heuristic`: Pre-fills the replay buffer with up to 50k transitions using clinical heuristic H3 before gradient descent begins.
4. **Config Extensions & Selection Bias Removal** (`rl/training/config.py`, `rl/training/callbacks.py`):
   - Added `algorithm`, `observation_version`, `heuristic_warmup_steps`, and `burn_in` fields to `DQNConfig`.
   - When `burn_in=False`, any checkpoint during the run can be selected based purely on 20-stream validation performance.
5. **Experiment Runner Harness** (`rl/training/run_experiments.py`):
   - Standardized harness for X0-X7:
     - `x0_control`: Masked DQN baseline (300k, 20 val streams, no burn-in)
     - `x1_double_dqn`: Double DQN
     - `x2a_lr_low`: Learning rate 1e-4
     - `x2b_lr_high`: Learning rate 1e-3
     - `x3_reward_scale`: Reward scale 50.0 (penalty 0.5)
     - `x4_gamma`: Gamma 0.99
     - `x5_heuristic_warmup`: 50k H3 transitions pre-filled
     - `x6_obs_v2`: Observation version 2 (17 features)
     - `x7_combo`: Combined winners
   - Provides summary comparison table against B1, H1, H3 targets.

### PR-3 Tests Implemented
- `tests/test_rl_training/test_double_dqn.py`: 2 tests verifying Double DQN target calculation and tiny training loop.
- `tests/test_rl_env/test_observation_v2.py`: 4 torch-free tests verifying shapes, feature normalization, step behavior, and version validation.
- `tests/test_rl_training/test_warmup.py`: Verifies buffer pre-population with H3 transitions.
- `tests/test_rl_training/test_training_pipeline.py`: Added config serialization tests and end-to-end smoke test with Double DQN, Obs v2, and warmup.

---

## 5. Current Test Suite Status

| Test Module | Test Count | Status | Notes |
|:---|:---:|:---:|:---|
| `tests/test_simulator/` | 23 | **PASS** | Simulator engine, allocation rules, metrics |
| `tests/test_ml_los/` | 12 | **PASS** | LOS predictor, synthetic pipeline |
| `tests/test_rl_env/` | 109 | **PASS** | Includes 4 new Observation v2 tests |
| `tests/test_safety/` | 124 | **PASS** | Independent safety layer, hard rules, guardrails |
| `tests/test_rl_training/` | 22 | **PASS** | Includes Double DQN, Warmup, Pipeline tests |
| `tests/test_backend/` | 9 | **PASS** | Integration tests (requires sandboxed bypass) |
| **Total** | **299** | **ALL GREEN** | Zero regressions |
