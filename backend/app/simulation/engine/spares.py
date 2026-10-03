"""Spare-part stock, consumption and lead-time replenishment."""

from __future__ import annotations

from collections import defaultdict
from collections import deque
from dataclasses import dataclass
from dataclasses import field
from uuid import UUID

from app.domain.reliability.compiled import CompiledSparePart
from app.domain.reliability.compiled import CompiledSpareReq


@dataclass(slots=True)
class SpareGrant:
    """Spares reserved for one maintenance job."""

    job_id: UUID
    parts: dict[UUID, int]


@dataclass(slots=True)
class _SpareWaiter:
    job_id: UUID
    requirements: tuple[CompiledSpareReq, ...]
    requested_at: float


@dataclass(slots=True)
class SparePartManager:
    """On-hand stock with optional lead-time replenishment."""

    stock: dict[UUID, int]
    lead_time: dict[UUID, float]
    waiters: deque[_SpareWaiter] = field(default_factory=deque)
    grants: dict[UUID, SpareGrant] = field(default_factory=dict)
    pending_orders: dict[UUID, float] = field(default_factory=dict)
    wait_started: dict[UUID, float] = field(default_factory=dict)
    total_wait_minutes: float = 0.0
    consumed: dict[UUID, int] = field(default_factory=dict)

    @classmethod
    def from_spares(
        cls, spares: tuple[CompiledSparePart, ...]
    ) -> SparePartManager:
        """Build a manager from compiled spare rows."""
        return cls(
            stock={s.id: s.stock for s in spares},
            lead_time={
                s.id: float(s.lead_time_minutes or 0.0) for s in spares
            },
        )

    def can_consume(self, requirements: tuple[CompiledSpareReq, ...]) -> bool:
        """Return whether stock covers all requirements."""
        if not requirements:
            return True
        needed: dict[UUID, int] = defaultdict(int)
        for req in requirements:
            needed[req.spare_part_id] += req.quantity
        for spare_id, quantity in needed.items():
            if self.stock.get(spare_id, 0) < quantity:
                return False
        return True

    def request(
        self,
        job_id: UUID,
        requirements: tuple[CompiledSpareReq, ...],
        now: float,
    ) -> tuple[bool, list[tuple[UUID, float]]]:
        """Try to reserve spares for ``job_id``.

        Returns ``(ok, orders)`` where ``orders`` lists
        ``(spare_id, available_at)`` replenishment events to schedule
        when stock is insufficient.
        """
        if job_id in self.grants:
            return True, []
        if self.can_consume(requirements):
            self._consume(job_id, requirements)
            if job_id in self.wait_started:
                self.total_wait_minutes += now - self.wait_started.pop(job_id)
            return True, []
        if any(waiter.job_id == job_id for waiter in self.waiters):
            return False, []
        self.waiters.append(
            _SpareWaiter(
                job_id=job_id,
                requirements=requirements,
                requested_at=now,
            )
        )
        self.wait_started.setdefault(job_id, now)
        orders: list[tuple[UUID, float]] = []
        needed: dict[UUID, int] = defaultdict(int)
        for req in requirements:
            needed[req.spare_part_id] += req.quantity
        for spare_id, quantity in needed.items():
            shortfall = quantity - self.stock.get(spare_id, 0)
            if shortfall <= 0:
                continue
            if spare_id in self.pending_orders:
                continue
            lead = self.lead_time.get(spare_id, 0.0)
            available_at = now + max(lead, 0.0)
            self.pending_orders[spare_id] = available_at
            # Order enough to cover the shortfall (at least 1).
            self.stock[spare_id] = self.stock.get(spare_id, 0)
            orders.append((spare_id, available_at))
            # Credit incoming stock immediately as "on order" marker
            # via pending_orders; physical stock rises on delivery.
            _ = shortfall
        return False, orders

    def deliver(self, spare_id: UUID, quantity: int = 1) -> list[UUID]:
        """Receive replenishment and try to satisfy waiters."""
        self.stock[spare_id] = self.stock.get(spare_id, 0) + quantity
        self.pending_orders.pop(spare_id, None)
        return self._drain_waiters()

    def release_unused(self, job_id: UUID) -> None:
        """Drop a grant without restocking (parts were consumed)."""
        self.grants.pop(job_id, None)

    def close_wait(self, job_id: UUID, now: float) -> None:
        """Accumulate waiting time when spares become available."""
        started = self.wait_started.pop(job_id, None)
        if started is not None:
            self.total_wait_minutes += now - started

    def _consume(
        self,
        job_id: UUID,
        requirements: tuple[CompiledSpareReq, ...],
    ) -> None:
        parts: dict[UUID, int] = defaultdict(int)
        for req in requirements:
            parts[req.spare_part_id] += req.quantity
            self.stock[req.spare_part_id] = (
                self.stock.get(req.spare_part_id, 0) - req.quantity
            )
            self.consumed[req.spare_part_id] = (
                self.consumed.get(req.spare_part_id, 0) + req.quantity
            )
        self.grants[job_id] = SpareGrant(job_id=job_id, parts=dict(parts))

    def _drain_waiters(self) -> list[UUID]:
        ready: list[UUID] = []
        remaining: deque[_SpareWaiter] = deque()
        while self.waiters:
            waiter = self.waiters.popleft()
            if self.can_consume(waiter.requirements):
                self._consume(waiter.job_id, waiter.requirements)
                ready.append(waiter.job_id)
            else:
                remaining.append(waiter)
        self.waiters = remaining
        return ready
