"""
CareGrid-RL: validation during training (Phase 8)

Every `val_every_steps` the current network is scored with the masked greedy policy on
held-out VALIDATION streams (never training or evaluation streams). The score is the
scenario-weighted acuity-weighted average wait (lower is better); the best checkpoint is
saved as best.zip.

Burn-in rule: only checkpoints taken after the exploration schedule has finished
(exploration_fraction x total_timesteps) may become best.zip. Before that the network is
barely trained, and an almost-random network can act like a fixed heuristic by chance and
score well on a handful of validation streams. Every checkpoint is still logged.
"""
import csv
import json
from pathlib import Path
from typing import Any, Callable, Dict, List

from stable_baselines3.common.callbacks import BaseCallback

from rl.agents.sb3_utils import sb3_q_fn
from rl.evaluation.evaluate import evaluate_on_streams
from rl.evaluation.policies import Policy, masked_greedy_policy
from rl.training.config import DQNConfig
from simulator.patients.streams import VAL_SEEDS

TRACKED = (("acuity_weighted_avg_wait_min", "weighted_wait"),
           ("avg_wait_incl_unadmitted_min", "avg_wait"),
           ("critical_avg_wait_min", "critical_wait"),
           ("patients_still_waiting", "still_waiting"),
           ("icu_utilization", "icu_util"),
           ("invalid_actions", "invalid_actions"))


def score_policy_on_validation(policy: Policy, config: DQNConfig, predictor: Any,
                               n_streams: int) -> Dict[str, Any]:
    """{'val_score': float, mode: {metric: mean}} on the first n_streams validation streams."""
    seeds = list(VAL_SEEDS)[:n_streams]
    total_w = float(sum(config.mode_weights.values()))
    out: Dict[str, Any] = {"val_score": 0.0}
    for mode, weight in config.mode_weights.items():
        res = evaluate_on_streams(policy, seeds=seeds, days=config.stream_days, mode=mode,
                                  drain_days=config.drain_days, los_predictor=predictor)
        s = res["summary"]
        out[mode] = {short: s[key]["mean"] for key, short in TRACKED}
        out["val_score"] += (weight / total_w) * s["acuity_weighted_avg_wait_min"]["mean"]
    out["val_score"] = round(out["val_score"], 4)
    return out


class ValidationCallback(BaseCallback):
    def __init__(self, config: DQNConfig, predictor: Any, run_dir: Path):
        super().__init__(verbose=0)
        self.config, self.predictor, self.run_dir = config, predictor, Path(run_dir)
        self.best_score = float("inf")
        self.best_step = 0
        self.min_select_step = int(config.exploration_fraction * config.total_timesteps)
        self.history: List[dict] = []
        self._next_eval = config.val_every_steps
        self._log_path = self.run_dir / "val_log.csv"
        self._header_written = False

    def _on_training_start(self) -> None:
        import time
        self._t_start = time.time()
        self.run_dir.mkdir(parents=True, exist_ok=True)
        if self._log_path.exists() and not self.resumed:
            self._log_path.unlink()

    # ---- resumable checkpoints (the training machine may be restarted at any time) ----

    resumed = False

    def save_resume_state(self, elapsed_seconds: float = 0.0) -> None:
        """Model + replay buffer first, then the small state file that marks them as complete."""
        self.model.save(self.run_dir / "resume.zip")
        self.model.save_replay_buffer(self.run_dir / "resume_buffer.pkl")
        state = {"num_timesteps": int(self.num_timesteps), "best_score": self.best_score,
                 "best_step": self.best_step, "next_eval": self._next_eval,
                 "elapsed_seconds": float(elapsed_seconds + self._elapsed())}
        tmp = self.run_dir / "resume_state.json.tmp"
        tmp.write_text(json.dumps(state))
        tmp.replace(self.run_dir / "resume_state.json")

    def restore(self, state: dict) -> None:
        self.best_score = state["best_score"] if state["best_score"] is not None else float("inf")
        self.best_step = int(state["best_step"])
        self._next_eval = int(state["next_eval"])
        self._header_written = self._log_path.exists()
        self.resumed = True
        self._elapsed_before = float(state.get("elapsed_seconds", 0.0))

    _elapsed_before = 0.0

    def _elapsed(self) -> float:
        import time
        return time.time() - getattr(self, "_t_start", time.time())

    def validate(self) -> Dict[str, Any]:
        policy = masked_greedy_policy(sb3_q_fn(self.model))
        result = score_policy_on_validation(policy, self.config, self.predictor,
                                            self.config.val_streams_during_training)
        row = {"timesteps": int(self.num_timesteps), "val_score": result["val_score"],
               "epsilon": round(float(getattr(self.model, "exploration_rate", 0.0)), 4)}
        for mode in self.config.mode_weights:
            for _, short in TRACKED:
                row[f"{mode}_{short}"] = result[mode][short]
        with open(self._log_path, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(row))
            if not self._header_written:
                writer.writeheader()
                self._header_written = True
            writer.writerow(row)
        self.history.append(row)
        if self.num_timesteps >= self.min_select_step and result["val_score"] < self.best_score:
            self.best_score, self.best_step = result["val_score"], int(self.num_timesteps)
            self.model.save(self.run_dir / "best.zip")
        print(f"[validation] step {self.num_timesteps:>9,d}  val_score {result['val_score']:9.2f}  "
              f"(best {self.best_score:.2f} @ {self.best_step:,d})  eps {row['epsilon']:.3f}"
              f"{'' if self.num_timesteps >= self.min_select_step else '  [burn-in]'}", flush=True)
        return result

    def _on_step(self) -> bool:
        if self.num_timesteps >= self._next_eval:
            self.validate()
            self._next_eval += self.config.val_every_steps
            self.save_resume_state(self._elapsed_before)
        return True
