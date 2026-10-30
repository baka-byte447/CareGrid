"""Tests for heuristic replay buffer warmup (skipped without torch/SB3)."""
import pytest

pytest.importorskip("gymnasium")
pytest.importorskip("torch")
pytest.importorskip("stable_baselines3")

from rl.agents.double_dqn import DoubleDQN
from rl.evaluation.policies import combined_heuristic_policy
from rl.training.config import DQNConfig
from rl.training.envs import make_training_env
from rl.training.warmup import fill_replay_buffer_with_heuristic
from tests.test_rl_training.test_training_pipeline import FakePredictor, tiny_config


def test_fill_replay_buffer_with_heuristic(tmp_path):
    config = tiny_config(tmp_path, total_timesteps=100)
    env = make_training_env(config, FakePredictor())
    model = DoubleDQN("MlpPolicy", env, buffer_size=500, learning_starts=100, seed=0, device="cpu")

    assert model.replay_buffer.size() == 0

    added = fill_replay_buffer_with_heuristic(model, env, 25, combined_heuristic_policy)
    assert added == 25
    assert model.replay_buffer.size() == 25
