import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from common.enums import Technology
from db.models import CapacityUnit
from db.session import init_db
from ingestion.mastr_transform import transform_table, upsert_capacity_units


def _storage_row(**overrides) -> dict:
    row = {
        "EinheitMastrNummer": "SEE123",
        "EinheitBetriebsstatus": "InBetrieb",
        "Inbetriebnahmedatum": "2023-05-01",
        "DatumEndgueltigeStilllegung": None,
        "Nettonennleistung": 5.0,
        "NutzbareSpeicherkapazitaet": 12.5,
        "Postleitzahl": "10115",
        "Gemeinde": "Berlin",
        "Gemeindeschluessel": "11000000",
        "Bundesland": "Berlin",
    }
    row.update(overrides)
    return row


def test_transform_storage_table_maps_core_fields():
    df = pd.DataFrame([_storage_row()])

    rows = transform_table(df, Technology.STORAGE, "storage_extended")

    assert len(rows) == 1
    row = rows[0]
    assert row["mastr_nummer"] == "SEE123"
    assert row["category"] == "storage"
    assert row["status"] == "in_operation"
    assert row["storage_capacity_kwh"] == 12.5
    assert row["kreis_ags"] == "11000"
    assert row["land_ags"] == "11"
    assert row["size_class"] == "10-30 kWh"


def test_transform_handles_missing_region_code():
    df = pd.DataFrame(
        [
            _storage_row(
                EinheitMastrNummer="SEE999",
                Postleitzahl=None,
                Gemeinde=None,
                Gemeindeschluessel=None,
                Bundesland=None,
            )
        ]
    )

    rows = transform_table(df, Technology.STORAGE, "storage_extended")

    assert rows[0]["kreis_ags"] is None
    assert rows[0]["land_ags"] is None


def test_transform_generation_size_class_and_no_storage_kwh():
    df = pd.DataFrame(
        [
            {
                "EinheitMastrNummer": "SGE1",
                "EinheitBetriebsstatus": "InBetrieb",
                "Inbetriebnahmedatum": "2022-01-01",
                "DatumEndgueltigeStilllegung": None,
                "Nettonennleistung": 7.5,
                "Postleitzahl": "80331",
                "Gemeinde": "Muenchen",
                "Gemeindeschluessel": "09162000",
                "Bundesland": "Bayern",
            }
        ]
    )

    rows = transform_table(df, Technology.SOLAR, "solar_extended")

    assert rows[0]["size_class"] == "<10 kW"
    assert rows[0]["kreis_ags"] == "09162"
    assert rows[0]["storage_capacity_kwh"] is None
    assert rows[0]["is_renewable"] is True


def test_transform_unknown_status_maps_to_other():
    df = pd.DataFrame([_storage_row(EinheitBetriebsstatus="SomeUnmappedValue")])

    rows = transform_table(df, Technology.STORAGE, "storage_extended")

    assert rows[0]["status"] == "other"
    assert rows[0]["status_raw"] == "SomeUnmappedValue"


def test_upsert_inserts_then_updates_by_mastr_nummer():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)

    df = pd.DataFrame([_storage_row(Nettonennleistung=5.0)])
    rows = transform_table(df, Technology.STORAGE, "storage_extended")

    with Session(engine) as session:
        upsert_capacity_units(session, rows)
        session.commit()
        assert session.query(CapacityUnit).count() == 1

        updated_rows = transform_table(
            pd.DataFrame([_storage_row(Nettonennleistung=6.0)]), Technology.STORAGE, "storage_extended"
        )
        upsert_capacity_units(session, updated_rows)
        session.commit()

        assert session.query(CapacityUnit).count() == 1
        assert session.query(CapacityUnit).one().capacity_kw == 6.0
