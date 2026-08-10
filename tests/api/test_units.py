def test_list_units_paginates(client):
    resp = client.get("/units", params={"limit": 2, "offset": 0})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 5
    assert len(body["items"]) == 2


def test_list_units_filtered_by_category(client):
    resp = client.get("/units", params={"category": "storage"})
    body = resp.json()
    assert body["total"] == 2
    assert all(item["category"] == "storage" for item in body["items"])


def test_get_unit_by_mastr_nummer(client):
    resp = client.get("/units/SOLAR1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["technology"] == "solar"
    assert body["capacity_kw"] == 50.0


def test_get_unit_404_for_unknown_id(client):
    resp = client.get("/units/DOES_NOT_EXIST")
    assert resp.status_code == 404
