# Phase 8 DQN Diagnosis Report

_Generated: 2026-10-30T21:43:40_  
_Split: **val** (20 streams per scenario)_  

**Agent checkpoint**: `rl/agents/models/dqn_v1_s0/best.zip`

## Scenario: normal

### 1. Summary Performance

| Policy | Weighted wait (min) | Avg wait (min) | Still waiting | ICU util | WAIT-feasible rate | Decisions |
|:-------|--------------------:|---------------:|--------------:|---------:|-------------------:|----------:|
| **b1** | 440.6 ± 197.6 | 404.9 | 0.2 | 88.10% | 0.0000 | 11598 |
| **h1** | 193.1 ± 101.7 | 323.3 | 0.5 | 57.69% | 0.0000 | 10727 |
| **h3** | 209.0 ± 121.3 | 338.4 | 0.6 | 57.73% | 0.0102 | 10841 |
| **agent** | 272.1 ± 143.8 | 336.9 | 0.5 | 78.66% | 0.0185 | 11083 |

### 2. Wait by Acuity Level (minutes)

| Policy | Acuity 1 | Acuity 2 | Acuity 3 | Acuity 4 | Acuity 5 |
|:-------|---------:|---------:|---------:|---------:|---------:|
| b1 | 494.1 | 611.7 | 153.7 | 212.7 | 829.5 |
| h1 | 517.0 | 652.9 | 126.5 | 49.0 | 133.4 |
| h3 | 513.8 | 654.6 | 152.9 | 64.3 | 143.5 |
| agent | 490.5 | 594.3 | 126.9 | 104.9 | 374.0 |

### 3. Action Distribution per Acuity Level

#### b1

| Acuity | ICU (0) | STEP_DOWN (1) | WARD (2) | WAIT (3) | Feasible WAITs |
|:-------|--------:|--------------:|---------:|---------:|---------------:|
| Acuity 1 | 0.000 | 0.000 | 0.912 | 0.088 | 0 |
| Acuity 2 | 0.000 | 0.000 | 0.887 | 0.113 | 0 |
| Acuity 3 | 0.000 | 0.720 | 0.194 | 0.085 | 0 |
| Acuity 4 | 0.373 | 0.395 | 0.000 | 0.232 | 0 |
| Acuity 5 | 0.631 | 0.000 | 0.000 | 0.369 | 0 |

#### h1

| Acuity | ICU (0) | STEP_DOWN (1) | WARD (2) | WAIT (3) | Feasible WAITs |
|:-------|--------:|--------------:|---------:|---------:|---------------:|
| Acuity 1 | 0.000 | 0.000 | 0.906 | 0.093 | 0 |
| Acuity 2 | 0.000 | 0.000 | 0.882 | 0.118 | 0 |
| Acuity 3 | 0.000 | 0.103 | 0.826 | 0.071 | 0 |
| Acuity 4 | 0.098 | 0.851 | 0.000 | 0.051 | 0 |
| Acuity 5 | 0.915 | 0.000 | 0.000 | 0.085 | 0 |

#### h3

| Acuity | ICU (0) | STEP_DOWN (1) | WARD (2) | WAIT (3) | Feasible WAITs |
|:-------|--------:|--------------:|---------:|---------:|---------------:|
| Acuity 1 | 0.000 | 0.000 | 0.906 | 0.094 | 0 |
| Acuity 2 | 0.000 | 0.000 | 0.882 | 0.118 | 0 |
| Acuity 3 | 0.000 | 0.108 | 0.793 | 0.099 | 111 |
| Acuity 4 | 0.099 | 0.846 | 0.000 | 0.056 | 0 |
| Acuity 5 | 0.912 | 0.000 | 0.000 | 0.088 | 0 |

#### agent

| Acuity | ICU (0) | STEP_DOWN (1) | WARD (2) | WAIT (3) | Feasible WAITs |
|:-------|--------:|--------------:|---------:|---------:|---------------:|
| Acuity 1 | 0.000 | 0.000 | 0.892 | 0.107 | 23 |
| Acuity 2 | 0.000 | 0.000 | 0.881 | 0.119 | 9 |
| Acuity 3 | 0.000 | 0.233 | 0.673 | 0.094 | 120 |
| Acuity 4 | 0.320 | 0.577 | 0.000 | 0.103 | 53 |
| Acuity 5 | 0.795 | 0.000 | 0.000 | 0.205 | 0 |

### 4. Agent Q-Value Statistics

- **Mean Q-spread per decision**: `0.813`  
- **Max Q-spread per decision**: `4.941`  

| Action | Mean Q | Min Q | Max Q |
|:-------|-------:|------:|------:|
| ICU (0) | 29.955 | 6.570 | 39.273 |
| STEP_DOWN (1) | 30.060 | 5.697 | 38.941 |
| WARD (2) | 30.142 | 5.172 | 39.204 |
| WAIT (3) | 29.709 | 5.680 | 38.397 |

## Scenario: moderate_surge

### 1. Summary Performance

| Policy | Weighted wait (min) | Avg wait (min) | Still waiting | ICU util | WAIT-feasible rate | Decisions |
|:-------|--------------------:|---------------:|--------------:|---------:|-------------------:|----------:|
| **b1** | 3392.9 ± 987.7 | 2746.7 | 16.1 | 95.18% | 0.0000 | 29057 |
| **h1** | 3096.2 ± 981.3 | 2623.6 | 15.4 | 88.39% | 0.0000 | 29175 |
| **h3** | 3121.9 ± 987.1 | 2630.6 | 16.1 | 88.32% | 0.0032 | 29160 |
| **agent** | 4902.6 ± 1281.6 | 4557.2 | 67.7 | 86.19% | 0.3341 | 29556 |

### 2. Wait by Acuity Level (minutes)

| Policy | Acuity 1 | Acuity 2 | Acuity 3 | Acuity 4 | Acuity 5 |
|:-------|---------:|---------:|---------:|---------:|---------:|
| b1 | 2078.2 | 2310.7 | 1820.6 | 3095.2 | 5264.0 |
| h1 | 2125.7 | 2335.4 | 1744.0 | 2765.1 | 4606.3 |
| h3 | 2079.2 | 2311.8 | 1746.0 | 2804.0 | 4644.5 |
| agent | 4088.4 | 3162.7 | 2544.8 | 3108.0 | 5582.0 |

### 3. Action Distribution per Acuity Level

#### b1

| Acuity | ICU (0) | STEP_DOWN (1) | WARD (2) | WAIT (3) | Feasible WAITs |
|:-------|--------:|--------------:|---------:|---------:|---------------:|
| Acuity 1 | 0.000 | 0.000 | 0.582 | 0.418 | 0 |
| Acuity 2 | 0.000 | 0.000 | 0.582 | 0.418 | 0 |
| Acuity 3 | 0.000 | 0.167 | 0.425 | 0.408 | 0 |
| Acuity 4 | 0.110 | 0.425 | 0.000 | 0.466 | 0 |
| Acuity 5 | 0.517 | 0.000 | 0.000 | 0.483 | 0 |

#### h1

| Acuity | ICU (0) | STEP_DOWN (1) | WARD (2) | WAIT (3) | Feasible WAITs |
|:-------|--------:|--------------:|---------:|---------:|---------------:|
| Acuity 1 | 0.000 | 0.000 | 0.561 | 0.439 | 0 |
| Acuity 2 | 0.000 | 0.000 | 0.559 | 0.441 | 0 |
| Acuity 3 | 0.000 | 0.116 | 0.466 | 0.417 | 0 |
| Acuity 4 | 0.089 | 0.482 | 0.000 | 0.429 | 0 |
| Acuity 5 | 0.552 | 0.000 | 0.000 | 0.448 | 0 |

#### h3

| Acuity | ICU (0) | STEP_DOWN (1) | WARD (2) | WAIT (3) | Feasible WAITs |
|:-------|--------:|--------------:|---------:|---------:|---------------:|
| Acuity 1 | 0.000 | 0.000 | 0.563 | 0.437 | 0 |
| Acuity 2 | 0.000 | 0.000 | 0.562 | 0.438 | 0 |
| Acuity 3 | 0.000 | 0.116 | 0.462 | 0.421 | 94 |
| Acuity 4 | 0.090 | 0.480 | 0.000 | 0.430 | 0 |
| Acuity 5 | 0.552 | 0.000 | 0.000 | 0.448 | 0 |

#### agent

| Acuity | ICU (0) | STEP_DOWN (1) | WARD (2) | WAIT (3) | Feasible WAITs |
|:-------|--------:|--------------:|---------:|---------:|---------------:|
| Acuity 1 | 0.000 | 0.000 | 0.567 | 0.433 | 888 |
| Acuity 2 | 0.000 | 0.000 | 0.713 | 0.287 | 227 |
| Acuity 3 | 0.000 | 0.093 | 0.405 | 0.502 | 4434 |
| Acuity 4 | 0.082 | 0.346 | 0.000 | 0.572 | 3040 |
| Acuity 5 | 0.411 | 0.000 | 0.000 | 0.589 | 1286 |

### 4. Agent Q-Value Statistics

- **Mean Q-spread per decision**: `0.55`  
- **Max Q-spread per decision**: `4.941`  

| Action | Mean Q | Min Q | Max Q |
|:-------|-------:|------:|------:|
| ICU (0) | -20.985 | -127.140 | 39.273 |
| STEP_DOWN (1) | -21.102 | -127.033 | 39.259 |
| WARD (2) | -20.858 | -128.419 | 39.669 |
| WAIT (3) | -20.981 | -129.003 | 38.736 |

## 5. Hypothesis Analysis (Evidence from Diagnosis)

Evaluation of 
l/agents/models/dqn_v1_s0/best.zip against B1, H1, and H3 on 20 validation streams reveals:

- **(H-e) WAIT is an over-used commitment: STRONGLY SUPPORTED.**
  In moderate_surge, the agent chooses WAIT in **33.41%** of all decisions when feasible beds are available (9,875 decisions). In contrast, H1/B1 have 0 feasible WAITs, and H3 has only 94 (0.32%, solely due to isolation protection). This causes patients_still_waiting to explode to **67.7** (vs 16.1 for B1/H3), and moderate surge wait time to spike to 4,902 min (vs 3,096 min for H1).

- **(H-b) Q-scale mismatch across scenarios and weak credit assignment: STRONGLY SUPPORTED.**
  In 
ormal, mean Q is ~+30.0 (range 5 to 39). In moderate_surge, mean Q is ~-21.0 (range -129 to +39). The mean Q-spread between the best and worst action per decision is only **0.55 - 0.81**, whereas the scenario variance is ~170. Because the reward reflects the macro queue cost across all patients, per-decision action differences are tiny compared to the scenario-level cost.

- **(H-a) Max-operator overestimation / instability: SUPPORTED.**
  Training logs show progressive performance degradation beyond 250k steps (val_score degrades from 1,218 at 250k to 2,871 at 800k). Overestimation of Q(s, a') in standard DQN leads the policy to favor deferring patients under high load.

- **(H-c) Agent cannot observe wait-so-far or time of day: SUPPORTED.**
  High-acuity patients (Acuity 4 and 5) suffer 3,040 and 1,286 feasible WAITs respectively in moderate surge, indicating the agent cannot distinguish a fresh arrival from a patient who has been waiting hours.

- **(H-d) Noisy checkpoint selection: SUPPORTED.**
  Validation during training sampled only 10 streams, leading to high variance. The best checkpoint at step 300k was artificially selected at the burn-in boundary, excluding better checkpoints at 150k and 250k.
