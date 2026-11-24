"""
Hierarchical Multi-Agent Environment for CareGrid.

Coordinates:
  1. Surge Agent (Macro): acts every K decisions, toggling NORMAL vs SURGE mode.
  2. Bed Agent (Micro): acts on every patient, executing bed allocations with
     constraints conditioned on the current macro mode.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple
import numpy as np
import gymnasium as gym
from gymnasium import spaces

from rl.environment.hospital_env import (
    BED_ACTIONS,
    WAIT_ACTION,
    QUEUE_LOG_CAP,
    CareGridHospitalEnv,
)
from rl.serving.numpy_policy import NumpyQPolicy
from simulator.hospital.allocation_rules import allocation_for_bed_type, candidate_bed_types
from simulator.hospital.state import HospitalState

MODE_NORMAL = 0
MODE_SURGE = 1


class CareGridMAEnv(gym.Env):
    """Two-agent hierarchical coordination environment."""

    metadata = {"render_modes": ["human"]}

    def __init__(
        self,
        base_env: Optional[CareGridHospitalEnv] = None,
        bed_policy: Optional[Any] = None,
        macro_interval: int = 10,
        icu_reserve_ratio: float = 0.20,
    ) -> None:
        super().__init__()
        self.env = base_env or CareGridHospitalEnv(observation_version=2)
        self.macro_interval = int(macro_interval)
        self.icu_reserve_ratio = float(icu_reserve_ratio)

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

        self.current_mode = MODE_NORMAL
        self.episode_decisions = 0
        self.mode_history = []

    def _get_surge_obs(self) -> np.ndarray:
        state: HospitalState = self.env.state
        if state is None:
            return np.zeros(6, dtype=np.float32)

        # ICU availability
        icu_beds = state.beds_by_type("ICU")
        icu_avail = sum(b.status == "AVAILABLE" for b in icu_beds) / len(icu_beds) if icu_beds else 0.0

        # Step-down availability
        sd_beds = state.beds_by_type("STEP_DOWN")
        sd_avail = sum(b.status == "AVAILABLE" for b in sd_beds) / len(sd_beds) if sd_beds else 0.0

        # Queue log normalized
        q_len = len(state.waiting_queue)
        q_norm = min(float(np.log1p(q_len)) / np.log1p(QUEUE_LOG_CAP), 1.0)

        # Critical share of queue
        waiting = state.waiting_queue
        if waiting and hasattr(self.env, "_patients"):
            crit = sum(self.env._patients[pid].acuity >= 4 for pid in waiting if pid in self.env._patients)
            crit_share = crit / len(waiting)
        else:
            crit_share = 0.0

        # Time of day
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

    def reset(
        self, *, seed: Optional[int] = None, options: Optional[dict] = None
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        super().reset(seed=seed)
        obs, info = self.env.reset(seed=seed, options=options)
        self.current_mode = MODE_NORMAL
        self.episode_decisions = 0
        self.mode_history = []
        return self._get_surge_obs(), {"micro_info": info}

    def _select_bed_action(self, micro_obs: np.ndarray) -> int:
        patient = self.env.current_patient
        if patient is None or self.env.state is None:
            return WAIT_ACTION

        valid_mask = self.env.valid_actions()

        # In SURGE mode: reserve ICU beds strictly for acuity 5 critical patients
        if self.current_mode == MODE_SURGE:
            if patient.acuity < 5:
                icu_beds = self.env.state.beds_by_type("ICU")
                total_icu = len(icu_beds)
                free_icu = sum(b.status == "AVAILABLE" for b in icu_beds)
                # If free ICU beds are within or below reserve threshold, forbid ICU for acuity < 5
                if free_icu <= max(1, int(total_icu * self.icu_reserve_ratio)):
                    valid_mask[0] = False  # Mask out ICU

        if self.bed_policy is not None:
            try:
                return self.bed_policy.best_action(micro_obs, valid_mask=valid_mask)
            except Exception:
                pass

        # Fallback heuristic: lowest tier first among valid
        for tier_idx in (2, 1, 0):  # WARD -> STEP_DOWN -> ICU
            if valid_mask[tier_idx]:
                return tier_idx
        return WAIT_ACTION

    def step(
        self, surge_action: int
    ) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
        self.current_mode = int(surge_action)
        self.mode_history.append(self.current_mode)

        total_micro_reward = 0.0
        decisions_executed = 0
        done = False
        terminated = False
        truncated = False
        last_micro_info = {}

        # Run micro bed agent for macro_interval steps (or until episode termination)
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

        surge_info = {
            "mode": "SURGE" if self.current_mode == MODE_SURGE else "NORMAL",
            "decisions_in_macro_step": decisions_executed,
            "total_decisions": self.episode_decisions,
            "micro_info": last_micro_info,
        }

        is_done = self.env._done or terminated or truncated
        return surge_obs, float(total_micro_reward), bool(terminated or is_done), bool(truncated), surge_info

