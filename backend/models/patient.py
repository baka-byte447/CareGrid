from datetime import datetime

from sqlalchemy import String, Integer, Float, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.database import Base


class Patient(Base):
    __tablename__ = "patients"

    patient_id: Mapped[str] = mapped_column(
        String(10),
        primary_key=True
    )

    age_group: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )

    acuity: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    specialty: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )

    predicted_los: Mapped[float] = mapped_column(
        Float,
        nullable=False
    )

    isolation_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False
    )

    ventilator_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False
    )

    arrival_time: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False
    )

    current_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )