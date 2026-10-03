"""Deterministic priority event queue."""

from __future__ import annotations

import heapq
from dataclasses import dataclass
from dataclasses import field

from app.simulation.events.types import SimulationEvent


@dataclass(order=True)
class _HeapItem:
    """Internal heap entry ordered by ``(time, seq)``."""

    time: float
    seq: int
    event: SimulationEvent = field(compare=False)


class EventQueue:
    """Min-heap of events with a deterministic tie-break.

    Events with equal time are ordered by the insertion sequence
    number ``seq`` (smaller first).
    """

    def __init__(self) -> None:
        """Create an empty queue."""
        self._heap: list[_HeapItem] = []
        self._next_seq = 0

    def __len__(self) -> int:
        """Return the number of pending events."""
        return len(self._heap)

    def schedule(self, event: SimulationEvent) -> SimulationEvent:
        """Push ``event``, assigning a monotonic ``seq``.

        Returns the scheduled event with its assigned ``seq``.
        """
        seq = self._next_seq
        self._next_seq += 1
        scheduled = event.model_copy(update={"seq": seq})
        heapq.heappush(
            self._heap,
            _HeapItem(time=scheduled.time, seq=seq, event=scheduled),
        )
        return scheduled

    def peek(self) -> SimulationEvent | None:
        """Return the next event without removing it."""
        if not self._heap:
            return None
        return self._heap[0].event

    def pop(self) -> SimulationEvent:
        """Remove and return the next event."""
        if not self._heap:
            raise IndexError("pop from empty EventQueue")
        return heapq.heappop(self._heap).event

    def clear(self) -> None:
        """Drop all pending events."""
        self._heap.clear()
