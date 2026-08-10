from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from db.models import Base


def get_engine(database_url: str | None = None) -> Engine:
    url = database_url or os.environ.get(
        "DATABASE_URL", "sqlite:///data/processed/mastr_analytics.db"
    )
    return create_engine(url)


def init_db(engine: Engine) -> None:
    Base.metadata.create_all(engine)


def get_session_factory(engine: Engine):
    return sessionmaker(bind=engine)
