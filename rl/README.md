# RL environment and evaluation (Phase 7 / 7b)

`CareGridHospitalEnv` (`rl/environment/hospital_env.py`) wraps the discrete-event
simulator as a Gymnasium environment. One step = one decision about one waiting
patient.

## Action space: `Discrete(4)`
`0` ICU, `1` STEP_DOWN, `2` WARD, `3` WAIT. Actions that break a hard rule (wrong tier
for the acuity, no isolation bed, no ventilator, bed not free) are rejected safely:
nothing changes, the agent is penalised and `info["invalid_reason"]` says why.

## Observation: 14 floats in [0, 1] (`OBSERVATION_FEATURES`)
| # | Feature | # | Feature |
|---|---|---|---|
| 0 | acuity / 5 | 7 | ward beds available (ratio) |
| 1 | age 65+ | 8 | ventilators available (ratio) |
| 2 | isolation required | 9 | waiting queue size |
| 3 | ventilator required | 10 | ICU isolation beds available (ratio) |
| 4 | **LOS estimate** / 10 | 11 | step-down isolation beds available (ratio) |
| 5 | ICU beds available (ratio) | 12 | ward isolation beds available (ratio) |
| 6 | step-down beds available (ratio) | 13 | critical (acuity 4-5) share of the queue |

The LOS value comes from `ml/los` (computed once per episode, in one batch). The
patient's *true* stay (`predicted_los` in the CSV) is never observable.

## Reward
`+1` per admission, minus `0.05 x days waited` (capped at 10 days) at admission, minus
`0.05` per WAIT, minus `1.0` per invalid action. **Known limitation:** the wait term is
tiny next to the admission bonus (a 5-hour wait costs ~0.01), so the reward mostly says
"admit them" and hardly distinguishes fast from slow. Reshape it (acuity-weighted wait
cost) before relying on it for DQN.

## Patient streams and seeds
By default every episode replays `data/synthetic/patients.csv` (fine for debugging, but an
agent can memorise it). For training pass a stream source:

```python
from simulator.patients.streams import StreamSampler, TRAIN_SEEDS, EVAL_SEEDS
env = CareGridHospitalEnv(patient_source=StreamSampler(TRAIN_SEEDS, days=30, mode="normal"))
```

| Seeds | Used for |
|---|---|
| 42 | `patients.csv` (demo dataset) |
| 1001 / 2002 | LOS model train / test |
| `TRAIN_SEEDS` 10000-10499 | RL training episodes |
| `EVAL_SEEDS` 90000-90049 | held-out evaluation, never used for training or tuning |

`StreamSampler` refuses the reserved seeds; tests enforce that the ranges never overlap.

## Evaluate any policy
A policy is `policy(observation, env) -> action`. Baselines (`rl/evaluation/policies.py`)
read the simulator state; a trained model is wrapped with `model_policy(model)`.

```bash
python -m rl.evaluation.evaluate --policy rule_based --mode normal --streams 10 --days 30
python -m rl.evaluation.evaluate --policy random --mode severe_surge --save
```
```python
from rl.evaluation.evaluate import evaluate_on_streams
from rl.evaluation.policies import model_policy
evaluate_on_streams(model_policy(model), seeds=EVAL_SEEDS[:10], mode="normal", name="dqn_v1")
```
Every policy is scored by the same code (`MetricsCollector` + `compute_metrics`).
Patients never admitted count as waiting until the common horizon end
(`avg_wait_incl_unadmitted_min`), so a policy cannot look good by leaving them in the queue.
Driving the rule policy through the env reproduces `SimulationEngine.run()` exactly
(`tests/test_rl_env/test_evaluation.py`).

## Baseline reference (rule-based B1, 10 held-out streams x 30 days)
| Scenario | Avg wait incl. unadmitted | P90 | ICU util | Still waiting at end |
|---|---|---|---|---|
| normal | 367 min (std 124) | 1,176 min | 0.87 | 0.4 |
| moderate_surge | 2,971 min | 7,713 min | 0.95 | 17.5 |
| severe_surge | 14,011 min | 23,410 min | 0.97 | 561 |

Streams differ a lot (std 124 on a mean of 367), so compare policies on the **same**
streams and use at least 10.

## Phase 8 / PR-3 & PR-4 Final Evaluation Results (Held-Out EVAL_SEEDS 90000-90049)

Across 50 held-out evaluation streams per scenario (generated once, evaluated identically across policies):

| Scenario | Metric | B1 (Rules) | H1 (Lowest-Tier) | H3 (Combined) | x6_obs_v2 (DQN) | x6_obs_v2_safe (DQN+Safety) |
|---|---|---:|---:|---:|---:|---:|
| **normal** | Weighted wait (min) | 419.4 ± 206.1 | 180.8 ± 107.5 | 184.1 ± 108.7 | 256.2 ± 178.6 | **253.3 ± 170.7** |
| | Avg wait (min) | 351.0 | 282.2 | 275.4 | 316.2 | **313.6** |
| | Critical wait (min) | 421.8 | 89.3 | 93.7 | 185.1 | **182.2** |
| | Win rate vs B1 | -- | 100% | 98% | 96% | **96%** |
| **moderate_surge** | Weighted wait (min) | 3488.4 ± 1008.1 | 3144.0 ± 970.5 | 3190.2 ± 972.8 | 3472.5 ± 970.4 | **3287.0 ± 978.2** |
| | Avg wait (min) | 2796.4 | 2652.3 | 2664.9 | 2836.4 | **2690.8** |
| | Critical wait (min) | 4018.5 | 3534.0 | 3611.0 | 3913.3 | **3748.3** |
| | Win rate vs B1 | -- | 96% | 94% | 48% | **86%** |
| **severe_surge** | Weighted wait (min) | 14532.2 ± 644.3 | 14473.7 ± 634.1 | 14492.6 ± 638.4 | 14753.2 ± 669.8 | **14468.5 ± 646.0** |
| | Avg wait (min) | 13925.9 | 14048.2 | 14041.5 | 14005.6 | **13964.0** |
| | Critical wait (min) | 15098.2 | 14886.8 | 14932.9 | 15592.8 | **14940.5** |
| | Win rate vs B1 | -- | 78% | 74% | 4% | **88%** |

Full report: docs/results/phase8_final_evaluation.md  
Curated metrics: experiments/results/curated/phase8_final_evaluation.json
