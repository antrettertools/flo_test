"""GET /units (paginated drill-down) and GET /units/{mastr_nummer}."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps import get_db
from api.queries import CapacityFilters, capacity_filters, query_units
from api.schemas import UnitListResponse, UnitOut
from db.models import CapacityUnit

router = APIRouter(prefix="/units", tags=["units"])


@router.get("", response_model=UnitListResponse)
def list_units(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    filters: CapacityFilters = Depends(capacity_filters),
    db: Session = Depends(get_db),
) -> UnitListResponse:
    total, rows = query_units(
        db, filters, limit=limit, offset=offset, date_from=date_from, date_to=date_to
    )
    return UnitListResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=[UnitOut.model_validate(r) for r in rows],
    )


@router.get("/{mastr_nummer}", response_model=UnitOut)
def get_unit(mastr_nummer: str, db: Session = Depends(get_db)) -> UnitOut:
    unit = db.scalar(select(CapacityUnit).where(CapacityUnit.mastr_nummer == mastr_nummer))
    if unit is None:
        raise HTTPException(status_code=404, detail="unit not found")
    return UnitOut.model_validate(unit)
