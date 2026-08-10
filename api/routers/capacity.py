"""GET /capacity/additions and GET /capacity/totals.

One router handles both categories via the `category` discriminator that
api.queries.run_aggregation always includes in its grouping -- see that
module's docstring."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.deps import get_db
from api.queries import CapacityFilters, capacity_filters, run_aggregation
from api.schemas import (
    CapacityAdditionsResponse,
    CapacityGroupResult,
    CapacityTotalsResponse,
    GroupByField,
)

router = APIRouter(prefix="/capacity", tags=["capacity"])


@router.get("/additions", response_model=CapacityAdditionsResponse)
def get_additions(
    group_by: list[GroupByField] = Query(default=[]),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    filters: CapacityFilters = Depends(capacity_filters),
    db: Session = Depends(get_db),
) -> CapacityAdditionsResponse:
    group_by_values = [g.value for g in group_by]
    rows = run_aggregation(db, filters, group_by_values, date_from=date_from, date_to=date_to)
    return CapacityAdditionsResponse(
        date_from=date_from,
        date_to=date_to,
        group_by=group_by_values,
        results=[CapacityGroupResult(**row) for row in rows],
    )


@router.get("/totals", response_model=CapacityTotalsResponse)
def get_totals(
    group_by: list[GroupByField] = Query(default=[]),
    as_of_date: date | None = Query(default=None),
    include_decommissioned: bool = Query(default=False),
    filters: CapacityFilters = Depends(capacity_filters),
    db: Session = Depends(get_db),
) -> CapacityTotalsResponse:
    effective_as_of = as_of_date or date.today()
    group_by_values = [g.value for g in group_by]
    rows = run_aggregation(
        db,
        filters,
        group_by_values,
        as_of_date=effective_as_of,
        include_decommissioned=include_decommissioned,
    )
    return CapacityTotalsResponse(
        as_of_date=effective_as_of,
        include_decommissioned=include_decommissioned,
        group_by=group_by_values,
        results=[CapacityGroupResult(**row) for row in rows],
    )
