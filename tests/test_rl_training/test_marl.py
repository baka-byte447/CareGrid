"""
Tests for Multi-Agent Reinforcement Learning (MARL) package.
"""
from __future__ import annotations

from pathlib import Path
import numpy as np
import pytest

from rl.environment.hospital_env import CareGridHospitalEnv
from rl.marl.multi_agent_env import CareGridMAEnv, MODE_NORMAL, MODE_SURGE
from rl.marl.surge_agent import SurgeAgent


def test_marl_env_dimensions_and_step():
    base_env = CareGridHospitalEnv(max_episode_days=2.0)
    ma_env = CareGridMAEnv(base_env=base_env, macro_interval=5)

    obs, info = ma_env.reset(seed=123)
    assert obs.shape == (6,)
    assert obs.dtype == np.float32
    assert np.all(obs >= 0.0) and np.all(obs <= 1.0)
    assert ma_env.current_mode == MODE_NORMAL

    # Step in SURGE mode
    next_obs, reward, term, trunc, s_info = ma_env.step(MODE_SURGE)
    assert next_obs.shape == (6,)
    assert isinstance(reward, float)
    assert ma_env.current_mode == MODE_SURGE
    assert s_info["mode"] == "SURGE"
    assert s_info["decisions_in_macro_step"] > 0


def test_surge_agent_inference_save_load(tmp_path):
    agent = SurgeAgent()
    obs = np.array([0.1, 0.2, 0.8, 0.6, 0.5, 0.5], dtype=np.float32)

    # In a crisis situation (high queue, high critical share, low beds), SURGE should be favored
    action = agent.predict(obs)
    assert action in (0, 1)

    # Test save and load
    save_file = tmp_path / "surge_agent.npz"
    agent.save(save_file)
    assert save_file.exists()

    loaded = SurgeAgent.load(save_file)
    np.testing.assert_allclose(agent.W, loaded.W)
    np.testing.assert_allclose(agent.b, loaded.b)
    assert loaded.predict(obs) == action


def test_surge_agent_training_run():
    base_env = CareGridHospitalEnv(max_episode_days=1.0)
    ma_env = CareGridMAEnv(base_env=base_env, macro_interval=5)
    agent = SurgeAgent()

    # Fast 2-episode training check
    rewards = agent.train(ma_env, total_episodes=2)
    assert len(rewards) == 2

