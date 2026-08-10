"""Metadata endpoints: drives filter UI and a "data as of" footer without
the frontend hardcoding technology/size-class values or import status."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps import get_db
from api.schemas import HealthResponse, SizeClassMeta, TechnologyMeta
from common.enums import CATEGORY_BY_TECHNOLOGY, IS_RENEWABLE, Technology
from common.size_class import size_class_definitions
from db.models import ImportBatch

router = APIRouter(prefix="/meta", tags=["meta"])


@router.get("/technologies", response_model=list[TechnologyMeta])
def get_technologies() -> list[TechnologyMeta]:
    return [
        TechnologyMeta(
            technology=tech.value,
            category=CATEGORY_BY_TECHNOLOGY[tech].value,
            is_renewable=IS_RENEWABLE[tech],
        )
        for tech in Technology
    ]


@router.get("/size-classes", response_model=list[SizeClassMeta])
def get_size_classes() -> list[SizeClassMeta]:
    return [
        SizeClassMeta(category=category, size_classes=classes)
        for category, classes in size_class_definitions().items()
    ]


@router.get("/health", response_model=HealthResponse)
def get_health(db: Session = Depends(get_db)) -> HealthResponse:
    batch = db.execute(
        select(ImportBatch).order_by(ImportBatch.started_at.desc()).limit(1)
    ).scalar_one_or_none()

    if batch is None:
        return HealthResponse(has_data=False)

    return HealthResponse(
        has_data=True,
        last_import_finished_at=batch.finished_at,
        vg250_source_version=batch.vg250_source_version,
        region_join_match_rate=(
            float(batch.region_join_match_rate)
            if batch.region_join_match_rate is not None
            else None
        ),
        mastr_row_counts=(
            json.loads(batch.mastr_row_counts_json)
            if batch.mastr_row_counts_json
            else None
        ),
    )
