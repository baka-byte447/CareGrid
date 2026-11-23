"""
Phase M1 – Export the trained DQN policy to a framework-free NumPy archive.

Usage:
  python -m rl.serving.export_policy \
      --model rl/agents/models/x6_obs_v2/best.zip \
      --out models/serving/dqn_x6_obs_v2 \
      [--write-parity-fixture tests/fixtures/dqn_parity.json]

The script writes:
  <out>.npz          – weights + biases (w0,b0,w1,b1,w2,b2), all float32
  <out>.metadata.json – algorithm, obs metadata, eval score, git SHA, npz SHA
  <fixture>           – 64-step rollout of (obs, q_values) for parity tests
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np


def _git_head() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


def export_dqn(model_path: str, out_prefix: str, write_parity: str | None = None) -> None:
    """Extract Q-network weights from a Stable-Baselines3 DQN best.zip and
    write a pure-NumPy .npz that NumpyQPolicy can load without torch/SB3."""
    # Import SB3 only here — never from backend/ or rl/serving/
    from stable_baselines3 import DQN  # type: ignore
    import torch  # type: ignore

    model_path = Path(model_path)
    out_prefix = Path(out_prefix)
    out_prefix.parent.mkdir(parents=True, exist_ok=True)

    print(f"Loading model from {model_path} …")
    model = DQN.load(str(model_path))

    # SB3 DQN q_net is a Sequential: Linear-ReLU-Linear-ReLU-Linear
    layers = list(model.policy.q_net.q_net.children())
    linear_layers = [l for l in layers if hasattr(l, "weight")]
    if len(linear_layers) != 3:
        raise RuntimeError(
            f"Expected 3 Linear layers in q_net, found {len(linear_layers)}. "
            "Check SB3 net_arch or model architecture."
        )

    weights: dict[str, np.ndarray] = {}
    for i, layer in enumerate(linear_layers):
        # SB3 stores W as [out, in]; we transpose to [in, out] for matmul(obs, W)
        w = layer.weight.detach().cpu().numpy().T.astype(np.float32)
        b = layer.bias.detach().cpu().numpy().astype(np.float32)
        weights[f"w{i}"] = w
        weights[f"b{i}"] = b
        print(f"  Layer {i}: W {w.shape}, b {b.shape}")

    npz_path = out_prefix.with_suffix(".npz")
    np.savez(npz_path, **weights)

    # SHA-256 of the npz
    sha256 = hashlib.sha256(npz_path.read_bytes()).hexdigest()

    # Load agent metadata
    meta_src = model_path.parent / "metadata.json"
    agent_meta: dict = {}
    if meta_src.exists():
        agent_meta = json.loads(meta_src.read_text(encoding="utf-8"))

    n_inputs = weights["w0"].shape[0]
    n_actions = weights["w2"].shape[1]

    serving_meta = {
        "algorithm": "masked_dqn",
        "obs_version": int(agent_meta.get("config", {}).get("observation_version", 2)),
        "n_inputs": n_inputs,
        "n_actions": n_actions,
        "action_names": ["ICU", "STEP_DOWN", "WARD", "WAIT"],
        "net_arch": [int(weights["w0"].shape[1]), int(weights["w1"].shape[1])],
        "val_score": float(agent_meta.get("best_checkpoint_validation", {}).get("val_score", 0.0)),
        "git_commit_model": str(agent_meta.get("git_commit", "unknown")),
        "git_commit_export": _git_head(),
        "source_model": str(model_path),
        "npz_sha256": sha256,
    }

    meta_path = out_prefix.parent / (out_prefix.name + ".metadata.json")
    meta_path.write_text(json.dumps(serving_meta, indent=2), encoding="utf-8")
    print(f"Wrote {npz_path} ({npz_path.stat().st_size} bytes)")
    print(f"Wrote {meta_path}")
    print(f"  n_inputs={n_inputs}, n_actions={n_actions}, val_score={serving_meta['val_score']:.4f}")

    # Optional parity fixture
    if write_parity:
        _write_parity_fixture(model, weights, n_inputs, n_actions, write_parity)


def _write_parity_fixture(
    model,
    weights: dict[str, np.ndarray],
    n_inputs: int,
    n_actions: int,
    fixture_path: str,
) -> None:
    """Generate 64 random observations and record both torch and numpy Q-values."""
    import torch  # type: ignore

    rng = np.random.default_rng(42)
    fixture_path = Path(fixture_path)
    fixture_path.parent.mkdir(parents=True, exist_ok=True)

    records = []
    for _ in range(64):
        obs = rng.random(n_inputs).astype(np.float32)
        # Torch forward pass
        with torch.no_grad():
            t_obs = torch.tensor(obs, dtype=torch.float32).unsqueeze(0)
            t_q = model.policy.q_net.q_net(t_obs).squeeze(0).numpy().tolist()

        # NumPy forward pass (must match NumpyQPolicy._forward)
        x = obs.copy()
        for i in range(2):
            x = x @ weights[f"w{i}"] + weights[f"b{i}"]
            x = np.maximum(x, 0.0)  # ReLU
        q_np = (x @ weights["w2"] + weights["b2"]).tolist()

        records.append({"obs": obs.tolist(), "q_values_torch": t_q, "q_values_numpy": q_np})

    fixture_path.write_text(json.dumps(records, indent=2), encoding="utf-8")
    print(f"Wrote parity fixture with {len(records)} records → {fixture_path}")

    # Quick sanity
    max_err = max(
        max(abs(a - b) for a, b in zip(r["q_values_torch"], r["q_values_numpy"]))
        for r in records
    )
    print(f"  Max Q-value absolute error (torch vs numpy): {max_err:.6e}")
    if max_err > 1e-4:
        print("  WARNING: error > 1e-4 — check dtype or weight transposition")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export DQN Q-network to NumPy")
    parser.add_argument("--model", required=True, help="Path to SB3 best.zip")
    parser.add_argument("--out", required=True, help="Output prefix (no extension)")
    parser.add_argument("--write-parity-fixture", default=None,
                        help="Write parity JSON for unit tests")
    args = parser.parse_args()
    export_dqn(args.model, args.out, args.write_parity_fixture)


if __name__ == "__main__":
    main()

