"""Tests for SimulationClock and EventQueue."""

import pytest

from app.simulation.events import EventQueue
from app.simulation.events import EventType
from app.simulation.events import SimulationClock
from app.simulation.events import SimulationEvent


def test_clock_advances_and_rejects_backwards() -> None:
    clock = SimulationClock()
    assert clock.advance_to(10.0) == 10.0
    assert clock.time == 10.0
    with pytest.raises(ValueError):
        clock.advance_to(5.0)


def test_queue_orders_by_time_then_seq() -> None:
    queue = EventQueue()
    later = queue.schedule(
        SimulationEvent(time=20.0, event_type=EventType.FAILURE)
    )
    early_b = queue.schedule(
        SimulationEvent(time=10.0, event_type=EventType.DETECTION)
    )
    early_a = queue.schedule(
        SimulationEvent(time=10.0, event_type=EventType.POTENTIAL_FAILURE)
    )
    first = queue.pop()
    second = queue.pop()
    third = queue.pop()
    assert first.time == 10.0
    assert first.seq < second.seq
    assert {first.event_type, second.event_type} == {
        EventType.DETECTION,
        EventType.POTENTIAL_FAILURE,
    }
    assert first.event_type is EventType.DETECTION
    assert second.event_type is EventType.POTENTIAL_FAILURE
    assert third.event_type is EventType.FAILURE
    # ``later`` was scheduled first, so it has the smallest seq.
    assert later.seq < early_b.seq < early_a.seq
