"""
CareGrid-RL: acuity-weighted queue-cost reward (Phase 8)

The agent is charged for every minute patients spend waiting, weighted by how urgent
they are:

    cost = sum over waiting patients p of  weight[acuity_p] * elapsed_days

The waiting set only changes at simulation events, so the integral is exact: the
tracker is called by the engine's tick hook after every event and decision and adds
(time since the previous tick) x (weighted size of the queue during that time).
Over a whole episode the accumulated cost is exactly

    sum over patients of  weight[acuity] * wait_days     (waits censored at the horizon end)

which is the acuity-weighted wait that the evaluation harness reports.
"""
from datetime import datetime
from typing import Dict, Mapping, Optional

DEFAULT_ACUITY_WEIGHTS: Dict[int, float] = {1: 1.0, 2: 1.0, 3: 2.0, 4: 4.0, 5: 8.0}


def validate_weights(weights: Optional[Mapping[int, float]]) -> Dict[int, float]:
    """Returns a clean copy of the weights (default table when None)."""
    if weights is None:
        return dict(DEFAULT_ACUITY_WEIGHTS)
    clean = {int(k): float(v) for k, v in weights.items()}
    missing = [a for a in range(1, 6) if a not in clean]
    if missing:
        raise ValueError(f"acuity_weights must define acuity levels 1-5 (missing {missing})")
    if any(v <= 0 for v in clean.values()):
        raise ValueError("acuity_weights must all be positive")
    return clean


class QueueCostTracker:
    def __init__(self, weights: Mapping[int, float]):
        self.weights = validate_weights(weights)
        self.reset()

    def reset(self) -> None:
        self._last_time: Optional[datetime] = None
        self._weighted_queue = 0.0
        self._accrued = 0.0

    def update(self, state, patients) -> None:
        """Call after every engine event / decision with the current state."""
        now = state.current_time
        if now is None:
            return
        if self._last_time is not None and now > self._last_time:
            days = (now - self._last_time).total_seconds() / 86400.0
            self._accrued += days * self._weighted_queue
        self._last_time = now
        self._weighted_queue = sum(
            self.weights[patients[pid].acuity] for pid in state.waiting_queue)

    def close(self, end_time: datetime) -> None:
        """Charge the still-waiting patients until the common horizon end, so every
        policy is costed to the same instant (also when the event queue ran dry)."""
        if self._last_time is not None and end_time > self._last_time:
            days = (end_time - self._last_time).total_seconds() / 86400.0
            self._accrued += days * self._weighted_queue
            self._last_time = end_time

    def pop(self) -> float:
        """Cost accrued since the previous pop (in weighted patient-days)."""
        value, self._accrued = self._accrued, 0.0
        return value
