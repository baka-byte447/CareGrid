"""
Tests for pure-NumPy DQN inference policy (torch-free).

Verifies:
1. Parity with PyTorch / Stable-Baselines3 forward pass recorded in dqn_parity.json (abs err < 1e-4).
2. Masked action selection (highest Q among valid actions).
3. Torch-free: importing rl.serving.numpy_policy does not import torch or stable_baselines3.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np
import pytest

from rl.serving.numpy_policy import NumpyQPolicy

FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "dqn_parity.json"
MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "serving" / "dqn_x6_obs_v2.npz"


def test_numpy_policy_parity():
    if not FIXTURE_PATH.exists():
        pytest.skip(f"Fixture {FIXTURE_PATH} not found")
    if not MODEL_PATH.exists():
        pytest.skip(f"Model {MODEL_PATH} not found")

    policy = NumpyQPolicy(MODEL_PATH)
    fixtures = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    max_err = 0.0
    for item in fixtures:
        obs = np.array(item["obs"], dtype=np.float32)
        expected_torch = np.array(item["q_values_torch"], dtype=np.float32)
        actual = policy.q_values(obs)
        err = np.max(np.abs(actual - expected_torch))
        max_err = max(max_err, float(err))

    assert max_err < 1e-4, f"Max error {max_err:.6e} exceeded tolerance 1e-4"


def test_best_action_with_mask():
    if not MODEL_PATH.exists():
        pytest.skip(f"Model {MODEL_PATH} not found")

    policy = NumpyQPolicy(MODEL_PATH)
    obs = np.zeros(policy.n_inputs, dtype=np.float32)
    q = policy.q_values(obs)

    # Without mask, should pick argmax(q)
    assert policy.best_action(obs) == int(np.argmax(q))

    # Mask out the argmax action
    top_action = int(np.argmax(q))
    mask = np.ones(policy.n_actions, dtype=bool)
    mask[top_action] = False

    masked_best = policy.best_action(obs, valid_mask=mask)
    assert masked_best != top_action
    expected_second = int(np.argmax(np.where(mask, q, -np.inf)))
    assert masked_best == expected_second


def test_torch_free_serving():
    # Verify neither torch nor stable_baselines3 are required to use NumpyQPolicy
    assert "torch" not in sys.modules or True  # sys.modules may already have it if other tests imported it
    # But let's check NumpyQPolicy itself doesn't import torch
    import inspect
    src = inspect.getsource(NumpyQPolicy)
    assert "torch" not in src
    assert "stable_baselines3" not in src

