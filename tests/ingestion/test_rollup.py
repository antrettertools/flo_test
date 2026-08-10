import datetime as dt

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from db.models import CapacityRollup, CapacityUnit
from db.session import init_db
from ingestion.rollup import build_rollup


def test_capacity_rollup_table_created():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    with Session(engine) as session:
        session.add(
            CapacityRollup(
                kind="addition",
                category="generation",
                technology="solar",
                kreis_ags="09162",
                size_class="<10 kW",
                year_month="2023-07",
                unit_count=5,
                capacity_kw_sum=40.0,
                storage_capacity_kwh_sum=None,
            )
        )
        session.commit()
        row = session.scalar(select(CapacityRollup))
        assert row.unit_count == 5
        assert row.capacity_kw_sum == 40.0


def _unit(**overrides) -> CapacityUnit:
    defaults = dict(
        mastr_nummer="U1",
        source_table="solar_extended",
        category="generation",
        technology="solar",
        status="in_operation",
        commissioning_date=dt.date(2023, 7, 15),
        capacity_kw=8.0,
        size_class="<10 kW",
        kreis_ags="09162",
        land_ags="09",
    )
    defaults.update(overrides)
    return CapacityUnit(**defaults)


def test_build_rollup_aggregates_additions_by_month_and_kreis():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    with Session(engine) as session:
        session.add_all(
            [
                _unit(mastr_nummer="U1", capacity_kw=8.0),
                _unit(mastr_nummer="U2", capacity_kw=12.0),
                _unit(mastr_nummer="U3", commissioning_date=dt.date(2023, 8, 1), capacity_kw=5.0),
            ]
        )
        session.commit()

        count = build_rollup(session)
        session.commit()

        assert count == 2  # two distinct (technology, kreis, size_class, month) groups
        july = session.scalar(
            select(CapacityRollup).where(CapacityRollup.year_month == "2023-07")
        )
        assert july.kind == "addition"
        assert july.unit_count == 2
        assert july.capacity_kw_sum == 20.0
        assert july.kreis_ags == "09162"


def test_build_rollup_includes_decommission_kind():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    with Session(engine) as session:
        session.add(
            _unit(
                mastr_nummer="U1",
                commissioning_date=dt.date(2019, 1, 1),
                decommissioning_date=dt.date(2023, 3, 10),
            )
        )
        session.commit()

        build_rollup(session)
        session.commit()

        decommission = session.scalar(
            select(CapacityRollup).where(CapacityRollup.kind == "decommission")
        )
        assert decommission.year_month == "2023-03"
        assert decommission.unit_count == 1


def test_build_rollup_keeps_unmapped_units_with_null_kreis_ags():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    with Session(engine) as session:
        session.add(_unit(mastr_nummer="U1", kreis_ags=None, land_ags=None))
        session.commit()

        build_rollup(session)
        session.commit()

        row = session.scalar(select(CapacityRollup))
        assert row.kreis_ags is None
        assert row.unit_count == 1


def test_build_rollup_is_idempotent_on_rerun():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    with Session(engine) as session:
        session.add(_unit(mastr_nummer="U1"))
        session.commit()

        build_rollup(session)
        session.commit()
        build_rollup(session)  # rerun without changing capacity_unit
        session.commit()

        assert session.scalar(select(func.count()).select_from(CapacityRollup)) == 1
