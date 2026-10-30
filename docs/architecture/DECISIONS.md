# CareGrid-RL: Architecture & Engineering Decisions

**Date**: 2026-10-30  
**Phase**: PR-2 (Safety Layer) & PR-3 (RL Learning Fixes)  
**Status**: Implemented & Verified  

---

## 1. Context & Motivation

In Phase 8, baseline training of `dqn_v1_s0` (1M steps, seed 0) failed to beat rule-based and heuristic baselines:
- **Baseline Targets (Validation 20 streams)**:
  - B1 (Rule-Based): Normal 440.6 / Moderate 3392.9 (`val_score` 1326.3)
  - H1 (Lowest-Tier): Normal 193.1 / Moderate 3096.2 (`val_score` 1064.0)
  - H3 (Combined): Normal 209.0 / Moderate 3121.9 (`val_score` 1082.9)
- **dqn_v1_s0 Result**: Normal 272.1 / Moderate 4902.6 (`val_score` 1661.3) — significantly worse than B1 and H3.
- **Empirical Diagnostics (PR-1)**:
  - Under surge, `best.zip` deferred 33.41% of decisions where feasible beds existed (vs 0.32% for H3).
  - Q-values swung from +39 (quiet) to -129 (surge), while per-decision Q-spread between actions was only 0.55–0.81.
  - Policy degraded over the course of training (first 5 checkpoints mean 1475; last 5 checkpoints mean 2563).

The decisions below document the architectural fixes engineered in PR-2 and PR-3 to address these findings.

---

## 2. PR-2 Decisions: Safety Layer Architecture

### Decision D-PR2-1: Torch-Free Independent Hard Constraint Verification
- **Choice**: Implemented `safety/rules.py` completely independent of `simulator/hospital/allocation_rules.py`, `torch`, and `stable_baselines3`.
- **Reasoning**:
  1. Prevents circular dependencies between the RL agent and the simulator's internal feasibility functions.
  2. Guarantees that the safety package can be imported into lightweight backend services or deployment containers without heavy ML dependencies (PyTorch/SB3).
  3. Formulates constraints H1–H5 directly from clinical documentation and the independent metric auditor (`simulator/metrics/audit.py`).
- **Verified by**: Subprocess test verifying `import safety` never populates `torch` or `stable_baselines3` in `sys.modules`.

### Decision D-PR2-2: Two-Tier Defense (Hard Checks + Soft Guardrails)
- **Choice**: Separated validation into immutable hard feasibility checks (rules H1–H5) and configurable clinical guardrails (G1, G2).
  - **G1 (Critical Patient Deferral Prevention)**: Patients with acuity >= 4 must not be left `WAIT`ing if any feasible bed tier exists.
  - **G2 (Max Waiting Time Threshold)**: Patients who have waited longer than `max_wait_hours[acuity]` must not be left `WAIT`ing if a feasible bed is open.
- **Reasoning**: Hard rules ensure clinical and resource impossibility never occurs (no invalid actions, no illegal tiers, no equipment shortages). Guardrails specifically prevent the RL agent from falling into the catastrophic `WAIT` trap observed in `dqn_v1_s0`.
- **Clinical Assumptions Requiring Mentor Sign-off**:
  - `critical_acuity`: 4
  - `max_wait_hours`: `{5: 2h, 4: 6h, 3: 24h, 2: 72h, 1: 72h}`
  - `fallback`: `"h3"` (lowest-tier-first heuristic fallback)

### Decision D-PR2-3: Fallback Re-Validation
- **Choice**: If a policy proposal is overridden by the safety layer, the proposed fallback action is itself passed through hard constraint validation before execution.
- **Reasoning**: If a fallback heuristic attempts an allocation that has become momentarily unavailable due to equipment or isolation constraints, it must safely degrade to `WAIT` rather than executing an illegal assignment.

---

## 3. PR-3 Decisions: RL Learning Fixes

### Decision D-PR3-1: Double DQN (X1)
- **Choice**: Created `DoubleDQN` (`rl/agents/double_dqn.py`) subclassing SB3 `DQN`, overriding `train()`:
  Action selection in next state is chosen by the online network `q_net`, while action evaluation is computed by the target network `q_net_target`.
  Integrated with `MaskedReplayBuffer` so that action selection in s' masks invalid actions with -inf.
- **Reasoning**: Standard DQN uses the target network to both select the argmax action and evaluate its Q-value.
  In environments with high transition variance (surges, arrival bursts), this creates severe positive maximization bias. Over hundreds of thousands of steps, Q-values inflate and optimistic values extrapolate into invalid/suboptimal regions. Decoupling selection (online net) from evaluation (target net) stabilizes value estimation.

### Decision D-PR3-2: Removal of Arbitrary Selection Burn-In
- **Choice**: Added `burn_in: bool = True` to `DQNConfig` for backward compatibility, but disabled it (`burn_in=False`) for experiment evaluation and selection.
- **Reasoning**: In `dqn_v1_s0`, `ValidationCallback` enforced `min_select_step = exploration_fraction * total_timesteps` (300k steps). Checkpoints at 150k and 250k steps achieved superior validation scores but were artificially barred from selection, forcing the runner to save the degraded 300k checkpoint. Model selection must evaluate actual validation score on held-out streams, without artificial boundary hacks.

### Decision D-PR3-3: Heuristic Replay Buffer Warmup (X5)
- **Choice**: Created `rl/training/warmup.py:fill_replay_buffer_with_heuristic` to pre-fill the replay buffer with up to 50k transitions collected from `combined_heuristic_policy` (H3) before starting gradient updates.
- **Reasoning**: Early uniform exploration in an environment with high queue penalties frequently visits catastrophic states (e.g. invalid allocations incurring -0.1 or queue explosions). The network easily learns the false local optimum that `WAIT` is safer than attempting allocations. Seeding the buffer with H3 transitions ensures the replay distribution contains viable admission examples and feasible state trajectories from step 0.

### Decision D-PR3-4: Observation Space v2 (X6)
- **Choice**: Added `observation_version: int = 1` parameter to `CareGridHospitalEnv` and `DQNConfig`:
  - `observation_version=1`: 14 features (exact original behavior, bit-for-bit preserved).
  - `observation_version=2`: 17 features, adding:
    1. `wait_so_far`: `min(elapsed_days / 7.0, 1.0)` - how long the current patient has already been waiting.
    2. `time_of_day_sin`: `(sin(2*pi*hour/24) + 1) / 2` - cyclical diurnal admission phase.
    3. `time_of_day_cos`: `(cos(2*pi*hour/24) + 1) / 2` - cyclical diurnal admission phase.
  - All features strictly normalized to [0.0, 1.0].
- **Reasoning**: The original 14-feature vector gave the agent no indication of whether a patient was newly arrived or had been repeatedly deferred for 48 hours. By revealing patient wait duration, the agent receives state signal directly aligned with the acuity-weighted queue cost objective.

### Decision D-PR3-5: Variance Dampening via Reward Scale Tuning (X3)
- **Choice**: Parameterized `reward_scale: float = 50.0` (with proportional `invalid_action_penalty = 0.5`).
- **Reasoning**: At `reward_scale=10.0`, total episode returns swing by hundreds of points between normal and moderate surge scenarios, causing macro queue variance to drown out the individual step action signal (mean Q-spread was only 0.55). Increasing scale to 50 reduces the magnitude of TD errors and gradients, stabilizing Bellman convergence.

### Decision D-PR3-6: Unified Experiment Harness (`run_experiments.py`)
- **Choice**: Implemented `rl/training/run_experiments.py` with programmatic execution for `x0_control`, `x1_double_dqn`, `x2a/b_lr`, `x3_reward_scale`, `x4_gamma`, `x5_heuristic_warmup`, `x6_obs_v2`, and `x7_combo`.
- **Reasoning**: Standardizes hyperparameters (300k steps, seed 0, 20 validation streams, evaluation every 25k steps, no burn-in filter) across all experiments so each factor is evaluated under strictly identical conditions. Includes automated CLI comparison reporting against baseline targets (B1, H1, H3).
