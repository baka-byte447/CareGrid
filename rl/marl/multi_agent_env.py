"""
Hierarchical Multi-Agent Environment for CareGrid (3-Agent Coordination).

Coordinates:
  1. Surge Agent (Macro): acts every K decisions, toggling NORMAL vs SURGE mode.
  2. Resource Manager Agent (Meso): acts every K decisions, managing bed
     turnover cleaning speed, ventilator mobilization, and nurse floating.
  3. Bed Agent (Micro): acts on every patient, executing bed allocations with
     constraints conditioned on the current macro mode and live supply.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple, Union
import numpy as np
import gymnasium as gym
from gymnasium import spaces

from rl.environment.hospital_env import (
    WAIT_ACTION,
    QUEUE_LOG_CAP,
    CareGridHospitalEnv,
)
from rl.marl.resource_agent import (
    RESOURCE_ACTION_NAMES,
    RESOURCE_EXPEDITE_CLEANING,
    RESOURCE_FLOAT_STAFF,
    RESOURCE_HOLD,
    RESOURCE_MOBILIZE_VENT,
)
from rl.serving.numpy_policy import NumpyQPolicy
from simulator.hospital.state import HospitalState

MODE_NORMAL = 0
MODE_SURGE = 1


class CareGridMAEnv(gym.Env):
    """Three-agent hierarchical coordination environment."""

    metadata = {"render_modes": ["human"]}

    def __init__(
        self,
        base_env: Optional[CareGridHospitalEnv] = None,
        bed_policy: Optional[Any] = None,
        macro_interval: int = 10,
        icu_reserve_ratio: float = 0.20,
        resource_intervention_cost: float = 0.05,
    ) -> None:
        super().__init__()
        self.env = base_env or CareGridHospitalEnv(observation_version=2)
        self.macro_interval = int(macro_interval)
        self.icu_reserve_ratio = float(icu_reserve_ratio)
        self.resource_intervention_cost = float(resource_intervention_cost)

        # Bed policy (NumpyQPolicy or fallback)
        self.bed_policy = bed_policy
        if self.bed_policy is None:
            from rl.serving.service import DEFAULT_MODEL_PATH
            if DEFAULT_MODEL_PATH.exists():
                try:
                    self.bed_policy = NumpyQPolicy(DEFAULT_MODEL_PATH)
                except Exception:
                    self.bed_policy = None

        # Surge agent observation & action spaces
        # [icu_avail, step_down_avail, queue_log_norm, critical_share, tod_sin, tod_cos]
        self.observation_space = spaces.Box(
            low=0.0, high=1.0, shape=(6,), dtype=np.float32
        )
        self.action_space = spaces.Discrete(2)

        # Resource Manager observation & action spaces
        self.resource_observation_space = spaces.Box(
            low=0.0, high=1.0, shape=(8,), dtype=np.float32
        )
        self.resource_action_space = spaces.Discrete(4)

        self.current_mode = MODE_NORMAL
        self.episode_decisions = 0
        self.mode_history: list[int] = []
        self.resource_history: list[int] = []

    def _get_surge_obs(self) -> np.ndarray:
        state: HospitalState = self.env.state
        if state is None:
            return np.zeros(6, dtype=np.float32)

        icu_beds = state.beds_by_type("ICU")
        icu_avail = sum(b.status == "AVAILABLE" for b in icu_beds) / len(icu_beds) if icu_beds else 0.0

        sd_beds = state.beds_by_type("STEP_DOWN")
        sd_avail = sum(b.status == "AVAILABLE" for b in sd_beds) / len(sd_beds) if sd_beds else 0.0

        q_len = len(state.waiting_queue)
        q_norm = min(float(np.log1p(q_len)) / np.log1p(QUEUE_LOG_CAP), 1.0)

        waiting = state.waiting_queue
        if waiting and hasattr(self.env, "_patients"):
            crit = sum(self.env._patients[pid].acuity >= 4 for pid in waiting if pid in self.env._patients)
            crit_share = crit / len(waiting)
        else:
            crit_share = 0.0

        if state.current_time:
            hour = state.current_time.hour + state.current_time.minute / 60.0
            tod_sin = (np.sin(2.0 * np.pi * hour / 24.0) + 1.0) / 2.0
            tod_cos = (np.cos(2.0 * np.pi * hour / 24.0) + 1.0) / 2.0
        else:
            tod_sin, tod_cos = 0.5, 0.5

        return np.asarray(
            [icu_avail, sd_avail, q_norm, crit_share, tod_sin, tod_cos],
            dtype=np.float32,
        )

    def get_resource_obs(self) -> np.ndarray:
        """Build 8-feature observation vector for the Resource Manager Agent."""
        state: HospitalState = self.env.state
        if state is None:
            return np.zeros(8, dtype=np.float32)

        icu_beds = state.beds_by_type("ICU")
        icu_cleaning = len(state.cleaning_beds_by_type("ICU")) / len(icu_beds) if icu_beds else 0.0

        sd_beds = state.beds_by_type("STEP_DOWN")
        sd_cleaning = len(state.cleaning_beds_by_type("STEP_DOWN")) / len(sd_beds) if sd_beds else 0.0

        vents = [e for e in state.equipment.values() if e.type == "VENTILATOR"]
        vent_maint = len(state.maintenance_ventilators()) / len(vents) if vents else 0.0
        vent_avail = len(state.available_ventilators()) / len(vents) if vents else 0.0

        total_staff = len(state.staff)
        crit_staff = len(state.staff_by_skill("Critical-care")) / total_staff if total_staff else 0.0

        q_len = len(state.waiting_queue)
        q_norm = min(float(np.log1p(q_len)) / np.log1p(QUEUE_LOG_CAP), 1.0)

        waiting = state.waiting_queue
        if waiting and hasattr(self.env, "_patients"):
            crit = sum(self.env._patients[pid].acuity >= 4 for pid in waiting if pid in self.env._patients)
            crit_share = crit / len(waiting)
        else:
            crit_share = 0.0

        surge_flag = 1.0 if self.current_mode == MODE_SURGE else 0.0

        return np.asarray(
            [icu_cleaning, sd_cleaning, vent_maint, vent_avail, crit_staff, q_norm, crit_share, surge_flag],
            dtype=np.float32,
        )

    def valid_resource_actions(self) -> np.ndarray:
        """Boolean mask over the 4 Resource Manager actions."""
        mask = np.zeros(4, dtype=bool)
        mask[RESOURCE_HOLD] = True
        state = self.env.state
        if state is None:
            return mask
        mask[RESOURCE_EXPEDITE_CLEANING] = bool(
            state.cleaning_beds_by_type("ICU") or state.cleaning_beds_by_type("STEP_DOWN")
        )
        mask[RESOURCE_MOBILIZE_VENT] = bool(state.maintenance_ventilators())
        mask[RESOURCE_FLOAT_STAFF] = bool(
            state.staff_by_skill("General") or state.staff_by_skill("Step-down")
        )
        return mask

    def _apply_resource_action(self, action: int) -> Tuple[bool, float]:
        """Execute a Resource Manager intervention on the underlying engine."""
        engine = self.env.engine
        if engine is None or action == RESOURCE_HOLD:
            return False, 0.0

        applied = False
        if action == RESOURCE_EXPEDITE_CLEANING:
            acc_icu = engine.expedite_cleaning("ICU", minutes=10)
            acc_sd = engine.expedite_cleaning("STEP_DOWN", minutes=12)
            applied = (acc_icu + acc_sd) > 0
        elif action == RESOURCE_MOBILIZE_VENT:
            applied = engine.mobilize_ventilator() is not None
        elif action == RESOURCE_FLOAT_STAFF:
            moved = engine.float_staff("General", "Critical-care")
            if moved is None:
                moved = engine.float_staff("Step-down", "Critical-care")
            applied = moved is not None

        cost = self.resource_intervention_cost if applied else 0.0
        return applied, cost

    def reset(
        self, *, seed: Optional[int] = None, options: Optional[dict] = None
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        super().reset(seed=seed)
        obs, info = self.env.reset(seed=seed, options=options)
        self.current_mode = MODE_NORMAL
        self.episode_decisions = 0
        self.mode_history = []
        self.resource_history = []
        return self._get_surge_obs(), {
            "micro_info": info,
            "resource_obs": self.get_resource_obs(),
        }

    def _select_bed_action(self, micro_obs: np.ndarray) -> int:
        patient = self.env.current_patient
        if patient is None or self.env.state is None:
            return WAIT_ACTION

        valid_mask = self.env.valid_actions()

        if self.current_mode == MODE_SURGE and patient.acuity < 5:
            icu_beds = self.env.state.beds_by_type("ICU")
            total_icu = len(icu_beds)
            free_icu = sum(b.status == "AVAILABLE" for b in icu_beds)
            if free_icu <= max(1, int(total_icu * self.icu_reserve_ratio)):
                valid_mask[0] = False

        if self.bed_policy is not None:
            try:
                return self.bed_policy.best_action(micro_obs, valid_mask=valid_mask)
            except Exception:
                pass

        for tier_idx in (2, 1, 0):
            if valid_mask[tier_idx]:
                return tier_idx
        return WAIT_ACTION

    def step(
        self,
        action: Union[int, Tuple[int, int], Dict[str, int]],
    ) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
        if isinstance(action, dict):
            surge_action = int(action.get("surge", MODE_NORMAL))
            resource_action = int(action.get("resource", RESOURCE_HOLD))
        elif isinstance(action, (tuple, list)):
            surge_action = int(action[0])
            resource_action = int(action[1])
        else:
            surge_action = int(action)
            resource_action = RESOURCE_HOLD

        self.current_mode = surge_action
        self.mode_history.append(self.current_mode)
        self.resource_history.append(resource_action)

        intervened, res_cost = self._apply_resource_action(resource_action)

        total_micro_reward = 0.0
        decisions_executed = 0
        terminated = False
        truncated = False
        last_micro_info = {}

        for _ in range(self.macro_interval):
            if self.env._done:
                break

            micro_obs = self.env._observation()
            bed_action = self._select_bed_action(micro_obs)
            next_obs, r, term, trunc, info = self.env.step(bed_action)

            total_micro_reward += r
            decisions_executed += 1
            last_micro_info = info

            if term or trunc:
                terminated = term
                truncated = trunc
                break

        self.episode_decisions += decisions_executed
        surge_obs = self._get_surge_obs()
        resource_obs = self.get_resource_obs()

        total_reward = float(total_micro_reward) - float(res_cost)

        surge_info = {
            "mode": "SURGE" if self.current_mode == MODE_SURGE else "NORMAL",
            "resource_action": RESOURCE_ACTION_NAMES[resource_action]
            if 0 <= resource_action < len(RESOURCE_ACTION_NAMES)
            else "HOLD",
            "resource_intervened": intervened,
            "resource_obs": resource_obs,
            "decisions_in_macro_step": decisions_executed,
            "total_decisions": self.episode_decisions,
            "micro_info": last_micro_info,
        }

        is_done = self.env._done or terminated or truncated
        return surge_obs, total_reward, bool(terminated or is_done), bool(truncated), surge_info
