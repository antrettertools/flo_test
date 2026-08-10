def test_totals_default_as_of_today_excludes_decommissioned(client):
    resp = client.get("/capacity/totals")
    assert resp.status_code == 200
    body = resp.json()
    by_cat = {r["category"]: r for r in body["results"]}
    assert by_cat["storage"]["unit_count"] == 1
    assert by_cat["storage"]["storage_capacity_kwh_sum"] == 12.5


def test_totals_include_decommissioned_true(client):
    resp = client.get("/capacity/totals", params={"include_decommissioned": "true"})
    body = resp.json()
    by_cat = {r["category"]: r for r in body["results"]}
    assert by_cat["storage"]["unit_count"] == 2


def test_additions_date_range_and_group_by_region(client):
    resp = client.get(
        "/capacity/additions",
        params={
            "date_from": "2022-01-01",
            "date_to": "2022-12-31",
            "group_by": "region",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["date_from"] == "2022-01-01"
    # Two rows share region_ags "09162" here (one per category) -- filter on
    # both fields, since group order across categories isn't guaranteed.
    munich_generation = next(
        r
        for r in body["results"]
        if r["region_ags"] == "09162" and r["category"] == "generation"
    )
    assert munich_generation["capacity_kw_sum"] == 50.0


def test_additions_filtered_by_technology(client):
    resp = client.get("/capacity/additions", params={"technology": "wind"})
    body = resp.json()
    assert len(body["results"]) == 1
    assert body["results"][0]["capacity_kw_sum"] == 3000.0


def test_additions_group_by_multiple_dims(client):
    resp = client.get(
        "/capacity/additions",
        params={"group_by": ["technology", "region"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    solar_munich = next(
        r
        for r in body["results"]
        if r.get("technology") == "solar" and r.get("region_ags") == "09162"
    )
    assert solar_munich["unit_count"] == 2
    assert solar_munich["capacity_kw_sum"] == 58.0
