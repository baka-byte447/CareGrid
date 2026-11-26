from pathlib import Path

from ml.los.predictor import DEFAULT_MODEL, LOSPredictor
from rl.environment.hospital_env import CareGridHospitalEnv
from rl.marl.multi_agent_env import CareGridMAEnv
from rl.marl.resource_agent import ResourceManagerAgent
from rl.marl.surge_agent import SurgeAgent


class PopulationLosEstimate:
    """Use the serving baseline when the optional fitted LOS artifact is absent."""
    def predict(self, patient):
        return 3.0


def run_adaptive(state, patients, hours, collector, *, models=None, seed=0, predictor=None):
    if models is None:
        models = Path(__file__).resolve().parents[2] / "models" / "serving"
    surge = SurgeAgent.load(models / "surge_agent.npz")
    resource = ResourceManagerAgent.load(models / "resource_agent.npz")
    if predictor is None:
        predictor = LOSPredictor.load() if DEFAULT_MODEL.is_file() else PopulationLosEstimate()
    base = CareGridHospitalEnv(max_episode_days=hours / 24, observation_version=2, los_predictor=predictor)
    env = CareGridMAEnv(base_env=base)
    obs, _ = env.reset(seed=seed, options={"initial_state": state, "patients": patients, "on_tick": collector.on_tick})
    interrupts = 0
    while not env.env._done:
        mode = surge.predict(obs)
        env.current_mode = mode
        action = resource.predict(env.get_resource_obs(), valid_mask=env.valid_resource_actions())
        obs, _, terminated, truncated, info = env.step((mode, action))
        interrupts += int(info["macro_interrupt"])
        if terminated or truncated:
            break
    return env.env.engine, interrupts
