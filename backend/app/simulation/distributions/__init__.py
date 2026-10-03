"""Distribution sampling uses domain distributions (minutes)."""

from app.domain.reliability.distributions import Distribution
from app.domain.reliability.distributions import parse_distribution

__all__ = ["Distribution", "parse_distribution"]
