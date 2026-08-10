"""Shared technology/status enums and mappings.

Used by both ingestion/ and api/, so this module has zero third-party
dependencies -- api/ should never need to pull in geopandas/GDAL just to
import an enum.
"""
from __future__ import annotations

from enum import Enum


class Category(str, Enum):
    GENERATION = "generation"
    STORAGE = "storage"


class Technology(str, Enum):
    SOLAR = "solar"
    WIND = "wind"
    BIOMASS = "biomass"
    HYDRO = "hydro"
    NUCLEAR = "nuclear"
    GSGK = "gsgk"  # Geothermie, Solarthermie, Grubengas, Klaerschlamm, Druckentspannung
    COMBUSTION = "combustion"
    STORAGE = "storage"


CATEGORY_BY_TECHNOLOGY: dict[Technology, Category] = {
    Technology.SOLAR: Category.GENERATION,
    Technology.WIND: Category.GENERATION,
    Technology.BIOMASS: Category.GENERATION,
    Technology.HYDRO: Category.GENERATION,
    Technology.NUCLEAR: Category.GENERATION,
    Technology.GSGK: Category.GENERATION,
    Technology.COMBUSTION: Category.GENERATION,
    Technology.STORAGE: Category.STORAGE,
}

IS_RENEWABLE: dict[Technology, bool | None] = {
    Technology.SOLAR: True,
    Technology.WIND: True,
    Technology.BIOMASS: True,
    Technology.HYDRO: True,
    Technology.NUCLEAR: False,
    Technology.GSGK: True,
    Technology.COMBUSTION: False,
    # Storage is neither "renewable generation" nor fossil generation --
    # category (storage vs generation) is the meaningful split for it, not
    # this flag. Left as None rather than guessing true/false.
    Technology.STORAGE: None,
}


class UnitStatus(str, Enum):
    IN_OPERATION = "in_operation"
    PLANNED = "planned"
    TEMPORARILY_DECOMMISSIONED = "temporarily_decommissioned"
    PERMANENTLY_DECOMMISSIONED = "permanently_decommissioned"
    OTHER = "other"


# open-mastr per-technology table name -> Technology. Only "storage_extended"
# has been confirmed against a real bulk download so far (see project
# history: Mastr().download(method="bulk", data=["storage"]) produced
# storage_extended + storage_eeg). The others follow open-mastr's documented
# per-technology naming pattern but are NOT yet verified -- confirm against
# a real full download in Phase 2 before trusting non-storage ingestion.
MASTR_TABLE_TO_TECHNOLOGY: dict[str, Technology] = {
    "storage_extended": Technology.STORAGE,
    "solar_extended": Technology.SOLAR,
    "wind_extended": Technology.WIND,
    "biomass_extended": Technology.BIOMASS,
    "hydro_extended": Technology.HYDRO,
    "nuclear_extended": Technology.NUCLEAR,
    "gsgk_extended": Technology.GSGK,
    "combustion_extended": Technology.COMBUSTION,
}

# MaStR's raw EinheitBetriebsstatus values -> normalized UnitStatus. Exact
# casing/spelling should be re-checked against a real download in Phase 2.
MASTR_STATUS_MAP: dict[str, UnitStatus] = {
    "InBetrieb": UnitStatus.IN_OPERATION,
    "InPlanung": UnitStatus.PLANNED,
    "VoruebergehendStillgelegt": UnitStatus.TEMPORARILY_DECOMMISSIONED,
    "EndgueltigStillgelegt": UnitStatus.PERMANENTLY_DECOMMISSIONED,
}


def normalize_status(raw: str | None) -> UnitStatus:
    if raw is None:
        return UnitStatus.OTHER
    return MASTR_STATUS_MAP.get(raw, UnitStatus.OTHER)
