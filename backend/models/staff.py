from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.database import Base


class Staff(Base):
    __tablename__ = "staff"

    staff_id: Mapped[str] = mapped_column(
        String(10),
        primary_key=True
    )

    role: Mapped[str] = mapped_column(
        String(30),
        nullable=False
    )

    skill_level: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )

    shift: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )

    workload: Mapped[int] = mapped_column(
        nullable=False
    )