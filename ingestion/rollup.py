"""Builds capacity_rollup from capacity_unit -- see db/models.py's
CapacityRollup docstring for the grain. Run via `python -m ingestion.cli
rollup` standalone, or automatically at the end of `ingestion.build_db.build()`.
"""
from __future__ import annotations

from sqlalchemy import case, delete, func, select
from sqlalchemy.orm import Session

from db.models import CapacityRollup, CapacityUnit


def build_rollup(session: Session) -> int:
    session.execute(delete(CapacityRollup))

    addition_rows = _aggregate(session, kind="addition", date_column=CapacityUnit.commissioning_date)
    decommission_rows = _aggregate(
        session, kind="decommission", date_column=CapacityUnit.decommissioning_date
    )

    all_rows = addition_rows + decommission_rows
    if all_rows:
        session.bulk_insert_mappings(CapacityRollup, all_rows)
    return len(all_rows)


def _aggregate(session: Session, *, kind: str, date_column) -> list[dict]:
    year_month = func.strftime("%Y-%m", date_column)
    query = (
        select(
            CapacityUnit.category,
            CapacityUnit.technology,
            CapacityUnit.kreis_ags,
            CapacityUnit.size_class,
            year_month.label("year_month"),
            func.count(CapacityUnit.id).label("unit_count"),
            func.sum(
                case((CapacityUnit.category == "generation", CapacityUnit.capacity_kw))
            ).label("capacity_kw_sum"),
            func.sum(
                case((CapacityUnit.category == "storage", CapacityUnit.storage_capacity_kwh))
            ).label("storage_capacity_kwh_sum"),
        )
        .where(date_column.is_not(None))
        .group_by(
            CapacityUnit.category,
            CapacityUnit.technology,
            CapacityUnit.kreis_ags,
            CapacityUnit.size_class,
            year_month,
        )
    )
    return [{"kind": kind, **dict(row._mapping)} for row in session.execute(query).all()]
