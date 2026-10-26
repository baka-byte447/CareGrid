from typing import Any, Iterable, List, Mapping

import pandas as pd

CATEGORICAL = ["age_group", "specialty"]
NUMERIC = ["acuity"]
BINARY = ["isolation_required", "ventilator_required"]
FEATURES: List[str] = CATEGORICAL + NUMERIC + BINARY

# LOS bounds used by the synthetic generator; predictions are clipped to them.
LOS_MIN_DAYS = 1.0
LOS_MAX_DAYS = 10.0


def _as_bool(value: Any) -> int:
    """Accepts bool, 0/1, or the CSV strings 'YES'/'NO'."""
    if isinstance(value, str):
        return 1 if value.strip().upper() in ("YES", "Y", "TRUE", "1") else 0
    return int(bool(value))


def _get(record: Any, name: str) -> Any:
    if isinstance(record, Mapping):
        return record[name]
    return getattr(record, name)


def to_frame(records: Iterable[Any]) -> pd.DataFrame:
    """Builds the model input frame from simulator Patient objects OR dicts
    (CSV rows / API payloads). Same code path for training and inference, so
    the two cannot drift apart."""
    rows = []
    for r in records:
        rows.append({
            "age_group": str(_get(r, "age_group")),
            "specialty": str(_get(r, "specialty")),
            "acuity": int(_get(r, "acuity")),
            "isolation_required": _as_bool(_get(r, "isolation_required")),
            "ventilator_required": _as_bool(_get(r, "ventilator_required")),
        })
    return pd.DataFrame(rows, columns=FEATURES)
