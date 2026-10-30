"""
CareGrid Safety Layer: validate and optionally override allocation decisions.

Pipeline: policy PROPOSES -> safety layer VALIDATES -> fallback if needed -> audit record.

Hard constraints (always enforced):
  check_hard_constraints() from safety.rules — action must be in range, tier must be
  allowed for the acuity, a bed must be free, isolation/ventilator requirements met.

Soft guardrails (only when config.guardrails=True):
  G1  Critical patient (acuity >= critical_acuity) should not WAIT when any feasible
      bed tier exists -> override with fallback policy.
  G2  Any patient whose wait exceeds max_wait_hours[acuity] and a feasible tier exists
      -> override with fallback policy.

The fallback policy itself is re-validated against hard constraints: if the fallback's
choice is also infeasible, the final action is WAIT (the safest default).

CLINICAL ASSUMPTIONS flagged for mentor sign-off:
  - critical_acuity=4 (acuity 4+ triggers G1)
  - max_wait_hours defaults: {5:2, 4:6, 3:24, 2:72, 1:72}
  All are configurable via SafetyConfig.
"""
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from safety.events import AuditRecord, SafetyDecision
from safety.rules import (BED_TIERS, WAIT_ACTION, check_hard_constraints,
                          feasible_actions, is_action_feasible)


# Default maximum wait hours per acuity (CLINICAL ASSUMPTIONS — needs mentor sign-off)
DEFAULT_MAX_WAIT_HOURS: Dict[int, float] = {
    5: 2.0,    # Critical: max 2 hours
    4: 6.0,    # High: max 6 hours
    3: 24.0,   # Medium: max 24 hours
    2: 72.0,   # Low: max 72 hours
    1: 72.0,   # Minimal: max 72 hours
}


@dataclass
class SafetyConfig:
    """Configuration for the safety layer.

    Attributes
    ----------
    fallback : str
        Which heuristic to use as fallback when overriding: "h3" (combined) or "b1" (rule).
    guardrails : bool
        Whether to enforce soft guardrails G1/G2.
    critical_acuity : int
        Acuity threshold for G1 (>= this is critical). Default 4.
    max_wait_hours : dict
        Per-acuity maximum wait hours for G2. Default: clinical assumptions above.
    """
    fallback: str = "h3"
    guardrails: bool = True
    critical_acuity: int = 4
    max_wait_hours: Dict[int, float] = field(
        default_factory=lambda: dict(DEFAULT_MAX_WAIT_HOURS))


class SafetyLayer:
    """Validates and optionally overrides allocation decisions.

    Usage::

        layer = SafetyLayer(SafetyConfig())
        decision = layer.review(patient, state, proposed_action, env=env)
        actual_action = decision.final_action
    """

    def __init__(self, config: Optional[SafetyConfig] = None):
        self.config = config or SafetyConfig()
        # Counters
        self.stats: Dict[str, int] = Counter()
        self.audit_records: List[Dict[str, Any]] = []

    def reset_stats(self) -> None:
        """Reset counters and audit records (e.g. between episodes)."""
        self.stats = Counter()
        self.audit_records = []

    def _get_fallback_action(self, patient, state, env=None) -> int:
        """Compute the fallback action using the configured heuristic.

        This is intentionally independent of allocation_rules.py — it uses the
        env's valid_actions() mask when available, otherwise checks feasibility
        via safety.rules directly.
        """
        if env is not None:
            # Use the environment's valid_actions for the fallback heuristic
            from rl.evaluation.policies import (combined_heuristic_policy,
                                                rule_based_policy)
            if self.config.fallback == "b1":
                return rule_based_policy(None, env)
            else:
                return combined_heuristic_policy(None, env)

        # Without env, use safety.rules to find feasible actions
        feasible = feasible_actions(patient, state)
        bed_actions = [a for a in feasible if a != WAIT_ACTION]
        if not bed_actions:
            return WAIT_ACTION

        if self.config.fallback == "h3":
            # H3: lowest tier first (reversed order), with isolation protection
            # For acuity 3 isolation patients, only STEP_DOWN
            if patient.acuity == 3 and patient.isolation_required:
                return 1 if 1 in bed_actions else WAIT_ACTION  # STEP_DOWN
            # Reverse order: WARD(2) -> STEP_DOWN(1) -> ICU(0) — cheapest first
            for a in reversed(bed_actions):
                return a
        else:
            # B1: rule-table order (highest tier first)
            return bed_actions[0]

        return WAIT_ACTION

    def _patient_wait_hours(self, patient, state) -> float:
        """Hours the patient has been waiting (0 if just arrived)."""
        if state.current_time is None or patient.arrival_time is None:
            return 0.0
        delta = (state.current_time - patient.arrival_time).total_seconds()
        return max(delta / 3600.0, 0.0)

    def review(
        self,
        patient,
        state,
        proposed_action: int,
        env=None,
    ) -> SafetyDecision:
        """Validate a proposed action and return the safety decision.

        Parameters
        ----------
        patient : Patient
        state : HospitalState
        proposed_action : int
            The action proposed by the policy (0-3).
        env : CareGridHospitalEnv, optional
            If available, used for fallback heuristic computation.

        Returns
        -------
        SafetyDecision
            Contains proposed_action, final_action, status, reason_codes, etc.
        """
        self.stats["reviewed"] += 1
        decision = SafetyDecision(
            proposed_action=proposed_action,
            final_action=proposed_action,
            status="APPROVED",
        )

        # --- Hard constraint check ---
        hard_violations = check_hard_constraints(patient, state, proposed_action)
        if hard_violations:
            decision.reason_codes = hard_violations
            # Override with fallback
            fallback_action = self._get_fallback_action(patient, state, env)
            # Re-validate the fallback
            fb_violations = check_hard_constraints(patient, state, fallback_action)
            if fb_violations:
                fallback_action = WAIT_ACTION  # ultimate safe default
            decision.final_action = fallback_action
            decision.status = "OVERRIDDEN"
            decision.fallback_used = True
            self.stats["overridden"] += 1
            self.stats[f"overridden_acuity_{patient.acuity}"] += 1
            for rc in hard_violations:
                self.stats[f"reason_{rc}"] += 1

        # --- Soft guardrails (only when enabled and action was approved so far) ---
        if self.config.guardrails and decision.status == "APPROVED":
            override_reason = self._check_guardrails(patient, state, proposed_action)
            if override_reason:
                fallback_action = self._get_fallback_action(patient, state, env)
                # Re-validate fallback
                fb_violations = check_hard_constraints(patient, state, fallback_action)
                if fb_violations:
                    fallback_action = WAIT_ACTION

                # Only override if fallback is different and not WAIT
                # (guardrails fire to prevent unnecessary WAIT, so overriding to WAIT is pointless)
                if fallback_action != proposed_action and fallback_action != WAIT_ACTION:
                    decision.final_action = fallback_action
                    decision.status = "OVERRIDDEN"
                    decision.fallback_used = True
                    decision.guardrail_triggered = override_reason
                    self.stats["overridden"] += 1
                    self.stats[f"overridden_acuity_{patient.acuity}"] += 1
                    self.stats[f"guardrail_{override_reason}"] += 1

        # Record audit
        record = AuditRecord(
            timestamp=state.current_time,
            patient_id=patient.patient_id,
            patient_acuity=patient.acuity,
            proposed_action=proposed_action,
            final_action=decision.final_action,
            status=decision.status,
            reason_codes=",".join(decision.reason_codes),
            fallback_used=decision.fallback_used,
            guardrail_triggered=decision.guardrail_triggered or "",
        )
        self.audit_records.append(record.to_dict())

        return decision

    def _check_guardrails(self, patient, state, action: int) -> Optional[str]:
        """Check soft guardrails G1/G2. Returns reason string or None."""
        if action != WAIT_ACTION:
            return None  # guardrails only fire on WAIT decisions

        # Check if any bed action is feasible
        has_feasible = any(
            is_action_feasible(patient, state, a)
            for a in (0, 1, 2)
        )
        if not has_feasible:
            return None  # no feasible alternative, WAIT is the only option

        # G1: Critical patient should not wait when feasible beds exist
        if patient.acuity >= self.config.critical_acuity:
            return "G1_CRITICAL_WAIT"

        # G2: Patient exceeding max wait time
        wait_hours = self._patient_wait_hours(patient, state)
        max_hours = self.config.max_wait_hours.get(patient.acuity, float("inf"))
        if wait_hours >= max_hours:
            return "G2_MAX_WAIT"

        return None

    @property
    def override_rate(self) -> float:
        """Fraction of reviewed decisions that were overridden."""
        reviewed = self.stats.get("reviewed", 0)
        if reviewed == 0:
            return 0.0
        return self.stats.get("overridden", 0) / reviewed

