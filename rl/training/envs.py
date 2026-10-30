"""
CareGrid-RL: training environment factory (Phase 8)

Every episode is a FRESH patient stream (scenario and seed drawn at reset) so the agent
cannot memorise one sequence, and the reward is the acuity-weighted queue cost.
Training is NOT action-masked on purpose (plan decision D11): an invalid action is
'WAIT plus a penalty', which keeps the Bellman targets consistent. Masking is applied
only when acting (rl.evaluation.policies.masked_greedy_policy).
"""
from rl.environment.hospital_env import CareGridHospitalEnv
from rl.training.config import DQNConfig
from simulator.patients.streams import TRAIN_SEEDS, MixedStreamSampler


def make_training_env(config: DQNConfig, predictor):
    from stable_baselines3.common.monitor import Monitor
    env = CareGridHospitalEnv(
        los_predictor=predictor,
        max_episode_days=config.stream_days + config.drain_days,
        reward_mode="queue_cost",
        acuity_weights=config.acuity_weights,
        reward_scale=config.reward_scale,
        invalid_action_penalty=config.invalid_action_penalty,
        patient_source=MixedStreamSampler(config.mode_weights, TRAIN_SEEDS, config.stream_days),
        observation_version=getattr(config, "observation_version", 1),
    )
    return Monitor(env)
