# LOS Prediction (Phase 6)

Estimates a patient's length of stay (days) **at arrival**, from age group,
specialty, acuity, isolation need and ventilator need. The estimate becomes one
feature of the RL state (Phase 7).

## Use it

```python
from ml.los.predictor import LOSPredictor

predictor = LOSPredictor.load()        # loads ml/los/models/los_rf_v1.joblib
days = predictor.predict(patient)      # simulator Patient object OR dict / API payload
days = predictor.predict_many(patients)
```

Dict keys: `age_group, specialty, acuity, isolation_required, ventilator_required`
(`isolation_required` / `ventilator_required` may be `True/False` or `"YES"/"NO"`).
Output is clipped to 1.0 – 10.0 days.

## Get the model file (once per machine)

The trained model (`*.joblib`) is **git-ignored**, so after cloning run:

```bash
pip install -r ml/requirements.txt
python -m ml.los.train                  # ~1 min, writes ml/los/models/los_rf_v1.*
python -m pytest tests/test_ml_los -q
```

Training on your own machine means the file always matches your scikit-learn
version (a pickled model from another version triggers scikit-learn's
`InconsistentVersionWarning` -- just retrain).

`models/los_rf_v1.metadata.json` is tracked and records the reference results
(metrics, seeds, hyperparameters). Running the trainer rewrites it with your
local timestamp and versions, so **don't commit it** unless you are deliberately
publishing new reference results.

## Important rule: truth vs. estimate

In `patients.csv` the column `predicted_los` is **not a prediction**. In the
synthetic data it is the patient's *true* stay, which the simulator uses to
schedule the discharge. It is the training **target** only.

- The simulator keeps using `predicted_los` as the real stay.
- The RL agent / dashboard may only see `LOSPredictor.predict(...)`.
- Never pass the CSV column to the agent as a state feature (that is leakage).

## Data and honest evaluation

- Train: 20,000 fresh synthetic patients (seed 1001). Test: 5,000 (seed 2002).
  Neither overlaps `patients.csv`, which is used only as a final check.
- Hyperparameter (`min_samples_leaf`) chosen by 5-fold CV on the training set.
- Every model is reported next to a global-mean and a per-acuity-mean baseline
  and an estimated noise floor (see the metadata file).

| Holdout (5,000 patients) | MAE (days) |
|---|---|
| Global mean | 1.870 |
| Per-acuity mean | 0.796 |
| **Random Forest** | **0.724** (R² 0.826) |
| Best possible on this data (noise floor) | ~0.720 |

Because the synthetic LOS is generated from acuity, age 65+ and ventilator need
plus random noise, a good model can only recover that structure -- it cannot
show real-world clinical accuracy. Validating on real data (e.g. MIMIC-IV,
credentialed access) is a stated extension, not part of the MVP.
