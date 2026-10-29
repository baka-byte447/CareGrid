"""Phase 8 / T5: the DQN training pipeline (skipped when torch / stable-baselines3 are missing)."""
import csv
import json

import numpy as np
import pytest

pytest.importorskip("gymnasium")
pytest.importorskip("torch")
pytest.importorskip("stable_baselines3")

from stable_baselines3 import DQN                                         # noqa: E402

from rl.agents.sb3_utils import sb3_q_fn                                  # noqa: E402
from rl.evaluation.evaluate import evaluate_policy                        # noqa: E402
from rl.evaluation.policies import masked_greedy_policy                   # noqa: E402
from rl.training.config import DQNConfig                                  # noqa: E402
from rl.training.envs import make_training_env                            # noqa: E402
from rl.training.train_dqn import train                                   # noqa: E402
from simulator.patients.streams import EVAL_SEEDS, VAL_SEEDS, generate_stream   # noqa: E402


class FakePredictor:
    def predict(self, p):
        return 3.0

    def predict_many(self, patients):
        return [3.0 for _ in patients]


def tiny_config(tmp_path, **kw):
    base = dict(run_name="tiny", out_dir=str(tmp_path), total_timesteps=1_500, learning_starts=200,
                buffer_size=5_000, batch_size=32, target_update_interval=200, net_arch=(16,),
                stream_days=2.0, drain_days=1.0, mode_weights={"normal": 1.0},
                val_every_steps=600, val_streams_during_training=2, final_val_streams=2)
    base.update(kw)
    return DQNConfig(**base)


def test_config_defaults_match_the_plan_and_serialise():
    c = DQNConfig()
    assert (c.gamma, c.learning_rate, c.batch_size, c.target_update_interval) == (0.995, 3e-4, 128, 2_000)
    assert c.net_arch == (128, 128) and c.total_timesteps == 1_000_000
    assert c.mode_weights == {"normal": 0.7, "moderate_surge": 0.3}
    d = c.to_dict()
    assert d["net_arch"] == [128, 128] and set(d["acuity_weights"]) == {"1", "2", "3", "4", "5"}
    json.dumps(d)                                                       # fully JSON-serialisable
    assert DQNConfig.smoke().total_timesteps == 20_000


def test_training_env_uses_queue_cost_and_draws_a_new_stream_per_seed():
    env = make_training_env(tiny_config("."), FakePredictor())
    inner = env.unwrapped
    assert inner.reward_mode == "queue_cost" and inner.invalid_action_penalty == 0.1
    assert inner.max_episode_days == pytest.approx(3.0)
    env.reset(seed=1)
    a = [(p.patient_id, p.arrival_time) for p in inner._patients.values()]
    env.reset(seed=1)
    b = [(p.patient_id, p.arrival_time) for p in inner._patients.values()]
    env.reset(seed=2)
    c = [(p.patient_id, p.arrival_time) for p in inner._patients.values()]
    assert a == b and a != c


def test_q_function_has_one_value_per_action(tmp_path):
    env = make_training_env(tiny_config(tmp_path), FakePredictor())
    model = DQN("MlpPolicy", env, policy_kwargs={"net_arch": [8]}, learning_starts=10, device="cpu", seed=0)
    obs, _ = env.reset(seed=0)
    q = sb3_q_fn(model)(obs)
    assert q.shape == (4,) and np.isfinite(q).all()


def test_end_to_end_smoke_training_produces_a_safe_loadable_model(tmp_path):
    meta = train(tiny_config(tmp_path), predictor=FakePredictor())
    run = tmp_path / "tiny"
    for name in ("best.zip", "last.zip", "metadata.json", "val_log.csv"):
        assert (run / name).exists(), name
    on_disk = json.loads((run / "metadata.json").read_text())
    for key in ("run_name", "seed", "config", "versions", "git_commit", "duration_seconds",
                "steps_per_second", "best_step", "best_checkpoint_validation", "baseline_validation"):
        assert key in on_disk, key
    assert set(on_disk["baseline_validation"]) >= {"b1_rule", "h1_lowest_tier", "random", "always_wait"}
    assert meta["best_checkpoint_validation"]["val_score"] > 0

    rows = list(csv.DictReader(open(run / "val_log.csv")))
    assert len(rows) >= 2 and {"timesteps", "val_score", "epsilon", "normal_weighted_wait"} <= set(rows[0])

    # the saved model loads and, with the mask, never produces an invalid action or a violation
    model = DQN.load(run / "best.zip", device="cpu")
    stream = generate_stream(EVAL_SEEDS[0], days=3)                     # smoke test only: not tuned on
    r = evaluate_policy(masked_greedy_policy(sb3_q_fn(model)), stream, drain_days=1,
                        los_predictor=FakePredictor())
    assert r["invalid_actions"] == 0 and r["metrics"]["constraint_violations"]["total"] == 0


def test_validation_uses_only_validation_seeds(tmp_path, monkeypatch):
    """The checkpoint-selection score must never touch training or evaluation streams."""
    import rl.training.callbacks as cb
    seen = []
    real = cb.evaluate_on_streams

    def spy(policy, *, seeds, **kw):
        seen.extend(seeds)
        return real(policy, seeds=seeds, **kw)

    monkeypatch.setattr(cb, "evaluate_on_streams", spy)
    train(tiny_config(tmp_path, total_timesteps=800, val_every_steps=400), predictor=FakePredictor())
    assert seen and set(seen) <= set(VAL_SEEDS)


def test_checkpoints_before_the_burn_in_never_become_best(tmp_path):
    """An almost-untrained network can look good by chance; it must not be selected."""
    cfg = tiny_config(tmp_path, total_timesteps=1_500, val_every_steps=300, exploration_fraction=0.6)
    meta = train(cfg, predictor=FakePredictor())
    min_step = int(0.6 * 1_500)                                    # 900
    rows = list(csv.DictReader(open(tmp_path / "tiny" / "val_log.csv")))
    assert any(int(r["timesteps"]) < min_step for r in rows)        # early checkpoints were logged ...
    assert meta["best_step"] >= min_step                            # ... but cannot be selected


def test_interrupted_training_resumes_from_its_checkpoint(tmp_path, monkeypatch):
    """The training machine can be restarted at any time: a run must continue, not start over."""
    import rl.training.callbacks as cb

    cfg = tiny_config(tmp_path, total_timesteps=1_800, val_every_steps=400, exploration_fraction=0.3)
    calls = {"n": 0}
    real = cb.ValidationCallback.validate

    def dying_validate(self):
        calls["n"] += 1
        if calls["n"] == 3:
            raise KeyboardInterrupt("simulated machine restart")
        return real(self)

    monkeypatch.setattr(cb.ValidationCallback, "validate", dying_validate)
    with pytest.raises(KeyboardInterrupt):
        train(cfg, predictor=FakePredictor())
    run = tmp_path / "tiny"
    state = json.loads((run / "resume_state.json").read_text())
    assert 400 <= state["num_timesteps"] < 1_800 and (run / "resume.zip").exists()
    rows_before = len(list(csv.DictReader(open(run / "val_log.csv"))))

    monkeypatch.setattr(cb.ValidationCallback, "validate", real)
    meta = train(cfg, predictor=FakePredictor(), resume=True)
    assert meta["resumed_from_step"] == state["num_timesteps"]
    rows = list(csv.DictReader(open(run / "val_log.csv")))
    assert len(rows) > rows_before and int(rows[-1]["timesteps"]) >= 1_800     # history kept, continued
    assert not (run / "resume.zip").exists()                                    # cleaned up when done
    assert (run / "best.zip").exists() and (run / "metadata.json").exists()


def test_resume_without_a_checkpoint_just_starts_a_new_run(tmp_path):
    meta = train(tiny_config(tmp_path, total_timesteps=600, val_every_steps=300), FakePredictor(), resume=True)
    assert meta["resumed_from_step"] is None
