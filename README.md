# BNetzA Renewable Capacity Pipeline

Analyzes German renewable generation and storage capacity additions from
Bundesnetzagentur's Marktstammdatenregister (MaStR), with regional
boundaries from BKG's VG250 product.

See `/root/.claude/plans/ethereal-munching-stallman.md` (or the conversation
history) for the full architecture writeup. Short version:

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
all tested against synthetic fixtures (`pytest`). Phase 2 (a real ingestion
run producing the actual database) requires running `ingestion/` locally --
see `ingestion/README.md`.

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```
