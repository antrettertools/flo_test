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
all tested against synthetic fixtures (`pytest`). Phase 2 complete: a real
ingestion run has produced `data/processed/mastr_analytics.db` -- see
`ingestion/README.md`. Phase 3 complete: `api/` implements all routers from
`docs/architecture-plan.md` against the real Phase 2 database, tested
against synthetic fixtures (`pytest tests/api`). Run it locally with:

```bash
pip install -r api/requirements.txt
DATABASE_URL=sqlite:///data/processed/mastr_analytics.db GEO_ASSETS_DIR=data/processed \
  uvicorn api.main:app --reload
```

Then open `http://localhost:8000/docs`. Phase 4 (`frontend/`) is not yet built.

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```
