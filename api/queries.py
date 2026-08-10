"""Shared SQLAlchemy filter/aggregation builders for /capacity/* and /units.

Kept in one module so both routers filter identically -- the architecture
plan calls this out explicitly ("shared SQLAlchemy aggregation builders")
to avoid two slightly-different copies of the same WHERE-clause logic.

Temporal-filter contract (the three endpoints deliberately disagree --
this is the one place that says so): `/capacity/totals` and
`/capacity/additions` treat a unit as "active as of `as_of_date`" only
when `commissioning_date <= as_of_date`; a NULL `commissioning_date`
therefore silently drops the unit from every total (but it still lands
in `/capacity/additions`' `month: null` bucket when no date range is
given). `/units` intentionally ignores `as_of_date` /
`include_decommissioned` and always returns every status and every
date -- it is not filtered to match `/capacity/totals`' population, so a
drill-down from a totals figure to `/units` for the same filters will not
always reconcile in row count.
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date

from fastapi import Query
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from common.enums import Category, Technology
from db.models import CapacityRollup, CapacityUnit
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


def _raw_aggregate(
    session: Session,
    filters: CapacityFilters,
    group_by: list[str],
    *,
    date_column,
    date_from: date | None,
    date_to: date | None,
) -> list[dict]:
    region_col = _region_column(filters.region_level)

    group_cols = [CapacityUnit.category]
    if "technology" in group_by:
        group_cols.append(CapacityUnit.technology)
    if "region" in group_by:
        group_cols.append(region_col.label("region_ags"))
    if "size_class" in group_by:
        group_cols.append(CapacityUnit.size_class)
    if "month" in group_by:
        group_cols.append(func.strftime("%Y-%m", CapacityUnit.commissioning_date).label("month"))

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
        filters, region_col, date_from=None, date_to=None, as_of_date=None, include_decommissioned=True
    )
    conditions.append(date_column.is_not(None))
    if date_from is not None:
        conditions.append(date_column >= date_from)
    if date_to is not None:
        conditions.append(date_column <= date_to)
    query = query.where(*conditions)

    query = query.group_by(*group_cols)
    return [dict(row._mapping) for row in session.execute(query).all()]


def _rollup_aggregate(
    session: Session,
    filters: CapacityFilters,
    group_by: list[str],
    *,
    kind: str,
    year_month_from: str | None,
    year_month_to: str | None,
) -> list[dict]:
    is_land = filters.region_level == RegionLevel.LAND.value
    region_col = func.substr(CapacityRollup.kreis_ags, 1, 2) if is_land else CapacityRollup.kreis_ags

    group_cols = [CapacityRollup.category]
    if "technology" in group_by:
        group_cols.append(CapacityRollup.technology)
    if "region" in group_by:
        group_cols.append(region_col.label("region_ags"))
    if "size_class" in group_by:
        group_cols.append(CapacityRollup.size_class)
    if "month" in group_by:
        group_cols.append(CapacityRollup.year_month.label("month"))

    query = select(
        *group_cols,
        func.sum(CapacityRollup.unit_count).label("unit_count"),
        func.sum(CapacityRollup.capacity_kw_sum).label("capacity_kw_sum"),
        func.sum(CapacityRollup.storage_capacity_kwh_sum).label("storage_capacity_kwh_sum"),
    ).where(CapacityRollup.kind == kind)

    if filters.technology:
        query = query.where(CapacityRollup.technology.in_(filters.technology))
    if filters.category:
        query = query.where(CapacityRollup.category == filters.category)
    if filters.region_ags:
        query = query.where(region_col.in_(filters.region_ags))
    if filters.size_class:
        query = query.where(CapacityRollup.size_class.in_(filters.size_class))
    if year_month_from is not None:
        query = query.where(CapacityRollup.year_month >= year_month_from)
    if year_month_to is not None:
        query = query.where(CapacityRollup.year_month <= year_month_to)

    query = query.group_by(*group_cols)
    return [dict(row._mapping) for row in session.execute(query).all()]


def _kind_aggregate(
    session: Session,
    filters: CapacityFilters,
    group_by: list[str],
    *,
    kind: str,
    date_from: date | None,
    date_to: date | None,
) -> list[dict]:
    rollup_lo, rollup_hi, raw_ranges = _split_date_range(date_from, date_to)
    rows: list[dict] = []

    no_bounds = rollup_lo is None and rollup_hi is None and raw_ranges
    inverted = rollup_lo is not None and rollup_hi is not None and rollup_lo > rollup_hi
    use_rollup = not no_bounds and not inverted
    if use_rollup:
        rows += _rollup_aggregate(
            session, filters, group_by, kind=kind, year_month_from=rollup_lo, year_month_to=rollup_hi
        )

    date_column = CapacityUnit.commissioning_date if kind == "addition" else CapacityUnit.decommissioning_date
    for range_from, range_to in raw_ranges:
        rows += _raw_aggregate(
            session, filters, group_by, date_column=date_column, date_from=range_from, date_to=range_to
        )

    return rows


def _raw_totals_as_of(
    session: Session,
    filters: CapacityFilters,
    group_by: list[str],
    *,
    as_of_date: date,
    include_decommissioned: bool,
) -> list[dict]:
    """Exact fallback for month-grouped totals as of a date.

    capacity_rollup's decommission rows are keyed by decommissioning month,
    not by each unit's original commissioning month, so the fast
    additions-minus-decommissions rollup diff in run_aggregation can't
    correctly net a decommissioned unit out of its commissioning-month
    bucket once grouping by month -- the subtraction lands in a different
    key and produces a phantom row in the commissioning month plus a
    negative row in the decommissioning month instead of the unit simply
    vanishing from the as-of-date snapshot. Mirrors the pre-rollup raw scan
    exactly: a single WHERE clause encoding "active as of as_of_date",
    grouped by commissioning month -- no subtraction needed.
    """
    region_col = _region_column(filters.region_level)

    group_cols = [CapacityUnit.category]
    if "technology" in group_by:
        group_cols.append(CapacityUnit.technology)
    if "region" in group_by:
        group_cols.append(region_col.label("region_ags"))
    if "size_class" in group_by:
        group_cols.append(CapacityUnit.size_class)
    if "month" in group_by:
        group_cols.append(func.strftime("%Y-%m", CapacityUnit.commissioning_date).label("month"))

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
        date_from=None,
        date_to=None,
        as_of_date=as_of_date,
        include_decommissioned=include_decommissioned,
    )
    if conditions:
        query = query.where(*conditions)

    query = query.group_by(*group_cols)
    return [dict(row._mapping) for row in session.execute(query).all()]


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
    result row never mixes generation kW with storage kWh in one sum.

    Reads from capacity_rollup for whole calendar months and falls back to a
    day-precision capacity_unit scan only for the partial boundary month(s)
    of the request -- see _split_date_range. A "totals as of D" request is
    computed as additions-up-to-D minus decommissions-up-to-D, EXCEPT when
    grouping by month, where that netting can't be expressed correctly from
    the rollup's grain -- see _raw_totals_as_of.
    """
    if as_of_date is not None:
        if "month" in group_by:
            return _raw_totals_as_of(
                session,
                filters,
                group_by,
                as_of_date=as_of_date,
                include_decommissioned=include_decommissioned,
            )

        rows = _kind_aggregate(session, filters, group_by, kind="addition", date_from=None, date_to=as_of_date)
        if not include_decommissioned:
            decommissions = _kind_aggregate(
                session, filters, group_by, kind="decommission", date_from=None, date_to=as_of_date
            )
            rows += [_negate_row(r) for r in decommissions]
        return _merge_group_rows(rows)

    rows = _kind_aggregate(session, filters, group_by, kind="addition", date_from=date_from, date_to=date_to)
    return _merge_group_rows(rows)


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
        for field in _NUMERIC_FIELDS[1:]:
            if row.get(field) is not None:
                target[field] = (target[field] or 0) + row[field]
    return list(merged.values())


def _negate_row(row: dict) -> dict:
    negated = dict(row)
    negated["unit_count"] = -row["unit_count"]
    for field in _NUMERIC_FIELDS[1:]:
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
