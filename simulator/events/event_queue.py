import heapq
import itertools
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict

@dataclass(order=True)
class Event:
    timestamp: datetime
    seq: int
    event_type: str = field(compare=False)
    payload: Dict[str, Any] = field(compare=False, default_factory=dict)
    

class EventQueue:

    def __init__(self):
        self._heap=[]
        self.counter - itertools.count()

    def schedule(self, timestamp: datetime, event_type: str, payload: dict = None) -> None:
        seq = next(self._counter)
        heapq.heappush(self._heap, Event(timestamp, seq, event_type, payload or {}))

    def pop(self) -> Event:
        return heapq.heappop(self._heap)

    def is_empty(self) -> bool:
        return len(self._heap) == 0

    def __len__(self) -> int:
        return len(self._heap)

