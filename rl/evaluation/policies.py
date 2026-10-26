"""
CareGrid-RL: policies that can be evaluated on the Gymnasium environment

A policy is a callable  policy(observation, env) -> action  (0=ICU, 1=STEP_DOWN,
2=WARD, 3=WAIT). Baselines read the full simulator state through `env`; learned
agents only use the observation, exactly like a real RL agent would.
"""
from typing import Callable

import numpy as np

from rl.environment.hospital_env import BED_ACTIONS, WAIT_ACTION, CareGridHospitalEnv
from simulator.hospital.allocation_rules import decide_bed

Policy = Callable[[np.ndarray, CareGridHospitalEnv], int]


def rule_based_policy(obs: np.ndarray, env: CareGridHospitalEnv) -> int:
    """Baseline B1: the strict rule table, executed through the environment.
    Reproduces SimulationEngine.run() exactly (tested)."""
    decision = decide_bed(env.current_patient, env.state)
    if decision is None:
        return WAIT_ACTION
    return BED_ACTIONS.index(env.state.beds[decision.bed_id].bed_type)


def always_wait_policy(obs: np.ndarray, env: CareGridHospitalEnv) -> int:
    """Sanity floor: never admits anyone."""
    return WAIT_ACTION


def make_random_policy(seed: int = 0) -> Policy:
    """Sanity floor: uniformly random action (invalid choices are rejected safely)."""
    rng = np.random.default_rng(seed)
    return lambda obs, env: int(rng.integers(4))


def model_policy(model) -> Policy:
    """Wraps any trained model with `predict(obs, deterministic=True)` (e.g. a
    Stable-Baselines3 DQN) as a policy."""
    return lambda obs, env: int(np.asarray(model.predict(obs, deterministic=True)[0]).reshape(-1)[0])


BASELINES = {
    "rule_based": lambda: rule_based_policy,
    "always_wait": lambda: always_wait_policy,
    "random": lambda: make_random_policy(0),
}
