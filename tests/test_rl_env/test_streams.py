"""Patient streams: reproducible, fresh per episode, and strictly separated seeds."""
import numpy as np
import pytest

from ml.los.data import TEST_SEED, TRAIN_SEED
from simulator.patients.streams import (DEMO_DATASET_SEED, EVAL_SEEDS, LOS_TEST_SEED,
                                        LOS_TRAIN_SEED, RESERVED_SEEDS, TRAIN_SEEDS,
                                        StreamSampler, generate_stream)


def signature(patients):
    return [(p.patient_id, p.acuity, p.arrival_time, p.predicted_los) for p in patients]


def test_seed_ranges_are_disjoint_from_every_other_dataset():
    assert (LOS_TRAIN_SEED, LOS_TEST_SEED) == (TRAIN_SEED, TEST_SEED)   # stays in sync with ml/los
    assert DEMO_DATASET_SEED == 42
    assert not RESERVED_SEEDS.intersection(TRAIN_SEEDS)
    assert not RESERVED_SEEDS.intersection(EVAL_SEEDS)
    assert not set(TRAIN_SEEDS).intersection(EVAL_SEEDS)


def test_streams_are_reproducible_and_differ_between_seeds():
    a1, a2 = generate_stream(10_001, days=3), generate_stream(10_001, days=3)
    b = generate_stream(10_002, days=3)
    assert signature(a1) == signature(a2)
    assert signature(a1) != signature(b)


def test_stream_respects_the_time_horizon_and_starts_waiting():
    stream = generate_stream(10_003, days=2)
    start = min(p.arrival_time for p in stream)
    assert max(p.arrival_time for p in stream) <= start.replace(hour=8, minute=0, second=0) \
        .__class__(2026, 1, 3, 8, 0, 0)
    assert all(p.status == "WAITING" and 1 <= p.acuity <= 5 for p in stream)


def test_surge_modes_bring_more_patients_in_the_same_time():
    n = {m: len(generate_stream(10_004, days=5, mode=m))
         for m in ("normal", "moderate_surge", "severe_surge")}
    assert n["normal"] < n["moderate_surge"] < n["severe_surge"]


def test_invalid_arguments_are_rejected():
    with pytest.raises(ValueError):
        generate_stream(1, mode="chaos")
    with pytest.raises(ValueError):
        generate_stream(1, days=0)


def test_sampler_refuses_reserved_seeds():
    with pytest.raises(ValueError, match="reserved"):
        StreamSampler(seeds=[10_000, 42])
    with pytest.raises(ValueError):
        StreamSampler(seeds=[])


def test_sampler_is_deterministic_for_a_given_random_generator():
    s = StreamSampler(seeds=TRAIN_SEEDS, days=2)
    first = signature(s(np.random.default_rng(7)))
    again = signature(s(np.random.default_rng(7)))
    other = signature(s(np.random.default_rng(8)))
    assert first == again
    assert first != other
