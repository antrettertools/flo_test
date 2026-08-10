def test_units_points_requires_kreis_ags(client):
    resp = client.get("/units/points")
    assert resp.status_code == 422


def test_units_points_returns_points_for_kreis(client):
    resp = client.get("/units/points", params={"kreis_ags": "09162"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["truncated"] is False
    mastr_nummern = {p["mastr_nummer"] for p in body["points"]}
    assert mastr_nummern == {"SOLAR1", "SOLAR2", "STORAGE1"}


def test_units_points_excludes_units_without_coordinates(client):
    resp = client.get("/units/points", params={"kreis_ags": "11000"})
    body = resp.json()
    mastr_nummern = {p["mastr_nummer"] for p in body["points"]}
    assert mastr_nummern == {"WIND1"}  # STORAGE2_DECOMMISSIONED has no lat/lon


def test_units_points_filters_by_technology(client):
    resp = client.get(
        "/units/points", params={"kreis_ags": "09162", "technology": "storage"}
    )
    body = resp.json()
    assert {p["mastr_nummer"] for p in body["points"]} == {"STORAGE1"}


def test_units_points_truncates_and_flags_when_over_cap(client):
    resp = client.get("/units/points", params={"kreis_ags": "09162", "limit": 1})
    body = resp.json()
    assert len(body["points"]) == 1
    assert body["truncated"] is True
