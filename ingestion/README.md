# Ingestion

Fetches and transforms MaStR + VG250 data into the processed analytics
database read by `api/`. **Must run on a machine with normal internet
access** -- marktstammdatenregister.de and bkg.bund.de are blocked from this
project's cloud dev sandbox, confirmed during initial feasibility testing.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate   # or .venv\Scripts\Activate.ps1 on Windows
pip install -r ingestion/requirements.txt
```

## 1. Sync MaStR

```bash
python -m ingestion.cli sync
```

Bulk-downloads via `open-mastr` into `data/raw/open-mastr.db`. Only the
`storage` technology has been confirmed end-to-end so far; a full sync
across all technologies in `ingestion/config.py:TECHNOLOGIES` will take
considerably longer and produce a much larger raw database.

## 2. Get VG250(-EW)

Manual step -- BKG's portal isn't reachable from automation in this project:

1. Open BKG's GDZ open-data catalog and find **VG250** (prefer the
   **VG250-EW** variant, which adds population/area per region) at
   https://gdz.bkg.bund.de/index.php/default/open-data/verwaltungsgebiete-1-250-000-stand-01-01-vg250-01-01.html
2. Download in **Geopackage** format, UTM32/ETRS89 (EPSG:25832).
3. Unzip if it arrives as a zip.

## 3. Build the processed database

```bash
python -m ingestion.cli build --vg250-path "<path to the .gpkg file or unzipped folder>"
```

Or run both steps at once: `python -m ingestion.cli all --vg250-path ...`.

Output lands in `data/processed/`: `mastr_analytics.db`, `kreise.geo.json`,
`bundeslaender.geo.json`. Point `api/`'s `DATABASE_URL` and `GEO_ASSETS_DIR`
at this directory (copy it over if the API runs somewhere else).

Re-running `build` is safe -- `capacity_unit` rows are upserted by
`mastr_nummer`, and `region` rows are merged by `ags`.
