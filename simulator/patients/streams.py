"""
CareGrid-RL: fresh synthetic patient streams for RL training and evaluation

Why this exists: data/synthetic/patients.csv is ONE fixed sequence of patients. An RL
agent trained on it can simply memorise that sequence. Instead every training episode
draws a fresh stream from the project's own generator, and evaluation uses streams the
agent has never seen.

Seed discipline (all disjoint, enforced by tests):
    42                  data/synthetic/patients.csv (the demo dataset)
    1001 / 2002         LOS-model training / test data (ml/los/data.py)
    TRAIN_SEEDS         RL training episodes
    VAL_SEEDS           RL validation (model selection / hyperparameter tuning)
    EVAL_SEEDS          RL evaluation (never used for training or tuning)

The generator file is loaded by path and left unmodified.
"""
import importlib.util
import random
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Sequence

import numpy as np

from simulator.patients.patient import Patient

GENERATOR_PATH = (Path(__file__).resolve().parents[2]
                  / "data" / "synthetic" / "generate_synthetic_data.py")

DEMO_DATASET_SEED = 42
LOS_TRAIN_SEED = 1001
LOS_TEST_SEED = 2002
RESERVED_SEEDS = frozenset({DEMO_DATASET_SEED, LOS_TRAIN_SEED, LOS_TEST_SEED})

TRAIN_SEEDS = range(10_000, 10_500)     # 500 distinct training streams
VAL_SEEDS = range(80_000, 80_020)       # 20 validation streams (checkpoint / config selection)
VAL_CONFIRM_SEEDS = range(81_000, 81_020)  # 20 confirmation streams (never used for selection)
EVAL_SEEDS = range(90_000, 90_050)      # 50 held-out evaluation streams (final claim only)

STREAM_START = datetime(2026, 1, 1, 8, 0, 0)
_MAX_RATE_PER_HOUR = 3.0                # above every scenario rate in the generator
MODES = ("normal", "moderate_surge", "severe_surge")


def _load_generator():
    spec = importlib.util.spec_from_file_location("caregrid_generator", GENERATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)        # note: this seeds `random` with 42
    return module


def generate_stream(seed: int, days: float = 30.0, mode: str = "normal") -> List[Patient]:
    """Patients arriving during the first `days` days of a fresh hospital timeline.
    Same (seed, days, mode) always gives the same stream."""
    if mode not in MODES:
        raise ValueError(f"Unknown mode '{mode}'. Choose from {MODES}")
    if days <= 0:
        raise ValueError("days must be positive")
    gen = _load_generator()
    random.seed(seed)                      # re-seed AFTER import (import sets 42)
    n = int(days * 24 * _MAX_RATE_PER_HOUR) + 50
    rows = gen.generate_patients(num_patients=n, mode=mode, start_time=STREAM_START)
    patients = [Patient.from_csv_row(r) for r in rows]
    horizon = STREAM_START.timestamp() + days * 86400
    return [p for p in patients if p.arrival_time.timestamp() <= horizon]


class StreamSampler:
    """Callable for CareGridHospitalEnv(patient_source=...): every reset() draws a
    new stream, reproducibly from the env's own seeded random generator."""

    def __init__(self, seeds: Sequence[int] = TRAIN_SEEDS, days: float = 30.0,
                 mode: str = "normal"):
        seeds = list(seeds)
        if not seeds:
            raise ValueError("seeds must not be empty")
        clash = RESERVED_SEEDS.intersection(seeds)
        if clash:
            raise ValueError(f"Seeds {sorted(clash)} are reserved for the demo dataset / LOS model")
        self.seeds, self.days, self.mode = seeds, days, mode
        self.last_seed: Optional[int] = None

    def __call__(self, rng: np.random.Generator) -> List[Patient]:
        self.last_seed = int(self.seeds[int(rng.integers(len(self.seeds)))])
        return generate_stream(self.last_seed, self.days, self.mode)


class MixedStreamSampler:
    """Like StreamSampler, but every reset() also draws the SCENARIO at random, e.g.
    70% normal / 30% moderate_surge, so one agent sees both quiet and busy hospitals."""

    def __init__(self, mode_weights: dict, seeds: Sequence[int] = TRAIN_SEEDS,
                 days: float = 30.0):
        if not mode_weights:
            raise ValueError("mode_weights must not be empty")
        bad = [m for m in mode_weights if m not in MODES]
        if bad:
            raise ValueError(f"Unknown modes {bad}. Choose from {MODES}")
        if any(w <= 0 for w in mode_weights.values()):
            raise ValueError("mode weights must be positive")
        seeds = list(seeds)
        if not seeds:
            raise ValueError("seeds must not be empty")
        clash = RESERVED_SEEDS.intersection(seeds)
        if clash:
            raise ValueError(f"Seeds {sorted(clash)} are reserved for the demo dataset / LOS model")
        total = float(sum(mode_weights.values()))
        self.modes = list(mode_weights)
        self.probs = np.array([mode_weights[m] / total for m in self.modes])
        self.seeds, self.days = seeds, days
        self.last_mode: Optional[str] = None
        self.last_seed: Optional[int] = None

    def __call__(self, rng: np.random.Generator) -> List[Patient]:
        self.last_mode = str(self.modes[int(rng.choice(len(self.modes), p=self.probs))])
        self.last_seed = int(self.seeds[int(rng.integers(len(self.seeds)))])
        return generate_stream(self.last_seed, self.days, self.last_mode)
