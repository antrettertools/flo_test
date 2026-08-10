"""Transforms open-mastr's per-technology tables into unified capacity_unit rows.

Column names in DEFAULT_COLUMN_MAP are MaStR's documented field names, but
are only confirmed end-to-end against a real download for storage
(storage_extended / storage_eeg, see project history). The other
technologies follow open-mastr's per-technology table pattern and MaStR's
documented field-naming convention, but have NOT yet been confirmed against
a real bulk download -- re-check this mapping against the real schema in
Phase 2 before trusting non-storage ingestion output.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from sqlalchemy.orm import Session

from common.enums import CATEGORY_BY_TECHNOLOGY, IS_RENEWABLE, Category, Technology, normalize_status
from common.size_class import size_class_for
from db.models import CapacityUnit


@dataclass(frozen=True)
class ColumnMap:
    mastr_nummer: str = "EinheitMastrNummer"
    status: str = "EinheitBetriebsstatus"
    commissioning_date: str = "Inbetriebnahmedatum"
    decommissioning_date: str = "DatumEndgueltigeStilllegung"
    capacity_kw: str = "Nettonennleistung"
    storage_capacity_kwh: str = "NutzbareSpeicherkapazitaet"
    postcode: str = "Postleitzahl"
    municipality_name: str = "Gemeinde"
    gemeinde_ags: str = "Gemeindeschluessel"
    land_name: str = "Bundesland"


DEFAULT_COLUMN_MAP = ColumnMap()


def _derive_region_codes(gemeinde_ags: str | None) -> tuple[str | None, str | None]:
    if not gemeinde_ags or len(str(gemeinde_ags)) < 5:
        return None, None
    gemeinde_ags = str(gemeinde_ags)
    return gemeinde_ags[:5], gemeinde_ags[:2]


def _parse_date(value):
    """MaStR dates arrive as strings from raw XML-sourced tables, but pandas
    may also hand back Timestamp/date objects depending on the source
    column's dtype -- normalize either case to a plain date, or None."""
    if value is None or pd.isna(value):
        return None
    return pd.to_datetime(value).date()


def transform_table(
    df: pd.DataFrame,
    technology: Technology,
    source_table: str,
    column_map: ColumnMap = DEFAULT_COLUMN_MAP,
) -> list[dict]:
    """Map one open-mastr per-technology DataFrame to unified capacity_unit dict rows."""
    category = CATEGORY_BY_TECHNOLOGY[technology]
    rows: list[dict] = []

    for _, r in df.iterrows():
        gemeinde_ags = r.get(column_map.gemeinde_ags)
        kreis_ags, land_ags = _derive_region_codes(gemeinde_ags)

        capacity_kw = r.get(column_map.capacity_kw)
        storage_capacity_kwh = (
            r.get(column_map.storage_capacity_kwh) if category == Category.STORAGE else None
        )

        rows.append(
            {
                "mastr_nummer": r.get(column_map.mastr_nummer),
                "source_table": source_table,
                "category": category.value,
                "technology": technology.value,
                "is_renewable": IS_RENEWABLE.get(technology),
                "status": normalize_status(r.get(column_map.status)).value,
                "status_raw": r.get(column_map.status),
                "commissioning_date": _parse_date(r.get(column_map.commissioning_date)),
                "decommissioning_date": _parse_date(r.get(column_map.decommissioning_date)),
                "capacity_kw": capacity_kw,
                "capacity_kw_type": "net_nominal",
                "storage_capacity_kwh": storage_capacity_kwh,
                "size_class": size_class_for(category, capacity_kw, storage_capacity_kwh),
                "postcode": r.get(column_map.postcode),
                "municipality_name": r.get(column_map.municipality_name),
                "gemeinde_ags": gemeinde_ags,
                "kreis_ags": kreis_ags,
                "land_ags": land_ags,
                "land_name": r.get(column_map.land_name),
            }
        )

    return rows


def upsert_capacity_units(
    session: Session, rows: list[dict], import_batch_id: int | None = None
) -> int:
    """Insert-or-update capacity_unit rows keyed by mastr_nummer (idempotent re-sync)."""
    count = 0
    for row in rows:
        existing = (
            session.query(CapacityUnit)
            .filter_by(mastr_nummer=row["mastr_nummer"])
            .one_or_none()
        )
        if existing is not None:
            for key, value in row.items():
                setattr(existing, key, value)
            existing.import_batch_id = import_batch_id
        else:
            session.add(CapacityUnit(**row, import_batch_id=import_batch_id))
        count += 1
    return count
