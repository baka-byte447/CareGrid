"""Phase 8: DQN with masked Bellman targets (skipped without torch / stable-baselines3)."""
import numpy as np
import pytest

pytest.importorskip("gymnasium")
pytest.importorskip("torch")
pytest.importorskip("stable_baselines3")

import torch as th                                                          # noqa: E402
from gymnasium import spaces                                                # noqa: E402
from stable_baselines3 import DQN                                           # noqa: E402

import rl.agents.masked_dqn as md                                           # noqa: E402
from rl.agents.masked_dqn import MaskedDQN, MaskedReplayBuffer, masked_next_values   # noqa: E402
from rl.training.envs import make_training_env                              # noqa: E402
from rl.training.train_dqn import train                                     # noqa: E402

from .test_training_pipeline import FakePredictor, tiny_config              # noqa: E402


def t(rows):
    return th.tensor(rows, dtype=th.float32)


def b(rows):
    return th.tensor(rows, dtype=th.bool)


def test_masked_max_ignores_invalid_actions():
    q = t([[5.0, 100.0, 7.0, 1.0]])
    assert masked_next_values(q, b([[True, False, True, True]])).item() == 7.0
    assert masked_next_values(q, b([[True, True, True, True]])).item() == 100.0


def test_masked_max_fixes_the_optimism_that_unmasked_targets_have():
    """All costs are negative: an invalid action whose Q was never trained (about 0) would win a
    plain max. With the mask the target uses the best VALID value instead."""
    q = t([[-1.0, -5.0, -9.0, -3.0]])                      # action 0 is invalid but looks best
    assert q.max().item() == -1.0                           # what plain DQN would bootstrap from
    assert masked_next_values(q, b([[False, False, False, True]])).item() == -3.0
    assert masked_next_values(q, b([[False, True, False, True]])).shape == (1, 1)


def test_masked_max_never_returns_minus_infinity():
    q = t([[1.0, 2.0, 3.0, 4.0]])
    out = masked_next_values(q, b([[False, False, False, False]]))       # impossible in practice
    assert th.isfinite(out).all() and out.item() == 4.0


def test_replay_buffer_keeps_the_mask_aligned_with_each_transition():
    obs_space, act_space = spaces.Box(0, 1, (3,), np.float32), spaces.Discrete(4)
    buf = MaskedReplayBuffer(50, obs_space, act_space, device="cpu", n_envs=1)
    masks = {}
    for i in range(20):
        mask = [bool(i % 2), True, bool((i // 2) % 2), True]
        masks[i] = mask
        buf.add(np.full((1, 3), i / 20, np.float32), np.full((1, 3), (i + 1) / 20, np.float32),
                np.array([i % 4]), np.array([-float(i)]), np.array([False]),
                [{"next_valid_actions": mask}])
    samples = buf._get_samples(np.arange(20))
    for i in range(20):
        assert samples.next_valid[i].tolist() == masks[i]
        assert samples.rewards[i].item() == -float(i)                    # same row as the mask


def test_replay_buffer_defaults_to_all_valid_when_the_env_gives_no_mask():
    buf = MaskedReplayBuffer(10, spaces.Box(0, 1, (2,), np.float32), spaces.Discrete(4), device="cpu")
    buf.add(np.zeros((1, 2), np.float32), np.zeros((1, 2), np.float32), np.array([0]),
            np.array([0.0]), np.array([False]), [{}])
    assert buf._get_samples(np.array([0])).next_valid.all()


def test_replay_buffer_rejects_multiple_envs():
    with pytest.raises(ValueError):
        MaskedReplayBuffer(10, spaces.Box(0, 1, (2,), np.float32), spaces.Discrete(4), n_envs=2)


def test_maskeddqn_trains_and_actually_uses_the_masked_target(tmp_path, monkeypatch):
    calls = []
    real = md.masked_next_values

    def spy(next_q, next_valid):
        calls.append(tuple(next_valid.shape))
        return real(next_q, next_valid)

    monkeypatch.setattr(md, "masked_next_values", spy)
    env = make_training_env(tiny_config(tmp_path), FakePredictor())
    model = MaskedDQN("MlpPolicy", env, policy_kwargs={"net_arch": [8]}, learning_starts=100,
                      buffer_size=2_000, batch_size=16, device="cpu", seed=0, verbose=0)
    model.learn(total_timesteps=600)
    assert calls and calls[0][1] == 4 and isinstance(model.replay_buffer, MaskedReplayBuffer)
    # masks stored by the real environment are not all-True (some actions are impossible)
    stored = model.replay_buffer.next_valid[: model.replay_buffer.pos]
    assert (~stored).any() and stored[:, 3].all()                         # WAIT always valid


def test_masked_model_can_be_loaded_for_evaluation_with_plain_dqn(tmp_path):
    env = make_training_env(tiny_config(tmp_path), FakePredictor())
    model = MaskedDQN("MlpPolicy", env, policy_kwargs={"net_arch": [8]}, learning_starts=50,
                      buffer_size=500, batch_size=16, device="cpu", seed=0)
    model.learn(total_timesteps=150)
    model.save(tmp_path / "m.zip")
    loaded = DQN.load(tmp_path / "m.zip", device="cpu")
    obs, _ = env.reset(seed=0)
    assert loaded.policy.q_net(loaded.policy.obs_to_tensor(obs)[0]).shape == (1, 4)


@pytest.mark.parametrize("masked", [True, False])
def test_training_runs_with_and_without_masked_targets(tmp_path, masked):
    meta = train(tiny_config(tmp_path / str(masked), masked_targets=masked), predictor=FakePredictor())
    assert meta["config"]["masked_targets"] is masked
    assert (tmp_path / str(masked) / "tiny" / "best.zip").exists()
