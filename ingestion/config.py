from __future__ import annotations

import os
from pathlib import Path

RAW_DB_PATH = Path(os.environ.get("MASTR_RAW_DB_PATH", "data/raw/open-mastr.db"))
PROCESSED_DIR = Path(os.environ.get("MASTR_PROCESSED_DIR", "data/processed"))
PROCESSED_DB_PATH = PROCESSED_DIR / "mastr_analytics.db"

# Technologies passed to Mastr().download(data=[...]). Only "storage" has
# been confirmed to sync successfully against a real bulk download so far
# (see project history). Confirm the rest in Phase 2 before relying on them.
TECHNOLOGIES = [
    "storage",
    "solar",
    "wind",
    "biomass",
    "hydro",
    "nuclear",
    "gsgk",
    "combustion",
]

VG250_KREIS_LAYER = "vg250_krs"
VG250_LAND_LAYER = "vg250_lan"
