"""Shared SQLAlchemy filter/aggregation builders for /capacity/* and /units.

Kept in one module so both routers filter identically -- the architecture
plan calls this out explicitly ("shared SQLAlchemy aggregation builders")
to avoid two slightly-different copies of the same WHERE-clause logic.
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date

from fastapi import Query
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from common.enums import Category, Technology
from db.models import CapacityUnit
from api.schemas import RegionLevel


@dataclass(frozen=True)
class CapacityFilters:
    technology: list[str] | None = None
    category: str | None = None
    region_level: str | None = None
    region_ags: list[str] | None = None
    size_class: list[str] | None = None


def capacity_filters(
    technology: list[Technology] | None = Query(default=None),
    category: Category | None = Query(default=None),
    region_level: RegionLevel | None = Query(default=None),
    region_ags: list[str] | None = Query(default=None),
    size_class: list[str] | None = Query(default=None),
) -> CapacityFilters:
    """FastAPI dependency: turns query params into a CapacityFilters. Shared
    by capacity.py and units.py so both routers accept identical filter
    params without duplicating the Query(...) declarations."""
    return CapacityFilters(
        technology=[t.value for t in technology] if technology else None,
        category=category.value if category else None,
        region_level=region_level.value if region_level else None,
        region_ags=region_ags,
        size_class=size_class,
    )


def _region_column(region_level: str | None):
    """Defaults to Kreis-level grouping/filtering when region_level is omitted."""
    if region_level == RegionLevel.LAND.value:
        return CapacityUnit.land_ags
    return CapacityUnit.kreis_ags


def _build_conditions(
    filters: CapacityFilters,
    region_col,
    *,
    date_from: date | None,
    date_to: date | None,
    as_of_date: date | None,
    include_decommissioned: bool,
) -> list:
    conditions = []
    if filters.technology:
        conditions.append(CapacityUnit.technology.in_(filters.technology))
    if filters.category:
        conditions.append(CapacityUnit.category == filters.category)
    if filters.region_ags:
        conditions.append(region_col.in_(filters.region_ags))
    if filters.size_class:
        conditions.append(CapacityUnit.size_class.in_(filters.size_class))

    if date_from is not None:
        conditions.append(CapacityUnit.commissioning_date >= date_from)
    if date_to is not None:
        conditions.append(CapacityUnit.commissioning_date <= date_to)

    if as_of_date is not None:
        conditions.append(CapacityUnit.commissioning_date <= as_of_date)
        if not include_decommissioned:
            conditions.append(
                or_(
                    CapacityUnit.decommissioning_date.is_(None),
                    CapacityUnit.decommissioning_date > as_of_date,
                )
            )

    return conditions


def run_aggregation(
    session: Session,
    filters: CapacityFilters,
    group_by: list[str],
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    as_of_date: date | None = None,
    include_decommissioned: bool = False,
) -> list[dict]:
    """Always groups by category in addition to whatever's in group_by, so a
    result row never mixes generation kW with storage kWh in one sum."""
    region_col = _region_column(filters.region_level)

    group_cols = [CapacityUnit.category]
    if "technology" in group_by:
        group_cols.append(CapacityUnit.technology)
    if "region" in group_by:
        group_cols.append(region_col.label("region_ags"))
    if "size_class" in group_by:
        group_cols.append(CapacityUnit.size_class)
    if "month" in group_by:
        group_cols.append(
            func.strftime("%Y-%m", CapacityUnit.commissioning_date).label("month")
        )

    query = select(
        *group_cols,
        func.count(CapacityUnit.id).label("unit_count"),
        func.sum(
            case((CapacityUnit.category == Category.GENERATION.value, CapacityUnit.capacity_kw))
        ).label("capacity_kw_sum"),
        func.sum(
            case(
                (CapacityUnit.category == Category.STORAGE.value, CapacityUnit.storage_capacity_kwh)
            )
        ).label("storage_capacity_kwh_sum"),
    )

    conditions = _build_conditions(
        filters,
        region_col,
        date_from=date_from,
        date_to=date_to,
        as_of_date=as_of_date,
        include_decommissioned=include_decommissioned,
    )
    if conditions:
        query = query.where(*conditions)

    query = query.group_by(*group_cols)

    return [dict(row._mapping) for row in session.execute(query).all()]


def _month_start(d: date) -> date:
    return d.replace(day=1)


def _month_end(d: date) -> date:
    last_day = calendar.monthrange(d.year, d.month)[1]
    return d.replace(day=last_day)


def _year_month(d: date) -> str:
    return d.strftime("%Y-%m")


def _shift_year_month(year_month: str, delta_months: int) -> str:
    year, month = int(year_month[:4]), int(year_month[5:7])
    total = year * 12 + (month - 1) + delta_months
    return f"{total // 12:04d}-{(total % 12) + 1:02d}"


def _split_date_range(
    date_from: date | None, date_to: date | None
) -> tuple[str | None, str | None, list[tuple[date, date]]]:
    """Splits [date_from, date_to] into a whole-month span (rollup_lo,
    rollup_hi -- either may be None for an unbounded side) and up to two
    partial-month day-precision ranges the rollup can't answer exactly."""
    if date_from is None and date_to is None:
        return None, None, []

    if (
        date_from is not None
        and date_to is not None
        and _year_month(date_from) == _year_month(date_to)
    ):
        return None, None, [(date_from, date_to)]

    raw_ranges: list[tuple[date, date]] = []

    rollup_lo = None
    if date_from is not None:
        if date_from == _month_start(date_from):
            rollup_lo = _year_month(date_from)
        else:
            raw_ranges.append((date_from, _month_end(date_from)))
            rollup_lo = _shift_year_month(_year_month(date_from), 1)

    rollup_hi = None
    if date_to is not None:
        if date_to == _month_end(date_to):
            rollup_hi = _year_month(date_to)
        else:
            raw_ranges.append((_month_start(date_to), date_to))
            rollup_hi = _shift_year_month(_year_month(date_to), -1)

    return rollup_lo, rollup_hi, raw_ranges


_NUMERIC_FIELDS = ("unit_count", "capacity_kw_sum", "storage_capacity_kwh_sum")
_GROUP_KEY_FIELDS = ("category", "technology", "region_ags", "size_class", "month")


def _merge_group_rows(rows: list[dict]) -> list[dict]:
    merged: dict[tuple, dict] = {}
    for row in rows:
        key = tuple(row.get(k) for k in _GROUP_KEY_FIELDS)
        if key not in merged:
            merged[key] = {
                **{k: row.get(k) for k in _GROUP_KEY_FIELDS},
                "unit_count": 0,
                "capacity_kw_sum": None,
                "storage_capacity_kwh_sum": None,
            }
        target = merged[key]
        target["unit_count"] += row["unit_count"]
        for field in ("capacity_kw_sum", "storage_capacity_kwh_sum"):
            if row.get(field) is not None:
                target[field] = (target[field] or 0) + row[field]
    return list(merged.values())


def _negate_row(row: dict) -> dict:
    negated = dict(row)
    negated["unit_count"] = -row["unit_count"]
    for field in ("capacity_kw_sum", "storage_capacity_kwh_sum"):
        if row.get(field) is not None:
            negated[field] = -row[field]
    return negated


def query_units(
    session: Session,
    filters: CapacityFilters,
    *,
    limit: int,
    offset: int,
    date_from: date | None = None,
    date_to: date | None = None,
) -> tuple[int, list[CapacityUnit]]:
    region_col = _region_column(filters.region_level)
    conditions = _build_conditions(
        filters,
        region_col,
        date_from=date_from,
        date_to=date_to,
        as_of_date=None,
        include_decommissioned=True,
    )

    base = select(CapacityUnit)
    if conditions:
        base = base.where(*conditions)

    total = session.scalar(select(func.count()).select_from(base.subquery()))
    rows = list(
        session.scalars(base.order_by(CapacityUnit.id).limit(limit).offset(offset)).all()
    )
    return total, rows
