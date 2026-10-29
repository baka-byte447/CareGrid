"""Gymnasium environment for sequential hospital bed allocation decisions.

Actions: 0=ICU, 1=STEP_DOWN, 2=WARD, 3=WAIT. Bed type actions are accepted only
when clinically/resource compatible; invalid actions are rejected and the patient
remains waiting. The observation deliberately excludes Patient.predicted_los,
which is the simulator's hidden discharge target, and uses LOSPredictor output.

Patient streams: by default every episode replays the patient file. Pass
`patient_source` (e.g. simulator.patients.streams.StreamSampler) so each reset()
draws a fresh stream, or `reset(options={"patients": [...]})` for an explicit one.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np
import gymnasium as gym
from gymnasium import spaces

from ml.los.predictor import LOSPredictor
from simulator.hospital.allocation_rules import AllocationDecision, allocation_for_bed_type
from rl.environment.rewards import (DEFAULT_ACUITY_WEIGHTS, QueueCostTracker,
                                    validate_weights)
from simulator.hospital.engine import SimulationEngine
from simulator.hospital.loader import load_hospital_state, load_patients
from simulator.hospital.state import HospitalState
from simulator.patients.patient import Patient

BED_ACTIONS = ("ICU", "STEP_DOWN", "WARD")
WAIT_ACTION = 3

# Order of the observation vector (all values in [0, 1]).
OBSERVATION_FEATURES = (
    "acuity",                      # acuity / 5
    "age_65_plus",
    "isolation_required",
    "ventilator_required",
    "los_estimate",                # LOS model estimate / 10 (never the true stay)
    "icu_beds_available",          # available / total, per tier
    "step_down_beds_available",
    "ward_beds_available",
    "ventilators_available",
    "waiting_queue_size",          # log1p(waiting) / log1p(200), capped at 1
    "icu_isolation_beds_available",        # available / total isolation-capable, per tier
    "step_down_isolation_beds_available",
    "ward_isolation_beds_available",
    "critical_share_of_queue",     # waiting patients with acuity >= 4 / waiting patients
)
N_OBSERVATIONS = len(OBSERVATION_FEATURES)

# Waiting-queue feature: log scale so that 3, 11 and 118 waiting patients stay
# distinguishable, and so the value does not depend on the size of the episode.
QUEUE_LOG_CAP = 200

REWARD_MODES = ("legacy", "queue_cost")


class CareGridHospitalEnv(gym.Env):
    """Event-driven, single-agent allocation environment over a synthetic episode.

    Observation: 14 float32 values in [0, 1], named in OBSERVATION_FEATURES. Besides
    the patient's attributes and the LOS estimate, the agent sees how many beds are
    free per tier, how many ISOLATION-capable beds are free per tier (isolation
    beds are the scarce resource that drives waiting), ventilator availability and
    the size / severity mix of the waiting queue.
    """

    metadata = {"render_modes": ["human"]}

    def __init__(
        self,
        data_dir: Optional[str | Path] = None,
        patient_file: str = "patients.csv",
        max_episode_days: float = 30.0,
        los_predictor: Optional[Any] = None,
        render_mode: Optional[str] = None,
        wait_penalty: float = 0.05,
        invalid_action_penalty: float = 1.0,
        admission_reward: float = 1.0,
        patient_source: Optional[Callable[[np.random.Generator], list]] = None,
        reward_mode: str = "legacy",
        acuity_weights: Optional[dict] = None,
        reward_scale: float = 10.0,
    ) -> None:
        super().__init__()
        project_root = Path(__file__).resolve().parents[2]
        self.data_dir = Path(data_dir) if data_dir else project_root / "data" / "synthetic"
        self.patient_file = patient_file
        self.max_episode_days = float(max_episode_days)
        if self.max_episode_days <= 0:
            raise ValueError("max_episode_days must be positive")
        self.los_predictor = los_predictor
        self.render_mode = render_mode
        self.wait_penalty = float(wait_penalty)
        self.invalid_action_penalty = float(invalid_action_penalty)
        self.admission_reward = float(admission_reward)
        self.patient_source = patient_source
        if reward_mode not in REWARD_MODES:
            raise ValueError(f"reward_mode must be one of {REWARD_MODES}, got {reward_mode!r}")
        if reward_scale <= 0:
            raise ValueError("reward_scale must be positive")
        self.reward_mode = reward_mode
        self.acuity_weights = validate_weights(acuity_weights)
        self.reward_scale = float(reward_scale)
        self._tracker = QueueCostTracker(self.acuity_weights)
        self._user_tick: Optional[Callable] = None
        self.action_space = spaces.Discrete(4)
        self.observation_space = spaces.Box(
            low=0.0, high=1.0, shape=(N_OBSERVATIONS,), dtype=np.float32)
        self.state: Optional[HospitalState] = None
        self.engine: Optional[SimulationEngine] = None
        self._patients: dict[str, Patient] = {}
        self._los_estimates: dict[str, float] = {}
        self._start_time: Optional[datetime] = None
        self._end_time: Optional[datetime] = None
        self._current_patient_id: Optional[str] = None
        self._done = False
        self._decision_count = 0
        self._last_info: dict[str, Any] = {}

    @property
    def current_patient(self) -> Optional[Patient]:
        """The patient the agent is currently deciding for (None between episodes)."""
        if self._current_patient_id is None:
            return None
        return self._patients.get(self._current_patient_id)

    def _on_tick(self, state: HospitalState) -> None:
        """Engine hook: charge the queue cost, then forward to the caller's own hook
        (e.g. a MetricsCollector given through reset(options={'on_tick': ...}))."""
        if self.reward_mode == "queue_cost":
            self._tracker.update(state, self._patients)
        if self._user_tick is not None:
            self._user_tick(state)

    def valid_actions(self) -> np.ndarray:
        """Boolean mask over the 4 actions for the CURRENT patient: True where the hard
        rules (tier for the acuity, isolation bed, ventilator, bed free) allow it.
        WAIT is always valid. Use it to mask Q-values when acting (never to train)."""
        mask = np.zeros(4, dtype=bool)
        mask[WAIT_ACTION] = True
        patient = self.current_patient
        if patient is None or self.state is None:
            return mask
        for index, bed_type in enumerate(BED_ACTIONS):
            decision, _ = allocation_for_bed_type(patient, self.state, bed_type)
            mask[index] = decision is not None
        return mask

    def _ensure_predictor(self) -> Any:
        if self.los_predictor is None:
            self.los_predictor = LOSPredictor.load()
        return self.los_predictor

    def _estimate_los(self, patients: list) -> dict[str, float]:
        """One batched LOS-model call per episode instead of one per step (a single
        call costs ~10 ms, a batch ~0.06 ms per patient). The estimate depends only on
        attributes known at arrival, so it can be computed up front without leaking
        anything about the future or the true stay."""
        predictor = self._ensure_predictor()
        if hasattr(predictor, "predict_many"):
            values = predictor.predict_many(patients)
        else:
            values = [predictor.predict(p) for p in patients]
        return {p.patient_id: float(v) for p, v in zip(patients, values)}

    def reset(self, *, seed: Optional[int] = None, options: Optional[dict] = None):
        super().reset(seed=seed)
        # Seed is accepted for Gymnasium reproducibility. The supplied patient
        # arrival file is fixed; stochastic extensions should use self.np_random.
        self.state = load_hospital_state(str(self.data_dir), start_empty=True)
        if options and options.get("patients") is not None:
            loaded_patients = deepcopy(list(options["patients"]))
        elif self.patient_source is not None:
            loaded_patients = list(self.patient_source(self.np_random))
        else:
            loaded_patients = load_patients(str(self.data_dir), self.patient_file)
        if not loaded_patients:
            raise ValueError("The episode has no patients (empty file, stream or options)")
        self._patients = {patient.patient_id: patient for patient in loaded_patients}
        self._los_estimates = self._estimate_los(loaded_patients)
        self.engine = SimulationEngine(self.state, list(self._patients.values()))
        self._user_tick = (options or {}).get("on_tick")
        self._tracker.reset()
        self.engine.enable_external_decisions(on_tick=self._on_tick)
        self.engine.seed_arrivals()
        self._start_time = min(p.arrival_time for p in self._patients.values())
        self._end_time = self._start_time + timedelta(days=self.max_episode_days)
        self._current_patient_id = None
        self._done = False
        self._decision_count = 0
        self._last_info = {}
        self._advance_to_decision()
        return self._observation(), self._info()

    def step(self, action: int):
        if self._done or self.engine is None or self.state is None:
            raise RuntimeError("Episode is finished. Call reset() before step().")
        if self._current_patient_id is None:
            self._finish_episode(truncated=False)
            return self._observation(), 0.0, True, False, self._info()

        patient = self._patients[self._current_patient_id]
        reward = 0.0
        action = int(action)
        admitted = False
        invalid_reason = None
        allocation = None

        if action == WAIT_ACTION:
            self.engine.defer_pending_patient()
            reward -= self.wait_penalty
        elif action not in (0, 1, 2):
            invalid_reason = "action_out_of_range"
            self.engine.defer_pending_patient()
            reward -= self.invalid_action_penalty
        else:
            requested_type = BED_ACTIONS[action]
            allocation, invalid_reason = self._allocation_for(patient, requested_type)
            if allocation is None:
                # Hard constraint: no unsafe allocation occurs. Invalid choice is
                # treated as wait, so the episode always makes progress.
                self.engine.defer_pending_patient()
                reward -= self.invalid_action_penalty
            else:
                self.engine.admit_pending_patient(allocation)
                admitted = True
                reward += self.admission_reward
                # Small preference for avoiding unnecessary waits while keeping
                # the reward scale interpretable for later DQN experiments.
                if patient.arrival_time and self.state.current_time:
                    elapsed_days = max(0.0, (self.state.current_time - patient.arrival_time).total_seconds() / 86400)
                    reward -= min(elapsed_days, 10.0) * self.wait_penalty

        self._decision_count += 1
        self._last_info = {
            "patient_id": patient.patient_id,
            "action": action,
            "requested_bed_type": BED_ACTIONS[action] if action in (0, 1, 2) else "WAIT" if action == WAIT_ACTION else "INVALID",
            "admitted": admitted,
            "invalid_reason": invalid_reason,
            "allocation": ({"bed_id": allocation.bed_id, "equipment_id": allocation.equipment_id} if allocation else None),
            "decision_count": self._decision_count,
        }
        self._advance_to_decision()
        if self.reward_mode == "queue_cost":
            if self._done:
                self._tracker.close(self._end_time)
            cost = self._tracker.pop()
            reward = -cost / self.reward_scale
            if invalid_reason is not None:
                reward -= self.invalid_action_penalty
            self._last_info["queue_cost"] = cost
        terminated = self._done and not self._last_info.get("time_limit_reached", False)
        truncated = self._done and self._last_info.get("time_limit_reached", False)
        return self._observation(), float(reward), terminated, truncated, self._info()

    def _allocation_for(self, patient: Patient, bed_type: str):
        """Use the simulator's shared feasibility rules for an agent action."""
        assert self.state is not None
        return allocation_for_bed_type(patient, self.state, bed_type)

    def _advance_to_decision(self) -> None:
        assert self.engine is not None and self.state is not None and self._end_time is not None
        patient_id = self.engine.advance_to_decision(max_time=self._end_time)
        if patient_id is None:
            time_limit = not self.engine.queue.is_empty() and self.engine.queue.peek().timestamp > self._end_time
            self._finish_episode(truncated=time_limit)
            self._current_patient_id = None
        else:
            self._current_patient_id = patient_id

    def _finish_episode(self, truncated: bool) -> None:
        self._done = True
        self._last_info["time_limit_reached"] = bool(truncated)
        self._last_info["episode_summary"] = {
            "admitted": self.engine.admitted_count if self.engine else 0,
            "discharged": self.engine.discharged_count if self.engine else 0,
            "waiting": len(self.state.waiting_queue) if self.state else 0,
            "decisions": self._decision_count,
        }

    def _observation(self) -> np.ndarray:
        assert self.state is not None
        patient = self._patients.get(self._current_patient_id) if self._current_patient_id else None
        if patient is None:
            # Terminal observation is all zeros; no hidden patient target is exposed.
            return np.zeros(N_OBSERVATIONS, dtype=np.float32)
        predicted_los = self._los_estimates[patient.patient_id]
        values = [
            patient.acuity / 5.0,
            1.0 if patient.age_group in ("65+", "65_PLUS", "SENIOR", "ELDERLY") else 0.0,
            float(patient.isolation_required),
            float(patient.ventilator_required),
            min(max(predicted_los, 1.0), 10.0) / 10.0,
        ]
        for bed_type in BED_ACTIONS:
            beds = self.state.beds_by_type(bed_type)
            available = sum(b.status == "AVAILABLE" for b in beds)
            values.append(available / len(beds) if beds else 0.0)
        vents = [e for e in self.state.equipment.values() if e.type == "VENTILATOR"]
        available_vents = sum(e.status == "AVAILABLE" for e in vents)
        values.append(available_vents / len(vents) if vents else 0.0)
        values.append(min(float(np.log1p(len(self.state.waiting_queue))) / np.log1p(QUEUE_LOG_CAP), 1.0))
        for bed_type in BED_ACTIONS:
            iso_beds = [b for b in self.state.beds_by_type(bed_type) if b.isolation_capable]
            free = sum(b.status == "AVAILABLE" for b in iso_beds)
            values.append(free / len(iso_beds) if iso_beds else 0.0)
        waiting = self.state.waiting_queue
        critical = sum(self._patients[pid].acuity >= 4 for pid in waiting)
        values.append(critical / len(waiting) if waiting else 0.0)
        return np.asarray(values, dtype=np.float32)

    def _info(self) -> dict[str, Any]:
        info = dict(self._last_info)
        if self.state is not None:
            info["simulation_time"] = self.state.current_time.isoformat() if self.state.current_time else None
            info["waiting_count"] = len(self.state.waiting_queue)
            info["admitted_count"] = self.engine.admitted_count if self.engine else 0
        # which actions are valid for the NEXT decision (used for masked Bellman targets)
        info["next_valid_actions"] = self.valid_actions().tolist()
        return info

    def render(self):
        if self.render_mode == "human" and self.state is not None:
            print(self.state.snapshot())

    def close(self):
        self._done = True
