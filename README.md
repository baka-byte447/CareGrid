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

_Last updated: 2026-10-23_

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
- [ ] Gymnasium RL environment
- [ ] DQN agent trained on the simulator and compared with the baseline
- [ ] Safety layer (independent validation of every proposed action)
- [ ] Simple MARL (Bed Agent + Surge Agent)
- [ ] Final evaluation: rule-based vs DQN vs MARL across all scenarios

**Application**
- [x] PostgreSQL schema, Alembic migrations, CSV import
- [x] FastAPI: patients, beds, staff, equipment, recommend, approve, surge simulation, metrics, audit log
- [x] Recommendations come from the same allocation code the simulator uses (`simulator/hospital/allocation_rules.py`)
- [x] React dashboard: overview, wards, patient queue with approve flow, audit log
- [ ] Reject / override with a reason
- [ ] Surge-simulator and analytics pages (rule vs DQN vs MARL charts)
- [ ] RL + safety layer behind `/allocation/recommend` (selectable algorithm)
- [ ] Authentication (JWT, roles)
- [ ] Mock FHIR endpoint
- [ ] End-to-end demo

**Quality**
- [x] Automated tests: simulator, metrics, load calibration, LOS model, allocation API

### Quick start

```bash
pip install -r requirements-dev.txt          # backend + ML + test dependencies
python -m simulator.hospital.run             # run the simulator with the rule-based baseline
python -m experiments.run_experiment --scenario normal      # metrics (also: moderate_surge, severe_surge)
python -m ml.los.train                       # train the LOS model once (the model file is git-ignored)
python -m pytest tests -q                    # full test suite
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
