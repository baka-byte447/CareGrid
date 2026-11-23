from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.database import Base


class EquipmentAssignment(Base):
    __tablename__ = "equipment_assignments"
    __table_args__ = (
        CheckConstraint("released_at IS NULL OR released_at >= assigned_at", name="ck_equipment_assignment_release_after_assign"),
        Index("ix_equipment_assignments_encounter", "encounter_id"),
        Index("ix_equipment_assignments_equipment", "equipment_id"),
        Index("uq_equipment_assignments_active_equipment", "equipment_id", unique=True, postgresql_where=text("released_at IS NULL"), sqlite_where=text("released_at IS NULL")),
    )

    assignment_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    encounter_id: Mapped[int] = mapped_column(ForeignKey("encounters.encounter_id", ondelete="RESTRICT"), nullable=False)
    equipment_id: Mapped[str] = mapped_column(ForeignKey("equipment.equipment_id", ondelete="RESTRICT"), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assigned_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    release_reason: Mapped[str | None] = mapped_column(String(100))

    encounter: Mapped["Encounter"] = relationship(back_populates="equipment_assignments")
    equipment: Mapped["Equipment"] = relationship()
    assigning_user: Mapped["User | None"] = relationship()
