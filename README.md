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
