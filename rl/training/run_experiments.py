"""
CareGrid-RL: Experiment runner for Phase 8 learning fixes (PR-3)

Runs one factor at a time (300k steps, seed 0, 20 val streams, no burn-in filter),
logs validation metrics, and compares against control and baseline targets (B1, H1, H3).

Usage:
    python -m rl.training.run_experiments --list
    python -m rl.training.run_experiments --run x0_control
    python -m rl.training.run_experiments --run x1_double_dqn
    python -m rl.training.run_experiments --summary
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

from rl.training.config import DQNConfig
from rl.training.train_dqn import train

EXPERIMENTS: Dict[str, Dict[str, Any]] = {
    "x0_control": {
        "description": "Control: Masked DQN baseline (300k, 20 val streams, no burn-in)",
        "config": dict(
            algorithm="masked_dqn",
            total_timesteps=300_000,
            val_every_steps=25_000,
            val_streams_during_training=20,
            final_val_streams=20,
            burn_in=False,
        ),
    },
    "x1_double_dqn": {
        "description": "X1: Double DQN (online net action selection, target net evaluation)",
        "config": dict(
            algorithm="double_dqn",
            total_timesteps=300_000,
            val_every_steps=25_000,
            val_streams_during_training=20,
            final_val_streams=20,
            burn_in=False,
        ),
    },
    "x2a_lr_low": {
        "description": "X2a: Lower learning rate (1e-4 vs default 3e-4)",
        "config": dict(
            algorithm="masked_dqn",
            learning_rate=1e-4,
            total_timesteps=300_000,
            val_every_steps=25_000,
            val_streams_during_training=20,
            final_val_streams=20,
            burn_in=False,
        ),
    },
    "x2b_lr_high": {
        "description": "X2b: Higher learning rate (1e-3 vs default 3e-4)",
        "config": dict(
            algorithm="masked_dqn",
            learning_rate=1e-3,
            total_timesteps=300_000,
            val_every_steps=25_000,
            val_streams_during_training=20,
            final_val_streams=20,
            burn_in=False,
        ),
    },
    "x3_reward_scale": {
        "description": "X3: Reward scale 50.0 (variance reduction, scale 50 vs 10)",
        "config": dict(
            algorithm="masked_dqn",
            reward_scale=50.0,
            invalid_action_penalty=0.5,
            total_timesteps=300_000,
            val_every_steps=25_000,
            val_streams_during_training=20,
            final_val_streams=20,
            burn_in=False,
        ),
    },
    "x4_gamma": {
        "description": "X4: Discount factor gamma 0.99 (vs default 0.995)",
        "config": dict(
            algorithm="masked_dqn",
            gamma=0.99,
            total_timesteps=300_000,
            val_every_steps=25_000,
            val_streams_during_training=20,
            final_val_streams=20,
            burn_in=False,
        ),
    },
    "x5_heuristic_warmup": {
        "description": "X5: Heuristic replay seeding (50k H3 transitions pre-filled)",
        "config": dict(
            algorithm="masked_dqn",
            heuristic_warmup_steps=50_000,
            total_timesteps=300_000,
            val_every_steps=25_000,
            val_streams_during_training=20,
            final_val_streams=20,
            burn_in=False,
        ),
    },
    "x6_obs_v2": {
        "description": "X6: Observation v2 (17 features: +wait_so_far, +time_of_day_sin/cos)",
        "config": dict(
            algorithm="masked_dqn",
            observation_version=2,
            total_timesteps=300_000,
            val_every_steps=25_000,
            val_streams_during_training=20,
            final_val_streams=20,
            burn_in=False,
        ),
    },
    "x7_combo": {
        "description": "X7: Combined top winners (Double DQN + Obs v2 + Warmup + Reward scale 50)",
        "config": dict(
            algorithm="double_dqn",
            observation_version=2,
            reward_scale=50.0,
            invalid_action_penalty=0.5,
            heuristic_warmup_steps=25_000,
            total_timesteps=300_000,
            val_every_steps=25_000,
            val_streams_during_training=20,
            final_val_streams=20,
            burn_in=False,
        ),
    },
}


def run_experiment(exp_name: str, smoke: bool = False, timesteps: int = None) -> dict:
    if exp_name not in EXPERIMENTS:
        raise ValueError(f"Unknown experiment: {exp_name}. Available: {list(EXPERIMENTS.keys())}")

    info = EXPERIMENTS[exp_name]
    cfg_args = dict(info["config"])
    cfg_args["run_name"] = exp_name
    if timesteps is not None:
        cfg_args["total_timesteps"] = timesteps

    if smoke:
        cfg_args["total_timesteps"] = 2_000
        cfg_args["val_every_steps"] = 1_000
        cfg_args["val_streams_during_training"] = 2
        cfg_args["final_val_streams"] = 2

    config = DQNConfig(**cfg_args)
    print(f"\n{'='*70}\nStarting experiment: {exp_name}\nDescription: {info['description']}\n{'='*70}\n", flush=True)
    return train(config)


def summarize_experiments(models_dir: str = "rl/agents/models") -> None:
    p = Path(models_dir)
    rows = []
    for exp_name in EXPERIMENTS:
        exp_dir = p / exp_name
        meta_file = exp_dir / "metadata.json"
        if not meta_file.exists():
            continue
        try:
            meta = json.loads(meta_file.read_text())
            val = meta.get("best_checkpoint_validation", {})
            val_score = val.get("val_score", float("nan"))
            norm = val.get("normal", {}).get("weighted_wait", float("nan"))
            mod = val.get("moderate_surge", {}).get("weighted_wait", float("nan"))
            best_step = meta.get("best_step", 0)
            rows.append({
                "name": exp_name,
                "val_score": val_score,
                "normal": norm,
                "moderate": mod,
                "best_step": best_step,
                "description": EXPERIMENTS[exp_name]["description"],
            })
        except Exception as e:
            print(f"Error reading {meta_file}: {e}", file=sys.stderr)

    if not rows:
        print("No completed experiment metadata found.")
        return

    print("\n" + "=" * 80)
    print("CareGrid-RL Phase 8 Learning Fixes Summary (Validation 20 streams)")
    print("=" * 80)
    print(f"{'Experiment':<22} | {'Val Score':<10} | {'Normal':<10} | {'Moderate':<10} | {'Best Step':<10}")
    print("-" * 80)

    # Reference baselines (from Phase 8 targets):
    print(f"{'B1 (Rule-based)':<22} | {'1326.3':<10} | {'440.6':<10} | {'3392.9':<10} | {'--':<10}")
    print(f"{'H1 (Lowest-tier)':<22} | {'1064.0':<10} | {'193.1':<10} | {'3096.2':<10} | {'--':<10}")
    print(f"{'H3 (Combined)':<22} | {'1082.9':<10} | {'209.0':<10} | {'3121.9':<10} | {'--':<10}")
    print("-" * 80)

    for r in sorted(rows, key=lambda x: x["val_score"]):
        print(f"{r['name']:<22} | {r['val_score']:<10.2f} | {r['normal']:<10.2f} | {r['moderate']:<10.2f} | {r['best_step']:<10,d}")
    print("=" * 80 + "\n")


def main() -> None:
    ap = argparse.ArgumentParser(description="CareGrid-RL Experiment Runner (PR-3)")
    ap.add_argument("--list", action="store_true", help="list configured experiments")
    ap.add_argument("--run", type=str, default=None, help="run a specific experiment name")
    ap.add_argument("--smoke", action="store_true", help="run in tiny smoke mode (2k steps)")
    ap.add_argument("--timesteps", type=int, default=None, help="override timesteps")
    ap.add_argument("--summary", action="store_true", help="show summary table of completed runs")
    args = ap.parse_args()

    if args.list:
        print("\nConfigured Phase 8 Experiments:")
        for name, info in EXPERIMENTS.items():
            print(f"  {name:<22} : {info['description']}")
        print()
        return

    if args.summary:
        summarize_experiments()
        return

    if args.run:
        run_experiment(args.run, smoke=args.smoke, timesteps=args.timesteps)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
