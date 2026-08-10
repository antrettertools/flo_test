def test_list_regions_returns_all_four(client):
    resp = client.get("/regions")
    assert resp.status_code == 200
    ags_values = {r["ags"] for r in resp.json()}
    assert ags_values == {"09", "09162", "11", "11000"}


def test_list_regions_filtered_by_level(client):
    resp = client.get("/regions", params={"level": "land"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    assert all(r["level"] == "land" for r in body)


def test_kreis_geojson_returns_fixture_feature_collection(client):
    resp = client.get("/regions/kreis/geojson")
    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "FeatureCollection"
    assert body["features"][0]["properties"]["ags"] == "09162"


def test_invalid_level_returns_400(client):
    resp = client.get("/regions/gemeinde/geojson")
    assert resp.status_code == 400
