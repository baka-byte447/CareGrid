"""
CareGrid-RL: train a DQN allocation agent (Phase 8)

    python -m rl.training.train_dqn --run-name dqn_v1_s0 --seed 0            # full run (1M steps)
    python -m rl.training.train_dqn --run-name smoke --smoke                  # ~1 minute pipeline check

Writes rl/agents/models/<run-name>/{best.zip, last.zip, metadata.json, val_log.csv}.
best.zip is the checkpoint with the lowest VALIDATION score (never chosen on evaluation seeds).
"""
import argparse
import json
import platform
import random
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np

from rl.training.config import DQNConfig


def _git_commit() -> Optional[str]:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10,
                             cwd=Path(__file__).resolve().parents[2])
        return out.stdout.strip() or None
    except Exception:
        return None


def _versions() -> dict:
    import gymnasium, sklearn, stable_baselines3, torch
    return {"python": platform.python_version(), "torch": torch.__version__,
            "stable_baselines3": stable_baselines3.__version__, "gymnasium": gymnasium.__version__,
            "numpy": np.__version__, "scikit_learn": sklearn.__version__}


def train(config: DQNConfig, predictor=None) -> dict:
    import torch
    from stable_baselines3 import DQN

    from ml.los.predictor import LOSPredictor
    from rl.agents.sb3_utils import sb3_q_fn
    from rl.evaluation.policies import (always_wait_policy, combined_heuristic_policy,
                                        lowest_tier_first_policy, make_random_policy,
                                        masked_greedy_policy, rule_based_policy)
    from rl.training.callbacks import ValidationCallback, score_policy_on_validation
    from rl.training.envs import make_training_env

    run_dir = Path(config.out_dir) / config.run_name
    run_dir.mkdir(parents=True, exist_ok=True)
    random.seed(config.seed)
    np.random.seed(config.seed)
    torch.manual_seed(config.seed)
    torch.set_num_threads(1)                 # tiny network: one thread is fastest, no oversubscription

    predictor = predictor or LOSPredictor.load()
    env = make_training_env(config, predictor)
    model = DQN(
        "MlpPolicy", env,
        learning_rate=config.learning_rate, buffer_size=config.buffer_size,
        learning_starts=config.learning_starts, batch_size=config.batch_size, tau=config.tau,
        gamma=config.gamma, train_freq=config.train_freq, gradient_steps=config.gradient_steps,
        target_update_interval=config.target_update_interval,
        exploration_fraction=config.exploration_fraction,
        exploration_initial_eps=config.exploration_initial_eps,
        exploration_final_eps=config.exploration_final_eps, max_grad_norm=config.max_grad_norm,
        policy_kwargs={"net_arch": list(config.net_arch)}, seed=config.seed, device="cpu", verbose=1)

    callback = ValidationCallback(config, predictor, run_dir)
    started = datetime.now()
    t0 = time.time()
    model.learn(total_timesteps=config.total_timesteps, callback=callback, progress_bar=False)
    duration = time.time() - t0
    if not callback.history or callback.history[-1]["timesteps"] != int(model.num_timesteps):
        callback.validate()                               # always score the final network too
    model.save(run_dir / "last.zip")

    best = DQN.load(run_dir / "best.zip", device="cpu")
    n = config.final_val_streams
    final_val = score_policy_on_validation(masked_greedy_policy(sb3_q_fn(best)), config, predictor, n)
    context = {name: score_policy_on_validation(policy, config, predictor, n)
               for name, policy in (("b1_rule", rule_based_policy), ("h1_lowest_tier", lowest_tier_first_policy),
                                    ("h3_combined", combined_heuristic_policy),
                                    ("random", make_random_policy(0)), ("always_wait", always_wait_policy))}
    metadata = {
        "run_name": config.run_name, "seed": config.seed, "config": config.to_dict(),
        "versions": _versions(), "git_commit": _git_commit(),
        "started_at": started.isoformat(timespec="seconds"),
        "duration_seconds": round(duration, 1),
        "steps_per_second": round(config.total_timesteps / max(duration, 1e-9), 1),
        "best_val_score_during_training": round(callback.best_score, 4),
        "best_step": callback.best_step,
        "final_validation_streams": n,
        "best_checkpoint_validation": final_val,
        "baseline_validation": context,
    }
    (run_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))
    print(f"\nSaved {run_dir}  (best step {callback.best_step:,d}, validation score "
          f"{final_val['val_score']:.2f} vs B1 {context['b1_rule']['val_score']:.2f}, "
          f"H1 {context['h1_lowest_tier']['val_score']:.2f})", flush=True)
    return metadata


def _parse_weights(text: str) -> dict:
    return {k.strip(): float(v) for k, v in (item.split("=") for item in text.split(",") if item)}


def main() -> None:
    ap = argparse.ArgumentParser(description="Train a CareGrid DQN allocation agent")
    ap.add_argument("--run-name", default="dqn_v1_s0")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--timesteps", type=int, default=None)
    ap.add_argument("--smoke", action="store_true", help="tiny pipeline check (~1 minute)")
    ap.add_argument("--out-dir", default="rl/agents/models")
    ap.add_argument("--learning-rate", type=float, default=None)
    ap.add_argument("--gamma", type=float, default=None)
    ap.add_argument("--target-update-interval", type=int, default=None)
    ap.add_argument("--buffer-size", type=int, default=None)
    ap.add_argument("--batch-size", type=int, default=None)
    ap.add_argument("--net-arch", default=None, help="comma separated, e.g. 128,128")
    ap.add_argument("--exploration-fraction", type=float, default=None)
    ap.add_argument("--mode-weights", default=None, help="e.g. normal=0.7,moderate_surge=0.3")
    ap.add_argument("--val-every", type=int, default=None)
    args = ap.parse_args()

    overrides = {"run_name": args.run_name, "seed": args.seed, "out_dir": args.out_dir}
    for flag, field_name in (("timesteps", "total_timesteps"), ("learning_rate", "learning_rate"),
                             ("gamma", "gamma"), ("target_update_interval", "target_update_interval"),
                             ("buffer_size", "buffer_size"), ("batch_size", "batch_size"),
                             ("exploration_fraction", "exploration_fraction"), ("val_every", "val_every_steps")):
        value = getattr(args, flag)
        if value is not None:
            overrides[field_name] = value
    if args.net_arch:
        overrides["net_arch"] = tuple(int(x) for x in args.net_arch.split(","))
    if args.mode_weights:
        overrides["mode_weights"] = _parse_weights(args.mode_weights)
    config = DQNConfig.smoke(**overrides) if args.smoke else DQNConfig(**overrides)
    train(config)


if __name__ == "__main__":
    main()
