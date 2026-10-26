from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from ml.los.features import BINARY, CATEGORICAL, NUMERIC


def build_pipeline(n_estimators: int = 200, min_samples_leaf: int = 20,
                   max_depth=None, random_state: int = 42) -> Pipeline:
    pre = ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL),
        ("num", "passthrough", NUMERIC + BINARY),
    ])
    rf = RandomForestRegressor(
        n_estimators=n_estimators,
        min_samples_leaf=min_samples_leaf,
        max_depth=max_depth,
        random_state=random_state,
        n_jobs=-1,
    )
    return Pipeline([("prep", pre), ("rf", rf)])
