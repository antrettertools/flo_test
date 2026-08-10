"""FastAPI dependencies: DB session and static geo-assets directory.

Both read from environment variables so `uvicorn api.main:app` and tests can
point at different databases/directories without code changes -- see
`ingestion/README.md`'s documented `DATABASE_URL`/`GEO_ASSETS_DIR` workflow.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Generator

from sqlalchemy.orm import Session

from db.session import get_engine, get_session_factory

_engine = get_engine()
_SessionLocal = get_session_factory(_engine)


def get_db() -> Generator[Session, None, None]:
    session = _SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_geo_assets_dir() -> Path:
    return Path(os.environ.get("GEO_ASSETS_DIR", "data/processed"))
