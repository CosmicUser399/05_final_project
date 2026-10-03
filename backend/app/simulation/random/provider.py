"""Deterministic RNG streams based on ``numpy.random.SeedSequence``."""

from __future__ import annotations

import numpy as np


class RandomProvider:
    """Independent NumPy generators derived from a master seed.

    Stream derivation uses ``SeedSequence(entropy=seed,
    spawn_key=(run_id, *key))`` so results are stable across Python
    versions and do not rely on ``hash()``.
    """

    def __init__(self, seed: int, run_id: int = 0) -> None:
        """Create a provider for one Monte Carlo trial."""
        self._seed = int(seed)
        self._run_id = int(run_id)
        self._cache: dict[tuple[int, ...], np.random.Generator] = {}

    @property
    def seed(self) -> int:
        """Return the master seed."""
        return self._seed

    @property
    def run_id(self) -> int:
        """Return the run index used in ``spawn_key``."""
        return self._run_id

    def generator(self, *key: int) -> np.random.Generator:
        """Return (and cache) a generator for the given stream key."""
        full_key = (self._run_id, *key)
        cached = self._cache.get(full_key)
        if cached is not None:
            return cached
        sequence = np.random.SeedSequence(
            entropy=self._seed,
            spawn_key=full_key,
        )
        rng = np.random.default_rng(sequence)
        self._cache[full_key] = rng
        return rng

    def bernoulli(self, *key: int, p: float) -> bool:
        """Draw a Bernoulli(``p``) sample from stream ``key``."""
        if not 0.0 <= p <= 1.0:
            raise ValueError(f"p must be in [0, 1], got {p!r}")
        if p <= 0.0:
            return False
        if p >= 1.0:
            return True
        return bool(self.generator(*key).random() < p)
