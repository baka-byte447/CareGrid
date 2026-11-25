# Phase 10: Shortage Scenario Benchmark (50 Held-Out Evaluation Streams)

## Scenario: `icu_shortage`

| Policy | Weighted Wait (min) | Avg Wait (min) | Critical Wait (min) | Still Waiting | ICU Util | Violations |
|---|---:|---:|---:|---:|---:|---:|
| `b1` | 2225.31 | 1017.16 | 2622.99 | 3.86 | 0.48 | 0.0 |
| `h1` | 1591.13 | 789.51 | 1780.6 | 2.78 | 0.44 | 0.0 |
| `h3` | 1641.14 | 820.91 | 1844.43 | 2.58 | 0.44 | 0.0 |
| `dqn_safe` | 1675.51 | 829.7 | 1907.62 | 2.86 | 0.44 | 0.0 |
| `marl_3agent_safe` | 1671.39 | 828.56 | 1902.49 | 2.84 | 0.44 | 0.0 |

- **MARL vs B1 (`acuity_weighted_avg_wait_min`)**: diff = `-553.92` min (95% CI `[-650.46, -460.91]`, win rate `96.0%`)
- **MARL vs DQN+Safety (`acuity_weighted_avg_wait_min`)**: diff = `-4.12` min (95% CI `[-6.36, -1.12]`, win rate `88.0%`)

## Scenario: `equipment_shortage`

| Policy | Weighted Wait (min) | Avg Wait (min) | Critical Wait (min) | Still Waiting | ICU Util | Violations |
|---|---:|---:|---:|---:|---:|---:|
| `b1` | 771.73 | 501.21 | 943.52 | 1.1 | 0.89 | 0.0 |
| `h1` | 553.99 | 435.5 | 654.23 | 0.96 | 0.56 | 0.0 |
| `h3` | 557.24 | 432.13 | 656.74 | 0.88 | 0.56 | 0.0 |
| `dqn_safe` | 674.42 | 489.09 | 802.21 | 1.0 | 0.81 | 0.0 |
| `marl_3agent_safe` | 252.39 | 323.91 | 173.73 | 0.6 | 0.7 | 0.0 |

- **MARL vs B1 (`acuity_weighted_avg_wait_min`)**: diff = `-519.34` min (95% CI `[-652.31, -394.14]`, win rate `100.0%`)
- **MARL vs DQN+Safety (`acuity_weighted_avg_wait_min`)**: diff = `-422.03` min (95% CI `[-551.48, -303.85]`, win rate `96.0%`)

## Scenario: `staff_shortage`

| Policy | Weighted Wait (min) | Avg Wait (min) | Critical Wait (min) | Still Waiting | ICU Util | Violations |
|---|---:|---:|---:|---:|---:|---:|
| `b1` | 568.51 | 483.62 | 594.32 | 0.68 | 0.89 | 0.0 |
| `h1` | 298.12 | 388.14 | 196.46 | 0.7 | 0.63 | 0.0 |
| `h3` | 348.76 | 440.84 | 229.98 | 0.66 | 0.64 | 0.0 |
| `dqn_safe` | 359.6 | 423.74 | 281.66 | 0.76 | 0.72 | 0.0 |
| `marl_3agent_safe` | 359.53 | 424.6 | 279.72 | 0.78 | 0.73 | 0.0 |

- **MARL vs B1 (`acuity_weighted_avg_wait_min`)**: diff = `-208.98` min (95% CI `[-240.55, -177.03]`, win rate `98.0%`)
- **MARL vs DQN+Safety (`acuity_weighted_avg_wait_min`)**: diff = `-0.07` min (95% CI `[-2.27, 2.57]`, win rate `74.0%`)

## Scenario: `combined_crisis`

| Policy | Weighted Wait (min) | Avg Wait (min) | Critical Wait (min) | Still Waiting | ICU Util | Violations |
|---|---:|---:|---:|---:|---:|---:|
| `b1` | 7184.47 | 4345.28 | 8689.34 | 56.2 | 0.49 | 0.0 |
| `h1` | 6687.42 | 4181.57 | 8041.18 | 53.28 | 0.47 | 0.0 |
| `h3` | 6787.81 | 4253.64 | 8167.24 | 58.96 | 0.47 | 0.0 |
| `dqn_safe` | 6950.41 | 4273.14 | 8389.67 | 55.22 | 0.48 | 0.0 |
| `marl_3agent_safe` | 6768.73 | 4272.91 | 8010.24 | 54.0 | 0.48 | 0.0 |

- **MARL vs B1 (`acuity_weighted_avg_wait_min`)**: diff = `-415.74` min (95% CI `[-468.69, -364.77]`, win rate `100.0%`)
- **MARL vs DQN+Safety (`acuity_weighted_avg_wait_min`)**: diff = `-181.68` min (95% CI `[-222.26, -142.73]`, win rate `92.0%`)
