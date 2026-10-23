from pathlib import Path

import pytest


@pytest.fixture
def data_dir() -> Path:
    """Return the repository's synthetic hospital data directory."""
    return Path(__file__).resolve().parents[2] / "data" / "synthetic"
