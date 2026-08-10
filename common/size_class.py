"""Installation size-class bucketing.

Not an official BNetzA scheme -- a judgment call made once here so ingestion
and the API's /meta/size-classes endpoint share a single source of truth
instead of duplicating thresholds.
"""
from __future__ import annotations

from common.enums import Category

# (upper_bound_exclusive, label), ordered ascending. Last bucket is open-ended.
GENERATION_BUCKETS_KW: list[tuple[float | None, str]] = [
    (10, "<10 kW"),
    (30, "10-30 kW"),
    (100, "30-100 kW"),
    (500, "100-500 kW"),
    (1_000, "500 kW-1 MW"),
    (10_000, "1-10 MW"),
    (None, ">=10 MW"),
]

STORAGE_BUCKETS_KWH: list[tuple[float | None, str]] = [
    (5, "<5 kWh"),
    (10, "5-10 kWh"),
    (30, "10-30 kWh"),
    (100, "30-100 kWh"),
    (1_000, "100 kWh-1 MWh"),
    (10_000, "1-10 MWh"),
    (None, ">=10 MWh"),
]


def _bucket(value: float | None, buckets: list[tuple[float | None, str]]) -> str | None:
    if value is None:
        return None
    for upper, label in buckets:
        if upper is None or value < upper:
            return label
    return buckets[-1][1]


def size_class_for(
    category: Category,
    capacity_kw: float | None,
    storage_capacity_kwh: float | None,
) -> str | None:
    if category == Category.STORAGE:
        return _bucket(storage_capacity_kwh, STORAGE_BUCKETS_KWH)
    return _bucket(capacity_kw, GENERATION_BUCKETS_KW)


def size_class_definitions() -> dict[str, list[str]]:
    return {
        Category.GENERATION.value: [label for _, label in GENERATION_BUCKETS_KW],
        Category.STORAGE.value: [label for _, label in STORAGE_BUCKETS_KWH],
    }
