"""
Joint training script for the 3-agent CareGrid MARL system.

Freezes the trained Bed Agent (DQN x6_obs_v2) and jointly trains:
  - SurgeAgent (macro operating mode: NORMAL vs SURGE)
  - ResourceManagerAgent (meso supply coordinator: HOLD / EXPEDITE_CLEANING /
    MOBILIZE_VENTILATOR / FLOAT_STAFF)

Usage:
  python -m rl.marl.train_marl --episodes 40 --out-dir models/serving
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Any

import numpy as np

from rl.environment.hospital_env import CareGridHospitalEnv
from rl.marl.multi_agent_env import CareGridMAEnv
from rl.marl.resource_agent import ResourceManagerAgent
from rl.marl.surge_agent import SurgeAgent
from rl.serving.numpy_policy import NumpyQPolicy
from simulator.patients.streams import TRAIN_SEEDS, generate_stream


def train_marl(
    bed_model_path: str = "models/serving/dqn_x6_obs_v2.npz",
    out_dir: str = "models/serving",
    episodes: int = 40,
    lr: float = 0.015,
    gamma: float = 0.95,
    seed: int = 0,
) -> Dict[str, Any]:
    rng = np.random.default_rng(seed)
    bed_policy = NumpyQPolicy(bed_model_path) if Path(bed_model_path).exists() else None

    base_env = CareGridHospitalEnv(
        observation_version=2,
        reward_mode="queue_cost",
        reward_scale=10.0,
        max_episode_days=30.0,
    )
    ma_env = CareGridMAEnv(base_env=base_env, bed_policy=bed_policy, macro_interval=10)

    surge_agent = SurgeAgent()
    resource_agent = ResourceManagerAgent()

    # Mix normal, moderate surge, and shortage conditions during training
    train_configs = [
        ("normal", None),
        ("moderate_surge", None),
        ("normal", "icu_shortage"),
        ("normal", "equipment_shortage"),
        ("normal", "staff_shortage"),
        ("moderate_surge", "combined_crisis"),
    ]

    history = []
    for ep in range(episodes):
        mode, shortage = train_configs[ep % len(train_configs)]
        stream_seed = int(TRAIN_SEEDS[ep % len(TRAIN_SEEDS)])
        patients = generate_stream(stream_seed, days=30.0, mode=mode)

        surge_obs, info = ma_env.reset(
            seed=stream_seed,
            options={"patients": patients, "shortage_scenario": shortage},
        )
        res_obs = info["resource_obs"]

        done = False
        ep_reward = 0.0
        eps = max(0.05, 0.4 * (1.0 - ep / max(1, episodes)))

        while not done:
            # 1. Surge Agent action
            if rng.random() < eps:
                s_act = int(rng.integers(2))
            else:
                s_act = surge_agent.predict(surge_obs)

            # 2. Resource Manager action (masked to valid interventions)
            res_mask = ma_env.valid_resource_actions()
            if rng.random() < eps:
                valid_idx = np.flatnonzero(res_mask)
                r_act = int(rng.choice(valid_idx))
            else:
                r_act = resource_agent.predict(res_obs, valid_mask=res_mask)

            next_surge_obs, reward, term, trunc, step_info = ma_env.step((s_act, r_act))
            next_res_obs = step_info["resource_obs"]
            done = term or trunc
            ep_reward += reward

            # Q-learning update for SurgeAgent (clipped TD error for stability)
            target_s = reward + (
                0.0 if done else gamma * float(np.max(surge_agent.q_values(next_surge_obs)))
            )
            err_s = float(np.clip(target_s - float(surge_agent.q_values(surge_obs)[s_act]), -10.0, 10.0))
            surge_agent.W[:, s_act] += lr * err_s * surge_obs
            surge_agent.b[s_act] += lr * err_s

            # Q-learning update for ResourceManagerAgent
            resource_agent.update(
                res_obs, r_act, reward, next_res_obs, done, lr=lr, gamma=gamma
            )

            surge_obs = next_surge_obs
            res_obs = next_res_obs

        history.append(
            {
                "episode": ep,
                "mode": mode,
                "shortage": shortage or "none",
                "reward": round(float(ep_reward), 3),
                "surge_steps": sum(1 for m in ma_env.mode_history if m == 1),
                "resource_interventions": sum(1 for r in ma_env.resource_history if r != 0),
            }
        )
        if (ep + 1) % 10 == 0 or ep == 0:
            print(
                f"Episode {ep + 1:3d}/{episodes} | {mode:14s} | "
                f"shortage={str(shortage):18s} | reward={ep_reward:8.2f}"
            )

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    surge_path = out_path / "surge_agent.npz"
    res_path = out_path / "resource_agent.npz"
    surge_agent.save(surge_path)
    resource_agent.save(res_path)

    meta = {
        "episodes": episodes,
        "bed_model": bed_model_path,
        "surge_agent": str(surge_path),
        "resource_agent": str(res_path),
        "mean_reward_last_10": float(np.mean([h["reward"] for h in history[-10:]])),
    }
    (out_path / "marl_agents.metadata.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )
    print(f"Saved MARL agents to {surge_path} and {res_path}")
    return meta


def main() -> None:
    parser = argparse.ArgumentParser(description="Train 3-agent CareGrid MARL")
    parser.add_argument("--bed-model", default="models/serving/dqn_x6_obs_v2.npz")
    parser.add_argument("--out-dir", default="models/serving")
    parser.add_argument("--episodes", type=int, default=40)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    train_marl(
        bed_model_path=args.bed_model,
        out_dir=args.out_dir,
        episodes=args.episodes,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
