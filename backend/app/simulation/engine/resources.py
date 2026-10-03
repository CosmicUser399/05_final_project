"""Shared resource capacity and waiting queues."""

from __future__ import annotations

from collections import defaultdict
from collections import deque
from dataclasses import dataclass
from dataclasses import field
from uuid import UUID

from app.domain.reliability.compiled import CompiledResource
from app.domain.reliability.compiled import CompiledResourceReq


@dataclass(slots=True)
class ResourceLease:
    """Granted resource allocation for one maintenance job."""

    job_id: UUID
    allocations: dict[UUID, int]


@dataclass(slots=True)
class _Waiter:
    job_id: UUID
    requirements: tuple[CompiledResourceReq, ...]
    requested_at: float


@dataclass(slots=True)
class ResourceManager:
    """Track free capacity and a FIFO wait queue per resource."""

    capacity: dict[UUID, int]
    available: dict[UUID, int] = field(default_factory=dict)
    waiters: deque[_Waiter] = field(default_factory=deque)
    leases: dict[UUID, ResourceLease] = field(default_factory=dict)
    wait_started: dict[UUID, float] = field(default_factory=dict)
    total_wait_minutes: float = 0.0

    @classmethod
    def from_resources(
        cls, resources: tuple[CompiledResource, ...]
    ) -> ResourceManager:
        """Build a manager from compiled resource rows."""
        capacity = {r.id: r.capacity for r in resources}
        return cls(
            capacity=capacity,
            available=dict(capacity),
        )

    def can_acquire(
        self, requirements: tuple[CompiledResourceReq, ...]
    ) -> bool:
        """Return whether all requirements are free right now."""
        if not requirements:
            return True
        needed: dict[UUID, int] = defaultdict(int)
        for req in requirements:
            needed[req.resource_id] += req.quantity
        for resource_id, quantity in needed.items():
            free = self.available.get(resource_id, 0)
            if quantity > free:
                return False
        return True

    def acquire(
        self,
        job_id: UUID,
        requirements: tuple[CompiledResourceReq, ...],
        now: float,
    ) -> bool:
        """Try to acquire resources for ``job_id``.

        On success returns ``True``. On failure the job is queued and
        the method returns ``False``.
        """
        if job_id in self.leases:
            return True
        if self.can_acquire(requirements):
            self._take(job_id, requirements)
            if job_id in self.wait_started:
                self.total_wait_minutes += now - self.wait_started.pop(job_id)
            return True
        if any(waiter.job_id == job_id for waiter in self.waiters):
            return False
        self.waiters.append(
            _Waiter(
                job_id=job_id,
                requirements=requirements,
                requested_at=now,
            )
        )
        self.wait_started.setdefault(job_id, now)
        return False

    def release(self, job_id: UUID) -> list[UUID]:
        """Release a lease and grant resources to waiting jobs.

        Returns job ids that became ready (acquired successfully).
        """
        lease = self.leases.pop(job_id, None)
        if lease is not None:
            for resource_id, quantity in lease.allocations.items():
                self.available[resource_id] = (
                    self.available.get(resource_id, 0) + quantity
                )
        ready: list[UUID] = []
        if not self.waiters:
            return ready
        remaining: deque[_Waiter] = deque()
        while self.waiters:
            waiter = self.waiters.popleft()
            if self.can_acquire(waiter.requirements):
                self._take(waiter.job_id, waiter.requirements)
                if waiter.job_id in self.wait_started:
                    # wait end time is applied by caller via acquire path;
                    # here we only mark readiness; engine closes wait.
                    pass
                ready.append(waiter.job_id)
            else:
                remaining.append(waiter)
        self.waiters = remaining
        return ready

    def close_wait(self, job_id: UUID, now: float) -> None:
        """Accumulate waiting time when a queued job finally starts."""
        started = self.wait_started.pop(job_id, None)
        if started is not None:
            self.total_wait_minutes += now - started

    def _take(
        self,
        job_id: UUID,
        requirements: tuple[CompiledResourceReq, ...],
    ) -> None:
        allocations: dict[UUID, int] = defaultdict(int)
        for req in requirements:
            allocations[req.resource_id] += req.quantity
            self.available[req.resource_id] = (
                self.available.get(req.resource_id, 0) - req.quantity
            )
        self.leases[job_id] = ResourceLease(
            job_id=job_id, allocations=dict(allocations)
        )
