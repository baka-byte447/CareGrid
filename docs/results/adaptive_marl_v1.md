# Adaptive surge and resource policy evaluation

Keep the current serving weights. In moderate surge the candidate increased acuity-weighted waiting time by 102.6 minutes and critical-patient waiting time by 346.6 minutes. In severe surge it reduced weighted wait by 53.1 minutes, while critical patients waited 288.2 minutes longer.

## Held-out results

Values are minutes per patient. Differences subtract serving from candidate, so a negative difference indicates a shorter wait. Critical patients had acuity 4 or 5 at admission, or their waiting acuity when still queued. Intervals are per-scenario paired bootstrap estimates over 50 streams.

| Scenario | Serving weighted wait | Candidate weighted wait | Difference (95% CI) | Critical wait difference (95% CI) |
|---|---:|---:|---:|---:|
| Normal | 237.5 | 238.3 | +0.8 [+0.0, +2.3] | +0.5 [-0.0, +1.4] |
| Moderate surge | 2813.7 | 2916.3 | +102.6 [+67.5, +139.4] | +346.6 [+267.4, +430.7] |
| Severe surge | 10250.6 | 10197.6 | -53.1 [-71.3, -34.9] | +288.2 [+237.2, +342.3] |
| Icu shortage | 1355.5 | 1352.7 | -2.8 [-6.7, +0.1] | -2.8 [-6.6, +0.1] |
| Equipment shortage | 235.5 | 235.3 | -0.2 [-7.4, +6.6] | +4.0 [-5.2, +13.5] |
| Staff shortage | 395.8 | 397.8 | +1.9 [+0.1, +4.2] | +3.9 [+0.2, +8.6] |
| Combined crisis | 5252.6 | 5247.6 | -5.0 [-28.7, +19.1] | +42.9 [+3.7, +83.7] |

## Resource use

During normal demand the candidate averaged 6.34 staff floats per 30-day run, compared with 14 for serving. Both policies reached the maximum modeled fatigue index of 1.0 in at least one run. The highest observed daily cleaning overtime was 115.2 minutes for the candidate and 102.2 for serving, against a 300-minute modeled daily budget. The allocation audit counted zero violations across all 700 runs. It checks admission-tier compatibility, isolation, ventilation and overlapping bed assignments.

## Method

The trainer ran 30 episodes with exploration seed 0 and training patient streams 10000 through 10029. Only the surge and resource agents were trained. Evaluation used the adaptive planner on 30-day synthetic streams with an initially empty hospital, the same frozen DQN and fitted length-of-stay model, and matching shortage and simulator seeds for each pair. Patients still waiting at day 30 contributed their elapsed wait. These results measure simulated operations. Hospital outcomes and EHR integration require separate evidence.

The [paired results and artifact hashes](../../experiments/results/curated/adaptive_marl_v1.json) contain every per-stream observation. The [candidate metadata](../../models/candidates/adaptive_marl_v1/marl_agents.metadata.json) records the training command. Reproduce the paired evaluation from the repository root.

```sh
python -m experiments.compare_adaptive_policies --candidate models/candidates/adaptive_marl_v1 --output experiments/results/curated/adaptive_marl_v1.json
```
