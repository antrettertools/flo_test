import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.deps import get_db, get_geo_assets_dir
from api.main import app
from db.session import init_db
from tests.fixtures.seed import seed_all


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(engine)
    session = sessionmaker(bind=engine)()
    seed_all(session)
    yield session
    session.close()


@pytest.fixture()
def geo_assets_dir(tmp_path) -> Path:
    (tmp_path / "kreise.geo.json").write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"ags": "09162", "name": "Muenchen"},
                        "geometry": {"type": "Point", "coordinates": [11.58, 48.14]},
                    }
                ],
            }
        )
    )
    (tmp_path / "bundeslaender.geo.json").write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"ags": "09", "name": "Bayern"},
                        "geometry": {"type": "Point", "coordinates": [11.4, 48.8]},
                    }
                ],
            }
        )
    )
    return tmp_path


@pytest.fixture()
def client(db_session, geo_assets_dir):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_geo_assets_dir] = lambda: geo_assets_dir
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
