from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.database import Base


class Bed(Base):
    __tablename__ = "beds"

    bed_id: Mapped[str] = mapped_column(
        String(10),
        primary_key=True
    )

    bed_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False
    )

    ward: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )

    isolation_capable: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False
    )