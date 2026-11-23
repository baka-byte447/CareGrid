from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.database import Base


class BedAssignment(Base):
    __tablename__ = "bed_assignments"
    __table_args__ = (
        CheckConstraint("released_at IS NULL OR released_at >= assigned_at", name="ck_bed_assignment_release_after_assign"),
        Index("ix_bed_assignments_encounter", "encounter_id"),
        Index("ix_bed_assignments_bed", "bed_id"),
        Index("uq_bed_assignments_active_bed", "bed_id", unique=True, postgresql_where=text("released_at IS NULL"), sqlite_where=text("released_at IS NULL")),
        Index("uq_bed_assignments_active_encounter", "encounter_id", unique=True, postgresql_where=text("released_at IS NULL"), sqlite_where=text("released_at IS NULL")),
    )

    assignment_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    encounter_id: Mapped[int] = mapped_column(ForeignKey("encounters.encounter_id", ondelete="RESTRICT"), nullable=False)
    bed_id: Mapped[str] = mapped_column(ForeignKey("beds.bed_id", ondelete="RESTRICT"), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assigned_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    release_reason: Mapped[str | None] = mapped_column(String(100))

    encounter: Mapped["Encounter"] = relationship(back_populates="bed_assignments")
    bed: Mapped["Bed"] = relationship()
    assigning_user: Mapped["User | None"] = relationship()
