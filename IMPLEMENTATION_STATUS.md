# CareGrid-RL Implementation Status

**Date**: 2026-10-30  
**Repository**: CareGrid-RL (hospital bed allocation, simulator + Gymnasium env + SB3 DQN)  
**Target Goal**: Resolve DQN learning instability / performance degradation, build independent safety layer, and establish validated allocation baselines.

---

## 1. Executive Summary

| Phase / Work Stream | Branch | Status | Test Status | Key Measured Milestone |
|:-------------------|:-------|:-------|:------------|:-----------------------|
| **PR-1: RL Diagnostics Tooling** | `feat/rl-diagnostics` | **COMPLETED** | Green (100% pass) | Measured 33.41% WAIT-with-feasible rate for `best.zip` vs 0.32% for H3 |
| **PR-2: Independent Safety Layer** | `feat/safety-layer` | **IMPLEMENTED** (ready to commit) | Green (124/124 pass) | 0 violations on 5,000 adversarial tests & 30-day episodes |
| **PR-3: RL Learning Fixes** | `feat/rl-learning-fixes` | **PLANNED** | Ready to execute | Systematic X1-X7 experiments: Double DQN, LR, scale, demos, obs v2 |
| **PR-4: Final Evaluation & Docs** | `feat/rl-final-and-docs` | **PLANNED** | Pending PR-3 | T-FINAL run with `--final`, curated comparison results, doc updates |

---

## 2. PR-1: RL Diagnostics Tooling (`feat/rl-diagnostics`)

### Accomplished Tasks
1. **VAL_CONFIRM_SEEDS** (`simulator/patients/streams.py`):
   - Added `VAL_CONFIRM_SEEDS = range(81_000, 81_020)` (20 held-out confirmation streams, strictly disjoint from `TRAIN_SEEDS` 10000–10499, `VAL_SEEDS` 80000–80019, `EVAL_SEEDS` 90000–90049, and reserved seeds 42, 1001, 2002).
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

Evaluated across 20 validation streams per scenario (`VAL_SEEDS` 80000–80019):

| Scenario | Metric | B1 (Strict Rules) | H1 (Lowest Tier) | H3 (Combined) | DQN Agent (`best.zip`) |
|:---|:---|---:|---:|---:|---:|
| **Normal** | Acuity-weighted wait (min) | 440.6 ± 197.6 | 193.1 ± 101.7 | 209.0 ± 121.3 | **272.1 ± 143.8** |
| | Avg wait incl. unadmitted (min) | 404.9 | 323.3 | 338.4 | **336.9** |
| | Still waiting at end | 0.2 | 0.5 | 0.6 | **0.5** |
| | ICU utilization | 88.10% | 57.69% | 57.73% | **78.66%** |
| | **WAIT-with-feasible rate** | **0.0000** | **0.0000** | **0.0102** | **0.0185** |
| **Moderate Surge** | Acuity-weighted wait (min) | 3392.9 ± 987.7 | 3096.2 ± 981.3 | 3121.9 ± 987.1 | **4902.6 ± 1281.6** |
| | Avg wait incl. unadmitted (min) | 2746.7 | 2623.6 | 2630.6 | **4557.2** |
| | **Still waiting at end** | **16.1** | **15.4** | **16.1** | **67.7** |
| | ICU utilization | 95.18% | 88.39% | 88.32% | **86.19%** |
| | **WAIT-with-feasible rate** | **0.0000** | **0.0000** | **0.0032** | **0.3341 (33.4%)** |

### Acceptance Gate Verification
- **PR-1 Gate**: Report WAIT-with-feasible-bed rate of `best.zip` vs H3.
  - Normal: `best.zip` = **1.85%** vs H3 = **1.02%**
  - Moderate surge: `best.zip` = **33.41%** (9,875 decisions) vs H3 = **0.32%** (94 decisions)
  - **GATE PASSED**: Diagnostic tool successfully isolates the root failure mode of `dqn_v1_s0`.

### Hypothesis Findings
- **(H-e) WAIT over-use**: **STRONGLY SUPPORTED**. Under surge, the agent needlessly defers 1 in 3 feasible admissions, causing 4x backlog.
- **(H-b) Q-scale mismatch & weak credit assignment**: **STRONGLY SUPPORTED**. Q-values swing from +39 (quiet) to -129 (surge), while per-decision Q-spread between best and worst actions is only 0.55. Macro queue state overwhelms single-step action signal.
- **(H-a) Max-operator instability**: **SUPPORTED**. Policy degrades after 250k steps.
- **(H-c) Lack of observation of wait-so-far**: **SUPPORTED**. High-acuity patients suffer thousands of feasible waits.
- **(H-d) Noisy selection**: **SUPPORTED**. 10-stream training validation missed better 150k/250k checkpoints.

---

## 3. PR-2: Independent Safety Layer (`feat/safety-layer`)

### Architecture
- **Complete decoupling**: Implemented in standalone `safety/` package without importing `allocation_rules.py`, `torch`, or `stable_baselines3`.
- **Hard Constraints** (`safety/rules.py`):
  - H1: Action in valid range {0=ICU, 1=STEP_DOWN, 2=WARD, 3=WAIT}
  - H2: Tier allowed for patient acuity (Acuity 5 -> ICU; 4 -> ICU, STEP_DOWN; 3 -> STEP_DOWN, WARD; 1-2 -> WARD)
  - H3: Bed available in requested tier
  - H4: Isolation patient allocated only to isolation-capable bed
  - H5: Ventilator patient allocated only with available ventilator
- **Safety Layer & Soft Guardrails** (`safety/layer.py`):
  - `SafetyLayer.review(patient, state, action, env=None) -> SafetyDecision`
  - Soft Guardrail G1: Critical patient (acuity ≥ 4) must not WAIT when any feasible bed exists -> override with fallback.
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

## 4. Current Test Suite Status

| Test Module | Test Count | Status | Execution Time |
|:---|:---:|:---:|---:|
| `tests/test_simulator/` | 23 | PASS | 4.0s |
| `tests/test_ml_los/` | 12 | PASS | 10.5s |
| `tests/test_rl_env/` | 105 | PASS | 8.8s |
| `tests/test_safety/` | 124 | PASS | 8.6s |
| `tests/test_rl_training/` | 18 | PASS | 79.0s |
| `tests/test_backend/` | 9 | PASS | 20.3s |
| **Total** | **291** | **ALL GREEN** | **~2m 10s** |

---

## 5. Next Steps Plan

### Immediate Step 1: Commit PR-1 (`feat/rl-diagnostics`)
- Stage PR-1 files:
  - `simulator/patients/streams.py`
  - `tests/test_rl_env/test_streams.py`
  - `rl/evaluation/evaluate.py`
  - `rl/evaluation/diagnose.py`
  - `tests/test_rl_env/test_diagnostics.py`
  - `docs/results/phase8_diagnosis.md`
- Run local commit on `feat/rl-diagnostics`.

### Immediate Step 2: Branch and Commit PR-2 (`feat/safety-layer`)
- Branch `feat/safety-layer` from `feat/rl-diagnostics`.
- Stage PR-2 files:
  - `safety/__init__.py`
  - `safety/rules.py`
  - `safety/layer.py`
  - `safety/events.py`
  - `safety/README.md`
  - `rl/evaluation/policies.py` (safe_policy)
  - `tests/test_safety/test_safety_layer.py`
  - `tests/test_safety/__init__.py`
- Run test gate: `python -m pytest tests/test_safety -q`.
- Commit on `feat/safety-layer`.

### Step 3: Branch and Implement PR-3 (`feat/rl-learning-fixes`)
Branch `feat/rl-learning-fixes` from `feat/safety-layer`. Run 300k steps, seed 0 sequentially with 20-stream validation (no burn-in exclusion):
1. **X1 Double DQN**: Subclass SB3 DQN in `rl/agents/double_dqn.py` (online argmax, target eval).
2. **X2 Learning Rate**: Test 1e-4 and 1e-3.
3. **X3 Reward Scale**: Test reward_scale=50 (shrinks Q variance ~5x).
4. **X4 Gamma**: Test gamma=0.99 (reduces infinite-horizon accumulation).
5. **X5 Heuristic-Seeded Replay**: 50k transitions of H3 pre-populated into replay buffer.
6. **X6 Observation v2** (`observation_version=2`): Add wait-so-far (days/7 capped) + time-of-day sin/cos (17 features total).
7. **X7 Combination**: Top winners combined.
8. **Selection Gate**: Promote only configs beating control by >10% to 3-seed 1M validation. If none reach gate, document negative result and establish H3 + Safety Layer as deliverable.

### Step 4: PR-4 (`feat/rl-final-and-docs`)
1. Wrap best model with SafetyLayer and evaluate.
2. Single execution of T-FINAL on `EVAL_SEEDS` with `--final` guard.
3. Update `rl/README.md`, `safety/README.md`, and top-level `README.md` status checklist.
