from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.database import Base


class Equipment(Base):
    __tablename__ = "equipment"

    equipment_id: Mapped[str] = mapped_column(
        String(10),
        primary_key=True
    )

    type: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )

    location: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )