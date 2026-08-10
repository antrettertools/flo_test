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
    assert resp.json() == {
        "has_data": False,
        "last_import_finished_at": None,
        "vg250_source_version": None,
        "region_join_match_rate": None,
        "mastr_row_counts": None,
    }
