from pathlib import Path

import pytest


@pytest.fixture
def data_dir() -> Path:
    """Return the repository's synthetic hospital data directory."""
    return Path(__file__).resolve().parents[2] / "data" / "synthetic"


class CountingPredictor:
    """LOS predictor stand-in (does not need the trained model file) that counts calls."""

    def __init__(self, value: float = 3.0):
        self.value = value
        self.predict_calls = 0
        self.predict_many_calls = 0

    def predict(self, patient):
        self.predict_calls += 1
        return self.value

    def predict_many(self, patients):
        self.predict_many_calls += 1
        return [self.value for _ in patients]


@pytest.fixture
def counting_predictor() -> CountingPredictor:
    return CountingPredictor()
