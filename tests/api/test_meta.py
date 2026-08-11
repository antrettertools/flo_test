def test_technologies_lists_all_eight_with_category_and_renewable_flag(client):
    resp = client.get("/meta/technologies")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 8
    solar = next(t for t in body if t["technology"] == "solar")
    assert solar == {"technology": "solar", "category": "generation", "is_renewable": True}
    storage = next(t for t in body if t["technology"] == "storage")
    assert storage["category"] == "storage"
    assert storage["is_renewable"] is None


def test_size_classes_returns_generation_and_storage_buckets(client):
    resp = client.get("/meta/size-classes")
    assert resp.status_code == 200
    body = {row["category"]: row["size_classes"] for row in resp.json()}
    assert "<10 kW" in body["generation"]
    assert "<5 kWh" in body["storage"]


def test_health_reflects_no_import_batch_yet(client):
    resp = client.get("/meta/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["has_data"] is False
    assert body["last_import_finished_at"] is None
    assert body["vg250_source_version"] is None
    assert body["region_join_match_rate"] is None
    assert body["mastr_row_counts"] is None
    # The `db_session`/`client` fixtures seed capacity_unit rows and run
    # build_rollup() unconditionally (see conftest.py), independent of
    # whether an ImportBatch row exists. So even with has_data=False, the
    # rollup table is already populated from the 5 seeded units (5 addition
    # groups + 1 decommission group for STORAGE2_DECOMMISSIONED).
    assert body["capacity_rollup_row_count"] == 6


def test_health_reports_zero_rollup_row_count_when_rollup_table_is_empty():
    """capacity_rollup starts empty even after data is ingested, until the
    rollup build step runs (ingestion.build_db.build() or `python -m
    ingestion.cli rollup`). This is the signal DataProvenanceFooter uses to
    warn that /capacity/totals whole-month queries will silently return [].

    Uses its own engine/session (skipping seed_all/build_rollup) rather than
    the shared `db_session` fixture, since that fixture always runs
    build_rollup() and would mask exactly the scenario under test."""
    import datetime as dt

    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from api.deps import get_db
    from api.main import app
    from db.models import ImportBatch
    from db.session import init_db

    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    init_db(engine)
    session = sessionmaker(bind=engine)()
    session.add(
        ImportBatch(
            started_at=dt.datetime(2026, 8, 10, 0, 0, 0),
            finished_at=dt.datetime(2026, 8, 10, 0, 5, 0),
        )
    )
    session.commit()

    app.dependency_overrides[get_db] = lambda: session
    try:
        with TestClient(app) as c:
            resp = c.get("/meta/health")
    finally:
        app.dependency_overrides.clear()
        session.close()

    assert resp.status_code == 200
    body = resp.json()
    assert body["has_data"] is True
    assert body["capacity_rollup_row_count"] == 0
