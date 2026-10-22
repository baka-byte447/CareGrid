from datetime import datetime

import numpy as np
import pytest

from ml.los.data import (GENERATOR_PATH, TRAIN_SEED, _load_generator,
                         generate_frame, load_simulation_patients)
from ml.los.evaluate import evaluate
from ml.los.features import FEATURES, LOS_MAX_DAYS, LOS_MIN_DAYS, to_frame
from ml.los.model import build_pipeline
from ml.los.predictor import DEFAULT_MODEL, LOSPredictor
from simulator.patients.patient import Patient


def patient(acuity=3, age="36-50", spec="General", iso=False, vent=False):
    return {"age_group": age, "specialty": spec, "acuity": acuity,
            "isolation_required": iso, "ventilator_required": vent}


@pytest.fixture(scope="module")
def quick_model():
    """Small, fast model trained once for the whole module."""
    X, y = generate_frame(4000, TRAIN_SEED)
    Xt, yt = generate_frame(1500, 777)
    model = build_pipeline(n_estimators=60, min_samples_leaf=20).fit(X, y)
    return model, X, y, Xt, yt


# ---------- features ----------

def test_features_never_include_the_los_target_or_ids():
    banned = {"predicted_los", "los_days", "patient_id", "current_status", "arrival_time"}
    assert banned.isdisjoint(FEATURES)


def test_to_frame_accepts_csv_strings_dicts_and_patient_objects_identically():
    as_csv = {"age_group": "65+", "specialty": "Pulmonology", "acuity": "5",
              "isolation_required": "YES", "ventilator_required": "NO"}
    as_obj = Patient("P1", "65+", 5, "Pulmonology", 7.0, True, False,
                     datetime(2026, 1, 1))
    a, b = to_frame([as_csv]), to_frame([as_obj])
    assert a.equals(b)
    assert list(a.columns) == FEATURES


# ---------- data hygiene ----------

def test_training_data_is_not_the_simulation_patient_file():
    X, y = generate_frame(1000, TRAIN_SEED)
    Xs, ys = load_simulation_patients()
    assert not (X.reset_index(drop=True).equals(Xs.reset_index(drop=True))
                and np.allclose(y.to_numpy(), ys.to_numpy()))


def test_data_generation_is_reproducible():
    X1, y1 = generate_frame(300, 5)
    X2, y2 = generate_frame(300, 5)
    assert X1.equals(X2) and y1.equals(y2)


def test_generator_interface_contract_still_holds():
    """Fails loudly if someone changes the generator in a way that would
    silently break LOS training."""
    assert GENERATOR_PATH.exists()
    gen = _load_generator()
    rows = gen.generate_patients(num_patients=5, mode="normal",
                                 start_time=datetime(2026, 1, 1, 8))
    for key in ("age_group", "specialty", "acuity", "isolation_required",
                "ventilator_required", "predicted_los"):
        assert key in rows[0]


# ---------- model quality & behaviour ----------

def test_model_beats_naive_baselines_and_has_no_large_bias(quick_model):
    model, X, y, Xt, yt = quick_model
    r = evaluate(model, Xt, yt, X, y)
    rf = r["random_forest"]["mae_days"]
    assert rf < r["baseline_global_mean"]["mae_days"] * 0.6
    assert rf <= r["baseline_acuity_mean"]["mae_days"]
    assert r["random_forest"]["r2"] > 0.7
    assert abs(r["mean_error_bias_days"]) < 0.1


def test_predictions_are_clinically_ordered(quick_model):
    model = quick_model[0]
    p = LOSPredictor(model)
    mild, critical = p.predict(patient(acuity=1)), p.predict(patient(acuity=5))
    assert critical > mild + 3
    assert p.predict(patient(acuity=5, vent=True)) > p.predict(patient(acuity=5, vent=False))
    assert p.predict(patient(acuity=3, age="65+")) > p.predict(patient(acuity=3, age="18-35"))


def test_predictions_stay_in_valid_range(quick_model):
    p = LOSPredictor(quick_model[0])
    for a in range(1, 6):
        v = p.predict(patient(acuity=a, age="65+", vent=True))
        assert LOS_MIN_DAYS <= v <= LOS_MAX_DAYS


def test_unseen_category_does_not_crash(quick_model):
    p = LOSPredictor(quick_model[0])
    assert isinstance(p.predict(patient(spec="Dermatology")), float)


def test_predict_many_matches_single_and_handles_empty(quick_model):
    p = LOSPredictor(quick_model[0])
    batch = [patient(acuity=a) for a in range(1, 6)]
    assert p.predict_many(batch) == [p.predict(x) for x in batch]
    assert p.predict_many([]) == []


# ---------- committed artifact ----------

@pytest.mark.skipif(not DEFAULT_MODEL.exists(), reason="LOS artifact not trained yet")
def test_committed_artifact_loads_and_reports_metadata():
    p = LOSPredictor.load()
    assert p.model_name == "los_rf_v1"
    assert p.metadata["features"] == FEATURES
    assert "sklearn_version" in p.metadata
    assert 1.0 <= p.predict(patient(acuity=4, vent=True)) <= 10.0


def test_missing_artifact_gives_actionable_error(tmp_path):
    with pytest.raises(FileNotFoundError, match="ml.los.train"):
        LOSPredictor.load(tmp_path / "nope.joblib")
