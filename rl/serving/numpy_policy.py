"""
NumpyQPolicy – pure-NumPy DQN forward pass.

Loads a .npz file exported by rl.serving.export_policy and runs inference
without any torch / SB3 dependency.  Suitable for use inside backend/
where heavy ML imports are banned.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np


class NumpyQPolicy:
    """Forward-pass-only DQN Q-network backed by a .npz weight archive.

    Architecture is a 2-hidden-layer MLP with ReLU activations:
        obs → Linear(w0,b0) → ReLU → Linear(w1,b1) → ReLU → Linear(w2,b2) → Q

    The .npz must contain keys w0,b0,w1,b1,w2,b2 with weights stored as
    [in_features, out_features] (i.e., transposed from PyTorch convention).
    """

    def __init__(self, npz_path: str | Path) -> None:
        npz_path = Path(npz_path)
        if not npz_path.exists():
            raise FileNotFoundError(f"Model weights not found: {npz_path}")
        data = np.load(npz_path)
        required = {"w0", "b0", "w1", "b1", "w2", "b2"}
        missing = required - set(data.files)
        if missing:
            raise ValueError(f"Missing keys in {npz_path}: {missing}")
        self._w = [data["w0"], data["w1"], data["w2"]]
        self._b = [data["b0"], data["b1"], data["b2"]]
        self.n_inputs: int = int(self._w[0].shape[0])
        self.n_actions: int = int(self._w[2].shape[1])

    def q_values(self, obs: np.ndarray) -> np.ndarray:
        """Return Q-value vector of shape (n_actions,) for a single observation."""
        x = np.asarray(obs, dtype=np.float32).ravel()
        if x.shape[0] != self.n_inputs:
            raise ValueError(
                f"Observation has {x.shape[0]} features; model expects {self.n_inputs}"
            )
        for i in range(2):
            x = x @ self._w[i] + self._b[i]
            x = np.maximum(x, 0.0)  # ReLU
        return x @ self._w[2] + self._b[2]  # shape (n_actions,)

    def best_action(self, obs: np.ndarray, valid_mask: Optional[np.ndarray] = None) -> int:
        """Return the action with the highest Q-value among valid actions.

        Parameters
        ----------
        obs:       Float32 observation vector.
        valid_mask: Boolean array of length n_actions; True = valid.
                   If None, all actions are valid.
        """
        q = self.q_values(obs)
        if valid_mask is not None:
            mask = np.asarray(valid_mask, dtype=bool)
            if not mask.any():
                raise ValueError("valid_mask has no valid actions")
            q = np.where(mask, q, -np.inf)
        return int(np.argmax(q))

