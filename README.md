# CareGrid RL

### A simulation-driven Reinforcement Learning platform for dynamic hospital bed, staff, and medical-resource allocation.

CareGrid RL is an academic healthcare operations project that uses Reinforcement Learning (RL) and Multi-Agent Reinforcement
Learning (MARL) to help hospitals make better resource-allocation decisions under changing demand.

Instead of only predicting what might happen in a hospital, CareGrid RL focuses on the next operational decision:

> **Given the current patients, beds, staff, equipment, queues, and demand, what allocation should happen right now — and why?**

The system models hospital operations as a constrained sequential decision-making problem. It combines a hospital simulation environment,
prediction models, RL agents, a hard safety/constraint layer, explainable recommendations, and a web-based command-centre dashboard.

CareGrid RL is a **decision-support and simulation platform**, not an autonomous clinical system. Recommendations require human approval
before they are considered executed.

---

# Current Status

_Last updated: 2026-10-31_

**Data & simulation**
- [x] Problem definition, architecture, repository structure
- [x] Synthetic data generator (patients, beds, staff, equipment, events), arrival rates calibrated to the 100-bed hospital
- [x] Virtual hospital simulator (discrete-event) with a text command-centre dashboard
- [x] Rule-based allocation baseline (hard isolation / ventilator constraints)
- [x] Metrics pipeline and experiment runner (wait times, utilization, turnover, constraint violations)
- [x] Arrival-rate surge scenarios (normal / moderate / severe)
- [ ] Shortage scenarios (ICU, staff, equipment, combined crisis)

**AI**
- [x] Length-of-stay prediction (Random Forest, `ml/los`)
- [x] Gymnasium RL environment (14- and 17-feature observations, fresh patient streams with held-out evaluation seeds, ~16k steps/s)
- [x] Policy evaluation harness: baselines and learned agents scored by the same metrics (`python -m rl.evaluation.evaluate`)
- [x] Policy diagnostics harness (`rl/evaluation/diagnose.py`) — action distributions, Q-spreads, feasible-WAIT auditing
- [x] DQN / Double DQN agents trained and benchmarked (X1 Double DQN, X6 Obs-v2, X7 Combo; 300k steps each)
- [x] Safety layer (`safety/`) — independent two-tier validation: H1–H5 hard rules + G1/G2 soft guardrails; **0 hard violations, 0.94 % override rate**
- [x] Multi-stream statistical evaluation — 50 held-out eval streams, paired bootstrap, 95 % CIs (`rl/evaluation/compare.py`)
- [ ] Simple MARL (Bed Agent + Surge Agent)

**Application**
- [x] PostgreSQL schema, Alembic migrations, CSV import
- [x] FastAPI: patients, beds, staff, equipment, recommend, approve, surge simulation, metrics, audit log
- [x] Recommendations come from the same allocation code the simulator uses (`simulator/hospital/allocation_rules.py`)
- [x] React dashboard: command centre, patient queue with approve flow, bed board, staff roster, equipment, audit log
- [x] Surge capacity planner (`/surge`) and analytical reports (`/reports`)
- [ ] Reject / override with a reason (backend endpoint pending)
- [ ] RL + safety layer behind `/allocation/recommend` (selectable algorithm)
- [ ] Authentication (JWT, roles)
- [ ] Mock FHIR endpoint
- [ ] End-to-end demo

**Quality**
- [x] Automated tests: **290 tests passing** — simulator, metrics, load calibration, LOS model, Gymnasium env, DQN / Double DQN, safety layer

### Quick start

```bash
# -- Setup -------------------------------------------------------------------
pip install -r requirements-dev.txt            # backend + ML + RL + test deps

# -- Simulator & rule-based baseline ------------------------------------------
python -m simulator.hospital.run               # run simulator with rule-based baseline
python -m experiments.run_experiment --scenario normal   # metrics (also: moderate_surge, severe_surge)

# -- ML: Length-of-Stay predictor --------------------------------------------
python -m ml.los.train                         # train LOS model once (model file is git-ignored)

# -- RL: Train agents --------------------------------------------------------
python -m rl.training.run_experiments          # run all factor experiments (X0-X7)
python -m rl.training.train --factor x6_obs_v2 --steps 300000   # single factor

# -- RL: Diagnose & evaluate -------------------------------------------------
python -m rl.evaluation.diagnose --model rl/agents/models/x6_obs_v2/best.zip --mode surge
python -m rl.evaluation.evaluate --policy rule_based --mode normal
python -m rl.evaluation.compare --policies b1,h1,h2,h3 \
    --agent rl/agents/models/x6_obs_v2/best.zip --safe \
    --split eval --final --streams 50          # 50-stream held-out benchmark

# -- Backend & Frontend -------------------------------------------------------
uvicorn backend.api.main:app --reload          # FastAPI server  ->  http://localhost:8000
cd frontend && npm install && npm run dev      # React dashboard ->  http://localhost:5173

# -- Test suite --------------------------------------------------------------
python -m pytest tests --ignore=tests/test_backend -q   # 290 tests, ~55 s
```

Work happens on short-lived `feature/<area>-<desc>` branches merged into `main` by pull request; `main` must always run.

# Overview

Hospital resources are limited and constantly changing.

At any given time, a hospital may need to coordinate:

- ICU and general beds
- Isolation-capable beds
- Emergency admissions
- Nurses with different skills and workloads
- Ventilators and telemetry units
- Diagnostic equipment
- Patient transfers
- Discharges
- Sudden demand surges

Traditional manual or static allocation strategies can become inefficient when the hospital state changes quickly.

CareGrid RL addresses this problem by treating resource allocation as a **sequential decision-making problem**.

The platform maintains a simulated hospital state, evaluates available actions, removes unsafe actions using hard constraints,
and uses RL policies to recommend feasible allocations.

The recommendation is then presented to an authorized human operator for approval.

---

# Why CareGrid RL?

Existing hospital-capacity systems already demonstrate the value of predictive analytics and workflow automation.

The research focus of CareGrid RL is narrower:

> **Move from predicting hospital conditions to optimizing operational decisions under changing conditions
> and coupled resource constraints.**

For example:

**A prediction model might estimate:**
Patient P101  
Expected Length of Stay: 4.2 days

**CareGrid RL goes one step further:**
```
Patient P101
|
v
Current hospital state
|
+-- Available beds
+-- ICU capacity
+-- Staff availability
+-- Equipment availability
+-- Waiting patients
+-- Current demand
|
v
RL Decision Engine
|
v
Safety / Constraint Layer
|
v
Recommended allocation
```
---

#### Project Goals
The main goal is to design, implement, and evaluate a simulation-driven Multi-Agent Reinforcement Learning platform that can coordinate:

- Hospital beds
- Clinical staff
- High-demand medical equipment
- Surge response

while respecting hard clinical and operational constraints.

The system is evaluated against progressively stronger baselines rather than assuming that MARL is automatically better.

#### Safety Constraint Layer

RL agents are never allowed to freely execute every possible action.

Before an action is accepted:
```
All possible actions
|
v
Hard constraints
|
v
Invalid actions removed
|
v
RL agent selects from feasible actions
|
v
Final validation
|
v
Recommendation
```

This action-masking approach prevents the RL policy from intentionally or accidentally selecting an invalid allocation.

---

## Architecture Overview

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  React +    │────▶│  FastAPI      │────▶│ PostgreSQL  │
│  Vite       │◀────│  Backend      │◀────│             │
│  Dashboard  │     │               │     └─────────────┘
└─────────────┘     │  ┌──────────┐ │
                    │  │ RL Agent │ │     ┌─────────────┐
                    │  │ (SB3)   │◀┼────▶│ Hospital    │
                    │  └──────────┘ │     │ Simulator   │
                    └──────────────┘     └─────────────┘
```

- **Simulator**: Discrete-time hospital simulation with synthetic patients, beds, staff, equipment
- **RL Agent**: DQN/PPO agent (Stable-Baselines3) trained on the simulator via a Gymnasium environment
- **Backend**: FastAPI with async SQLAlchemy + PostgreSQL
- **Frontend**: React + Vite dashboard with Recharts visualizations

---
