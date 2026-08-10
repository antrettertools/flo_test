import datetime as dt

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from api.queries import _month_end, _month_start, _shift_year_month, _split_date_range


def test_month_start_and_end():
    assert _month_start(dt.date(2023, 7, 15)) == dt.date(2023, 7, 1)
    assert _month_end(dt.date(2023, 7, 15)) == dt.date(2023, 7, 31)
    assert _month_end(dt.date(2023, 2, 1)) == dt.date(2023, 2, 28)


def test_shift_year_month():
    assert _shift_year_month("2023-07", 1) == "2023-08"
    assert _shift_year_month("2023-12", 1) == "2024-01"
    assert _shift_year_month("2023-01", -1) == "2022-12"


def test_split_date_range_no_bounds():
    assert _split_date_range(None, None) == (None, None, [])


def test_split_date_range_both_month_aligned():
    lo, hi, raw = _split_date_range(dt.date(2023, 6, 1), dt.date(2023, 8, 31))
    assert (lo, hi, raw) == ("2023-06", "2023-08", [])


def test_split_date_range_same_partial_month():
    lo, hi, raw = _split_date_range(dt.date(2023, 7, 5), dt.date(2023, 7, 20))
    assert (lo, hi, raw) == (None, None, [(dt.date(2023, 7, 5), dt.date(2023, 7, 20))])


def test_split_date_range_partial_edges_across_months():
    lo, hi, raw = _split_date_range(dt.date(2023, 6, 15), dt.date(2023, 8, 10))
    assert lo == "2023-07"
    assert hi == "2023-07"
    assert raw == [
        (dt.date(2023, 6, 15), dt.date(2023, 6, 30)),
        (dt.date(2023, 8, 1), dt.date(2023, 8, 10)),
    ]


def test_split_date_range_only_lower_bound():
    lo, hi, raw = _split_date_range(dt.date(2023, 6, 15), None)
    assert lo == "2023-07"
    assert hi is None
    assert raw == [(dt.date(2023, 6, 15), dt.date(2023, 6, 30))]


def test_split_date_range_only_upper_bound():
    lo, hi, raw = _split_date_range(None, dt.date(2023, 8, 10))
    assert lo is None
    assert hi == "2023-07"
    assert raw == [(dt.date(2023, 8, 1), dt.date(2023, 8, 10))]


from api.queries import _merge_group_rows, _negate_row


def test_merge_group_rows_sums_matching_keys():
    rows = [
        {"category": "generation", "technology": "solar", "unit_count": 2, "capacity_kw_sum": 10.0, "storage_capacity_kwh_sum": None},
        {"category": "generation", "technology": "solar", "unit_count": 3, "capacity_kw_sum": 5.0, "storage_capacity_kwh_sum": None},
        {"category": "generation", "technology": "wind", "unit_count": 1, "capacity_kw_sum": 100.0, "storage_capacity_kwh_sum": None},
    ]
    merged = _merge_group_rows(rows)
    assert len(merged) == 2
    solar = next(r for r in merged if r["technology"] == "solar")
    assert solar["unit_count"] == 5
    assert solar["capacity_kw_sum"] == 15.0


def test_merge_group_rows_treats_none_as_no_contribution():
    rows = [
        {"category": "storage", "technology": "storage", "unit_count": 1, "capacity_kw_sum": None, "storage_capacity_kwh_sum": None},
    ]
    merged = _merge_group_rows(rows)
    assert merged[0]["capacity_kw_sum"] is None


def test_negate_row_flips_count_and_sums():
    row = {"category": "generation", "technology": "solar", "unit_count": 3, "capacity_kw_sum": 10.0, "storage_capacity_kwh_sum": None}
    negated = _negate_row(row)
    assert negated["unit_count"] == -3
    assert negated["capacity_kw_sum"] == -10.0
    assert negated["storage_capacity_kwh_sum"] is None
    assert negated["category"] == "generation"  # non-numeric fields untouched


from db.session import init_db
from ingestion.rollup import build_rollup
from api.queries import CapacityFilters, run_aggregation
from tests.fixtures.seed import seed_capacity_units


@pytest.fixture()
def rollup_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    init_db(engine)
    session = Session(engine)
    seed_capacity_units(session)
    session.commit()
    build_rollup(session)
    session.commit()
    yield session
    session.close()


def test_totals_as_of_date_matches_raw_and_rollup_combined(rollup_session):
    # fixture has SOLAR1 (2022-03-15, 50kW) and SOLAR2 (2023-07-01, 8kW) in Muenchen
    filters = CapacityFilters(technology=["solar"])
    rows = run_aggregation(rollup_session, filters, ["technology"], as_of_date=dt.date(2023, 7, 15))
    solar = next(r for r in rows if r.get("technology") == "solar")
    assert solar["unit_count"] == 2
    assert solar["capacity_kw_sum"] == 58.0


def test_totals_excludes_decommissioned_by_default(rollup_session):
    # STORAGE2_DECOMMISSIONED: commissioned 2019-05-01, decommissioned 2023-01-01
    filters = CapacityFilters(technology=["storage"])
    rows = run_aggregation(rollup_session, filters, [], as_of_date=dt.date(2023, 6, 1))
    storage = next(r for r in rows if r["category"] == "storage")
    assert storage["unit_count"] == 1  # only STORAGE1, STORAGE2 is decommissioned by June 2023


def test_totals_includes_decommissioned_when_requested(rollup_session):
    filters = CapacityFilters(technology=["storage"])
    rows = run_aggregation(
        rollup_session, filters, [], as_of_date=dt.date(2023, 6, 1), include_decommissioned=True
    )
    storage = next(r for r in rows if r["category"] == "storage")
    assert storage["unit_count"] == 2


def test_additions_partial_month_range(rollup_session):
    # SOLAR2 commissioned 2023-07-01 -- range starts mid-month, excludes it
    filters = CapacityFilters(technology=["solar"])
    rows = run_aggregation(
        rollup_session, filters, [], date_from=dt.date(2023, 7, 2), date_to=dt.date(2023, 7, 31)
    )
    assert rows == []


def test_additions_whole_month_range_includes_it(rollup_session):
    filters = CapacityFilters(technology=["solar"])
    rows = run_aggregation(
        rollup_session, filters, [], date_from=dt.date(2023, 7, 1), date_to=dt.date(2023, 7, 31)
    )
    solar = next(r for r in rows if r["category"] == "generation")
    assert solar["unit_count"] == 1


def test_land_level_totals_derive_from_kreis_grain(rollup_session):
    filters = CapacityFilters(technology=["solar"], region_level="land")
    rows = run_aggregation(rollup_session, filters, ["region"], as_of_date=dt.date(2023, 12, 31))
    bayern = next(r for r in rows if r["region_ags"] == "09")
    assert bayern["unit_count"] == 2


def test_totals_month_grouped_decommissioned_unit_not_phantom(rollup_session):
    # Regression test: capacity_rollup's decommission rows are keyed by
    # decommissioning month, not by each unit's original commissioning
    # month, so month-grouped totals-as-of-date can't be netted correctly
    # via the rollup-diff path -- STORAGE2_DECOMMISSIONED (commissioned
    # 2019-05-01, decommissioned 2023-01-01) must NOT surface as a phantom
    # +1 in 2019-05 nor a negative row in 2023-01; it should simply not
    # appear anywhere in the as-of-date snapshot, matching what
    # group_by=[] already nets to correctly (unit_count == 1, STORAGE1 only).
    filters = CapacityFilters(technology=["storage"])
    rows = run_aggregation(rollup_session, filters, ["month"], as_of_date=dt.date(2023, 6, 1))

    assert all(r["unit_count"] >= 0 for r in rows)

    by_month = {r["month"]: r for r in rows}
    assert "2019-05" not in by_month
    assert "2023-01" not in by_month
    assert by_month["2022-11"]["unit_count"] == 1
    assert by_month["2022-11"]["storage_capacity_kwh_sum"] == 12.5

    assert sum(r["unit_count"] for r in rows) == 1
