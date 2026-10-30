"""
CareGrid-RL: Replay buffer warmup with heuristic policy (Phase 8 learning fix X5).

Pre-populates the replay buffer with high-quality transitions from a heuristic
(e.g. combined_heuristic_policy H3) before gradient descent starts.
This prevents the agent from falling into early degenerate local optima (such as
over-using WAIT) during early random exploration.
"""
from typing import Any
import numpy as np


def fill_replay_buffer_with_heuristic(model: Any, env: Any, n_steps: int, policy: Any) -> int:
    """Run `policy` on `env` for `n_steps` and add every transition to `model.replay_buffer`.

    Returns the number of steps added.
    """
    if n_steps <= 0:
        return 0

    obs = env.reset()
    if isinstance(obs, tuple):
        obs = obs[0]

    underlying = env.unwrapped if hasattr(env, "unwrapped") else env

    steps_added = 0
    while steps_added < n_steps:
        # Single-decision policy call
        single_obs = obs[0] if (isinstance(obs, np.ndarray) and obs.ndim > 1) else obs
        action = int(policy(single_obs, underlying))

        step_res = env.step(action)
        if len(step_res) == 5:
            next_obs, reward, terminated, truncated, info = step_res
            done = bool(terminated or truncated)
        else:
            next_obs, reward, done, info = step_res

        single_next = next_obs[0] if (isinstance(next_obs, np.ndarray) and next_obs.ndim > 1) else next_obs

        # Format arrays for SB3 ReplayBuffer (expects batch dim n_envs=1)
        rb_obs = np.asarray(single_obs).reshape(1, -1)
        rb_next_obs = np.asarray(single_next).reshape(1, -1)
        rb_action = np.array([[action]])
        rb_reward = np.array([float(reward)])
        rb_done = np.array([bool(done)])
        rb_infos = [info] if isinstance(info, dict) else list(info)

        model.replay_buffer.add(rb_obs, rb_next_obs, rb_action, rb_reward, rb_done, rb_infos)
        steps_added += 1

        if done:
            obs = env.reset()
            if isinstance(obs, tuple):
                obs = obs[0]
        else:
            obs = next_obs

    return steps_added
