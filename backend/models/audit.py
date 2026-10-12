
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String

from backend.db.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(String(10), nullable=False, index=True)
    bed_id = Column(String(10), nullable=True)
    action = Column(String(30), nullable=False)
    algorithm = Column(String(30), nullable=False, default="rule_based")
    timestamp = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
