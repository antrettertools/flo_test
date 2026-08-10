"""Wraps open-mastr's bulk download.

Must run on a machine with unrestricted egress to marktstammdatenregister.de
-- confirmed working via local verification (see scripts/verify_mastr.py,
which this module supersedes). Not runnable/testable in the project's cloud
dev sandbox.
"""
from __future__ import annotations

from sqlalchemy import create_engine

from ingestion.config import RAW_DB_PATH, TECHNOLOGIES


def sync(technologies: list[str] | None = None) -> None:
    from open_mastr import Mastr  # imported lazily -- not a dependency of api/

    RAW_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{RAW_DB_PATH}")
    db = Mastr(engine=engine)
    db.download(method="bulk", data=technologies or TECHNOLOGIES)
