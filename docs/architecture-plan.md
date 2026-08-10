# BNetzA Renewable Capacity Pipeline + API + Dashboard

## Context

We want a tool that shows **new** (period additions) and **total** (cumulative) installed capacity of German renewable generation and storage, sourced from Bundesnetzagentur's Marktstammdatenregister (MaStR), sliceable by technology, region, and installation size class at unit-level granularity. This plan follows a research/brainstorm phase and hands-on local verification (see conversation history): `open-mastr` successfully bulk-downloaded and parsed MaStR storage data locally, producing `storage_extended` (unit master data: capacity, commissioning date, location) and `storage_eeg` (EEG subsidy attributes) tables; BKG's official VG250 boundary product was confirmed to carry a direct `AGS` (Amtlicher Gemeindeschlüssel) attribute on both `VG250_KRS` (Kreise) and `VG250_LAN` (Länder) layers, with a `GF` attribute needed to filter out duplicate coastal polygons (keep `GF==4`). The repo (`antrettertools/flo_test`) originally contained only two throwaway smoke-test scripts (`scripts/verify_mastr.py`, `scripts/verify_vg250.py`) — this plan replaces them with the real architecture.

**Hard environment constraint**: BNetzA/MaStR/SMARD and BKG domains are all blocked by the cloud sandbox's egress policy used for development. Actual data-fetching (`open-mastr` sync, VG250 download) can only run on the user's own machine (as already done for verification) — never in this project's dev sandbox. The architecture below is deliberately split so that everything requiring live internet access (`ingestion/`) is cleanly separable from everything that isn't (`api/`, `frontend/`, schema/transform logic tested against fixtures) — the latter can be built and tested end-to-end in the sandbox; the former needs a handoff back to the user's machine, the same way the verification scripts did.

## Repo layout

```
flo_test/
├── common/                        # zero-dependency, shared by ingestion AND api
│   ├── enums.py                   # Technology, Category, UnitStatus enums + is_renewable map
│   └── size_class.py              # bucket thresholds + bucketing fn (generation kW, storage kWh)
├── db/
│   ├── models.py                  # SQLAlchemy: CapacityUnit, Region, ImportBatch
│   └── session.py                 # engine/session factory, reads DATABASE_URL env var
├── ingestion/                     # needs geopandas/GDAL + live egress -- runs on user's machine only
│   ├── requirements.txt           # open-mastr, geopandas, pyogrio, pandas, sqlalchemy
│   ├── README.md                  # manual VG250-EW download steps
│   ├── config.py                  # raw/processed paths, technology list, VG250 layer names
│   ├── mastr_sync.py              # wraps Mastr().download(method="bulk", data=[...])
│   ├── mastr_transform.py         # per-technology extended tables -> unified CapacityUnit rows
│   ├── vg250_transform.py         # VG250 gpkg -> GF=4-filtered GeoJSON + Region rows
│   ├── build_db.py                # orchestrates transform steps -> data/processed/
│   └── cli.py                     # `python -m ingestion.cli sync|build|all`
├── api/                           # no GDAL/egress needed -- only reads processed artifacts
│   ├── requirements.txt           # fastapi, uvicorn, sqlalchemy, pydantic
│   ├── main.py                    # FastAPI app, CORS, router mounting
│   ├── deps.py                    # DB session + GEO_ASSETS_DIR dependencies
│   ├── schemas.py                 # Pydantic request/response models
│   ├── queries.py                 # shared SQLAlchemy aggregation builders
│   └── routers/
│       ├── capacity.py            # /capacity/additions, /capacity/totals
│       ├── units.py               # /units, /units/{mastr_nummer}
│       ├── regions.py             # /regions, /regions/{level}/geojson
│       └── meta.py                # /meta/technologies, /meta/size-classes, /meta/health
├── frontend/
│   └── src/
│       ├── api/client.ts
│       ├── state/filters.ts       # Zustand store: metric, mode, technologies, region level, dates
│       ├── hooks/useCapacityByRegion.ts
│       ├── hooks/useRegionGeojson.ts
│       └── components/
│           ├── Dashboard.tsx
│           ├── ChoroplethMap.tsx  # MapLibre GL, feature-state driven coloring
│           ├── MetricToggle.tsx   # "New in period" vs "Total installed"
│           ├── RegionLevelToggle.tsx
│           ├── TechnologyFilter.tsx  # generation multi-select vs. storage mode (mutually exclusive)
│           ├── DateRangeControl.tsx
│           └── Legend.tsx
├── data/                          # gitignored -- artifacts only
│   └── processed/                 # mastr_analytics.db, kreise.geo.json, bundeslaender.geo.json
├── scripts/                       # verify_mastr.py, verify_vg250.py -- deleted at end of Phase 2
└── tests/
    ├── fixtures/                  # tiny synthetic data -- no real downloads, sandbox-safe
    ├── ingestion/
    └── api/
```

## Schema

**`capacity_unit`** (unit-level fact table, source of truth for all aggregation):
`id, mastr_nummer (unique), source_table, category ('generation'|'storage'), technology, is_renewable, status (normalized), status_raw, commissioning_date, decommissioning_date, capacity_kw, capacity_kw_type, storage_capacity_kwh (storage only), size_class, postcode, municipality_name, gemeinde_ags, kreis_ags (derived, indexed), land_ags (derived, indexed), land_name, latitude, longitude, import_batch_id, created_at, updated_at`.

Indexes: unique(`mastr_nummer`); (`technology`,`commissioning_date`); (`kreis_ags`,`technology`); (`land_ags`,`technology`); (`status`); (`size_class`).

Rows with missing/malformed `gemeinde_ags` are still ingested (count toward national/technology totals) with `kreis_ags`/`land_ags` = NULL; `/meta/health` reports the unmatched rate so this stays visible. EEG subsidy fields are excluded from v1 (future join on `mastr_nummer` if needed).

**`region`**: `ags (PK), level ('land'|'kreis'), name, parent_ags`. No geometry in the DB — geometry lives in static `data/processed/{kreise,bundeslaender}.geo.json` (VG250, `GF==4` filtered, reprojected to EPSG:4326, properties trimmed to `{ags, name}`). Keeps SQLite→Postgres migration trivial (no PostGIS needed) and leaves room for a future density metric (VG250-EW's `EWZ`/`KFL` would just be two more numeric columns on `region`).

**`import_batch`**: `id, started_at, finished_at, mastr_row_counts_json, vg250_source_version, region_join_match_rate` — backs `/meta/health`.

**Size classes** (`common/size_class.py`, one ordered threshold list per category, judgment call not an official BNetzA scheme):
- Generation (`capacity_kw`): `<10kW, 10-30kW, 30-100kW, 100-500kW, 500kW-1MW, 1-10MW, ≥10MW`
- Storage (`storage_capacity_kwh`): `<5kWh, 5-10kWh, 10-30kWh, 30-100kWh, 100kWh-1MWh, 1-10MWh, ≥10MWh`

## Ingestion pipeline (`ingestion/`)

1. `mastr_sync.py` — wraps `Mastr(con="sqlite:///data/raw/open-mastr.db").download(method="bulk", data=[...])`, technology list from `common/enums.py`. **Only `storage_extended`/`storage_eeg` columns are verified so far** — solar/wind/etc. column names are assumed-by-pattern and must be confirmed against a real full download before `mastr_transform.py`'s per-technology mapping is finalized.
2. `mastr_transform.py` — per technology: maps source columns to canonical `capacity_unit` columns, normalizes status, derives `kreis_ags`/`land_ags` from `gemeinde_ags` (NULL-safe), computes `size_class`, upserts keyed by `mastr_nummer` (idempotent re-sync).
3. `vg250_transform.py` — loads `VG250_KRS`/`VG250_LAN` from the manually-downloaded Geopackage, filters `GF==4`, reprojects to EPSG:4326, writes the two GeoJSON files, populates `region` rows.
4. `build_db.py` — orchestrates 2+3 into `data/processed/mastr_analytics.db`, writes an `import_batch` row.
5. `cli.py` — `python -m ingestion.cli sync|build|all`.

Re-sync is manual/local-trigger only for v1 (scheduling is explicitly deferred — the environment constraint already rules out automating it from the dev sandbox).

## API (FastAPI, `api/`)

One endpoint pair handles both categories via a `category` discriminator (storage rows populate `storage_capacity_kwh_sum`, generation rows leave it null) rather than duplicating routes:

- `GET /capacity/additions` — params: `technology[], category, region_level (kreis|land), region_ags[], size_class[], date_from, date_to, group_by[] (technology|region|size_class|month)`. Filters on `commissioning_date`.
- `GET /capacity/totals` — same params minus dates, plus `as_of_date` (default today) and `include_decommissioned` (default false). Total = commissioned by `as_of_date` and not yet decommissioned.
- `GET /units` — paginated unit-level drill-down (same filters, no `group_by`).
- `GET /units/{mastr_nummer}` — single unit detail.
- `GET /regions`, `GET /regions/{level}/geojson` — region list / static boundary GeoJSON (frontend joins to capacity data client-side by `ags`).
- `GET /meta/technologies`, `/meta/size-classes`, `/meta/health` — drives filter UI and a "data as of" footer without hardcoding.

v1 aggregates run as indexed queries directly over `capacity_unit`. A materialized monthly rollup is an explicit fallback only if profiling shows it's needed — not built speculatively.

## Dashboard (`frontend/`, React + TypeScript + Vite)

**Map library: MapLibre GL JS** — purpose-built for interactive GeoJSON choropleths via `feature-state`-driven `fill-color` expressions, open-source/no API key, handles ~400 Kreis polygons comfortably, room to grow past the v1 static snapshot. State via Zustand (`metric: additions|totals`, `mode: generation|storage` — mutually exclusive since mixing kW and kWh in one choropleth is misleading, `technologies[]`, `regionLevel`, date range or as-of-date), data fetching via TanStack Query.

`ChoroplethMap.tsx` loads boundary GeoJSON once (`staleTime: Infinity`), loads capacity aggregates via `/capacity/*?group_by=region` on filter change, builds an `ags -> value` map, and applies it via `setFeatureState` rather than re-uploading GeoJSON per filter change. Join is purely client-side on `ags`.

## Build/run workflow

- **Ingestion** (user's machine only): `pip install -r ingestion/requirements.txt`, download VG250-EW Geopackage manually per `ingestion/README.md`, `python -m ingestion.cli sync`, `python -m ingestion.cli build --vg250-path <path>`, then bring `data/processed/*` back into this project (commit or copy) for the API to read.
- **API**: `pip install -r api/requirements.txt`; `DATABASE_URL=sqlite:///data/processed/mastr_analytics.db GEO_ASSETS_DIR=data/processed uvicorn api.main:app --reload`.
- **Frontend**: `npm install`; `VITE_API_BASE_URL=http://localhost:8000` in `.env.local`; `npm run dev`.
- **Tests**: `tests/ingestion`, `tests/api` run against small synthetic fixtures in `tests/fixtures/` — no real downloads, so they run fine in the dev sandbox.

## Phased build order

1. **Schema + ingestion transform logic** (buildable and testable in the dev sandbox, fixture-driven): `common/`, `db/models.py`, `mastr_transform.py`, `vg250_transform.py` + `pytest tests/ingestion` green. **Done** — see `common/`, `db/`, `ingestion/`, `tests/ingestion/`.
2. **Real ingestion run — handoff to user's machine**: run `mastr_sync` for real, reconcile actual per-technology column names against assumptions, run `vg250_transform` against a real VG250-EW download, produce the first real `mastr_analytics.db` + GeoJSON. Delete `scripts/verify_*.py` here.
3. **API**: implement all routers against the real Phase-2 database; sanity-check totals against BNetzA's own published EE-Statistik figures.
4. **Frontend hero map**: scaffold → static render → live region-grouped data with feature-state coloring → all toggles.
5. **Deferred**: animated time slider, Gemeinde-level drill-down, EEG tariff join, Postgres+Alembic, scheduled re-sync, density metric via VG250-EW `EWZ`/`KFL`.

## Verification

- Phase 1: `pytest tests/ingestion tests/api` pass against fixtures, entirely within the dev sandbox.
- Phase 2 (on user's machine): `python -m ingestion.cli all` completes; spot-check `import_batch.region_join_match_rate` is near 100%; spot-check a known technology's national total roughly matches BNetzA's published EE-Statistik figures (e.g. 2025 PV net addition ~16.5 GW).
- Phase 3: `uvicorn api.main:app` starts, `/docs` renders, manually hit `/capacity/totals?technology=solar&group_by=region` and `/regions/kreis/geojson` and confirm shapes/values look sane.
- Phase 4: `npm run dev`, open the dashboard, confirm the choropleth renders, toggling metric/mode/region-level updates colors, and a date-range change on "new in period" visibly changes the map.
