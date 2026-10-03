"""Statuses for AI generation jobs and proposals."""

from enum import StrEnum


class GenerationJobStatus(StrEnum):
    """Lifecycle of an equipment generation job."""

    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    DOWNLOADING = "DOWNLOADING"
    IMPORTING = "IMPORTING"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


TERMINAL_GENERATION_STATUSES: frozenset[GenerationJobStatus] = frozenset(
    {
        GenerationJobStatus.READY_FOR_REVIEW,
        GenerationJobStatus.FAILED,
        GenerationJobStatus.CANCELLED,
    }
)


class ProposalStatus(StrEnum):
    """Review state of a stored proposal."""

    PENDING = "PENDING"
    PARTIALLY_APPLIED = "PARTIALLY_APPLIED"
    APPLIED = "APPLIED"
    REJECTED = "REJECTED"


class ProposalItemDecision(StrEnum):
    """Per-row review decision."""

    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    EDITED = "EDITED"
    REJECTED = "REJECTED"
