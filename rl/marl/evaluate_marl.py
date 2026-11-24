"""
Compare Single-Agent DQN against Hierarchical Multi-Agent (Surge Agent + Bed Agent).

Evaluates on:
  - normal
  - moderate_surge
  - severe_surge
  - icu_shortage
  - combined_crisis
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Any

import numpy as np

from rl.environment.hospital_env import CareGridHospitalEnv
from rl.marl.multi_agent_env import CareGridMAEnv
from rl.marl.surge_agent import SurgeAgent
from rl.serving.numpy_policy import NumpyQPolicy
from simulator.metrics.collector import MetricsCollector
from simulator.metrics.summary import compute_metrics


def run_evaluation(
    bed_model_path: str,
    episodes_per_scenario: int = 5,
    out_file: str | None = None,
) -> Dict[str, Any]:
    scenarios = ["normal", "moderate_surge", "severe_surge", "icu_shortage", "combined_crisis"]
    bed_policy = NumpyQPolicy(bed_model_path)
    surge_agent = SurgeAgent()

    results = {}

    for sc in scenarios:
        single_agent_rewards = []
        marl_rewards = []

        # 1. Single Agent Baseline
        env_single = CareGridHospitalEnv(
            observation_version=2,
            patient_file="patients.csv",
            max_episode_days=10.0,
        )
        for seed in range(episodes_per_scenario):
            obs, _ = env_single.reset(seed=seed, options={"shortage_scenario": sc if sc in ("icu_shortage", "combined_crisis") else None})
            done = False
            total_r = 0.0
            while not done:
                mask = env_single.valid_actions()
                action = bed_policy.best_action(obs, valid_mask=mask)
                obs, r, term, trunc, _ = env_single.step(action)
                total_r += r
                done = term or trunc
            single_agent_rewards.append(total_r)

        # 2. Multi-Agent
        env_ma_base = CareGridHospitalEnv(
            observation_version=2,
            patient_file="patients.csv",
            max_episode_days=10.0,
        )
        ma_env = CareGridMAEnv(base_env=env_ma_base, bed_policy=bed_policy, macro_interval=10)
        for seed in range(episodes_per_scenario):
            obs, _ = ma_env.reset(seed=seed, options={"shortage_scenario": sc if sc in ("icu_shortage", "combined_crisis") else None})
            done = False
            total_r = 0.0
            while not done:
                macro_action = surge_agent.predict(obs)
                obs, r, term, trunc, _ = ma_env.step(macro_action)
                total_r += r
                done = term or trunc
            marl_rewards.append(total_r)

        results[sc] = {
            "single_agent_mean_reward": float(np.mean(single_agent_rewards)),
            "marl_mean_reward": float(np.mean(marl_rewards)),
            "improvement": float(np.mean(marl_rewards) - np.mean(single_agent_rewards)),
        }
        print(f"Scenario {sc:18s} | Single-Agent: {np.mean(single_agent_rewards):8.2f} | MARL: {np.mean(marl_rewards):8.2f}")

    if out_file:
        p = Path(out_file)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"Wrote MARL evaluation results to {out_file}")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--bed-model", default="models/serving/dqn_x6_obs_v2.npz")
    parser.add_argument("--episodes", type=int, default=3)
    parser.add_argument("--out", default="docs/results/marl_evaluation.json")
    args = parser.parse_args()
    run_evaluation(args.bed_model, args.episodes, args.out)

