"""
CareGrid-RL: Double DQN implementation (Phase 8 learning fix X1)

Subclasses Stable-Baselines3 DQN overriding train() so that:
  - Action selection in the next state is performed by the ONLINE network (q_net)
  - Action evaluation is performed by the TARGET network (q_net_target)

This decouples selection from evaluation, resolving the max-operator overestimation
bias inherent in standard DQN (van Hasselt et al., 2015).

Supports optional action masking when paired with MaskedReplayBuffer:
invalid actions in s' receive -inf so the online argmax only selects valid actions.
"""
from typing import Any, Optional

import numpy as np
import torch as th
from torch.nn import functional as F
from stable_baselines3 import DQN

from rl.agents.masked_dqn import MaskedReplayBuffer


class DoubleDQN(DQN):
    """Stable-Baselines3 DQN overriding train() for Double Q-learning.

    y = r + (1 - done) * gamma * Q_target(s', argmax_a Q_online(s', a))
    """

    def __init__(self, policy, env, masked_targets: bool = True, **kwargs):
        if masked_targets:
            kwargs.setdefault("replay_buffer_class", MaskedReplayBuffer)
        self.masked_targets = masked_targets
        super().__init__(policy, env, **kwargs)

    def train(self, gradient_steps: int, batch_size: int = 100) -> None:
        # Switch to train mode (affects batch norm / dropout)
        self.policy.set_training_mode(True)
        # Update learning rate according to schedule
        self._update_learning_rate(self.policy.optimizer)

        losses = []
        for _ in range(gradient_steps):
            # Sample replay buffer
            replay_data = self.replay_buffer.sample(batch_size, env=self._vec_normalize_env)
            discounts = replay_data.discounts if replay_data.discounts is not None else self.gamma

            with th.no_grad():
                # 1. Action selection using the ONLINE network (q_net)
                next_q_online = self.policy.q_net(replay_data.next_observations)
                if hasattr(replay_data, "next_valid") and self.masked_targets:
                    # Mask invalid actions with -inf so argmax only picks valid ones
                    masked_online = next_q_online.masked_fill(~replay_data.next_valid, float("-inf"))
                    # If all actions were invalid (should never happen), fall back to unmasked
                    fallback = next_q_online.argmax(dim=1, keepdim=True)
                    best_actions = masked_online.argmax(dim=1, keepdim=True)
                    has_finite = th.isfinite(th.gather(masked_online, dim=1, index=best_actions))
                    next_actions = th.where(has_finite, best_actions, fallback)
                else:
                    next_actions = next_q_online.argmax(dim=1, keepdim=True)

                # 2. Action evaluation using the TARGET network (q_net_target)
                next_q_target = self.policy.q_net_target(replay_data.next_observations)
                next_q_values = th.gather(next_q_target, dim=1, index=next_actions)

                # 1-step TD target
                target_q_values = replay_data.rewards + (1 - replay_data.dones) * discounts * next_q_values

            # Get current Q-values estimates
            current_q_values = self.policy.q_net(replay_data.observations)

            # Retrieve the q-values for the actions from the replay buffer
            current_q_values = th.gather(current_q_values, dim=1, index=replay_data.actions.long())

            # Compute Huber loss (less sensitive to outliers)
            loss = F.smooth_l1_loss(current_q_values, target_q_values)
            losses.append(loss.item())

            # Optimize the policy
            self.policy.optimizer.zero_grad()
            loss.backward()
            # Clip gradient norm
            th.nn.utils.clip_grad_norm_(self.policy.parameters(), self.max_grad_norm)
            self.policy.optimizer.step()

        # Increase update counter
        self._n_updates += gradient_steps

        self.logger.record("train/n_updates", self._n_updates, exclude="tensorboard")
        self.logger.record("train/loss", np.mean(losses))

