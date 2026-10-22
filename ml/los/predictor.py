
import json
import warnings
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import joblib
import numpy as np
import sklearn

from ml.los.features import LOS_MAX_DAYS, LOS_MIN_DAYS, to_frame

DEFAULT_MODEL = Path(__file__).parent / "models" / "los_rf_v1.joblib"


class LOSPredictor:
    def __init__(self, pipeline, metadata: Optional[Dict] = None):
        self._pipeline = pipeline
        self.metadata = metadata or {}

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "LOSPredictor":
        path = Path(path) if path else DEFAULT_MODEL
        if not path.exists():
            raise FileNotFoundError(
                f"LOS model not found at {path}. Train it with: python -m ml.los.train")
        meta_path = path.with_suffix(".metadata.json")
        metadata = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        trained_with = metadata.get("sklearn_version")
        if trained_with and trained_with != sklearn.__version__:
            warnings.warn(
                f"LOS model was trained with scikit-learn {trained_with} but "
                f"{sklearn.__version__} is installed; results may differ. "
                f"Retrain with: python -m ml.los.train", RuntimeWarning)
        return cls(joblib.load(path), metadata)

    @property
    def model_name(self) -> str:
        return self.metadata.get("model_name", "los_rf")

    def predict_many(self, patients: Iterable[Any]) -> List[float]:
        patients = list(patients)
        if not patients:
            return []
        raw = self._pipeline.predict(to_frame(patients))
        return [round(float(v), 2) for v in np.clip(raw, LOS_MIN_DAYS, LOS_MAX_DAYS)]

    def predict(self, patient: Any) -> float:
        return self.predict_many([patient])[0]
