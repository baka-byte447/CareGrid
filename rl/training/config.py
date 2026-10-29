"""
CareGrid-RL: DQN training configuration (Phase 8)

One dataclass holds every number that defines a training run, so a run is fully described
by its metadata.json. Defaults are the values chosen in the Phase 8 plan (decisions D5-D12).
"""
from dataclasses import asdict, dataclass, field
from typing import Dict, Optional, Tuple

from rl.environment.rewards import DEFAULT_ACUITY_WEIGHTS


@dataclass
class DQNConfig:
    run_name: str = "dqn_v1_s0"
    seed: int = 0
    out_dir: str = "rl/agents/models"
    total_timesteps: int = 1_000_000

    # --- algorithm (stable-baselines3 DQN) ---
    net_arch: Tuple[int, ...] = (128, 128)
    learning_rate: float = 3e-4
    learning_rate_final: Optional[float] = None   # if set: linear decay learning_rate -> this value
    buffer_size: int = 500_000
    learning_starts: int = 10_000
    batch_size: int = 128
    tau: float = 1.0                       # hard target-network copy
    target_update_interval: int = 2_000
    train_freq: int = 4
    gradient_steps: int = 1
    gamma: float = 0.995
    exploration_initial_eps: float = 1.0
    exploration_final_eps: float = 0.05
    exploration_fraction: float = 0.3
    max_grad_norm: float = 10.0
    masked_targets: bool = True           # MaskedDQN: Bellman max over valid next actions only

    # --- environment / reward ---
    mode_weights: Dict[str, float] = field(
        default_factory=lambda: {"normal": 0.7, "moderate_surge": 0.3})
    stream_days: float = 30.0
    drain_days: float = 7.0
    reward_scale: float = 10.0
    invalid_action_penalty: float = 0.1
    acuity_weights: Dict[int, float] = field(default_factory=lambda: dict(DEFAULT_ACUITY_WEIGHTS))

    # --- validation / model selection ---
    val_every_steps: int = 50_000
    val_streams_during_training: int = 10
    final_val_streams: int = 20

    @classmethod
    def smoke(cls, **overrides) -> "DQNConfig":
        """Tiny configuration that exercises the whole pipeline in about a minute."""
        base = dict(run_name="smoke", total_timesteps=20_000, stream_days=5.0, drain_days=2.0,
                    learning_starts=1_000, buffer_size=50_000, batch_size=64,
                    target_update_interval=500, exploration_fraction=0.5,
                    val_every_steps=5_000, val_streams_during_training=3, final_val_streams=3)
        base.update(overrides)
        return cls(**base)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["net_arch"] = list(self.net_arch)
        d["acuity_weights"] = {str(k): v for k, v in self.acuity_weights.items()}
        return d
