from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from db.models import CapacityRollup
from db.session import init_db


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
