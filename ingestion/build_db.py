"""Orchestrates mastr_transform + vg250_transform into the processed DB.

Runs on the user's machine in Phase 2, against a real raw MaStR sqlite (from
mastr_sync.sync()) and a manually downloaded VG250 dataset. Not testable in
the cloud dev sandbox -- requires real data on both sides.
"""
from __future__ import annotations

import datetime as dt
import json

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from common.enums import MASTR_TABLE_TO_TECHNOLOGY
from db.models import ImportBatch, Region
from db.session import init_db
from ingestion.config import PROCESSED_DB_PATH, RAW_DB_PATH
from ingestion.mastr_transform import transform_table, upsert_capacity_units
from ingestion.vg250_transform import to_region_rows, transform_vg250


def build(vg250_path: str, chunk_size: int = 50_000) -> None:
    """Streams each raw MaStR table through in chunks rather than loading it whole --
    solar/storage tables run into the millions of rows, and materializing an
    entire table as a DataFrame + a parallel list of dict rows at once was
    using tens of GB of memory."""
    PROCESSED_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{PROCESSED_DB_PATH}")
    init_db(engine)
    raw_engine = create_engine(f"sqlite:///{RAW_DB_PATH}")

    with Session(engine) as session:
        batch = ImportBatch(started_at=dt.datetime.utcnow())
        session.add(batch)
        session.flush()

        row_counts: dict[str, int] = {}
        total = 0
        matched = 0
        for table_name, technology in MASTR_TABLE_TO_TECHNOLOGY.items():
            try:
                chunks = pd.read_sql_table(table_name, raw_engine, chunksize=chunk_size)
            except ValueError:
                continue  # technology wasn't synced this run

            table_total = 0
            for chunk_df in chunks:
                rows = transform_table(chunk_df, technology, table_name)
                upsert_capacity_units(session, rows, import_batch_id=batch.id)
                table_total += len(rows)
                matched += sum(1 for r in rows if r["kreis_ags"])
                print(f"  {table_name}: {table_total} rows so far", flush=True)

            row_counts[table_name] = table_total
            total += table_total

        vg = transform_vg250(vg250_path)
        for region in to_region_rows(vg["kreise"], vg["bundeslaender"]):
            session.merge(Region(**region))

        batch.mastr_row_counts_json = json.dumps(row_counts)
        batch.vg250_source_version = vg250_path
        batch.region_join_match_rate = (matched / total) if total else None
        batch.finished_at = dt.datetime.utcnow()
        session.commit()

        if total:
            print(
                f"Ingested {total} units across {len(row_counts)} technologies; "
                f"region match rate {batch.region_join_match_rate:.1%}"
            )
        else:
            print("No rows ingested -- did mastr_sync.sync() run first?")
