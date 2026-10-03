"""Tests for deterministic RandomProvider streams."""

from app.simulation.random import RandomProvider


def test_same_seed_reproduces_stream() -> None:
    a = RandomProvider(seed=12345, run_id=0).generator(1, 2)
    b = RandomProvider(seed=12345, run_id=0).generator(1, 2)
    assert a.random() == b.random()
    assert a.integers(0, 1_000_000) == b.integers(0, 1_000_000)


def test_different_run_ids_are_independent() -> None:
    a = RandomProvider(seed=7, run_id=0).generator(1)
    b = RandomProvider(seed=7, run_id=1).generator(1)
    samples_a = [a.random() for _ in range(8)]
    samples_b = [b.random() for _ in range(8)]
    assert samples_a != samples_b


def test_different_stream_keys_are_independent() -> None:
    provider = RandomProvider(seed=99, run_id=0)
    samples_a = [provider.generator(1).random() for _ in range(1)]
    # Fresh providers so each call starts the stream at the beginning.
    left = [RandomProvider(99, 0).generator(1).random() for _ in range(5)]
    right = [RandomProvider(99, 0).generator(2).random() for _ in range(5)]
    assert left != right
    assert samples_a[0] == left[0]


def test_bernoulli_extremes() -> None:
    provider = RandomProvider(seed=1, run_id=0)
    assert provider.bernoulli(1, p=0.0) is False
    assert provider.bernoulli(2, p=1.0) is True
