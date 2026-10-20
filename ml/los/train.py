
import argparse
import json
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import GridSearchCV

from ml.los.data import (TEST_SEED, TRAIN_SEED, generate_frame,
                         load_simulation_patients)
from ml.los.evaluate import evaluate
from ml.los.features import FEATURES
from ml.los.model import build_pipeline

MODELS_DIR = Path(__file__).parent / "models"


def noise_floor_mae(X: pd.DataFrame, y: pd.Series) -> float:
    """Approximate best-possible MAE on this synthetic data. The generator's LOS
    depends only on acuity, age 65+ and ventilator need plus random noise, so the
    mean LOS within those groups is the ideal predictor; its MAE is the floor."""
    keys = [X["acuity"], (X["age_group"] == "65+").astype(int), X["ventilator_required"]]
    ideal = y.groupby(keys).transform("mean")
    return round(float(mean_absolute_error(y, ideal)), 4)


def main():
    ap = argparse.ArgumentParser(description="Train the CareGrid LOS model")
    ap.add_argument("--n-train", type=int, default=20000)
    ap.add_argument("--n-test", type=int, default=5000)
    ap.add_argument("--version", default="v1")
    ap.add_argument("--no-grid", action="store_true", help="skip CV tuning, use min_samples_leaf=20")
    args = ap.parse_args()

    print(f"Generating data (train={args.n_train}, test={args.n_test}) ...")
    X_tr, y_tr = generate_frame(args.n_train, TRAIN_SEED)
    X_te, y_te = generate_frame(args.n_test, TEST_SEED)
    X_sim, y_sim = load_simulation_patients()

    best_leaf, cv_table = 20, None
    if not args.no_grid:
        print("Tuning min_samples_leaf with 5-fold CV (MAE) ...")
        grid = GridSearchCV(build_pipeline(n_estimators=100),
                            {"rf__min_samples_leaf": [1, 5, 20, 50, 100]},
                            scoring="neg_mean_absolute_error", cv=5, n_jobs=1)
        grid.fit(X_tr, y_tr)
        best_leaf = int(grid.best_params_["rf__min_samples_leaf"])
        cv_table = {str(p["rf__min_samples_leaf"]): round(float(-s), 4)
                    for p, s in zip(grid.cv_results_["params"], grid.cv_results_["mean_test_score"])}
        print(f"  CV MAE by min_samples_leaf: {cv_table} -> best {best_leaf}")

    model = build_pipeline(n_estimators=200, min_samples_leaf=best_leaf)
    model.fit(X_tr, y_tr)

    metrics = {
        "holdout_synthetic": evaluate(model, X_te, y_te, X_tr, y_tr),
        "simulation_patients": evaluate(model, X_sim, y_sim, X_tr, y_tr),
        "noise_floor_mae_days": noise_floor_mae(X_te, y_te),
    }

    name = f"los_rf_{args.version}"
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODELS_DIR / f"{name}.joblib", compress=3)
    meta = {
        "model_name": name,
        "algorithm": "RandomForestRegressor (sklearn Pipeline with one-hot encoding)",
        "target": "los_days (true LOS from the synthetic generator)",
        "features": FEATURES,
        "hyperparameters": {"n_estimators": 200, "min_samples_leaf": best_leaf},
        "cv_mae_by_min_samples_leaf": cv_table,
        "n_train": args.n_train, "n_test": args.n_test,
        "train_seed": TRAIN_SEED, "test_seed": TEST_SEED,
        "trained_at": datetime.now().isoformat(timespec="seconds"),
        "sklearn_version": sklearn.__version__,
        "numpy_version": np.__version__,
        "metrics": metrics,
    }
    (MODELS_DIR / f"{name}.metadata.json").write_text(json.dumps(meta, indent=2))

    h = metrics["holdout_synthetic"]
    print(f"\nHoldout MAE (days):  RF {h['random_forest']['mae_days']} | "
          f"acuity-mean {h['baseline_acuity_mean']['mae_days']} | "
          f"global-mean {h['baseline_global_mean']['mae_days']} | "
          f"noise floor ~{metrics['noise_floor_mae_days']}")
    print(f"Holdout R2:          RF {h['random_forest']['r2']}")
    s = metrics["simulation_patients"]
    print(f"patients.csv MAE:    RF {s['random_forest']['mae_days']} (n={s['n']})")
    print(f"Saved: {MODELS_DIR / (name + '.joblib')}")


if __name__ == "__main__":
    main()

