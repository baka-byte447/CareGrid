"""
Surge Agent – Macro policy for high-level surge mode management.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Tuple
import numpy as np


class SurgeAgent:
    """Macro-level surge coordination policy.

    Observation: (6,) float32 vector:
      [icu_avail, step_down_avail, queue_log_norm, critical_share, tod_sin, tod_cos]
    Action: Discrete(2) [0: NORMAL, 1: SURGE]
    """

    def __init__(self, weights: Optional[np.ndarray] = None, bias: Optional[np.ndarray] = None) -> None:
        # Default linear weights mapping 6 features -> 2 Q-values
        if weights is not None:
            self.W = np.asarray(weights, dtype=np.float32)
            self.b = np.asarray(bias, dtype=np.float32) if bias is not None else np.zeros(2, dtype=np.float32)
        else:
            # Calibrated heuristic initialization:
            # High queue or high critical share with low ICU/step-down increases SURGE Q-value
            self.W = np.array([
                [-1.0, -2.5],  # icu_avail (low icu promotes surge)
                [-0.5, -1.5],  # step_down_avail
                [ 0.0,  3.0],  # queue_log_norm (high queue strongly promotes surge)
                [ 0.0,  2.0],  # critical_share (critical patients promote surge mode)
                [ 0.0,  0.2],  # tod_sin
                [ 0.0,  0.2],  # tod_cos
            ], dtype=np.float32)
            self.b = np.array([1.0, 0.0], dtype=np.float32)

    def q_values(self, obs: np.ndarray) -> np.ndarray:
        x = np.asarray(obs, dtype=np.float32).ravel()
        return x @ self.W + self.b

    def predict(self, obs: np.ndarray, deterministic: bool = True) -> int:
        q = self.q_values(obs)
        return int(np.argmax(q))

    def save(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        np.savez(p, W=self.W, b=self.b)

    @classmethod
    def load(cls, path: str | Path) -> "SurgeAgent":
        p = Path(path)
        data = np.load(p)
        return cls(weights=data["W"], bias=data["b"])

    def train(
        self,
        env,
        total_episodes: int = 30,
        lr: float = 0.02,
        gamma: float = 0.95,
        epsilon_start: float = 0.5,
        epsilon_end: float = 0.05,
    ) -> list[float]:
        """Simple SARSA/Q-learning training on CareGridMAEnv."""
        episode_rewards = []
        rng = np.random.default_rng(42)

        for ep in range(total_episodes):
            obs, _ = env.reset(seed=ep)
            done = False
            ep_reward = 0.0
            eps = max(epsilon_end, epsilon_start * (1.0 - ep / total_episodes))

            while not done:
                if rng.random() < eps:
                    action = int(rng.integers(2))
                else:
                    action = self.predict(obs)

                next_obs, reward, terminated, truncated, _ = env.step(action)
                done = terminated or truncated
                ep_reward += reward

                # Q-learning gradient update
                target = reward + (0.0 if done else gamma * np.max(self.q_values(next_obs)))
                curr_q = self.q_values(obs)[action]
                error = target - curr_q

                # Gradient step: dQ/dW = obs, dQ/db = 1
                self.W[:, action] += lr * error * obs
                self.b[action] += lr * error

                obs = next_obs

            episode_rewards.append(ep_reward)

        return episode_rewards

