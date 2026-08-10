from api.queries import CapacityFilters, query_units, run_aggregation


def _by_category(rows: list[dict]) -> dict[str, dict]:
    return {r["category"]: r for r in rows}


def test_totals_default_excludes_decommissioned(db_session):
    from datetime import date

    rows = run_aggregation(db_session, CapacityFilters(), [], as_of_date=date(2026, 1, 1))
    by_cat = _by_category(rows)

    assert by_cat["storage"]["unit_count"] == 1
    assert by_cat["storage"]["storage_capacity_kwh_sum"] == 12.5
    assert by_cat["generation"]["unit_count"] == 3
    assert by_cat["generation"]["capacity_kw_sum"] == 50.0 + 8.0 + 3000.0


def test_totals_include_decommissioned(db_session):
    from datetime import date

    rows = run_aggregation(
        db_session,
        CapacityFilters(),
        [],
        as_of_date=date(2026, 1, 1),
        include_decommissioned=True,
    )
    by_cat = _by_category(rows)

    assert by_cat["storage"]["unit_count"] == 2
    assert by_cat["storage"]["storage_capacity_kwh_sum"] == 12.5 + 8.0


def test_additions_filtered_by_date_range(db_session):
    from datetime import date

    rows = run_aggregation(
        db_session,
        CapacityFilters(),
        [],
        date_from=date(2022, 1, 1),
        date_to=date(2022, 12, 31),
    )
    by_cat = _by_category(rows)

    assert by_cat["generation"]["unit_count"] == 1
    assert by_cat["generation"]["capacity_kw_sum"] == 50.0
    assert by_cat["storage"]["unit_count"] == 1
    assert by_cat["storage"]["storage_capacity_kwh_sum"] == 12.5


def test_additions_grouped_by_region_kreis(db_session):
    rows = run_aggregation(
        db_session,
        CapacityFilters(region_level="kreis"),
        ["region"],
    )
    munich_generation = next(
        r for r in rows if r["region_ags"] == "09162" and r["category"] == "generation"
    )
    assert munich_generation["unit_count"] == 2
    assert munich_generation["capacity_kw_sum"] == 58.0

    berlin_storage = next(
        r for r in rows if r["region_ags"] == "11000" and r["category"] == "storage"
    )
    assert berlin_storage["unit_count"] == 1
    assert berlin_storage["storage_capacity_kwh_sum"] == 8.0


def test_additions_grouped_by_month(db_session):
    from datetime import date

    rows = run_aggregation(
        db_session,
        CapacityFilters(),
        ["month"],
        date_from=date(2022, 1, 1),
        date_to=date(2022, 12, 31),
    )
    months = {r["month"] for r in rows}
    assert months == {"2022-03", "2022-11"}


def test_technology_filter_narrows_results(db_session):
    rows = run_aggregation(db_session, CapacityFilters(technology=["wind"]), [])
    assert len(rows) == 1
    assert rows[0]["category"] == "generation"
    assert rows[0]["unit_count"] == 1
    assert rows[0]["capacity_kw_sum"] == 3000.0


def test_query_units_paginates_and_filters(db_session):
    total, rows = query_units(
        db_session, CapacityFilters(category="generation"), limit=2, offset=0
    )
    assert total == 3
    assert len(rows) == 2

    total2, rows2 = query_units(
        db_session, CapacityFilters(category="generation"), limit=2, offset=2
    )
    assert total2 == 3
    assert len(rows2) == 1
