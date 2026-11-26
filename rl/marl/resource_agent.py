"""
Resource Manager Agent – Meso-level supply-side coordinator.

Monitors bed cleaning backlogs, ventilator maintenance/availability, and
critical-care staffing levels, and triggers targeted operational interventions:
  0: HOLD (no intervention cost)
  1: EXPEDITE_CLEANING (reduce ICU/Step-Down cleaning time 25m -> 10m)
  2: MOBILIZE_VENTILATOR (pull a ventilator out of MAINTENANCE)
  3: FLOAT_STAFF (reassign lowest-workload General/Step-down RN to Critical-care)
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional
import numpy as np

RESOURCE_HOLD = 0
RESOURCE_EXPEDITE_CLEANING = 1
RESOURCE_MOBILIZE_VENT = 2
RESOURCE_FLOAT_STAFF = 3

RESOURCE_ACTION_NAMES = (
    "HOLD",
    "EXPEDITE_CLEANING",
    "MOBILIZE_VENTILATOR",
    "FLOAT_STAFF",
)


class ResourceManagerAgent:
    """Supply-side Resource Manager policy.

    Observation: (8,) float32 vector in [0, 1]:
      [icu_cleaning_ratio, sd_cleaning_ratio, vent_maint_ratio, vent_avail_ratio,
       crit_staff_ratio, queue_log_norm, critical_share, surge_mode_flag]
    Action: Discrete(4)
    """

    def __init__(
        self,
        weights: Optional[np.ndarray] = None,
        bias: Optional[np.ndarray] = None,
    ) -> None:
        if weights is not None:
            self.W = np.asarray(weights, dtype=np.float32)
            self.b = (
                np.asarray(bias, dtype=np.float32)
                if bias is not None
                else np.zeros(4, dtype=np.float32)
            )
        else:
            # Clinically calibrated prior over 8 features -> 4 actions
            # Columns: [HOLD, EXPEDITE_CLEANING, MOBILIZE_VENT, FLOAT_STAFF]
            self.W = np.array([
                [-0.5,  3.0,  0.0,  0.0],  # icu_cleaning_ratio
                [-0.3,  1.8,  0.0,  0.0],  # sd_cleaning_ratio
                [-0.2,  0.0,  3.5,  0.0],  # vent_maint_ratio
                [ 0.8,  0.0, -2.5,  0.0],  # vent_avail_ratio (low avail -> mobilize)
                [ 0.5,  0.0,  0.0, -2.0],  # crit_staff_ratio (low crit staff -> float)
                [-0.8,  1.2,  1.0,  1.0],  # queue_log_norm
                [-0.5,  1.0,  1.2,  1.2],  # critical_share
                [-0.4,  0.8,  0.8,  0.8],  # surge_mode_flag
            ], dtype=np.float32)
            self.b = np.array([1.2, -0.2, -0.3, -0.4], dtype=np.float32)

    def q_values(self, obs: np.ndarray) -> np.ndarray:
        x = np.asarray(obs, dtype=np.float32).ravel()
        return x @ self.W + self.b

    def predict(
        self,
        obs: np.ndarray,
        valid_mask: Optional[np.ndarray] = None,
        deterministic: bool = True,
    ) -> int:
        q = self.q_values(obs)
        if valid_mask is not None:
            mask = np.asarray(valid_mask, dtype=bool)
            if mask.any():
                q = np.where(mask, q, -np.inf)
        return int(np.argmax(q))

    def update(
        self,
        obs: np.ndarray,
        action: int,
        reward: float,
        next_obs: np.ndarray,
        done: bool,
        lr: float = 0.01,
        gamma: float = 0.95,
    ) -> float:
        target = reward + (0.0 if done else gamma * float(np.max(self.q_values(next_obs))))
        curr_q = float(self.q_values(obs)[action])
        error = float(np.clip(target - curr_q, -10.0, 10.0))
        x = np.asarray(obs, dtype=np.float32).ravel()
        self.W[:, action] += lr * error * x
        self.b[action] += lr * error
        return error

    def save(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        np.savez(p, W=self.W, b=self.b)

    @classmethod
    def load(cls, path: str | Path) -> "ResourceManagerAgent":
        data = np.load(Path(path))
        return cls(weights=data["W"], bias=data["b"])
