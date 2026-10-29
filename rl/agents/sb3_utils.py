"""
CareGrid-RL: glue between Stable-Baselines3 models and the evaluation harness.
torch is imported lazily so that importing this module never requires it.
"""
from typing import Callable

import numpy as np


def sb3_q_fn(model) -> Callable[[np.ndarray], np.ndarray]:
    """Returns obs -> array of the 4 action values, from a trained SB3 DQN model.
    Pair with rl.evaluation.policies.masked_greedy_policy."""
    import torch

    def q_fn(obs: np.ndarray) -> np.ndarray:
        with torch.no_grad():
            tensor, _ = model.policy.obs_to_tensor(np.asarray(obs, dtype=np.float32))
            return model.policy.q_net(tensor).cpu().numpy().reshape(-1)

    return q_fn
