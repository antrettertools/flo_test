"""Pydantic response models. See Task 2 for the full set (capacity/units/regions)."""
from __future__ import annotations

import datetime as dt

from pydantic import BaseModel


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
