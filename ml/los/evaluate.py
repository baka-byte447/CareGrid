
from typing import Dict

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from ml.los.features import LOS_MAX_DAYS, LOS_MIN_DAYS


def _scores(y_true, y_pred) -> Dict[str, float]:
    return {
        "mae_days": round(float(mean_absolute_error(y_true, y_pred)), 4),
        "rmse_days": round(float(np.sqrt(mean_squared_error(y_true, y_pred))), 4),
        "r2": round(float(r2_score(y_true, y_pred)), 4),
    }


def evaluate(model, X: pd.DataFrame, y: pd.Series, X_train: pd.DataFrame,
             y_train: pd.Series) -> Dict:
    pred = np.clip(model.predict(X), LOS_MIN_DAYS, LOS_MAX_DAYS)

    global_mean = np.full(len(y), y_train.mean())
    acuity_means = y_train.groupby(X_train["acuity"]).mean()
    acuity_pred = X["acuity"].map(acuity_means).fillna(y_train.mean()).to_numpy()

    by_acuity = {}
    for a in sorted(X["acuity"].unique()):
        m = (X["acuity"] == a).to_numpy()
        by_acuity[str(int(a))] = {
            "n": int(m.sum()),
            "mae_days": round(float(mean_absolute_error(y[m], pred[m])), 4),
            "mean_actual": round(float(y[m].mean()), 3),
            "mean_predicted": round(float(pred[m].mean()), 3),
        }

    return {
        "n": int(len(y)),
        "random_forest": _scores(y, pred),
        "baseline_global_mean": _scores(y, global_mean),
        "baseline_acuity_mean": _scores(y, acuity_pred),
        "by_acuity": by_acuity,
        "mean_error_bias_days": round(float((pred - y).mean()), 4),
    }



    