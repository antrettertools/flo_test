# BNetzA Renewable Capacity Pipeline

Analyzes German renewable generation and storage capacity additions from
Bundesnetzagentur's Marktstammdatenregister (MaStR), with regional
boundaries from BKG's VG250 product.

See [`docs/architecture-plan.md`](docs/architecture-plan.md) for the full
architecture writeup. Short version:

- **`common/`** -- shared enums and size-class bucketing, no third-party deps.
- **`db/`** -- SQLAlchemy models for the processed analytics database.
- **`ingestion/`** -- fetches MaStR (via `open-mastr`) and VG250, transforms
  both into a unified unit-level `capacity_unit` table plus `region`
  boundaries. **Must run on a machine with normal internet access** --
  BNetzA/BKG domains are blocked from this project's cloud dev sandbox. See
  `ingestion/README.md`.
- **`api/`** -- FastAPI service reading the processed database (not yet
  built).
- **`frontend/`** -- dashboard with a Kreis/Bundesland choropleth map (not
  yet built).

## Status

Phase 1 complete: schema, shared utilities, and ingestion transform logic,
all tested against synthetic fixtures (`pytest`). Phase 2 complete: the
ingestion pipeline (`ingestion/cli.py sync|build|all`) is implemented and
tested against synthetic fixtures, and runs against real MaStR/VG250 downloads
-- see `ingestion/README.md`. Run it locally to produce `data/processed/mastr_analytics.db`
(gitignored -- a per-machine artifact, not shipped in the repo; a full bulk sync
can take a couple of hours). Phase 3 complete: `api/` implements all routers from
`docs/architecture-plan.md` against the real Phase 2 database, tested
against synthetic fixtures (`pytest tests/api`). Run it locally with:

```bash
pip install -r api/requirements.txt
DATABASE_URL=sqlite:///data/processed/mastr_analytics.db GEO_ASSETS_DIR=data/processed \
  uvicorn api.main:app --reload
```

Then open `http://localhost:8000/docs`. Phase 4 complete: `frontend/` is a React/Vite
dashboard over this API -- see `frontend/README.md` to run it.

If you already have a `mastr_analytics.db` from before the Phase 4 rollup table existed,
you don't need to re-run `sync`/`build` -- just add the table and populate it in place:

```bash
python -m ingestion.cli rollup
```

(`MASTR_PROCESSED_DIR` controls where this looks for the DB, same as `build`; defaults to
`data/processed`.)

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```
