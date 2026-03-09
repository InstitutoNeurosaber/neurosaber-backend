import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.sql.base import Base
from app.database.sql.mixins import TimestampMixin


class Course(TimestampMixin, Base):
    __tablename__ = "courses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    guru_product_id: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False
    )
    guru_internal_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    group_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    group_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    carga_horaria: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    conteudo_programatico: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    registration_info: Mapped[str | None] = mapped_column(Text, nullable=True)

    emissions: Mapped[list["CertificateEmission"]] = relationship(
        back_populates="course"
    )


class CertificateEmission(TimestampMixin, Base):
    __tablename__ = "certificate_emissions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    token: Mapped[str] = mapped_column(
        String(20), unique=True, index=True, nullable=False
    )
    contact_name: Mapped[str] = mapped_column(String(500), nullable=False)
    contact_cpf: Mapped[str] = mapped_column(String(14), index=True, nullable=False)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("courses.id"), nullable=False
    )
    guru_transaction_id: Mapped[str] = mapped_column(String(255), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(tz=UTC), nullable=False
    )
    issued_location: Mapped[str | None] = mapped_column(String(255), nullable=True)

    course: Mapped["Course"] = relationship(back_populates="emissions")
