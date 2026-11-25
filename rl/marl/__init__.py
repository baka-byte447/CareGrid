"""
CareGrid Multi-Agent Reinforcement Learning (MARL) package.

Implements 3-agent hierarchical coordination:
  - Surge Agent (Macro): decides hospital operating mode (NORMAL vs SURGE).
  - Resource Manager Agent (Meso): manages bed cleaning speed, ventilator
    mobilization, and critical-care staff floating.
  - Bed Agent (Micro): executes bed assignments under active mode & supply.
"""
from rl.marl.multi_agent_env import CareGridMAEnv
from rl.marl.resource_agent import ResourceManagerAgent
from rl.marl.surge_agent import SurgeAgent

__all__ = ["CareGridMAEnv", "SurgeAgent", "ResourceManagerAgent"]
