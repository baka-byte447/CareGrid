"""
CareGrid-RL: policies that can be evaluated on the Gymnasium environment

A policy is a callable  policy(observation, env) -> action  (0=ICU, 1=STEP_DOWN,
2=WARD, 3=WAIT). Baselines read the full simulator state through `env`; learned
agents only use the observation, exactly like a real RL agent would.
"""
from typing import Callable

import numpy as np

from rl.environment.hospital_env import BED_ACTIONS, WAIT_ACTION, CareGridHospitalEnv
from simulator.hospital.allocation_rules import (allocation_for_bed_type, candidate_bed_types,
                                                 decide_bed)

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


def _first_feasible(env: CareGridHospitalEnv, tiers) -> int:
    """Index of the first bed tier that can take the current patient right now, else WAIT."""
    patient = env.current_patient
    for tier in tiers:
        decision, _ = allocation_for_bed_type(patient, env.state, tier)
        if decision is not None:
            return BED_ACTIONS.index(tier)
    return WAIT_ACTION


def lowest_tier_first_policy(obs: np.ndarray, env: CareGridHospitalEnv) -> int:
    """Heuristic H1: try the acceptable tiers cheapest-first (the REVERSE of the rule
    table's order), so scarce ICU beds stay free for patients who need them."""
    return _first_feasible(env, list(reversed(candidate_bed_types(env.current_patient.acuity))))


def protect_isolation_policy(obs: np.ndarray, env: CareGridHospitalEnv) -> int:
    """Heuristic H2: rule-table order, except an acuity-3 isolation patient may only use
    a step-down bed, never one of the very few ward isolation beds (those are the only
    place acuity 1-2 isolation patients can go)."""
    patient = env.current_patient
    if patient.acuity == 3 and patient.isolation_required:
        return _first_feasible(env, ["STEP_DOWN"])
    return _first_feasible(env, candidate_bed_types(patient.acuity))


def combined_heuristic_policy(obs: np.ndarray, env: CareGridHospitalEnv) -> int:
    """Heuristic H3 = H1 (cheapest tier first) + the H2 isolation override."""
    patient = env.current_patient
    if patient.acuity == 3 and patient.isolation_required:
        return _first_feasible(env, ["STEP_DOWN"])
    return _first_feasible(env, list(reversed(candidate_bed_types(patient.acuity))))


def masked_greedy_policy(q_fn: Callable[[np.ndarray], np.ndarray]) -> Policy:
    """Greedy policy over Q-values with the hard-rule mask applied: invalid actions can
    never be chosen (WAIT is always valid, so a choice always exists). `q_fn(obs)` must
    return the 4 action values; see rl/agents/sb3_utils.py for a Stable-Baselines3 model."""
    def policy(obs: np.ndarray, env: CareGridHospitalEnv) -> int:
        q = np.array(q_fn(obs), dtype=float).reshape(-1)
        q[~env.valid_actions()] = -np.inf
        return int(np.argmax(q))
    return policy


BASELINES = {
    "rule_based": lambda: rule_based_policy,
    "b1": lambda: rule_based_policy,                       # alias used in reports
    "h1_lowest_tier": lambda: lowest_tier_first_policy,
    "h2_protect_isolation": lambda: protect_isolation_policy,
    "h3_combined": lambda: combined_heuristic_policy,
    "always_wait": lambda: always_wait_policy,
    "random": lambda: make_random_policy(0),
}



def safe_policy(base_policy: Policy, layer) -> Policy:
    """Wrap any policy with a SafetyLayer: the layer validates (and may override)
    each decision before it reaches the environment.

    The wrapped policy has the same (obs, env) -> action signature as any other policy.
    After running an episode, check ``layer.override_rate`` and ``layer.stats``.
    """
    def policy(obs: np.ndarray, env: CareGridHospitalEnv) -> int:
        proposed = base_policy(obs, env)
        patient = env.current_patient
        state = env.state
        if patient is None or state is None:
            return proposed
        decision = layer.review(patient, state, proposed, env=env)
        return decision.final_action
    policy.observation_version = getattr(base_policy, "observation_version", 1)
    return policy
