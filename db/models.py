"""SQLAlchemy models for the processed analytics database.

capacity_unit is the unit-level fact table -- the source of truth all API
aggregations query against. region carries no geometry (geometry lives in
static GeoJSON files served alongside the DB); this keeps a future
SQLite -> Postgres move trivial, with no PostGIS dependency required.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class ImportBatch(Base):
    __tablename__ = "import_batch"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    mastr_row_counts_json: Mapped[str | None] = mapped_column(String, nullable=True)
    vg250_source_version: Mapped[str | None] = mapped_column(String, nullable=True)
    region_join_match_rate: Mapped[float | None] = mapped_column(Numeric, nullable=True)

    units: Mapped[list["CapacityUnit"]] = relationship(back_populates="import_batch")


class Region(Base):
    __tablename__ = "region"

    ags: Mapped[str] = mapped_column(String(5), primary_key=True)
    level: Mapped[str] = mapped_column(String(8), nullable=False)  # 'land' | 'kreis'
    name: Mapped[str] = mapped_column(String, nullable=False)
    parent_ags: Mapped[str | None] = mapped_column(String(2), nullable=True)


class CapacityUnit(Base):
    __tablename__ = "capacity_unit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mastr_nummer: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    source_table: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String(16), nullable=False)  # 'generation' | 'storage'
    technology: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    is_renewable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status_raw: Mapped[str | None] = mapped_column(String, nullable=True)

    commissioning_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True, index=True)
    decommissioning_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)

    capacity_kw: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    capacity_kw_type: Mapped[str | None] = mapped_column(String(16), nullable=True)  # 'net_nominal' | 'gross'
    storage_capacity_kwh: Mapped[float | None] = mapped_column(Numeric, nullable=True)

    size_class: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)

    postcode: Mapped[str | None] = mapped_column(String(8), nullable=True)
    municipality_name: Mapped[str | None] = mapped_column(String, nullable=True)
    gemeinde_ags: Mapped[str | None] = mapped_column(String(8), nullable=True)
    kreis_ags: Mapped[str | None] = mapped_column(String(5), nullable=True, index=True)
    land_ags: Mapped[str | None] = mapped_column(String(2), nullable=True, index=True)
    land_name: Mapped[str | None] = mapped_column(String, nullable=True)

    latitude: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Numeric, nullable=True)

    import_batch_id: Mapped[int | None] = mapped_column(ForeignKey("import_batch.id"), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    import_batch: Mapped["ImportBatch | None"] = relationship(back_populates="units")

    __table_args__ = (
        Index("ix_capacity_unit_technology_commissioning", "technology", "commissioning_date"),
        Index("ix_capacity_unit_kreis_technology", "kreis_ags", "technology"),
        Index("ix_capacity_unit_land_technology", "land_ags", "technology"),
    )
