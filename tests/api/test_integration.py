def test_openapi_docs_render(client):
    resp = client.get("/docs")
    assert resp.status_code == 200


def test_openapi_schema_lists_all_routers(client):
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    paths = resp.json()["paths"]
    assert "/capacity/additions" in paths
    assert "/capacity/totals" in paths
    assert "/units" in paths
    assert "/units/{mastr_nummer}" in paths
    assert "/regions" in paths
    assert "/regions/{level}/geojson" in paths
    assert "/meta/technologies" in paths
    assert "/meta/size-classes" in paths
    assert "/meta/health" in paths


def test_cross_router_scenario_totals_then_drill_down_to_unit(client):
    totals = client.get("/capacity/totals", params={"technology": "wind"}).json()
    assert totals["results"][0]["capacity_kw_sum"] == 3000.0

    units = client.get("/units", params={"technology": "wind"}).json()
    assert units["total"] == 1
    mastr_nummer = units["items"][0]["mastr_nummer"]

    detail = client.get(f"/units/{mastr_nummer}").json()
    assert detail["capacity_kw"] == 3000.0
