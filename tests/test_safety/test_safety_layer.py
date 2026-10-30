"""Comprehensive tests for the safety layer (torch-free).

Tests:
  1. Property test: 5,000 random proposals on hand-built and simulated states
     -> final action never violates hard rules.
  2. Full 30-day episodes with random and always-ICU policies wrapped by the layer
     -> audit violations == 0 and invalid_actions == 0.
  3. G1/G2 guardrails fire in hand-built cases and do NOT fire when no feasible tier.
  4. Fallback re-validation.
  5. Layer is idempotent on valid H3 proposals (override_rate 0).
  6. `import safety` does not import torch.
"""
import random
from datetime import datetime, timedelta

import numpy as np
import pytest

pytest.importorskip("gymnasium")

from safety.events import AuditRecord, SafetyDecision
from safety.layer import SafetyConfig, SafetyLayer
from safety.rules import (ACUITY_TO_ALLOWED_TIERS, BED_TIERS, WAIT_ACTION,
                          check_hard_constraints, feasible_actions,
                          is_action_feasible)
from simulator.hospital.state import Bed, Equipment, HospitalState
from simulator.patients.patient import Patient


# ============================================================================
# Test fixtures
# ============================================================================

def make_patient(
    acuity: int = 3,
    isolation: bool = False,
    ventilator: bool = False,
    patient_id: str = "P001",
    arrival_time: datetime = datetime(2026, 1, 1, 8, 0, 0),
) -> Patient:
    return Patient(
        patient_id=patient_id,
        age_group="ADULT",
        acuity=acuity,
        specialty="GENERAL",
        predicted_los=3.0,
        isolation_required=isolation,
        ventilator_required=ventilator,
        arrival_time=arrival_time,
    )


def make_state(
    icu_available: int = 5,
    icu_isolation: int = 2,
    step_down_available: int = 10,
    step_down_isolation: int = 2,
    ward_available: int = 20,
    ward_isolation: int = 2,
    ventilators_available: int = 5,
    current_time: datetime = datetime(2026, 1, 1, 9, 0, 0),
) -> HospitalState:
    """Build a simplified hospital state with the given availability."""
    beds = {}
    bed_id = 0

    def add_beds(tier, total_avail, iso_count):
        nonlocal bed_id
        for i in range(total_avail):
            bid = f"B{bed_id:03d}"
            beds[bid] = Bed(
                bed_id=bid,
                bed_type=tier,
                ward=f"{tier}_WARD",
                status="AVAILABLE",
                isolation_capable=(i < iso_count),
            )
            bed_id += 1

    add_beds("ICU", icu_available, icu_isolation)
    add_beds("STEP_DOWN", step_down_available, step_down_isolation)
    add_beds("WARD", ward_available, ward_isolation)

    equipment = {}
    for i in range(ventilators_available):
        eid = f"V{i:03d}"
        equipment[eid] = Equipment(
            equipment_id=eid, type="VENTILATOR", status="AVAILABLE", location="ICU"
        )

    return HospitalState(
        beds=beds,
        equipment=equipment,
        current_time=current_time,
    )


# ============================================================================
# 1. Property test: 5,000 random proposals
# ============================================================================

class TestPropertyRandomProposals:
    """Final action from the safety layer must never violate hard rules."""

    @pytest.mark.parametrize("trial", range(100))  # 100 parametrized x 50 inner = 5000
    def test_random_proposals_never_violate_hard_rules(self, trial):
        rng = random.Random(trial)
        layer = SafetyLayer(SafetyConfig(guardrails=True))

        for _ in range(50):
            acuity = rng.randint(1, 5)
            iso = rng.random() < 0.3
            vent = rng.random() < 0.2

            # Vary hospital state
            state = make_state(
                icu_available=rng.randint(0, 5),
                icu_isolation=rng.randint(0, 2),
                step_down_available=rng.randint(0, 10),
                step_down_isolation=rng.randint(0, 3),
                ward_available=rng.randint(0, 20),
                ward_isolation=rng.randint(0, 2),
                ventilators_available=rng.randint(0, 5),
            )
            patient = make_patient(acuity=acuity, isolation=iso, ventilator=vent)

            # Adversarial proposed actions include out-of-range
            proposed = rng.choice([-1, 0, 0, 0, 1, 1, 2, 2, 3, 3, 5, 99])
            decision = layer.review(patient, state, proposed)

            # The FINAL action must pass hard checks
            violations = check_hard_constraints(patient, state, decision.final_action)
            assert violations == [], (
                f"Hard violation on final action {decision.final_action} for "
                f"acuity={acuity}, iso={iso}, vent={vent}, proposed={proposed}: {violations}"
            )


# ============================================================================
# 2. Full episode tests (random + always-ICU through the env)
# ============================================================================

class TestFullEpisodes:
    """Run complete episodes with adversarial policies wrapped by safety layer."""

    @pytest.fixture
    def data_dir(self):
        from pathlib import Path
        return Path(__file__).resolve().parents[2] / "data" / "synthetic"

    @pytest.fixture
    def counting_predictor(self):
        class P:
            def predict(self, patient): return 3.0
            def predict_many(self, patients): return [3.0] * len(patients)
        return P()

    def _run_episode(self, base_policy, data_dir, counting_predictor,
                     seed, days=7, mode="normal"):
        from rl.evaluation.evaluate import evaluate_policy
        from rl.evaluation.policies import safe_policy
        from simulator.patients.streams import generate_stream

        layer = SafetyLayer(SafetyConfig(guardrails=True))
        wrapped = safe_policy(base_policy, layer)
        stream = generate_stream(seed, days=days, mode=mode)
        result = evaluate_policy(
            wrapped, stream, drain_days=2,
            los_predictor=counting_predictor,
            data_dir=str(data_dir),
            record_actions=True,
        )
        return result, layer

    def test_random_policy_wrapped_has_zero_violations_normal(
            self, data_dir, counting_predictor):
        from rl.evaluation.policies import make_random_policy
        result, layer = self._run_episode(
            make_random_policy(42), data_dir, counting_predictor,
            seed=80_000, days=7, mode="normal")
        assert result["invalid_actions"] == 0
        violations = result["metrics"]["constraint_violations"]["total"]
        assert violations == 0, f"Violations: {result['metrics']['constraint_violations']}"

    def test_random_policy_wrapped_has_zero_violations_moderate(
            self, data_dir, counting_predictor):
        from rl.evaluation.policies import make_random_policy
        result, layer = self._run_episode(
            make_random_policy(7), data_dir, counting_predictor,
            seed=80_001, days=7, mode="moderate_surge")
        assert result["invalid_actions"] == 0
        assert result["metrics"]["constraint_violations"]["total"] == 0

    def test_always_icu_policy_wrapped_has_zero_violations(
            self, data_dir, counting_predictor):
        always_icu = lambda obs, env: 0  # always propose ICU
        result, layer = self._run_episode(
            always_icu, data_dir, counting_predictor,
            seed=80_002, days=7, mode="normal")
        assert result["invalid_actions"] == 0
        assert result["metrics"]["constraint_violations"]["total"] == 0
        # The layer should have overridden many actions
        assert layer.stats["overridden"] > 0


# ============================================================================
# 3. Guardrail tests (G1 / G2)
# ============================================================================

class TestGuardrails:
    """G1/G2 fire in hand-built cases and do NOT fire when no feasible tier."""

    def test_g1_fires_for_critical_patient_waiting_with_feasible_bed(self):
        """G1: acuity 5 patient WAITing when ICU bed is free -> override."""
        layer = SafetyLayer(SafetyConfig(guardrails=True, critical_acuity=4))
        patient = make_patient(acuity=5)
        state = make_state(icu_available=3)
        decision = layer.review(patient, state, WAIT_ACTION)
        assert decision.status == "OVERRIDDEN"
        assert decision.guardrail_triggered == "G1_CRITICAL_WAIT"
        assert decision.final_action == 0  # ICU

    def test_g1_fires_for_acuity4_waiting_with_feasible_bed(self):
        """G1: acuity 4 patient WAITing when STEP_DOWN bed is free -> override."""
        layer = SafetyLayer(SafetyConfig(guardrails=True, critical_acuity=4))
        patient = make_patient(acuity=4)
        state = make_state(icu_available=0, step_down_available=3)
        decision = layer.review(patient, state, WAIT_ACTION)
        assert decision.status == "OVERRIDDEN"
        assert decision.guardrail_triggered == "G1_CRITICAL_WAIT"

    def test_g1_does_not_fire_when_no_feasible_tier(self):
        """G1: acuity 5 with no ICU beds -> WAIT is the only option, no override."""
        layer = SafetyLayer(SafetyConfig(guardrails=True, critical_acuity=4))
        patient = make_patient(acuity=5)
        state = make_state(icu_available=0)
        decision = layer.review(patient, state, WAIT_ACTION)
        assert decision.status == "APPROVED"
        assert decision.final_action == WAIT_ACTION

    def test_g1_does_not_fire_for_low_acuity(self):
        """G1 only fires for acuity >= critical_acuity."""
        layer = SafetyLayer(SafetyConfig(guardrails=True, critical_acuity=4))
        patient = make_patient(acuity=2)
        state = make_state(ward_available=10)
        decision = layer.review(patient, state, WAIT_ACTION)
        # G1 should NOT fire for acuity 2
        assert decision.guardrail_triggered != "G1_CRITICAL_WAIT"

    def test_g2_fires_for_long_waiting_patient(self):
        """G2: patient waited > max_wait_hours -> override."""
        config = SafetyConfig(guardrails=True, max_wait_hours={1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0, 5: 1.0})
        layer = SafetyLayer(config)
        arrival = datetime(2026, 1, 1, 8, 0, 0)
        patient = make_patient(acuity=2, arrival_time=arrival)
        state = make_state(
            ward_available=5,
            current_time=arrival + timedelta(hours=2),  # 2 hours > max 1 hour
        )
        decision = layer.review(patient, state, WAIT_ACTION)
        assert decision.status == "OVERRIDDEN"
        assert decision.guardrail_triggered == "G2_MAX_WAIT"

    def test_g2_does_not_fire_when_within_limit(self):
        """G2: patient waited < max_wait_hours -> no override."""
        config = SafetyConfig(guardrails=True, max_wait_hours={1: 72, 2: 72, 3: 24, 4: 6, 5: 2})
        layer = SafetyLayer(config)
        arrival = datetime(2026, 1, 1, 8, 0, 0)
        patient = make_patient(acuity=2, arrival_time=arrival)
        state = make_state(
            ward_available=5,
            current_time=arrival + timedelta(hours=1),
        )
        decision = layer.review(patient, state, WAIT_ACTION)
        # Neither G1 nor G2 should fire (acuity 2, only 1 hour)
        assert decision.guardrail_triggered is None or decision.status == "APPROVED"

    def test_g2_does_not_fire_when_no_feasible_bed(self):
        """G2: patient waited long but no beds available -> WAIT approved."""
        config = SafetyConfig(guardrails=True, max_wait_hours={1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0, 5: 1.0})
        layer = SafetyLayer(config)
        arrival = datetime(2026, 1, 1, 8, 0, 0)
        patient = make_patient(acuity=2, arrival_time=arrival)
        state = make_state(
            ward_available=0,
            current_time=arrival + timedelta(hours=5),
        )
        decision = layer.review(patient, state, WAIT_ACTION)
        assert decision.status == "APPROVED"
        assert decision.final_action == WAIT_ACTION


# ============================================================================
# 4. Fallback re-validation
# ============================================================================

class TestFallbackRevalidation:
    """When the fallback heuristic also fails hard checks, fall back to WAIT."""

    def test_fallback_to_wait_when_fallback_also_infeasible(self):
        """Acuity 5 patient, no ICU beds: proposed ICU -> fallback tries ICU -> WAIT."""
        layer = SafetyLayer(SafetyConfig(guardrails=False))
        patient = make_patient(acuity=5)  # only ICU allowed
        state = make_state(icu_available=0)  # no ICU beds
        # Propose ICU (action 0) — infeasible because no beds
        decision = layer.review(patient, state, 0)
        assert decision.status == "OVERRIDDEN"
        assert decision.final_action == WAIT_ACTION

    def test_fallback_respects_isolation(self):
        """Isolation patient: proposed WARD bed, but no isolation ward beds."""
        layer = SafetyLayer(SafetyConfig(guardrails=False))
        patient = make_patient(acuity=2, isolation=True)
        # Ward beds exist but none isolation-capable
        state = make_state(ward_available=10, ward_isolation=0)
        decision = layer.review(patient, state, 2)  # propose WARD
        # WARD fails ISOLATION_BED_REQUIRED -> fallback, but WARD is the only
        # allowed tier for acuity 2, and no isolation beds -> WAIT
        assert decision.final_action == WAIT_ACTION

    def test_out_of_range_action_gets_corrected(self):
        """Action 99 -> override with fallback."""
        layer = SafetyLayer(SafetyConfig(guardrails=False))
        patient = make_patient(acuity=3)
        state = make_state()
        decision = layer.review(patient, state, 99)
        assert decision.status == "OVERRIDDEN"
        assert decision.final_action != 99
        # Final action should be valid
        assert check_hard_constraints(patient, state, decision.final_action) == []


# ============================================================================
# 5. Idempotent on H3
# ============================================================================

class TestIdempotentOnH3:
    """When the base policy is H3 (always valid), override rate is 0."""

    @pytest.fixture
    def data_dir(self):
        from pathlib import Path
        return Path(__file__).resolve().parents[2] / "data" / "synthetic"

    @pytest.fixture
    def counting_predictor(self):
        class P:
            def predict(self, patient): return 3.0
            def predict_many(self, patients): return [3.0] * len(patients)
        return P()

    def test_h3_wrapped_has_zero_overrides(self, data_dir, counting_predictor):
        from rl.evaluation.evaluate import evaluate_policy
        from rl.evaluation.policies import combined_heuristic_policy, safe_policy
        from simulator.patients.streams import generate_stream

        layer = SafetyLayer(SafetyConfig(guardrails=False))  # no guardrails, pure hard check
        wrapped = safe_policy(combined_heuristic_policy, layer)
        stream = generate_stream(80_003, days=7, mode="normal")
        result = evaluate_policy(
            wrapped, stream, drain_days=2,
            los_predictor=counting_predictor,
            data_dir=str(data_dir),
        )
        assert layer.override_rate == 0.0
        assert layer.stats.get("overridden", 0) == 0
        assert result["invalid_actions"] == 0


# ============================================================================
# 6. No torch import
# ============================================================================

class TestNoTorchImport:
    """Importing safety must not pull in torch."""

    def test_import_safety_does_not_import_torch(self):
        import subprocess
        import sys
        result = subprocess.run(
            [sys.executable, "-c",
             "import safety; import sys; "
             "assert 'torch' not in sys.modules, "
             "'torch was imported by safety'; print('OK')"],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, f"Failed: {result.stderr}"
        assert "OK" in result.stdout


# ============================================================================
# Hard constraint unit tests
# ============================================================================

class TestHardConstraints:
    """Unit tests for safety.rules.check_hard_constraints."""

    def test_wait_always_passes(self):
        for acuity in range(1, 6):
            patient = make_patient(acuity=acuity)
            state = make_state()
            assert check_hard_constraints(patient, state, WAIT_ACTION) == []

    def test_tier_not_allowed(self):
        # Acuity 5 cannot go to WARD
        patient = make_patient(acuity=5)
        state = make_state()
        reasons = check_hard_constraints(patient, state, 2)  # WARD
        assert "TIER_NOT_ALLOWED" in reasons

    def test_tier_allowed(self):
        # Acuity 3 can go to STEP_DOWN
        patient = make_patient(acuity=3)
        state = make_state()
        reasons = check_hard_constraints(patient, state, 1)  # STEP_DOWN
        assert reasons == []

    def test_no_free_bed(self):
        patient = make_patient(acuity=3)
        state = make_state(step_down_available=0)
        reasons = check_hard_constraints(patient, state, 1)  # STEP_DOWN
        assert "NO_FREE_BED" in reasons

    def test_isolation_required_no_iso_bed(self):
        patient = make_patient(acuity=3, isolation=True)
        state = make_state(step_down_available=5, step_down_isolation=0)
        reasons = check_hard_constraints(patient, state, 1)
        assert "ISOLATION_BED_REQUIRED" in reasons

    def test_ventilator_required_none_available(self):
        patient = make_patient(acuity=5, ventilator=True)
        state = make_state(ventilators_available=0)
        reasons = check_hard_constraints(patient, state, 0)  # ICU
        assert "NO_VENTILATOR" in reasons

    def test_action_out_of_range(self):
        patient = make_patient(acuity=3)
        state = make_state()
        reasons = check_hard_constraints(patient, state, 99)
        assert "ACTION_OUT_OF_RANGE" in reasons

    def test_all_valid_for_normal_case(self):
        patient = make_patient(acuity=3)
        state = make_state()
        for action in (1, 2):  # STEP_DOWN and WARD valid for acuity 3
            assert check_hard_constraints(patient, state, action) == []

    def test_feasible_actions(self):
        patient = make_patient(acuity=4)
        state = make_state(icu_available=2, step_down_available=3)
        fa = feasible_actions(patient, state)
        assert 0 in fa  # ICU
        assert 1 in fa  # STEP_DOWN
        assert 2 not in fa  # WARD not allowed for acuity 4
        assert 3 in fa  # WAIT always

