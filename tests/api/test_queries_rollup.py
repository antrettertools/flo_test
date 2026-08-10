import datetime as dt

import pytest

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
