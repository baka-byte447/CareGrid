"""
AllocationService – production-ready serving layer combining DQN inference
and the clinical SafetyLayer.

Framework-free: relies solely on NumPy and standard library.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from rl.environment.observation import build_observation
from rl.serving.numpy_policy import NumpyQPolicy
from safety.layer import SafetyConfig, SafetyLayer
from simulator.hospital.allocation_rules import (
    allocation_for_bed_type,
    decide_bed,
)
from simulator.hospital.state import HospitalState
from simulator.patients.patient import Patient

BED_ACTIONS = ("ICU", "STEP_DOWN", "WARD")
WAIT_ACTION = 3

DEFAULT_MODEL_PATH = (
    Path(__file__).resolve().parents[2] / "models" / "serving" / "dqn_x6_obs_v2.npz"
)


@dataclass
class SafetyBlock:
    overridden: bool
    rule_triggered: Optional[str] = None
    original_action: int = WAIT_ACTION
    reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ServingResult:
    patient_id: str
    proposed_action: int
    final_action: int
    proposed_bed_type: Optional[str]
    final_bed_type: Optional[str]
    recommended_bed_id: Optional[str]
    algorithm: str
    safety: SafetyBlock
    q_values: Optional[List[float]] = None
    los_estimate_days: float = 3.0
    status: str = "RECOMMENDED"
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AllocationService:
    """Combines NumpyQPolicy with SafetyLayer for live or testbed recommendations."""

    def __init__(
        self,
        model_path: Optional[str | Path] = None,
        safety_config: Optional[SafetyConfig] = None,
        los_predictor: Optional[Any] = None,
    ) -> None:
        self.model_path = Path(model_path) if model_path else DEFAULT_MODEL_PATH
        self.policy: Optional[NumpyQPolicy] = None
        self.fallback_reason: Optional[str] = None

        if self.model_path.exists():
            try:
                self.policy = NumpyQPolicy(self.model_path)
            except Exception as e:
                self.fallback_reason = f"Failed to load model from {self.model_path}: {e}"
        else:
            self.fallback_reason = f"Model file not found at {self.model_path}"

        self.safety_layer = SafetyLayer(safety_config or SafetyConfig())
        self.los_predictor = los_predictor
        self._los_predictor_attempted = False

    def _get_los_estimate(self, patient: Patient) -> float:
        if self.los_predictor is not None:
            try:
                return float(self.los_predictor.predict(patient))
            except Exception:
                pass

        if not self._los_predictor_attempted:
            self._los_predictor_attempted = True
            try:
                from ml.los.predictor import LOSPredictor
                self.los_predictor = LOSPredictor.load()
                return float(self.los_predictor.predict(patient))
            except Exception:
                self.los_predictor = None

        if patient.predicted_los is not None and patient.predicted_los > 0:
            return float(patient.predicted_los)
        return 3.0

    def recommend(
        self,
        patient: Patient,
        state: HospitalState,
        now: Optional[datetime] = None,
        patients_by_id: Optional[Dict[str, Patient]] = None,
    ) -> ServingResult:
        los_days = self._get_los_estimate(patient)
        effective_now = now or state.current_time

        # If policy cannot be loaded, fallback to safe rule-based decision
        if self.policy is None:
            decision = decide_bed(patient, state)
            bed_id = decision.bed_id if decision else None
            bed_type = state.beds[bed_id].bed_type if bed_id and bed_id in state.beds else None
            action = BED_ACTIONS.index(bed_type) if bed_type in BED_ACTIONS else WAIT_ACTION
            status = "RECOMMENDED" if bed_id else "NO_SUITABLE_BED"
            reasons = [self.fallback_reason or "Policy unavailable; rule-based fallback used"]
            return ServingResult(
                patient_id=patient.patient_id,
                proposed_action=action,
                final_action=action,
                proposed_bed_type=bed_type or "WAIT",
                final_bed_type=bed_type or "WAIT",
                recommended_bed_id=bed_id,
                algorithm="rule_based_fallback",
                safety=SafetyBlock(
                    overridden=False,
                    original_action=action,
                    reason="Model fallback active",
                ),
                q_values=None,
                los_estimate_days=los_days,
                status=status,
                reasons=reasons,
            )

        # 1. Compute valid action mask
        valid_mask = np.zeros(4, dtype=bool)
        valid_mask[WAIT_ACTION] = True
        for idx, tier in enumerate(BED_ACTIONS):
            alloc, _ = allocation_for_bed_type(patient, state, tier)
            valid_mask[idx] = alloc is not None

        # 2. Build observation vector
        obs = build_observation(
            patient=patient,
            state=state,
            los_estimate=los_days,
            now=effective_now,
            version=2,
            patients_by_id=patients_by_id,
        )

        # 3. Model forward pass & masked action selection
        q_vals = self.policy.q_values(obs)
        proposed_action = self.policy.best_action(obs, valid_mask=valid_mask)
        proposed_bed_type = (
            BED_ACTIONS[proposed_action] if proposed_action < len(BED_ACTIONS) else "WAIT"
        )

        # 4. SafetyLayer review
        safety_decision = self.safety_layer.review(patient, state, proposed_action)
        final_action = safety_decision.final_action
        final_bed_type = (
            BED_ACTIONS[final_action] if final_action < len(BED_ACTIONS) else "WAIT"
        )

        # 5. Resolve actual bed assignment
        recommended_bed_id: Optional[str] = None
        reasons: List[str] = list(safety_decision.reason_codes)

        if final_action == WAIT_ACTION:
            has_feasible_bed = any(valid_mask[:3])
            status = "WAIT" if has_feasible_bed else "NO_SUITABLE_BED"
            if not has_feasible_bed:
                reasons.append("No clinically compatible and free bed available")
            else:
                reasons.append("Policy or safety layer selected WAIT")
        else:
            alloc, err = allocation_for_bed_type(patient, state, final_bed_type)
            if alloc is not None:
                recommended_bed_id = alloc.bed_id
                status = "RECOMMENDED"
            else:
                status = "NO_SUITABLE_BED"
                if err:
                    reasons.append(err)

        safety_block = SafetyBlock(
            overridden=safety_decision.was_overridden,
            rule_triggered=safety_decision.guardrail_triggered,
            original_action=safety_decision.proposed_action,
            reason="; ".join(safety_decision.reason_codes) if safety_decision.reason_codes else None,
        )

        return ServingResult(
            patient_id=patient.patient_id,
            proposed_action=proposed_action,
            final_action=final_action,
            proposed_bed_type=proposed_bed_type,
            final_bed_type=final_bed_type,
            recommended_bed_id=recommended_bed_id,
            algorithm="dqn_safe",
            safety=safety_block,
            q_values=[round(float(v), 4) for v in q_vals],
            los_estimate_days=round(float(los_days), 2),
            status=status,
            reasons=reasons,
        )
