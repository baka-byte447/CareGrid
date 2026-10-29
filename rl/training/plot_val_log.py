"""
CareGrid-RL: learning curves from the validation logs (Phase 8)

    python -m rl.training.plot_val_log --runs dqn_v1_s0,dqn_v1_s1,dqn_v1_s2 \
        --out docs/results/dqn_v1_learning_curve.png

Plots the validation score (scenario-weighted acuity-weighted average wait, lower is better)
against training steps for each run, with the rule baseline B1 and the best simple heuristics
as horizontal reference lines (scored on the same validation streams).
"""
import argparse
import csv
import json
from pathlib import Path


def main() -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True, help="comma-separated run names")
    ap.add_argument("--models-dir", default="rl/agents/models")
    ap.add_argument("--out", default="docs/results/dqn_v1_learning_curve.png")
    args = ap.parse_args()

    fig, ax = plt.subplots(figsize=(9, 5))
    baselines = {}
    for run in [r for r in args.runs.split(",") if r]:
        run_dir = Path(args.models_dir) / run
        rows = list(csv.DictReader(open(run_dir / "val_log.csv")))
        ax.plot([int(r["timesteps"]) for r in rows], [float(r["val_score"]) for r in rows],
                marker="o", markersize=3, label=run)
        meta_path = run_dir / "metadata.json"
        if meta_path.exists() and not baselines:
            baselines = {k: v["val_score"] for k, v in json.loads(meta_path.read_text())["baseline_validation"].items()}
    styles = {"b1_rule": ("tab:red", "B1 rule baseline"), "h1_lowest_tier": ("tab:green", "H1 heuristic"),
              "h3_combined": ("tab:olive", "H3 heuristic")}
    for key, (color, label) in styles.items():
        if key in baselines:
            ax.axhline(baselines[key], color=color, linestyle="--", linewidth=1.2, label=f"{label} ({baselines[key]:.0f})")
    ax.set_xlabel("training steps")
    ax.set_ylabel("validation score (weighted wait, min; lower = better)")
    ax.set_title("DQN validation score during training")
    ax.set_yscale("log")
    ax.grid(alpha=0.3, which="both")
    ax.legend(fontsize=8)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(args.out, dpi=130)
    print(f"Saved {args.out}")


if __name__ == "__main__":
    main()
