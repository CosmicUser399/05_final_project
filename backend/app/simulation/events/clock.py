"""Simulation clock (current time in minutes)."""


class SimulationClock:
    """Monotonic simulation time in canonical minutes."""

    def __init__(self, start: float = 0.0) -> None:
        """Create a clock at ``start`` minutes."""
        if start < 0:
            raise ValueError("clock start must be >= 0")
        self._time = float(start)

    @property
    def time(self) -> float:
        """Return the current simulation time."""
        return self._time

    def advance_to(self, time: float) -> float:
        """Advance to ``time`` and return the elapsed delta.

        Raises ``ValueError`` if ``time`` is earlier than now.
        """
        if time < self._time:
            raise ValueError(
                f"cannot move clock backwards: {time} < {self._time}"
            )
        delta = time - self._time
        self._time = float(time)
        return delta
