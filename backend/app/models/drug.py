"""Drug reference table — mirrors `DRUGS` in frontend/src/services/seed.js.
See ARCHITECTURE.md §4.2."""
from __future__ import annotations

from sqlalchemy import Enum, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import DrugCategory


class Drug(Base):
    __tablename__ = "drugs"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[DrugCategory] = mapped_column(
        Enum(DrugCategory, name="category_enum", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
