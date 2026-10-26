import importlib.util
import random
from datetime import datetime
from pathlib import Path
from typing import Tuple

import pandas as pd

from ml.los.features import FEATURES, to_frame

REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATOR_PATH = REPO_ROOT / "data" / "synthetic" / "generate_synthetic_data.py"
TARGET = "los_days"

TRAIN_SEED = 1001
TEST_SEED = 2002


def _load_generator():
    spec = importlib.util.spec_from_file_location("caregrid_generator", GENERATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)      # note: this seeds `random` with 42
    return module


def generate_frame(n: int, seed: int, mode: str = "normal") -> Tuple[pd.DataFrame, pd.Series]:
    """Returns (X, y) for n freshly generated synthetic patients."""
    gen = _load_generator()
    random.seed(seed)                    # re-seed AFTER import (import sets 42)
    rows = gen.generate_patients(num_patients=n, mode=mode,
                                 start_time=datetime(2026, 1, 1, 8, 0, 0))
    X = to_frame(rows)
    y = pd.Series([float(r["predicted_los"]) for r in rows], name=TARGET)
    return X, y


def load_simulation_patients(data_dir: str = "data/synthetic",
                             filename: str = "patients.csv") -> Tuple[pd.DataFrame, pd.Series]:
    """The patients the simulator actually runs: used ONLY for evaluation."""
    df = pd.read_csv(REPO_ROOT / data_dir / filename)
    X = to_frame(df.to_dict("records"))
    y = df["predicted_los"].astype(float).rename(TARGET)
    return X, y
