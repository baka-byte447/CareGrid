"""
CareGrid Multi-Agent Reinforcement Learning (MARL) package.

Implements hierarchical multi-agent coordination:
  - Surge Agent: macro-level policy deciding hospital operating mode (NORMAL vs SURGE).
  - Bed Agent: micro-level allocation policy executing bed assignments under the active mode.
"""
from rl.marl.multi_agent_env import CareGridMAEnv
from rl.marl.surge_agent import SurgeAgent

__all__ = ["CareGridMAEnv", "SurgeAgent"]

