"""Shared synthetic fixture data for API tests.

Five capacity_unit rows spanning both categories, two technologies, two
Kreise/two Bundeslaender, and a decommissioned unit -- deliberately picked so
every filter dimension (technology, category, region level, size_class,
date range, decommissioned) has at least one row that matches and one that
doesn't. See docs/superpowers/plans/2026-08-10-phase3-api-implementation-plan.md
for the exact expected aggregates computed from this dataset.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy.orm import Session

from db.models import CapacityUnit, Region


def seed_regions(session: Session) -> None:
    session.add_all(
        [
            Region(ags="09", level="land", name="Bayern", parent_ags=None),
            Region(ags="09162", level="kreis", name="Muenchen", parent_ags="09"),
            Region(ags="11", level="land", name="Berlin", parent_ags=None),
            Region(ags="11000", level="kreis", name="Berlin", parent_ags="11"),
        ]
    )


def seed_capacity_units(session: Session) -> None:
    session.add_all(
        [
            CapacityUnit(
                mastr_nummer="SOLAR1",
                source_table="solar_extended",
                category="generation",
                technology="solar",
                is_renewable=True,
                status="in_operation",
                commissioning_date=dt.date(2022, 3, 15),
                capacity_kw=50.0,
                capacity_kw_type="net_nominal",
                size_class="30-100 kW",
                postcode="80331",
                municipality_name="Muenchen",
                gemeinde_ags="09162000",
                kreis_ags="09162",
                land_ags="09",
                land_name="Bayern",
                latitude=48.1351,
                longitude=11.5820,
            ),
            CapacityUnit(
                mastr_nummer="SOLAR2",
                source_table="solar_extended",
                category="generation",
                technology="solar",
                is_renewable=True,
                status="in_operation",
                commissioning_date=dt.date(2023, 7, 1),
                capacity_kw=8.0,
                capacity_kw_type="net_nominal",
                size_class="<10 kW",
                postcode="80331",
                municipality_name="Muenchen",
                gemeinde_ags="09162000",
                kreis_ags="09162",
                land_ags="09",
                land_name="Bayern",
                latitude=48.1400,
                longitude=11.5900,
            ),
            CapacityUnit(
                mastr_nummer="WIND1",
                source_table="wind_extended",
                category="generation",
                technology="wind",
                is_renewable=True,
                status="in_operation",
                commissioning_date=dt.date(2021, 1, 10),
                capacity_kw=3000.0,
                capacity_kw_type="net_nominal",
                size_class="1-10 MW",
                postcode="10115",
                municipality_name="Berlin",
                gemeinde_ags="11000000",
                kreis_ags="11000",
                land_ags="11",
                land_name="Berlin",
                latitude=52.5200,
                longitude=13.4050,
            ),
            CapacityUnit(
                mastr_nummer="STORAGE1",
                source_table="storage_extended",
                category="storage",
                technology="storage",
                is_renewable=None,
                status="in_operation",
                commissioning_date=dt.date(2022, 11, 20),
                capacity_kw=5.0,
                capacity_kw_type="net_nominal",
                storage_capacity_kwh=12.5,
                size_class="10-30 kWh",
                postcode="80331",
                municipality_name="Muenchen",
                gemeinde_ags="09162000",
                kreis_ags="09162",
                land_ags="09",
                land_name="Bayern",
                latitude=48.1360,
                longitude=11.5830,
            ),
            CapacityUnit(
                mastr_nummer="STORAGE2_DECOMMISSIONED",
                source_table="storage_extended",
                category="storage",
                technology="storage",
                is_renewable=None,
                status="permanently_decommissioned",
                commissioning_date=dt.date(2019, 5, 1),
                decommissioning_date=dt.date(2023, 1, 1),
                capacity_kw=3.0,
                capacity_kw_type="net_nominal",
                storage_capacity_kwh=8.0,
                size_class="5-10 kWh",
                postcode="10115",
                municipality_name="Berlin",
                gemeinde_ags="11000000",
                kreis_ags="11000",
                land_ags="11",
                land_name="Berlin",
            ),
        ]
    )


def seed_all(session: Session) -> None:
    seed_regions(session)
    seed_capacity_units(session)
    session.commit()
