"""
CareGrid Safety Layer: independent safety validation for allocation decisions.

This package provides a safety layer that validates and optionally overrides
allocation decisions made by any policy (rule-based, heuristic, or RL agent).
It is intentionally independent of simulator/hospital/allocation_rules.py:
the constraints are derived from clinical documentation and the audit module.

No torch or SB3 imports at module level.
"""

