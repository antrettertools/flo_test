import math

from common.enums import Category
from common.size_class import size_class_for


def test_size_class_for_none_storage_capacity_is_unknown():
    assert size_class_for(Category.STORAGE, capacity_kw=1.5, storage_capacity_kwh=None) is None


def test_size_class_for_nan_storage_capacity_is_unknown():
    """Real MaStR bulk exports leave NutzbareSpeicherkapazitaet unset for
    every storage row; pandas represents that as NaN (not None) once read
    through read_sql_table. NaN must not fall through to the open-ended
    top bucket."""
    assert (
        size_class_for(Category.STORAGE, capacity_kw=1.5, storage_capacity_kwh=math.nan)
        is None
    )


def test_size_class_for_nan_generation_capacity_is_unknown():
    assert size_class_for(Category.GENERATION, capacity_kw=math.nan, storage_capacity_kwh=None) is None


def test_size_class_for_real_storage_capacity_buckets_normally():
    assert size_class_for(Category.STORAGE, capacity_kw=1.5, storage_capacity_kwh=12.5) == "10-30 kWh"
