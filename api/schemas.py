"""Pydantic response models for the API, plus two API-only enums
(GroupByField, RegionLevel) that don't belong in common/enums.py since
they're query-parameter vocabulary, not domain concepts shared with
ingestion/."""
from __future__ import annotations

import datetime as dt
from enum import Enum

from pydantic import BaseModel, ConfigDict


class TechnologyMeta(BaseModel):
    technology: str
    category: str
    is_renewable: bool | None


class SizeClassMeta(BaseModel):
    category: str
    size_classes: list[str]


class HealthResponse(BaseModel):
    has_data: bool
    last_import_finished_at: dt.datetime | None = None
    vg250_source_version: str | None = None
    region_join_match_rate: float | None = None
    mastr_row_counts: dict[str, int] | None = None


class GroupByField(str, Enum):
    TECHNOLOGY = "technology"
    REGION = "region"
    SIZE_CLASS = "size_class"
    MONTH = "month"


class RegionLevel(str, Enum):
    KREIS = "kreis"
    LAND = "land"


class CapacityGroupResult(BaseModel):
    """One aggregated row. `category` is always present (results are always
    split by category even if not explicitly requested in group_by) so a
    single row never has to mix kW and kWh sums -- see
    docs/architecture-plan.md's API section."""

    category: str
    technology: str | None = None
    region_ags: str | None = None
    size_class: str | None = None
    month: str | None = None
    unit_count: int
    capacity_kw_sum: float | None = None
    storage_capacity_kwh_sum: float | None = None


class CapacityAdditionsResponse(BaseModel):
    date_from: dt.date | None
    date_to: dt.date | None
    group_by: list[str]
    results: list[CapacityGroupResult]


class CapacityTotalsResponse(BaseModel):
    as_of_date: dt.date
    include_decommissioned: bool
    group_by: list[str]
    results: list[CapacityGroupResult]


class RegionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ags: str
    level: str
    name: str
    parent_ags: str | None


class UnitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    mastr_nummer: str
    category: str
    technology: str
    is_renewable: bool | None
    status: str
    commissioning_date: dt.date | None
    decommissioning_date: dt.date | None
    capacity_kw: float | None
    storage_capacity_kwh: float | None
    size_class: str | None
    postcode: str | None
    municipality_name: str | None
    gemeinde_ags: str | None
    kreis_ags: str | None
    land_ags: str | None
    land_name: str | None


class UnitListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[UnitOut]
