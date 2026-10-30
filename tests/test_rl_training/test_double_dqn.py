"""Tests for DoubleDQN"""
import pytest

pytest.importorskip("gymnasium")
pytest.importorskip("torch")
pytest.importorskip("stable_baselines3")

import numpy as np

from rl.agents.double_dqn import DoubleDQN
from rl.training.config import DQNConfig
from rl.training.envs import make_training_env
from tests.test_rl_training.test_training_pipeline import FakePredictor, tiny_config


def test_double_dqn_target_calculation(tmp_path):
    """Verify that DoubleDQN can train and accumulates updates (structural smoke test)."""
    config = tiny_config(tmp_path, total_timesteps=300, learning_starts=50, batch_size=8)
    env = make_training_env(config, FakePredictor())

    model = DoubleDQN(
        "MlpPolicy", env,
        learning_rate=config.learning_rate, buffer_size=config.buffer_size,
        learning_starts=config.learning_starts, batch_size=config.batch_size,
        tau=config.tau, gamma=config.gamma, train_freq=config.train_freq,
        gradient_steps=config.gradient_steps, target_update_interval=config.target_update_interval,
        policy_kwargs={"net_arch": [16]}, seed=0, device="cpu", verbose=0,
    )
    model.learn(total_timesteps=200)
    # The model must have performed at least one gradient update
    assert model._n_updates >= 1
    assert model.num_timesteps >= 200


def test_double_dqn_training_run_on_tiny_env(tmp_path):
    """Verify that DoubleDQN can run a small training loop."""
    config = tiny_config(tmp_path, total_timesteps=300, learning_starts=50, batch_size=16)
    env = make_training_env(config, FakePredictor())

    model = DoubleDQN(
        "MlpPolicy", env,
        learning_rate=config.learning_rate, buffer_size=config.buffer_size,
        learning_starts=config.learning_starts, batch_size=config.batch_size,
        tau=config.tau, gamma=config.gamma, train_freq=config.train_freq,
        gradient_steps=config.gradient_steps, target_update_interval=config.target_update_interval,
        policy_kwargs={"net_arch": list(config.net_arch)}, seed=config.seed, device="cpu", verbose=0
    )
    model.learn(total_timesteps=150)
    assert model.num_timesteps >= 150
