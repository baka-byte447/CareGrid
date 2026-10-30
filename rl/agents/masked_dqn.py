"""
CareGrid-RL: DQN with MASKED Bellman targets (Phase 8)

Plain DQN computes its target as  r + gamma * max over ALL actions of Q_target(s', a').
In this hospital, some actions are impossible in s' (e.g. 'ICU' when the ICU is full). Their
Q-values are rarely trained once exploration is low, they extrapolate optimistically from
states where the same action was good, and the max then picks them: the targets inflate and
the learned policy degrades the longer training runs (observed in plan runs v1 and v2).

MaskedDQN stores, with every transition, which actions were valid in the NEXT state (the
environment reports them as info['next_valid_actions']) and takes the max over valid
actions only. WAIT is always valid, so the max always exists.

Only the Bellman target is masked. Exploration during training stays unmasked (an invalid
action is 'WAIT plus a penalty'); acting at evaluation time is masked separately
(rl.evaluation.policies.masked_greedy_policy).
"""
from typing import Any, NamedTuple, Optional

import numpy as np
import torch as th
from gymnasium import spaces
from stable_baselines3 import DQN
from stable_baselines3.common.buffers import ReplayBuffer
from torch.nn import functional as F

N_ACTIONS = 4


def masked_next_values(next_q: th.Tensor, next_valid: th.Tensor) -> th.Tensor:
    """max over valid actions of next_q, shape (batch, 1). Invalid entries become -inf;
    a row with no valid action (cannot happen: WAIT is always valid) falls back to the
    unmasked max instead of -inf."""
    masked = next_q.masked_fill(~next_valid, float("-inf"))
    best = masked.max(dim=1).values
    fallback = next_q.max(dim=1).values
    best = th.where(th.isfinite(best), best, fallback)
    return best.reshape(-1, 1)


class MaskedSamples(NamedTuple):
    observations: th.Tensor
    actions: th.Tensor
    next_observations: th.Tensor
    dones: th.Tensor
    rewards: th.Tensor
    discounts: Optional[th.Tensor]
    next_valid: th.Tensor


class MaskedReplayBuffer(ReplayBuffer):
    """ReplayBuffer that also remembers the valid-action mask of each next state."""

    def __init__(self, buffer_size, observation_space, action_space, device="auto", n_envs=1,
                 optimize_memory_usage=False, handle_timeout_termination=True):
        if n_envs != 1:
            raise ValueError("MaskedReplayBuffer supports a single environment")
        super().__init__(buffer_size, observation_space, action_space, device=device, n_envs=n_envs,
                         optimize_memory_usage=False, handle_timeout_termination=handle_timeout_termination)
        self.next_valid = np.ones((self.buffer_size, N_ACTIONS), dtype=bool)

    def add(self, obs, next_obs, action, reward, done, infos) -> None:
        mask = infos[0].get("next_valid_actions")
        self.next_valid[self.pos] = np.ones(N_ACTIONS, dtype=bool) if mask is None else np.asarray(mask, dtype=bool)
        super().add(obs, next_obs, action, reward, done, infos)   # advances self.pos

    def _get_samples(self, batch_inds: np.ndarray, env: Any = None) -> MaskedSamples:
        base = super()._get_samples(batch_inds, env)
        return MaskedSamples(*base, next_valid=th.as_tensor(self.next_valid[batch_inds], device=self.device))


class MaskedDQN(DQN):
    """stable-baselines3 DQN whose Bellman target maxes over valid next actions only."""

    def __init__(self, policy, env, **kwargs):
        kwargs.setdefault("replay_buffer_class", MaskedReplayBuffer)
        super().__init__(policy, env, **kwargs)

    def train(self, gradient_steps: int, batch_size: int = 100) -> None:
        # Identical to stable-baselines3 DQN.train, except for the masked maximum below.
        self.policy.set_training_mode(True)
        self._update_learning_rate(self.policy.optimizer)

        losses = []
        for _ in range(gradient_steps):
            replay_data = self.replay_buffer.sample(batch_size, env=self._vec_normalize_env)
            discounts = replay_data.discounts if replay_data.discounts is not None else self.gamma

            with th.no_grad():
                next_q_values = self.q_net_target(replay_data.next_observations)
                next_q_values = masked_next_values(next_q_values, replay_data.next_valid)
                target_q_values = replay_data.rewards + (1 - replay_data.dones) * discounts * next_q_values

            current_q_values = self.q_net(replay_data.observations)
            current_q_values = th.gather(current_q_values, dim=1, index=replay_data.actions.long())

            loss = F.smooth_l1_loss(current_q_values, target_q_values)
            losses.append(loss.item())

            self.policy.optimizer.zero_grad()
            loss.backward()
            th.nn.utils.clip_grad_norm_(self.policy.parameters(), self.max_grad_norm)
            self.policy.optimizer.step()

        self._n_updates += gradient_steps
        self.logger.record("train/n_updates", self._n_updates, exclude="tensorboard")
        self.logger.record("train/loss", np.mean(losses))
