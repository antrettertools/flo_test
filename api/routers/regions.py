"""Region list + static boundary GeoJSON passthrough.

Geometry never touches the DB (see db/models.py's Region docstring) -- it's
served straight from the GeoJSON files ingestion/vg250_transform.py writes,
read from GEO_ASSETS_DIR."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps import get_db, get_geo_assets_dir
from api.schemas import RegionOut
from db.models import Region

router = APIRouter(prefix="/regions", tags=["regions"])

_GEOJSON_FILENAMES = {"kreis": "kreise.geo.json", "land": "bundeslaender.geo.json"}


@router.get("", response_model=list[RegionOut])
def list_regions(
    level: str | None = None, db: Session = Depends(get_db)
) -> list[RegionOut]:
    query = select(Region)
    if level is not None:
        query = query.where(Region.level == level)
    regions = db.scalars(query.order_by(Region.ags)).all()
    return [RegionOut.model_validate(r) for r in regions]


@router.get("/{level}/geojson")
def get_region_geojson(
    level: str, geo_assets_dir: Path = Depends(get_geo_assets_dir)
) -> JSONResponse:
    filename = _GEOJSON_FILENAMES.get(level)
    if filename is None:
        raise HTTPException(status_code=400, detail="level must be 'kreis' or 'land'")

    path = geo_assets_dir / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"{filename} not found in GEO_ASSETS_DIR")

    return JSONResponse(content=json.loads(path.read_text()))
