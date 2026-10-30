"""
CareGrid Safety Layer: event records for audit logging.

Each SafetyDecision captures the full trail of a review: what the policy proposed,
what the safety layer decided, why, and whether a fallback was used. These records
are shaped for future integration with the backend audit log (Phase 15).
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class SafetyDecision:
    """Result of SafetyLayer.review()."""
    proposed_action: int
    final_action: int
    status: str  # "APPROVED" or "OVERRIDDEN"
    reason_codes: List[str] = field(default_factory=list)
    fallback_used: bool = False
    guardrail_triggered: Optional[str] = None  # e.g. "G1_CRITICAL_WAIT", "G2_MAX_WAIT"

    @property
    def was_overridden(self) -> bool:
        return self.status == "OVERRIDDEN"


@dataclass
class AuditRecord:
    """Flat dict-shaped record for the future backend audit log."""
    timestamp: Optional[datetime] = None
    patient_id: str = ""
    patient_acuity: int = 0
    proposed_action: int = 0
    final_action: int = 0
    status: str = ""
    reason_codes: str = ""  # comma-joined
    fallback_used: bool = False
    guardrail_triggered: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "patient_id": self.patient_id,
            "patient_acuity": self.patient_acuity,
            "proposed_action": self.proposed_action,
            "final_action": self.final_action,
            "status": self.status,
            "reason_codes": self.reason_codes,
            "fallback_used": self.fallback_used,
            "guardrail_triggered": self.guardrail_triggered,
        }

