from datetime import datetime
from typing import Optional, Dict

from simulator.hospital.state import HospitalState

BED_TYPES = ("ICU", "STEP_DOWN", "WARD")

class MetricsCollector:
    def __init__(self, window_start:datetime, window_end:datetime):
        self.window_start = window_start
        self.window_end = window_end

        self._last_time:Optional[datetime] = None
        self._last_occupied:Dict[str,int] = {t:0 for t in BED_TYPES}
        self._last_vents_in_use = 0
        self.last_waiting = 0

        self.occupied_minutes : Dict[str, float] = {t:0.0 for t in BED_TYPES}
        self.vent_in_use_minutes = 0.0
        self.peak_waiting = 0

    def _overlap_minutes(self, a:datetime, b:datetime) -> float:
        lo = max(a, self.window_start)
        hi = min(b, self.window_end)
        return max((hi-lo).total_seconds()/60.0,0.0)

    def on_tick(self, state:HospitalState) -> None:
        now = state.current_time
        if self._last_time is not None:
            dt = self._overlap_minutes(self._last_time,now)
            if dt>0:
                for t in BED_TYPES:
                    self.occupied_minutes[t]+=self._last_occupied[t]*dt
                self.vent_in_use_minutes+=self._last_vents_in_use*dt

        self._last_time = now
        for t in BED_TYPES:
            self._last_occupied[t] = sum(
                1 for b in state.beds.values()
                if b.bed_type == t and b.status == "OCCUPIED"
            )
        self._last_vents_in_use = sum(
            1 for e in state.equipment.values()
            if e.type == "VENTILATOR" and e.status == "IN_USE"
        )
        self._last_waiting = len(state.waiting_queue)
        if self.window_start <= now <= self.window_end:
            self.peak_waiting = max(self.peak_waiting, self._last_waiting)

    @property
    def window_minutes(self) -> float:
        return (self.window_end - self.window_start).total_seconds()/60.0
        
        