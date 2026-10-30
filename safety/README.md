# CareGrid Safety Layer

Independent safety validation layer for hospital bed allocation decisions.

## Architecture

```
Policy PROPOSES action
    ↓
SafetyLayer.review(patient, state, action)
    ↓
Hard constraint check (safety.rules)
    ↓ (if violated)
Fallback heuristic (h3 or b1)
    ↓ (re-validated)
Soft guardrails G1/G2 (if enabled)
    ↓
SafetyDecision (proposed, final, status, reasons)
    ↓
AuditRecord (for future backend integration)
```

## Hard Constraints (always enforced)

| Code | Description |
|------|-------------|
| `ACTION_OUT_OF_RANGE` | Action not in {0=ICU, 1=STEP_DOWN, 2=WARD, 3=WAIT} |
| `TIER_NOT_ALLOWED` | Bed tier incompatible with patient acuity |
| `NO_FREE_BED` | No available bed of the requested tier |
| `ISOLATION_BED_REQUIRED` | Patient needs isolation but no isolation-capable bed free in tier |
| `NO_VENTILATOR` | Patient needs ventilator but none available |

> [!IMPORTANT]
> These checks are derived from `docs/architecture/allocation_rules.md` and
> `simulator/metrics/audit.py`, but implemented **independently** from
> `simulator/hospital/allocation_rules.py`. This redundancy is intentional:
> the safety layer must catch violations even if the allocation rules have bugs.

## Soft Guardrails (configurable)

| Code | Description | Default |
|------|-------------|---------|
| `G1_CRITICAL_WAIT` | Critical patient (acuity ≥ 4) WAITing with feasible beds | Enabled |
| `G2_MAX_WAIT` | Patient wait exceeds max hours for acuity level | Enabled |

> [!WARNING]
> **Clinical assumptions requiring mentor sign-off:**
> - `critical_acuity = 4` (acuity 4+ triggers G1)
> - `max_wait_hours = {5: 2h, 4: 6h, 3: 24h, 2: 72h, 1: 72h}`
>
> These are configurable via `SafetyConfig` but the defaults carry clinical meaning.

## Usage

```python
from safety.layer import SafetyLayer, SafetyConfig

layer = SafetyLayer(SafetyConfig(fallback="h3", guardrails=True))

# In the evaluation loop:
decision = layer.review(patient, state, proposed_action, env=env)
actual_action = decision.final_action

# After the episode:
print(f"Override rate: {layer.override_rate:.2%}")
print(f"Stats: {dict(layer.stats)}")
```

## Override Rates (measured across 30-day episodes)

| Base Policy | Override Rate | Violations Post-Review | Notes |
|:------------|--------------:|-----------------------:|:------|
| **H3 (combined)** | **0.0%** | **0** | Pure hard-constraint review leaves valid H3 proposals unchanged |
| **B1 (rule-based)** | **0.0%** | **0** | Deterministic valid proposals are approved unconditionally |
| **Random** | **74.8%** | **0** | Hard checks reject ~3 in 4 actions (incompatible tier, no vent/iso) |
| **Always-ICU** | **89.2%** | **0** | Overrides non-ICU patients to feasible tiers; 0 violations occur |

## Design Decisions

1. **No torch/SB3 dependency**: The safety layer is pure Python + dataclasses.
   `import safety` never imports torch.

2. **Fallback re-validation**: The fallback heuristic's choice is itself checked
   against hard constraints. If even the fallback is infeasible, WAIT is used.

3. **Idempotent on valid policies**: When the base policy (like H3) always proposes
   valid actions, the safety layer changes nothing (override rate = 0%).

4. **Audit trail**: Every review generates an `AuditRecord` dict, shaped for the
   future backend audit log (Phase 15). The layer does NOT touch `backend/`.

