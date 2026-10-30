"""Tests for Observation v2 (torch-free)."""
import numpy as np
import pytest

from rl.environment.hospital_env import (
    CareGridHospitalEnv,
    N_OBSERVATIONS,
    N_OBSERVATIONS_V2,
    OBSERVATION_FEATURES,
    OBSERVATION_FEATURES_V2,
)


def test_observation_v1_and_v2_shapes():
    """Verify observation space shapes for v1 and v2."""
    assert N_OBSERVATIONS == 14
    assert N_OBSERVATIONS_V2 == 17
    assert len(OBSERVATION_FEATURES) == 14
    assert len(OBSERVATION_FEATURES_V2) == 17
    assert OBSERVATION_FEATURES_V2[:14] == OBSERVATION_FEATURES
    assert OBSERVATION_FEATURES_V2[14:] == ("wait_so_far", "time_of_day_sin", "time_of_day_cos")


def test_env_observation_version_1():
    """Verify v1 environment produces (14,) observation in [0, 1]."""
    env = CareGridHospitalEnv(max_episode_days=5.0, observation_version=1)
    obs, info = env.reset(seed=0)
    assert obs.shape == (14,)
    assert np.all(obs >= 0.0) and np.all(obs <= 1.0)
    next_obs, reward, terminated, truncated, info = env.step(3)  # WAIT
    assert next_obs.shape == (14,)
    assert np.all(next_obs >= 0.0) and np.all(next_obs <= 1.0)
    env.close()


def test_env_observation_version_2():
    """Verify v2 environment produces (17,) observation in [0, 1]."""
    env = CareGridHospitalEnv(max_episode_days=5.0, observation_version=2)
    obs, info = env.reset(seed=0)
    assert obs.shape == (17,)
    assert np.all(obs >= 0.0) and np.all(obs <= 1.0)
    # Step with WAIT to increase wait time
    for _ in range(5):
        next_obs, reward, terminated, truncated, info = env.step(3)
        assert next_obs.shape == (17,)
        assert np.all(next_obs >= 0.0) and np.all(next_obs <= 1.0)
        if terminated or truncated:
            break
    env.close()


def test_invalid_observation_version():
    """Verify invalid version raises ValueError."""
    with pytest.raises(ValueError, match="observation_version must be 1 or 2"):
        CareGridHospitalEnv(observation_version=3)
