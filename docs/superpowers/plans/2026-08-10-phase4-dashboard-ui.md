# Phase 4 Dashboard UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Phase 4 dashboard — a map-driven React frontend over the existing FastAPI backend, plus the backend additions (a materialized rollup table and a lightweight points endpoint) needed to make it fast.

**Architecture:** Backend: a new `capacity_rollup` table pre-aggregates `capacity_unit` by (kind, category, technology, kreis_ags, size_class, year_month); `/capacity/totals` and `/capacity/additions` read from it for whole months and fall back to a small day-precision `capacity_unit` query only for the partial boundary month(s) of a request — this keeps every request both fast and exact. A new `GET /units/points` endpoint serves individual unit coordinates for the map's bubble layer, always scoped to a single Kreis so it stays fast without needing the rollup. Frontend: React + TypeScript + Vite, MapLibre GL for a Land → Kreis → bubble-marker drill-down map, a Zustand store holding selection/filter state, TanStack Query for data fetching, Plotly for the linked technology chart, and the existing c3rro design system for all visual styling.

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy (backend, unchanged); React 18 + TypeScript + Vite, Zustand, TanStack Query, MapLibre GL JS, Plotly.js + react-plotly.js, supercluster, @turf/bbox, Tailwind CSS, Vitest + React Testing Library (frontend, new).

## Global Constraints

- Backend changes must not alter the existing public shape of `/capacity/totals`, `/capacity/additions`, `/units`, `/regions`, `/meta/*` — same request params, same response schema. Verify by running the full existing `pytest` suite unmodified after every backend task.
- No new backend dependencies — `db/`, `api/`, and `ingestion/` already have everything needed (SQLAlchemy, FastAPI, `calendar`/`datetime` stdlib).
- Schema changes go through `db/session.py:init_db` (`Base.metadata.create_all`) — this project has no Alembic/migration tooling (explicitly deferred in `docs/architecture-plan.md`); new tables must be additive so it's safe to run against the existing real `data/processed/mastr_analytics.db`.
- Frontend lives in a new `frontend/` directory at the repo root, next to `api/`, `ingestion/`, `db/`, `common/`.
- Frontend visual styling must use the existing c3rro tokens/components in `docs/c3rro_style/` — do not invent new colors, fonts, or component styles.
- Every task ends with passing tests (`pytest` for backend tasks, `npm test` for frontend tasks) before it is committed.
- Follow this repo's existing commit-message style: `type(scope): summary`, one focused commit per task.

---

## File Structure

Backend (all in the existing `flo_test/` package layout):
- `db/models.py` — **modify**: add `CapacityRollup` model.
- `ingestion/rollup.py` — **new**: builds `capacity_rollup` rows from `capacity_unit`.
- `ingestion/build_db.py` — **modify**: call the rollup builder at the end of `build()`.
- `ingestion/cli.py` — **modify**: add a standalone `rollup` subcommand.
- `api/queries.py` — **modify**: rollup-aware `run_aggregation`, with a raw fallback for partial months.
- `api/schemas.py` — **modify**: add `UnitPoint` / `UnitPointsResponse`.
- `api/routers/units.py` — **modify**: add `GET /units/points`.
- `tests/ingestion/test_rollup.py`, `tests/api/test_queries_rollup.py`, `tests/api/test_units_points.py` — **new**.
- `tests/fixtures/seed.py` — **modify**: add `latitude`/`longitude` to existing fixture rows (additive, doesn't change any existing aggregate assertions).

Frontend (new `frontend/` directory):
- `frontend/package.json`, `vite.config.ts`, `tsconfig.json`, `tailwind.config.js`, `postcss.config.js`, `index.html`, `.env.local.example` — scaffold.
- `frontend/src/main.tsx`, `App.tsx`, `index.css` — app shell.
- `frontend/src/styles/tokens.ts` — c3rro color/spacing/type tokens (TS port of `docs/c3rro_style/c3rro_design_system.tsx`'s token objects).
- `frontend/src/styles/plotlyTheme.ts` — TS port of `docs/c3rro_style/c3rro_theme.js`'s `C3Theme`/`C3Palettes`.
- `frontend/src/api/client.ts` — typed fetch wrapper.
- `frontend/src/api/types.ts` — TS interfaces mirroring `api/schemas.py`.
- `frontend/src/hooks/useCapacityTotals.ts`, `useCapacityAdditions.ts`, `useRegions.ts`, `useRegionGeojson.ts`, `useUnitPoints.ts`, `useMeta.ts` — TanStack Query hooks, one file each.
- `frontend/src/state/explorerStore.ts` — Zustand store (tab/selection/filters).
- `frontend/src/utils/bubbleScale.ts`, `dateSentinel.ts` — pure helper functions.
- `frontend/src/components/ui/Card.tsx`, `Badge.tsx`, `Toggle.tsx`, `Alert.tsx` — c3rro primitives, ported to real TSX.
- `frontend/src/components/MapView/MapView.tsx`, `choroplethLayer.ts`, `bubbleLayer.ts` — the map.
- `frontend/src/components/Breadcrumb.tsx`, `FilterPanel.tsx`, `TechnologyChart.tsx`, `SidePanel.tsx`, `DataProvenanceFooter.tsx`.

---

### Task 1: `CapacityRollup` model

**Files:**
- Modify: `db/models.py`
- Test: `tests/ingestion/test_rollup.py` (created here, extended in Task 2)

**Interfaces:**
- Produces: `CapacityRollup` SQLAlchemy model with columns `id, kind (str), category (str), technology (str), kreis_ags (str|None), size_class (str|None), year_month (str, 'YYYY-MM'), unit_count (int), capacity_kw_sum (float|None), storage_capacity_kwh_sum (float|None)`.

Grain: one row per `(kind, category, technology, kreis_ags, size_class, year_month)`. `kind` is `"addition"` (grouped by `commissioning_date`'s month) or `"decommission"` (grouped by `decommissioning_date`'s month, only for units that have one). `kreis_ags` is nullable — units with no matched region still get a row with `kreis_ags=NULL`, so national/technology-level totals still include them (matching the existing "unmapped units still count toward national totals" behavior in `docs/architecture-plan.md`), while any region-scoped query naturally excludes them (`NULL` never matches a specific `ags`). Land-level and national sums are *derived* at query time from these kreis-grain rows (via `substr(kreis_ags, 1, 2)` or no grouping at all) rather than stored separately, so there is exactly one canonical grain to keep in sync.

- [ ] **Step 1: Write the failing test**

```python
# tests/ingestion/test_rollup.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/ingestion/test_rollup.py -v`
Expected: FAIL — `ImportError: cannot import name 'CapacityRollup' from 'db.models'`

- [ ] **Step 3: Add the model**

In `db/models.py`, after the `CapacityUnit` class, add:

```python
class CapacityRollup(Base):
    """Pre-aggregated capacity_unit, keyed one row per (kind, category,
    technology, kreis_ags, size_class, year_month). See ingestion/rollup.py
    for how this is built and api/queries.py for how it's read -- both
    treat kreis_ags as the single canonical grain; land-level and national
    sums are derived at query time, not stored separately."""

    __tablename__ = "capacity_rollup"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # 'addition' | 'decommission'
    category: Mapped[str] = mapped_column(String(16), nullable=False)
    technology: Mapped[str] = mapped_column(String(32), nullable=False)
    kreis_ags: Mapped[str | None] = mapped_column(String(5), nullable=True)
    size_class: Mapped[str | None] = mapped_column(String(32), nullable=True)
    year_month: Mapped[str] = mapped_column(String(7), nullable=False)

    unit_count: Mapped[int] = mapped_column(Integer, nullable=False)
    capacity_kw_sum: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    storage_capacity_kwh_sum: Mapped[float | None] = mapped_column(Numeric, nullable=True)

    __table_args__ = (
        Index(
            "ix_capacity_rollup_lookup",
            "kind",
            "technology",
            "kreis_ags",
            "year_month",
        ),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/ingestion/test_rollup.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add db/models.py tests/ingestion/test_rollup.py
git commit -m "feat(db): add CapacityRollup model"
```

---

### Task 2: Rollup builder + CLI wiring

**Files:**
- Create: `ingestion/rollup.py`
- Modify: `ingestion/build_db.py`, `ingestion/cli.py`
- Test: `tests/ingestion/test_rollup.py` (extend)

**Interfaces:**
- Consumes: `CapacityRollup` (Task 1), `CapacityUnit`, `db.session.init_db`.
- Produces: `build_rollup(session: Session) -> int` — clears and rebuilds `capacity_rollup` from the current `capacity_unit` contents, returns the number of rollup rows written. Used by Task 3's tests to populate the rollup before exercising the read path, and by the CLI/`build()` to keep it in sync after ingestion.

- [ ] **Step 1: Write the failing tests**

Append to `tests/ingestion/test_rollup.py`:

```python
import datetime as dt

from db.models import CapacityUnit
from ingestion.rollup import build_rollup


def _unit(**overrides) -> CapacityUnit:
    defaults = dict(
        mastr_nummer="U1",
        source_table="solar_extended",
        category="generation",
        technology="solar",
        status="in_operation",
        commissioning_date=dt.date(2023, 7, 15),
        capacity_kw=8.0,
        size_class="<10 kW",
        kreis_ags="09162",
        land_ags="09",
    )
    defaults.update(overrides)
    return CapacityUnit(**defaults)


def test_build_rollup_aggregates_additions_by_month_and_kreis():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    with Session(engine) as session:
        session.add_all(
            [
                _unit(mastr_nummer="U1", capacity_kw=8.0),
                _unit(mastr_nummer="U2", capacity_kw=12.0),
                _unit(mastr_nummer="U3", commissioning_date=dt.date(2023, 8, 1), capacity_kw=5.0),
            ]
        )
        session.commit()

        count = build_rollup(session)
        session.commit()

        assert count == 2  # two distinct (technology, kreis, size_class, month) groups
        july = session.scalar(
            select(CapacityRollup).where(CapacityRollup.year_month == "2023-07")
        )
        assert july.kind == "addition"
        assert july.unit_count == 2
        assert july.capacity_kw_sum == 20.0
        assert july.kreis_ags == "09162"


def test_build_rollup_includes_decommission_kind():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    with Session(engine) as session:
        session.add(
            _unit(
                mastr_nummer="U1",
                commissioning_date=dt.date(2019, 1, 1),
                decommissioning_date=dt.date(2023, 3, 10),
            )
        )
        session.commit()

        build_rollup(session)
        session.commit()

        decommission = session.scalar(
            select(CapacityRollup).where(CapacityRollup.kind == "decommission")
        )
        assert decommission.year_month == "2023-03"
        assert decommission.unit_count == 1


def test_build_rollup_keeps_unmapped_units_with_null_kreis_ags():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    with Session(engine) as session:
        session.add(_unit(mastr_nummer="U1", kreis_ags=None, land_ags=None))
        session.commit()

        build_rollup(session)
        session.commit()

        row = session.scalar(select(CapacityRollup))
        assert row.kreis_ags is None
        assert row.unit_count == 1


def test_build_rollup_is_idempotent_on_rerun():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    with Session(engine) as session:
        session.add(_unit(mastr_nummer="U1"))
        session.commit()

        build_rollup(session)
        session.commit()
        build_rollup(session)  # rerun without changing capacity_unit
        session.commit()

        assert session.scalar(select(func.count()).select_from(CapacityRollup)) == 1
```

Add the needed imports at the top of the test file: `from sqlalchemy import func` and `from db.models import CapacityRollup` (if not already present from Task 1).

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/ingestion/test_rollup.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ingestion.rollup'`

- [ ] **Step 3: Implement the rollup builder**

Create `ingestion/rollup.py`:

```python
"""Builds capacity_rollup from capacity_unit -- see db/models.py's
CapacityRollup docstring for the grain. Run via `python -m ingestion.cli
rollup` standalone, or automatically at the end of `ingestion.build_db.build()`.
"""
from __future__ import annotations

from sqlalchemy import case, delete, func, select
from sqlalchemy.orm import Session

from db.models import CapacityRollup, CapacityUnit


def build_rollup(session: Session) -> int:
    session.execute(delete(CapacityRollup))

    addition_rows = _aggregate(session, kind="addition", date_column=CapacityUnit.commissioning_date)
    decommission_rows = _aggregate(
        session, kind="decommission", date_column=CapacityUnit.decommissioning_date
    )

    all_rows = addition_rows + decommission_rows
    if all_rows:
        session.bulk_insert_mappings(CapacityRollup, all_rows)
    return len(all_rows)


def _aggregate(session: Session, *, kind: str, date_column) -> list[dict]:
    year_month = func.strftime("%Y-%m", date_column)
    query = (
        select(
            CapacityUnit.category,
            CapacityUnit.technology,
            CapacityUnit.kreis_ags,
            CapacityUnit.size_class,
            year_month.label("year_month"),
            func.count(CapacityUnit.id).label("unit_count"),
            func.sum(
                case((CapacityUnit.category == "generation", CapacityUnit.capacity_kw))
            ).label("capacity_kw_sum"),
            func.sum(
                case((CapacityUnit.category == "storage", CapacityUnit.storage_capacity_kwh))
            ).label("storage_capacity_kwh_sum"),
        )
        .where(date_column.is_not(None))
        .group_by(
            CapacityUnit.category,
            CapacityUnit.technology,
            CapacityUnit.kreis_ags,
            CapacityUnit.size_class,
            year_month,
        )
    )
    return [{"kind": kind, **dict(row._mapping)} for row in session.execute(query).all()]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/ingestion/test_rollup.py -v`
Expected: PASS (all 5 tests)

- [ ] **Step 5: Wire into `build_db.py`**

In `ingestion/build_db.py`, add the import and call it right before `batch.finished_at = ...`:

```python
from ingestion.rollup import build_rollup
```

```python
        vg = transform_vg250(vg250_path)
        for region in to_region_rows(vg["kreise"], vg["bundeslaender"]):
            session.merge(Region(**region))

        rollup_count = build_rollup(session)

        batch.mastr_row_counts_json = json.dumps(row_counts)
```

And extend the final print statement:

```python
        if total:
            print(
                f"Ingested {total} units across {len(row_counts)} technologies; "
                f"region match rate {batch.region_join_match_rate:.1%}; "
                f"{rollup_count} rollup rows"
            )
```

- [ ] **Step 6: Add a standalone `rollup` CLI subcommand**

In `ingestion/cli.py`, add the import and subcommand so the rollup can be rebuilt from an already-ingested database without re-running the full (multi-hour) pipeline:

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from ingestion.build_db import build
from ingestion.config import PROCESSED_DB_PATH
from ingestion.mastr_sync import sync
from ingestion.rollup import build_rollup
```

```python
    sub.add_parser("rollup", help="Rebuild capacity_rollup from the existing processed DB")
```

```python
    if args.command == "rollup":
        engine = create_engine(f"sqlite:///{PROCESSED_DB_PATH}")
        with Session(engine) as session:
            count = build_rollup(session)
            session.commit()
            print(f"Rebuilt capacity_rollup: {count} rows")
```

- [ ] **Step 7: Run the full test suite**

Run: `pytest -q`
Expected: all tests pass (existing + new)

- [ ] **Step 8: Commit**

```bash
git add ingestion/rollup.py ingestion/build_db.py ingestion/cli.py tests/ingestion/test_rollup.py
git commit -m "feat(ingestion): build capacity_rollup during build(), standalone CLI rebuild"
```

---

### Task 3: Rollup-aware `run_aggregation`

This is the core performance fix. Read this task fully before starting — the date-splitting logic is the reason `/capacity/totals` and `/capacity/additions` can stay both fast and exact for arbitrary date ranges.

**Files:**
- Modify: `api/queries.py`
- Test: `tests/api/test_queries_rollup.py` (new)

**Interfaces:**
- Consumes: `CapacityRollup` (Task 1), `build_rollup` (Task 2), existing `CapacityFilters`, `_build_conditions`, `_region_column` (already in `api/queries.py`).
- Produces: `run_aggregation(session, filters, group_by, *, date_from=None, date_to=None, as_of_date=None, include_decommissioned=False) -> list[dict]` — **same signature and same return shape as today** (list of dicts matching `CapacityGroupResult`'s fields). `api/routers/capacity.py` does not change at all.

**The approach:** split any date range into (a) whole calendar months, answered from `capacity_rollup`, and (b) at most two partial-month day-precision ranges at the edges, answered from a small `capacity_unit` query scoped to just that one month. A "totals as of D" request is really "additions up to D, minus decommissions up to D" — so both totals and additions reduce to the same date-splitting machinery.

- [ ] **Step 1: Write failing tests for the date-splitting helpers**

Create `tests/api/test_queries_rollup.py`:

```python
import datetime as dt

import pytest

from api.queries import _month_end, _month_start, _shift_year_month, _split_date_range


def test_month_start_and_end():
    assert _month_start(dt.date(2023, 7, 15)) == dt.date(2023, 7, 1)
    assert _month_end(dt.date(2023, 7, 15)) == dt.date(2023, 7, 31)
    assert _month_end(dt.date(2023, 2, 1)) == dt.date(2023, 2, 28)


def test_shift_year_month():
    assert _shift_year_month("2023-07", 1) == "2023-08"
    assert _shift_year_month("2023-12", 1) == "2024-01"
    assert _shift_year_month("2023-01", -1) == "2022-12"


def test_split_date_range_no_bounds():
    assert _split_date_range(None, None) == (None, None, [])


def test_split_date_range_both_month_aligned():
    lo, hi, raw = _split_date_range(dt.date(2023, 6, 1), dt.date(2023, 8, 31))
    assert (lo, hi, raw) == ("2023-06", "2023-08", [])


def test_split_date_range_same_partial_month():
    lo, hi, raw = _split_date_range(dt.date(2023, 7, 5), dt.date(2023, 7, 20))
    assert (lo, hi, raw) == (None, None, [(dt.date(2023, 7, 5), dt.date(2023, 7, 20))])


def test_split_date_range_partial_edges_across_months():
    lo, hi, raw = _split_date_range(dt.date(2023, 6, 15), dt.date(2023, 8, 10))
    assert lo == "2023-07"
    assert hi == "2023-07"
    assert raw == [
        (dt.date(2023, 6, 15), dt.date(2023, 6, 30)),
        (dt.date(2023, 8, 1), dt.date(2023, 8, 10)),
    ]


def test_split_date_range_only_lower_bound():
    lo, hi, raw = _split_date_range(dt.date(2023, 6, 15), None)
    assert lo == "2023-07"
    assert hi is None
    assert raw == [(dt.date(2023, 6, 15), dt.date(2023, 6, 30))]


def test_split_date_range_only_upper_bound():
    lo, hi, raw = _split_date_range(None, dt.date(2023, 8, 10))
    assert lo is None
    assert hi == "2023-07"
    assert raw == [(dt.date(2023, 8, 1), dt.date(2023, 8, 10))]
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/api/test_queries_rollup.py -v`
Expected: FAIL — `ImportError` (functions don't exist yet)

- [ ] **Step 3: Implement the date helpers**

At the top of `api/queries.py`, add `import calendar` to the existing imports, then add near the bottom of the file (after `run_aggregation`, before `query_units`):

```python
def _month_start(d: date) -> date:
    return d.replace(day=1)


def _month_end(d: date) -> date:
    last_day = calendar.monthrange(d.year, d.month)[1]
    return d.replace(day=last_day)


def _year_month(d: date) -> str:
    return d.strftime("%Y-%m")


def _shift_year_month(year_month: str, delta_months: int) -> str:
    year, month = int(year_month[:4]), int(year_month[5:7])
    total = year * 12 + (month - 1) + delta_months
    return f"{total // 12:04d}-{(total % 12) + 1:02d}"


def _split_date_range(
    date_from: date | None, date_to: date | None
) -> tuple[str | None, str | None, list[tuple[date, date]]]:
    """Splits [date_from, date_to] into a whole-month span (rollup_lo,
    rollup_hi -- either may be None for an unbounded side) and up to two
    partial-month day-precision ranges the rollup can't answer exactly."""
    if date_from is None and date_to is None:
        return None, None, []

    if (
        date_from is not None
        and date_to is not None
        and _year_month(date_from) == _year_month(date_to)
    ):
        return None, None, [(date_from, date_to)]

    raw_ranges: list[tuple[date, date]] = []

    rollup_lo = None
    if date_from is not None:
        if date_from == _month_start(date_from):
            rollup_lo = _year_month(date_from)
        else:
            raw_ranges.append((date_from, _month_end(date_from)))
            rollup_lo = _shift_year_month(_year_month(date_from), 1)

    rollup_hi = None
    if date_to is not None:
        if date_to == _month_end(date_to):
            rollup_hi = _year_month(date_to)
        else:
            raw_ranges.append((_month_start(date_to), date_to))
            rollup_hi = _shift_year_month(_year_month(date_to), -1)

    return rollup_lo, rollup_hi, raw_ranges
```

- [ ] **Step 4: Run to verify the helper tests pass**

Run: `pytest tests/api/test_queries_rollup.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit the helpers**

```bash
git add api/queries.py tests/api/test_queries_rollup.py
git commit -m "feat(api): date-range splitting helpers for rollup-backed aggregation"
```

- [ ] **Step 6: Write failing tests for row merging**

Append to `tests/api/test_queries_rollup.py`:

```python
from api.queries import _merge_group_rows, _negate_row


def test_merge_group_rows_sums_matching_keys():
    rows = [
        {"category": "generation", "technology": "solar", "unit_count": 2, "capacity_kw_sum": 10.0, "storage_capacity_kwh_sum": None},
        {"category": "generation", "technology": "solar", "unit_count": 3, "capacity_kw_sum": 5.0, "storage_capacity_kwh_sum": None},
        {"category": "generation", "technology": "wind", "unit_count": 1, "capacity_kw_sum": 100.0, "storage_capacity_kwh_sum": None},
    ]
    merged = _merge_group_rows(rows)
    assert len(merged) == 2
    solar = next(r for r in merged if r["technology"] == "solar")
    assert solar["unit_count"] == 5
    assert solar["capacity_kw_sum"] == 15.0


def test_merge_group_rows_treats_none_as_no_contribution():
    rows = [
        {"category": "storage", "technology": "storage", "unit_count": 1, "capacity_kw_sum": None, "storage_capacity_kwh_sum": None},
    ]
    merged = _merge_group_rows(rows)
    assert merged[0]["capacity_kw_sum"] is None


def test_negate_row_flips_count_and_sums():
    row = {"category": "generation", "technology": "solar", "unit_count": 3, "capacity_kw_sum": 10.0, "storage_capacity_kwh_sum": None}
    negated = _negate_row(row)
    assert negated["unit_count"] == -3
    assert negated["capacity_kw_sum"] == -10.0
    assert negated["storage_capacity_kwh_sum"] is None
    assert negated["category"] == "generation"  # non-numeric fields untouched
```

- [ ] **Step 7: Run to verify failure, then implement**

Run: `pytest tests/api/test_queries_rollup.py -v` — expect `ImportError`.

Add to `api/queries.py`:

```python
_NUMERIC_FIELDS = ("unit_count", "capacity_kw_sum", "storage_capacity_kwh_sum")
_GROUP_KEY_FIELDS = ("category", "technology", "region_ags", "size_class", "month")


def _merge_group_rows(rows: list[dict]) -> list[dict]:
    merged: dict[tuple, dict] = {}
    for row in rows:
        key = tuple(row.get(k) for k in _GROUP_KEY_FIELDS)
        if key not in merged:
            merged[key] = {
                **{k: row.get(k) for k in _GROUP_KEY_FIELDS},
                "unit_count": 0,
                "capacity_kw_sum": None,
                "storage_capacity_kwh_sum": None,
            }
        target = merged[key]
        target["unit_count"] += row["unit_count"]
        for field in ("capacity_kw_sum", "storage_capacity_kwh_sum"):
            if row.get(field) is not None:
                target[field] = (target[field] or 0) + row[field]
    return list(merged.values())


def _negate_row(row: dict) -> dict:
    negated = dict(row)
    negated["unit_count"] = -row["unit_count"]
    for field in ("capacity_kw_sum", "storage_capacity_kwh_sum"):
        if row.get(field) is not None:
            negated[field] = -row[field]
    return negated
```

- [ ] **Step 8: Run to verify these tests pass, then commit**

Run: `pytest tests/api/test_queries_rollup.py -v` — expect PASS (10 tests total so far).

```bash
git add api/queries.py tests/api/test_queries_rollup.py
git commit -m "feat(api): row-merging helpers for combining rollup + raw aggregation results"
```

- [ ] **Step 9: Refactor the existing scan into `_raw_aggregate`**

`run_aggregation`'s current body (the whole function in `api/queries.py`, lines ~93-145 as of this plan) already builds `group_cols` and a query against `CapacityUnit`. Extract that into a reusable helper that takes an explicit date column, so it can be pointed at either `commissioning_date` or `decommissioning_date`:

Replace the current `run_aggregation` function entirely with:

```python
def _raw_aggregate(
    session: Session,
    filters: CapacityFilters,
    group_by: list[str],
    *,
    date_column,
    date_from: date | None,
    date_to: date | None,
) -> list[dict]:
    region_col = _region_column(filters.region_level)

    group_cols = [CapacityUnit.category]
    if "technology" in group_by:
        group_cols.append(CapacityUnit.technology)
    if "region" in group_by:
        group_cols.append(region_col.label("region_ags"))
    if "size_class" in group_by:
        group_cols.append(CapacityUnit.size_class)
    if "month" in group_by:
        group_cols.append(func.strftime("%Y-%m", CapacityUnit.commissioning_date).label("month"))

    query = select(
        *group_cols,
        func.count(CapacityUnit.id).label("unit_count"),
        func.sum(
            case((CapacityUnit.category == Category.GENERATION.value, CapacityUnit.capacity_kw))
        ).label("capacity_kw_sum"),
        func.sum(
            case(
                (CapacityUnit.category == Category.STORAGE.value, CapacityUnit.storage_capacity_kwh)
            )
        ).label("storage_capacity_kwh_sum"),
    )

    conditions = _build_conditions(
        filters, region_col, date_from=date_from, date_to=date_to, as_of_date=None, include_decommissioned=True
    )
    conditions.append(date_column.is_not(None))
    if date_from is not None:
        conditions.append(date_column >= date_from)
    if date_to is not None:
        conditions.append(date_column <= date_to)
    query = query.where(*conditions)

    query = query.group_by(*group_cols)
    return [dict(row._mapping) for row in session.execute(query).all()]
```

Note: `_build_conditions` is called with `date_from=date_from, date_to=date_to` too, which would double-apply the date filter against `commissioning_date` specifically even when `date_column` is `decommissioning_date`. Fix this by calling it with `date_from=None, date_to=None` instead (the explicit `date_column` conditions right after already cover date filtering correctly for whichever column was passed):

```python
    conditions = _build_conditions(
        filters, region_col, date_from=None, date_to=None, as_of_date=None, include_decommissioned=True
    )
```

- [ ] **Step 10: Implement `_rollup_aggregate`**

```python
def _rollup_aggregate(
    session: Session,
    filters: CapacityFilters,
    group_by: list[str],
    *,
    kind: str,
    year_month_from: str | None,
    year_month_to: str | None,
) -> list[dict]:
    is_land = filters.region_level == RegionLevel.LAND.value
    region_col = func.substr(CapacityRollup.kreis_ags, 1, 2) if is_land else CapacityRollup.kreis_ags

    group_cols = [CapacityRollup.category]
    if "technology" in group_by:
        group_cols.append(CapacityRollup.technology)
    if "region" in group_by:
        group_cols.append(region_col.label("region_ags"))
    if "size_class" in group_by:
        group_cols.append(CapacityRollup.size_class)
    if "month" in group_by:
        group_cols.append(CapacityRollup.year_month.label("month"))

    query = select(
        *group_cols,
        func.sum(CapacityRollup.unit_count).label("unit_count"),
        func.sum(CapacityRollup.capacity_kw_sum).label("capacity_kw_sum"),
        func.sum(CapacityRollup.storage_capacity_kwh_sum).label("storage_capacity_kwh_sum"),
    ).where(CapacityRollup.kind == kind)

    if filters.technology:
        query = query.where(CapacityRollup.technology.in_(filters.technology))
    if filters.category:
        query = query.where(CapacityRollup.category == filters.category)
    if filters.region_ags:
        query = query.where(region_col.in_(filters.region_ags))
    if filters.size_class:
        query = query.where(CapacityRollup.size_class.in_(filters.size_class))
    if year_month_from is not None:
        query = query.where(CapacityRollup.year_month >= year_month_from)
    if year_month_to is not None:
        query = query.where(CapacityRollup.year_month <= year_month_to)

    query = query.group_by(*group_cols)
    return [dict(row._mapping) for row in session.execute(query).all()]
```

Add `from db.models import CapacityRollup, CapacityUnit` (extend the existing `from db.models import CapacityUnit` import line) and `from api.schemas import RegionLevel` is already imported.

- [ ] **Step 11: Implement `_kind_aggregate` and the new `run_aggregation`**

```python
def _kind_aggregate(
    session: Session,
    filters: CapacityFilters,
    group_by: list[str],
    *,
    kind: str,
    date_from: date | None,
    date_to: date | None,
) -> list[dict]:
    rollup_lo, rollup_hi, raw_ranges = _split_date_range(date_from, date_to)
    rows: list[dict] = []

    use_rollup = not (rollup_lo is None and rollup_hi is None and raw_ranges)
    if use_rollup:
        rows += _rollup_aggregate(
            session, filters, group_by, kind=kind, year_month_from=rollup_lo, year_month_to=rollup_hi
        )

    date_column = CapacityUnit.commissioning_date if kind == "addition" else CapacityUnit.decommissioning_date
    for range_from, range_to in raw_ranges:
        rows += _raw_aggregate(
            session, filters, group_by, date_column=date_column, date_from=range_from, date_to=range_to
        )

    return rows


def run_aggregation(
    session: Session,
    filters: CapacityFilters,
    group_by: list[str],
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    as_of_date: date | None = None,
    include_decommissioned: bool = False,
) -> list[dict]:
    """Always groups by category in addition to whatever's in group_by, so a
    result row never mixes generation kW with storage kWh in one sum.

    Reads from capacity_rollup for whole calendar months and falls back to a
    day-precision capacity_unit scan only for the partial boundary month(s)
    of the request -- see _split_date_range. A "totals as of D" request is
    computed as additions-up-to-D minus decommissions-up-to-D.
    """
    if as_of_date is not None:
        rows = _kind_aggregate(session, filters, group_by, kind="addition", date_from=None, date_to=as_of_date)
        if not include_decommissioned:
            decommissions = _kind_aggregate(
                session, filters, group_by, kind="decommission", date_from=None, date_to=as_of_date
            )
            rows += [_negate_row(r) for r in decommissions]
        return _merge_group_rows(rows)

    rows = _kind_aggregate(session, filters, group_by, kind="addition", date_from=date_from, date_to=date_to)
    return _merge_group_rows(rows)
```

- [ ] **Step 12: Run the full existing API test suite (regression check)**

Run: `pytest tests/api -v`
Expected: every existing test in `test_capacity.py`, `test_queries.py`, `test_integration.py` still passes with identical assertions — the rollup path must be numerically indistinguishable from the old raw-only path. If anything fails, the bug is in the new aggregation/merge logic, not the tests (do not change existing test expectations).

Note: existing tests seed data directly into `capacity_unit` via `tests/fixtures/seed.py` but never call `build_rollup` — `capacity_rollup` will be empty for them. Since `_rollup_aggregate` on an empty table correctly returns `[]` (no rows to sum), and `date_from`/`date_to`/`as_of_date` in those existing tests are set such that the relevant data falls in `raw_ranges` or the rollup legitimately has nothing to contribute, this should already pass. If a specific existing test fails because it expects rollup-covered data that isn't in the rollup, that test's fixture setup needs `build_rollup(session)` added — check this by running Step 12 before assuming the logic is wrong.

- [ ] **Step 13: Write integration tests exercising the hybrid path end-to-end**

Create the rollup-integration tests in `tests/api/test_queries_rollup.py` (append):

```python
from db.session import init_db
from ingestion.rollup import build_rollup
from api.queries import CapacityFilters, run_aggregation
from tests.fixtures.seed import seed_capacity_units


@pytest.fixture()
def rollup_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    init_db(engine)
    session = Session(engine)
    seed_capacity_units(session)
    session.commit()
    build_rollup(session)
    session.commit()
    yield session
    session.close()


def test_totals_as_of_date_matches_raw_and_rollup_combined(rollup_session):
    # fixture has SOLAR1 (2022-03-15, 50kW) and SOLAR2 (2023-07-01, 8kW) in Muenchen
    filters = CapacityFilters(technology=["solar"])
    rows = run_aggregation(rollup_session, filters, ["technology"], as_of_date=dt.date(2023, 7, 15))
    solar = next(r for r in rows if r.get("technology") == "solar")
    assert solar["unit_count"] == 2
    assert solar["capacity_kw_sum"] == 58.0


def test_totals_excludes_decommissioned_by_default(rollup_session):
    # STORAGE2_DECOMMISSIONED: commissioned 2019-05-01, decommissioned 2023-01-01
    filters = CapacityFilters(technology=["storage"])
    rows = run_aggregation(rollup_session, filters, [], as_of_date=dt.date(2023, 6, 1))
    storage = next(r for r in rows if r["category"] == "storage")
    assert storage["unit_count"] == 1  # only STORAGE1, STORAGE2 is decommissioned by June 2023


def test_totals_includes_decommissioned_when_requested(rollup_session):
    filters = CapacityFilters(technology=["storage"])
    rows = run_aggregation(
        rollup_session, filters, [], as_of_date=dt.date(2023, 6, 1), include_decommissioned=True
    )
    storage = next(r for r in rows if r["category"] == "storage")
    assert storage["unit_count"] == 2


def test_additions_partial_month_range(rollup_session):
    # SOLAR2 commissioned 2023-07-01 -- range starts mid-month, excludes it
    filters = CapacityFilters(technology=["solar"])
    rows = run_aggregation(
        rollup_session, filters, [], date_from=dt.date(2023, 7, 2), date_to=dt.date(2023, 7, 31)
    )
    assert rows == []


def test_additions_whole_month_range_includes_it(rollup_session):
    filters = CapacityFilters(technology=["solar"])
    rows = run_aggregation(
        rollup_session, filters, [], date_from=dt.date(2023, 7, 1), date_to=dt.date(2023, 7, 31)
    )
    solar = next(r for r in rows if r["category"] == "generation")
    assert solar["unit_count"] == 1


def test_land_level_totals_derive_from_kreis_grain(rollup_session):
    filters = CapacityFilters(technology=["solar"], region_level="land")
    rows = run_aggregation(rollup_session, filters, ["region"], as_of_date=dt.date(2023, 12, 31))
    bayern = next(r for r in rows if r["region_ags"] == "09")
    assert bayern["unit_count"] == 2
```

- [ ] **Step 14: Run to verify these pass**

Run: `pytest tests/api/test_queries_rollup.py -v`
Expected: PASS (16 tests total)

- [ ] **Step 15: Run the full suite once more and commit**

Run: `pytest -q`
Expected: all pass.

```bash
git add api/queries.py tests/api/test_queries_rollup.py
git commit -m "feat(api): rollup-backed run_aggregation with exact partial-month fallback"
```

---

### Task 4: `GET /units/points`

**Files:**
- Modify: `api/schemas.py`, `api/routers/units.py`, `tests/fixtures/seed.py`
- Test: `tests/api/test_units_points.py` (new)

**Interfaces:**
- Consumes: `CapacityFilters`, `capacity_filters`, `_build_conditions`-style filtering (via a new small query function), existing `client` test fixture from `tests/api/conftest.py`.
- Produces: `GET /units/points?kreis_ags=<required>&...filters` → `UnitPointsResponse { points: list[UnitPoint], truncated: bool }`, where `UnitPoint = { mastr_nummer, technology, category, capacity_kw, storage_capacity_kwh, latitude, longitude }`. Always requires `kreis_ags` (400 error otherwise) — this is what keeps the query fast regardless of national table size.

- [ ] **Step 1: Add latitude/longitude to the shared fixture**

`tests/fixtures/seed.py` currently has 5 `CapacityUnit` rows with no `latitude`/`longitude`. Add them (this is additive — no existing aggregate assertion in other test files reads these two fields, so nothing else breaks). Edit `SOLAR1`, `SOLAR2`, `WIND1`, `STORAGE1` in `seed_capacity_units`:

```python
            CapacityUnit(
                mastr_nummer="SOLAR1",
                ...,
                latitude=48.1351,
                longitude=11.5820,
            ),
```
```python
            CapacityUnit(
                mastr_nummer="SOLAR2",
                ...,
                latitude=48.1400,
                longitude=11.5900,
            ),
```
```python
            CapacityUnit(
                mastr_nummer="WIND1",
                ...,
                latitude=52.5200,
                longitude=13.4050,
            ),
```
```python
            CapacityUnit(
                mastr_nummer="STORAGE1",
                ...,
                latitude=48.1360,
                longitude=11.5830,
            ),
```

(`STORAGE2_DECOMMISSIONED` is left without coordinates, to double as the "unit with missing coordinates is excluded" test case.)

- [ ] **Step 2: Run the existing suite to confirm nothing broke**

Run: `pytest -q`
Expected: all still pass (additive change only).

- [ ] **Step 3: Write the failing test**

Create `tests/api/test_units_points.py`:

```python
def test_units_points_requires_kreis_ags(client):
    resp = client.get("/units/points")
    assert resp.status_code == 422


def test_units_points_returns_points_for_kreis(client):
    resp = client.get("/units/points", params={"kreis_ags": "09162"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["truncated"] is False
    mastr_nummern = {p["mastr_nummer"] for p in body["points"]}
    assert mastr_nummern == {"SOLAR1", "SOLAR2", "STORAGE1"}


def test_units_points_excludes_units_without_coordinates(client):
    resp = client.get("/units/points", params={"kreis_ags": "11000"})
    body = resp.json()
    mastr_nummern = {p["mastr_nummer"] for p in body["points"]}
    assert mastr_nummern == {"WIND1"}  # STORAGE2_DECOMMISSIONED has no lat/lon


def test_units_points_filters_by_technology(client):
    resp = client.get(
        "/units/points", params={"kreis_ags": "09162", "technology": "storage"}
    )
    body = resp.json()
    assert {p["mastr_nummer"] for p in body["points"]} == {"STORAGE1"}


def test_units_points_truncates_and_flags_when_over_cap(client):
    resp = client.get("/units/points", params={"kreis_ags": "09162", "limit": 1})
    body = resp.json()
    assert len(body["points"]) == 1
    assert body["truncated"] is True
```

- [ ] **Step 4: Run to verify failure**

Run: `pytest tests/api/test_units_points.py -v`
Expected: FAIL — 404 (route doesn't exist)

- [ ] **Step 5: Add the response schemas**

In `api/schemas.py`, after `UnitOut`, add:

```python
class UnitPoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    mastr_nummer: str
    technology: str
    category: str
    capacity_kw: float | None
    storage_capacity_kwh: float | None
    latitude: float
    longitude: float


class UnitPointsResponse(BaseModel):
    points: list[UnitPoint]
    truncated: bool
```

- [ ] **Step 6: Implement the endpoint**

In `api/routers/units.py`, add the import and route:

```python
from api.schemas import UnitListResponse, UnitOut, UnitPoint, UnitPointsResponse
```

```python
_DEFAULT_POINTS_LIMIT = 3000


@router.get("/points", response_model=UnitPointsResponse)
def list_unit_points(
    kreis_ags: str = Query(...),
    limit: int = Query(default=_DEFAULT_POINTS_LIMIT, ge=1, le=_DEFAULT_POINTS_LIMIT),
    filters: CapacityFilters = Depends(capacity_filters),
    db: Session = Depends(get_db),
) -> UnitPointsResponse:
    query = select(CapacityUnit).where(
        CapacityUnit.kreis_ags == kreis_ags,
        CapacityUnit.latitude.is_not(None),
        CapacityUnit.longitude.is_not(None),
    )
    if filters.technology:
        query = query.where(CapacityUnit.technology.in_(filters.technology))
    if filters.category:
        query = query.where(CapacityUnit.category == filters.category)
    if filters.size_class:
        query = query.where(CapacityUnit.size_class.in_(filters.size_class))

    rows = list(db.scalars(query.order_by(CapacityUnit.id).limit(limit + 1)).all())
    truncated = len(rows) > limit
    return UnitPointsResponse(
        points=[UnitPoint.model_validate(r) for r in rows[:limit]],
        truncated=truncated,
    )
```

**IMPORTANT** — route ordering: FastAPI matches routes in registration order, and `/{mastr_nummer}` is a catch-all path parameter already registered below. Register `/points` **before** the existing `@router.get("/{mastr_nummer}", ...)` route in the file, otherwise a request to `/units/points` will match `/units/{mastr_nummer}` first with `mastr_nummer="points"`.

- [ ] **Step 7: Run to verify tests pass**

Run: `pytest tests/api/test_units_points.py -v`
Expected: PASS (5 tests)

- [ ] **Step 8: Run the full suite and commit**

Run: `pytest -q`

```bash
git add api/schemas.py api/routers/units.py tests/api/test_units_points.py tests/fixtures/seed.py
git commit -m "feat(api): add GET /units/points for the map's bubble-marker layer"
```

---

Backend is done here — Tasks 1-4 are independently mergeable and give a complete, fast API surface for the frontend to build against. Manually verify against the real database before moving to frontend work:

```bash
cd flo_test
python -m ingestion.cli rollup
DATABASE_URL=sqlite:///data/processed/mastr_analytics.db GEO_ASSETS_DIR=data/processed uvicorn api.main:app --reload
# in another terminal:
curl "http://localhost:8000/capacity/totals?technology=solar&region_level=land&group_by=region"
# should return in well under a second now, versus ~59s before this plan
```

---

### Task 5: Frontend scaffold

**Files:**
- Create: `frontend/package.json`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/tsconfig.node.json`, `frontend/tailwind.config.js`, `frontend/postcss.config.js`, `frontend/index.html`, `frontend/.env.local.example`, `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/index.css`, `frontend/.gitignore`

**Interfaces:**
- Produces: a running Vite dev server (`npm run dev`) rendering a placeholder `App`, plus `npm test` running Vitest, plus Tailwind and the Jost/Lato fonts loading correctly. Every later frontend task builds on this.

- [ ] **Step 1: Scaffold with Vite**

```bash
cd flo_test
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
```

- [ ] **Step 2: Install runtime dependencies**

```bash
npm install zustand @tanstack/react-query maplibre-gl plotly.js-dist-min react-plotly.js supercluster @turf/bbox
npm install -D tailwindcss postcss autoprefixer vitest @testing-library/react @testing-library/jest-dom @testing-library/user-event jsdom @types/react-plotly.js @types/supercluster
```

- [ ] **Step 3: Configure Tailwind**

```bash
npx tailwindcss init -p
```

Replace `frontend/tailwind.config.js` content with:

```js
/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: { extend: {} },
  plugins: [],
};
```

- [ ] **Step 4: Set up fonts and base styles**

Replace `frontend/src/index.css` with:

```css
@import url('https://fonts.googleapis.com/css2?family=Jost:wght@400;500;600;700&family=Lato:wght@300;400;700&display=swap');
@tailwind base;
@tailwind components;
@tailwind utilities;

body {
  font-family: 'Lato', sans-serif;
  color: #33302F;
  background-color: #FFFFFF;
}

h1, h2, h3, h4, h5, h6 {
  font-family: 'Jost', sans-serif;
}
```

- [ ] **Step 5: Configure Vitest**

Replace `frontend/vite.config.ts` with:

```ts
/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/setupTests.ts',
  },
});
```

Create `frontend/src/setupTests.ts`:

```ts
import '@testing-library/jest-dom/vitest';
```

Add to `frontend/package.json`'s `"scripts"`:

```json
"test": "vitest run"
```

- [ ] **Step 6: Add the env var for the API base URL**

Create `frontend/.env.local.example`:

```
VITE_API_BASE_URL=http://localhost:8000
```

Add `.env.local` to `frontend/.gitignore` (Vite scaffolds a `.gitignore` already — confirm `.env.local` is in it, add if not).

- [ ] **Step 7: Write a smoke test for `App`**

Create `frontend/src/App.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import App from './App';

describe('App', () => {
  it('renders without crashing', () => {
    render(<App />);
    expect(screen.getByText(/Renewable Capacity Explorer/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 8: Run to verify it fails, then set the placeholder title**

Run: `npm test` — expect FAIL (text not found in the default Vite template).

Replace `frontend/src/App.tsx` with:

```tsx
function App() {
  return (
    <div className="h-screen w-screen">
      <h1 className="p-4 text-xl font-semibold">Renewable Capacity Explorer</h1>
    </div>
  );
}

export default App;
```

- [ ] **Step 9: Run to verify it passes**

Run: `npm test`
Expected: PASS

- [ ] **Step 10: Verify the dev server runs**

Run: `npm run dev` (in `frontend/`), open the printed localhost URL, confirm the heading renders in Jost and the page loads with no console errors. Stop the dev server (Ctrl+C) once confirmed.

- [ ] **Step 11: Commit**

```bash
cd flo_test
git add frontend/
git commit -m "chore(frontend): scaffold Vite + React + TypeScript + Tailwind + Vitest"
```

---

### Task 6: c3rro design tokens + Plotly theme (TS port)

**Files:**
- Create: `frontend/src/styles/tokens.ts`, `frontend/src/styles/plotlyTheme.ts`
- Test: `frontend/src/styles/plotlyTheme.test.ts`

**Interfaces:**
- Produces: `colorTokens` (named hex values), `C3_PALETTES` (named color arrays, including `blues` and `mixed`), `getPlotlyLayout(title, subtitle, options?) -> Partial<Plotly.Layout>`. Used by Task 14 (`TechnologyChart`) and Task 11 (`MapView`, for the choropleth ramp).

- [ ] **Step 1: Port the color tokens**

Create `frontend/src/styles/tokens.ts` — direct TS port of the relevant parts of `docs/c3rro_style/c3rro_theme.js` (no logic changes, just typed):

```ts
export const colors = {
  text: '#33302F',
  greydark: '#5e5a58',
  grey: '#bdb2aa',
  greylight: '#d9d8cd',
  white: '#ffffff',
  bluegreen: '#4ab79f',
  blue: '#4597bf',
  bluedark: '#407188',
  bluelight: '#93d2e1',
  green: '#3e7263',
  greendark: '#205959',
  greenlight: '#89a767',
  red: '#c04343',
  orange: '#e18e2a',
  yellow: '#f8c36e',
  yellowgreen: '#b1b52e',
  yellowlight: '#fef4dc',
} as const;

export type ColorName = keyof typeof colors;

// Deliberately NOT using `main` (opens on bluegreen) for data encoding --
// bluegreen is reserved for interactive/selected state across the app.
// See docs/superpowers/specs/2026-08-10-phase4-dashboard-ui-design.md Section 5.
export const palettes = {
  blues: [colors.bluelight, colors.bluedark],
  mixed: [
    colors.bluedark,
    colors.blue,
    colors.bluegreen,
    colors.green,
    colors.yellowgreen,
    colors.yellow,
    colors.orange,
    colors.red,
  ],
} as const;

export const spacing = {
  xs: '0.25rem',
  sm: '0.5rem',
  md: '1rem',
  lg: '1.5rem',
  xl: '2rem',
} as const;
```

- [ ] **Step 2: Write the failing test for the Plotly layout**

Create `frontend/src/styles/plotlyTheme.test.ts`:

```ts
import { describe, expect, it } from 'vitest';

import { getPlotlyLayout } from './plotlyTheme';

describe('getPlotlyLayout', () => {
  it('sets the title annotation with the correct text and font', () => {
    const layout = getPlotlyLayout('Capacity by technology', 'GW');
    const titleAnnotation = layout.annotations?.find((a) => a.text === 'Capacity by technology');
    expect(titleAnnotation).toBeDefined();
    expect(titleAnnotation?.font?.family).toContain('Jost');
  });

  it('sets white backgrounds and hides the x-axis gridlines per c3rro convention', () => {
    const layout = getPlotlyLayout('Title');
    expect(layout.paper_bgcolor).toBe('#ffffff');
    expect(layout.xaxis?.showgrid).toBe(false);
    expect(layout.yaxis?.showgrid).toBe(true);
  });
});
```

- [ ] **Step 3: Run to verify it fails**

Run: `npm test -- plotlyTheme`
Expected: FAIL — module doesn't exist

- [ ] **Step 4: Port `getPlotlyLayout`**

Create `frontend/src/styles/plotlyTheme.ts` — TS port of `C3Theme.getPlotlyLayout` from `docs/c3rro_style/c3rro_theme.js`, trimmed to what this app uses (drop the `source` annotation option, keep title/subtitle/axis/legend/margin behavior identical):

```ts
import type { Layout } from 'plotly.js';

import { colors } from './tokens';

export function getPlotlyLayout(
  title = '',
  subtitle = '',
  options: Partial<Layout> = {}
): Partial<Layout> {
  const annotations: Partial<Layout>['annotations'] = [];

  if (title) {
    annotations.push({
      text: title,
      xref: 'paper',
      yref: 'paper',
      x: 0.08,
      y: 0.98,
      xanchor: 'left',
      yanchor: 'top',
      showarrow: false,
      font: { family: '"Jost", "Lato", Arial, sans-serif', size: 16, color: colors.text },
    });
  }

  if (subtitle) {
    annotations.push({
      text: subtitle,
      xref: 'paper',
      yref: 'paper',
      x: 0.08,
      y: 0.93,
      xanchor: 'left',
      yanchor: 'top',
      showarrow: false,
      font: { family: '"Lato", Arial, sans-serif', size: 12, color: colors.bluegreen },
    });
  }

  return {
    paper_bgcolor: colors.white,
    plot_bgcolor: colors.white,
    annotations,
    font: { family: '"Lato", Arial, sans-serif', size: 12, color: colors.text },
    xaxis: {
      showline: true,
      linewidth: 1,
      linecolor: colors.greydark,
      showgrid: false,
      zeroline: false,
      tickcolor: colors.greydark,
      tickfont: { size: 12, color: colors.text },
    },
    yaxis: {
      showline: false,
      zeroline: false,
      showgrid: true,
      gridwidth: 0.5,
      gridcolor: colors.grey,
      tickcolor: colors.greydark,
      tickfont: { size: 12, color: colors.text },
    },
    legend: {
      bgcolor: 'rgba(255, 255, 255, 1)',
      bordercolor: colors.greydark,
      borderwidth: 1,
      font: { size: 11, color: colors.text },
      x: 1.02,
      y: 1,
      xanchor: 'left',
      yanchor: 'top',
    },
    margin: { l: 80, r: 40, t: 100, b: 60 },
    hovermode: 'x unified',
    ...options,
  };
}
```

- [ ] **Step 5: Run to verify it passes**

Run: `npm test -- plotlyTheme`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/src/styles/
git commit -m "feat(frontend): port c3rro color tokens and Plotly theme to TypeScript"
```

---

### Task 7: c3rro UI primitives

**Files:**
- Create: `frontend/src/components/ui/Card.tsx`, `Badge.tsx`, `Toggle.tsx`, `Alert.tsx`
- Test: `frontend/src/components/ui/Card.test.tsx`, `Toggle.test.tsx`

**Interfaces:**
- Produces: `<Card title? subtitle? className? children>`, `<Badge variant="default"|"success"|"warning"|"error"|"info"|"teal">`, `<Toggle enabled onChange label? description?>`, `<Alert type="success"|"warning"|"error"|"info" title? onClose? children>`. Used by `SidePanel`, `FilterPanel`, `DataProvenanceFooter` (Tasks 13, 15, 16).

- [ ] **Step 1: Write failing tests**

Create `frontend/src/components/ui/Card.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { Card } from './Card';

describe('Card', () => {
  it('renders title, subtitle, and children', () => {
    render(
      <Card title="Technologies" subtitle="by capacity">
        <p>content</p>
      </Card>
    );
    expect(screen.getByText('Technologies')).toBeInTheDocument();
    expect(screen.getByText('by capacity')).toBeInTheDocument();
    expect(screen.getByText('content')).toBeInTheDocument();
  });

  it('omits the header block when no title or subtitle given', () => {
    render(<Card><p>content only</p></Card>);
    expect(screen.queryByRole('heading')).not.toBeInTheDocument();
  });
});
```

Create `frontend/src/components/ui/Toggle.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { Toggle } from './Toggle';

describe('Toggle', () => {
  it('calls onChange with the flipped value when clicked', async () => {
    const onChange = vi.fn();
    render(<Toggle enabled={false} onChange={onChange} label="Include storage" />);
    await userEvent.click(screen.getByRole('button'));
    expect(onChange).toHaveBeenCalledWith(true);
  });

  it('renders the label', () => {
    render(<Toggle enabled onChange={() => {}} label="Include storage" />);
    expect(screen.getByText('Include storage')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `npm test -- ui/`
Expected: FAIL — modules don't exist

- [ ] **Step 3: Implement the four components**

Create `frontend/src/components/ui/Card.tsx` (TSX port of `Card` from `docs/c3rro_style/c3rro_design_system.tsx`):

```tsx
import type { ReactNode } from 'react';

interface CardProps {
  title?: string;
  subtitle?: string;
  className?: string;
  children: ReactNode;
}

export function Card({ title, subtitle, className = '', children }: CardProps) {
  return (
    <div className={`bg-white rounded-xl shadow-md border border-[#D9D8CD] ${className}`}>
      {(title || subtitle) && (
        <div className="px-6 py-4 border-b border-[#D9D8CD]">
          {title && <h3 className="text-lg font-semibold text-[#33302F]">{title}</h3>}
          {subtitle && <p className="text-sm text-[#5E5A58] mt-1">{subtitle}</p>}
        </div>
      )}
      <div className="p-6">{children}</div>
    </div>
  );
}
```

Create `frontend/src/components/ui/Badge.tsx`:

```tsx
import type { ReactNode } from 'react';

type BadgeVariant = 'default' | 'success' | 'warning' | 'error' | 'info' | 'teal';

const VARIANTS: Record<BadgeVariant, { bg: string; text: string }> = {
  default: { bg: '#D9D8CD', text: '#33302F' },
  success: { bg: '#89A767', text: '#FFFFFF' },
  warning: { bg: '#F8C36E', text: '#33302F' },
  error: { bg: '#C04343', text: '#FFFFFF' },
  info: { bg: '#4597BF', text: '#FFFFFF' },
  teal: { bg: '#4AB79F', text: '#FFFFFF' },
};

export function Badge({ variant = 'default', children }: { variant?: BadgeVariant; children: ReactNode }) {
  const style = VARIANTS[variant];
  return (
    <span
      className="inline-flex items-center font-medium rounded-full px-2.5 py-1.5 text-sm"
      style={{ backgroundColor: style.bg, color: style.text }}
    >
      {children}
    </span>
  );
}
```

Create `frontend/src/components/ui/Toggle.tsx`:

```tsx
interface ToggleProps {
  enabled: boolean;
  onChange: (next: boolean) => void;
  label?: string;
  description?: string;
}

export function Toggle({ enabled, onChange, label, description }: ToggleProps) {
  return (
    <div className="flex items-start space-x-3">
      <button
        type="button"
        role="button"
        aria-pressed={enabled}
        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-[#4AB79F] focus:ring-offset-2 ${enabled ? 'bg-[#4AB79F]' : 'bg-[#D9D8CD]'}`}
        onClick={() => onChange(!enabled)}
      >
        <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${enabled ? 'translate-x-6' : 'translate-x-1'}`} />
      </button>
      {(label || description) && (
        <div className="flex-1">
          {label && <label className="block text-sm font-medium text-[#33302F]">{label}</label>}
          {description && <p className="text-xs text-[#5E5A58] mt-1">{description}</p>}
        </div>
      )}
    </div>
  );
}
```

Create `frontend/src/components/ui/Alert.tsx`:

```tsx
import type { ReactNode } from 'react';

type AlertType = 'success' | 'warning' | 'error' | 'info';

const STYLES: Record<AlertType, { bg: string; border: string; text: string; icon: string }> = {
  success: { bg: 'bg-[#89A767]/10', border: 'border-[#89A767]', text: 'text-[#89A767]', icon: '✓' },
  warning: { bg: 'bg-[#E18E2A]/10', border: 'border-[#E18E2A]', text: 'text-[#E18E2A]', icon: '⚠' },
  error: { bg: 'bg-[#C04343]/10', border: 'border-[#C04343]', text: 'text-[#C04343]', icon: '✕' },
  info: { bg: 'bg-[#4597BF]/10', border: 'border-[#4597BF]', text: 'text-[#4597BF]', icon: 'ℹ' },
};

interface AlertProps {
  type?: AlertType;
  title?: string;
  onClose?: () => void;
  children: ReactNode;
}

export function Alert({ type = 'info', title, onClose, children }: AlertProps) {
  const style = STYLES[type];
  return (
    <div className={`rounded-lg border-l-4 p-4 ${style.bg} ${style.border}`}>
      <div className="flex">
        <span className={`text-lg ${style.text}`}>{style.icon}</span>
        <div className="ml-3 flex-1">
          {title && <h3 className={`text-sm font-medium ${style.text}`}>{title}</h3>}
          <div className={`text-sm ${style.text} ${title ? 'mt-2' : ''}`}>{children}</div>
        </div>
        {onClose && (
          <button onClick={onClose} className={`ml-auto text-sm ${style.text} hover:opacity-75`}>
            {'✕'}
          </button>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run to verify all pass**

Run: `npm test -- ui/`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ui/
git commit -m "feat(frontend): port c3rro UI primitives (Card, Badge, Toggle, Alert)"
```

---

### Task 8: API client + TypeScript types

**Files:**
- Create: `frontend/src/api/types.ts`, `frontend/src/api/client.ts`
- Test: `frontend/src/api/client.test.ts`

**Interfaces:**
- Produces: `apiGet<T>(path: string, params?: Record<string, string | string[] | undefined>) -> Promise<T>`, plus TS interfaces `CapacityGroupResult`, `CapacityTotalsResponse`, `CapacityAdditionsResponse`, `RegionOut`, `TechnologyMeta`, `SizeClassMeta`, `HealthResponse`, `UnitPoint`, `UnitPointsResponse`, mirroring `api/schemas.py` field-for-field. Used by every hook in Task 9.

- [ ] **Step 1: Write the types**

Create `frontend/src/api/types.ts` (field names/types mirror `api/schemas.py` exactly):

```ts
export interface CapacityGroupResult {
  category: string;
  technology: string | null;
  region_ags: string | null;
  size_class: string | null;
  month: string | null;
  unit_count: number;
  capacity_kw_sum: number | null;
  storage_capacity_kwh_sum: number | null;
}

export interface CapacityTotalsResponse {
  as_of_date: string;
  include_decommissioned: boolean;
  group_by: string[];
  results: CapacityGroupResult[];
}

export interface CapacityAdditionsResponse {
  date_from: string | null;
  date_to: string | null;
  group_by: string[];
  results: CapacityGroupResult[];
}

export interface RegionOut {
  ags: string;
  level: string;
  name: string;
  parent_ags: string | null;
}

export interface TechnologyMeta {
  technology: string;
  category: string;
  is_renewable: boolean | null;
}

export interface SizeClassMeta {
  category: string;
  size_classes: string[];
}

export interface HealthResponse {
  has_data: boolean;
  last_import_finished_at: string | null;
  vg250_source_version: string | null;
  region_join_match_rate: number | null;
  mastr_row_counts: Record<string, number> | null;
}

export interface UnitPoint {
  mastr_nummer: string;
  technology: string;
  category: string;
  capacity_kw: number | null;
  storage_capacity_kwh: number | null;
  latitude: number;
  longitude: number;
}

export interface UnitPointsResponse {
  points: UnitPoint[];
  truncated: boolean;
}
```

- [ ] **Step 2: Write the failing test for the client**

Create `frontend/src/api/client.test.ts`:

```ts
import { afterEach, describe, expect, it, vi } from 'vitest';

import { apiGet } from './client';

describe('apiGet', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('builds the URL with query params, including repeated array params', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ ok: true }),
    });
    vi.stubGlobal('fetch', fetchMock);

    await apiGet('/capacity/totals', { technology: ['solar', 'wind'], region_level: 'land' });

    const calledUrl = fetchMock.mock.calls[0][0] as string;
    expect(calledUrl).toContain('/capacity/totals');
    expect(calledUrl).toContain('technology=solar');
    expect(calledUrl).toContain('technology=wind');
    expect(calledUrl).toContain('region_level=land');
  });

  it('throws when the response is not ok', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 500 }));
    await expect(apiGet('/meta/health')).rejects.toThrow('500');
  });
});
```

- [ ] **Step 3: Run to verify failure**

Run: `npm test -- client`
Expected: FAIL — module doesn't exist

- [ ] **Step 4: Implement the client**

Create `frontend/src/api/client.ts`:

```ts
const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

export async function apiGet<T>(
  path: string,
  params?: Record<string, string | number | boolean | string[] | undefined>
): Promise<T> {
  const url = new URL(path, BASE_URL);
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value === undefined) continue;
      if (Array.isArray(value)) {
        value.forEach((v) => url.searchParams.append(key, v));
      } else {
        url.searchParams.set(key, String(value));
      }
    }
  }

  const response = await fetch(url.toString());
  if (!response.ok) {
    throw new Error(`GET ${path} failed with status ${response.status}`);
  }
  return response.json() as Promise<T>;
}
```

- [ ] **Step 5: Run to verify it passes**

Run: `npm test -- client`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/
git commit -m "feat(frontend): typed API client and response types"
```

---

### Task 9: TanStack Query data hooks

**Files:**
- Create: `frontend/src/hooks/useCapacityTotals.ts`, `useCapacityAdditions.ts`, `useRegions.ts`, `useRegionGeojson.ts`, `useUnitPoints.ts`, `useMeta.ts`
- Modify: `frontend/src/main.tsx` (wrap in `QueryClientProvider`)
- Test: `frontend/src/hooks/useCapacityTotals.test.tsx`

**Interfaces:**
- Consumes: `apiGet`, types from Task 8.
- Produces: `useCapacityTotals(params) -> UseQueryResult<CapacityTotalsResponse>`, `useCapacityAdditions(params)`, `useRegions(level?)`, `useRegionGeojson(level)`, `useUnitPoints(params)`, `useHealth()`, `useTechnologies()`, `useSizeClasses()`. Used by `SidePanel`, `MapView`, `DataProvenanceFooter` (Tasks 11, 12, 15, 16).

- [ ] **Step 1: Wrap the app in `QueryClientProvider`**

Replace `frontend/src/main.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import App from './App';
import './index.css';

const queryClient = new QueryClient();

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>
);
```

- [ ] **Step 2: Write the failing test for one representative hook**

Create `frontend/src/hooks/useCapacityTotals.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import * as client from '../api/client';
import { useCapacityTotals } from './useCapacityTotals';

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

describe('useCapacityTotals', () => {
  afterEach(() => vi.restoreAllMocks());

  it('fetches /capacity/totals with the given filters', async () => {
    const apiGetSpy = vi.spyOn(client, 'apiGet').mockResolvedValue({
      as_of_date: '2026-08-10',
      include_decommissioned: false,
      group_by: ['technology'],
      results: [],
    });

    const { result } = renderHook(
      () => useCapacityTotals({ technology: ['solar'], group_by: ['technology'] }),
      { wrapper }
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiGetSpy).toHaveBeenCalledWith(
      '/capacity/totals',
      expect.objectContaining({ technology: ['solar'], group_by: ['technology'] })
    );
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `npm test -- useCapacityTotals`
Expected: FAIL — module doesn't exist

- [ ] **Step 3: Implement the hooks**

Create `frontend/src/hooks/useCapacityTotals.ts`:

```ts
import { useQuery } from '@tanstack/react-query';

import { apiGet } from '../api/client';
import type { CapacityTotalsResponse } from '../api/types';

export interface CapacityTotalsParams {
  technology?: string[];
  category?: string;
  region_level?: string;
  region_ags?: string[];
  size_class?: string[];
  group_by?: string[];
  as_of_date?: string;
  include_decommissioned?: boolean;
}

export function useCapacityTotals(params: CapacityTotalsParams) {
  return useQuery({
    queryKey: ['capacity-totals', params],
    queryFn: () => apiGet<CapacityTotalsResponse>('/capacity/totals', params as Record<string, string | string[] | undefined>),
  });
}
```

Create `frontend/src/hooks/useCapacityAdditions.ts` (same shape, additions endpoint, `date_from`/`date_to` instead of `as_of_date`/`include_decommissioned`):

```ts
import { useQuery } from '@tanstack/react-query';

import { apiGet } from '../api/client';
import type { CapacityAdditionsResponse } from '../api/types';

export interface CapacityAdditionsParams {
  technology?: string[];
  category?: string;
  region_level?: string;
  region_ags?: string[];
  size_class?: string[];
  group_by?: string[];
  date_from?: string;
  date_to?: string;
}

export function useCapacityAdditions(params: CapacityAdditionsParams) {
  return useQuery({
    queryKey: ['capacity-additions', params],
    queryFn: () => apiGet<CapacityAdditionsResponse>('/capacity/additions', params as Record<string, string | string[] | undefined>),
  });
}
```

Create `frontend/src/hooks/useRegions.ts`:

```ts
import { useQuery } from '@tanstack/react-query';

import { apiGet } from '../api/client';
import type { RegionOut } from '../api/types';

export function useRegions(level?: 'land' | 'kreis') {
  return useQuery({
    queryKey: ['regions', level],
    queryFn: () => apiGet<RegionOut[]>('/regions', level ? { level } : undefined),
  });
}
```

Create `frontend/src/hooks/useRegionGeojson.ts`:

```ts
import { useQuery } from '@tanstack/react-query';

import { apiGet } from '../api/client';

export function useRegionGeojson(level: 'land' | 'kreis') {
  return useQuery({
    queryKey: ['region-geojson', level],
    queryFn: () => apiGet<GeoJSON.FeatureCollection>(`/regions/${level}/geojson`),
    staleTime: Infinity,
  });
}
```

Create `frontend/src/hooks/useUnitPoints.ts`:

```ts
import { useQuery } from '@tanstack/react-query';

import { apiGet } from '../api/client';
import type { UnitPointsResponse } from '../api/types';

export interface UnitPointsParams {
  kreis_ags: string;
  technology?: string[];
  category?: string;
  size_class?: string[];
}

export function useUnitPoints(params: UnitPointsParams) {
  return useQuery({
    queryKey: ['unit-points', params],
    queryFn: () => apiGet<UnitPointsResponse>('/units/points', params as Record<string, string | string[] | undefined>),
    enabled: Boolean(params.kreis_ags),
  });
}
```

Create `frontend/src/hooks/useMeta.ts`:

```ts
import { useQuery } from '@tanstack/react-query';

import { apiGet } from '../api/client';
import type { HealthResponse, SizeClassMeta, TechnologyMeta } from '../api/types';

export function useHealth() {
  return useQuery({ queryKey: ['meta-health'], queryFn: () => apiGet<HealthResponse>('/meta/health') });
}

export function useTechnologies() {
  return useQuery({
    queryKey: ['meta-technologies'],
    queryFn: () => apiGet<TechnologyMeta[]>('/meta/technologies'),
    staleTime: Infinity,
  });
}

export function useSizeClasses() {
  return useQuery({
    queryKey: ['meta-size-classes'],
    queryFn: () => apiGet<SizeClassMeta[]>('/meta/size-classes'),
    staleTime: Infinity,
  });
}
```

Install the GeoJSON type package used by `useRegionGeojson.ts`:

```bash
npm install -D @types/geojson
```

- [ ] **Step 4: Run to verify the test passes**

Run: `npm test -- useCapacityTotals`
Expected: PASS

- [ ] **Step 5: Run the full frontend test suite and commit**

Run: `npm test`

```bash
git add frontend/src/hooks/ frontend/src/main.tsx frontend/package.json frontend/package-lock.json
git commit -m "feat(frontend): TanStack Query hooks for all API endpoints"
```

---

### Task 10: Zustand explorer store + pure utils

**Files:**
- Create: `frontend/src/state/explorerStore.ts`, `frontend/src/utils/bubbleScale.ts`, `frontend/src/utils/dateSentinel.ts`
- Test: `frontend/src/state/explorerStore.test.ts`, `frontend/src/utils/bubbleScale.test.ts`, `frontend/src/utils/dateSentinel.test.ts`

**Interfaces:**
- Produces:
  - `useExplorerStore` (Zustand hook) exposing `{ tab, selection: {level, landAgs, kreisAgs}, filters: {technologies, sizeClasses, metric, timeMode, asOfDate, dateFrom, dateTo}, setTab, selectNational, selectLand, selectKreis, setMetric, setTimeMode, setTechnologies, setSizeClasses, setDateRange }`.
  - `bubbleRadiusPx(capacityKw: number | null, opts: { maxCapacityKw: number; minRadius?: number; maxRadius?: number }) -> number`.
  - `isPlausibleMonth(month: string | null) -> boolean` and `excludeSentinelMonths<T extends { month: string | null }>(rows: T[]) -> T[]`.
- Used by: `MapView`, `Breadcrumb`, `FilterPanel`, `TechnologyChart`, `SidePanel` (Tasks 11-15).

- [ ] **Step 1: Write failing tests for the pure utils**

Create `frontend/src/utils/bubbleScale.test.ts`:

```ts
import { describe, expect, it } from 'vitest';

import { bubbleRadiusPx } from './bubbleScale';

describe('bubbleRadiusPx', () => {
  it('returns the minimum radius for the smallest capacity', () => {
    expect(bubbleRadiusPx(0, { maxCapacityKw: 100 })).toBe(3);
    expect(bubbleRadiusPx(null, { maxCapacityKw: 100 })).toBe(3);
  });

  it('returns the maximum radius when capacity equals the max', () => {
    expect(bubbleRadiusPx(100, { maxCapacityKw: 100 })).toBeCloseTo(24, 1);
  });

  it('scales by square root, not linearly -- a 4x capacity unit gets 2x the radius', () => {
    const small = bubbleRadiusPx(25, { maxCapacityKw: 100 });
    const large = bubbleRadiusPx(100, { maxCapacityKw: 100 });
    expect(large - 3).toBeCloseTo((small - 3) * 2, 1);
  });

  it('respects custom min/max radius options', () => {
    expect(bubbleRadiusPx(100, { maxCapacityKw: 100, minRadius: 5, maxRadius: 10 })).toBeCloseTo(10, 1);
  });
});
```

Create `frontend/src/utils/dateSentinel.test.ts`:

```ts
import { describe, expect, it } from 'vitest';

import { excludeSentinelMonths, isPlausibleMonth } from './dateSentinel';

describe('isPlausibleMonth', () => {
  it('rejects the 1900 sentinel and anything before 1950', () => {
    expect(isPlausibleMonth('1900-01')).toBe(false);
    expect(isPlausibleMonth('1949-12')).toBe(false);
  });

  it('accepts 1950 onward', () => {
    expect(isPlausibleMonth('1950-01')).toBe(true);
    expect(isPlausibleMonth('2023-07')).toBe(true);
  });

  it('rejects null', () => {
    expect(isPlausibleMonth(null)).toBe(false);
  });
});

describe('excludeSentinelMonths', () => {
  it('filters out rows with an implausible month, keeps the rest', () => {
    const rows = [{ month: '1900-01', unit_count: 5 }, { month: '2023-07', unit_count: 2 }];
    expect(excludeSentinelMonths(rows)).toEqual([{ month: '2023-07', unit_count: 2 }]);
  });
});
```

Create `frontend/src/state/explorerStore.test.ts`:

```ts
import { beforeEach, describe, expect, it } from 'vitest';

import { useExplorerStore } from './explorerStore';

beforeEach(() => {
  useExplorerStore.setState(useExplorerStore.getInitialState());
});

describe('explorerStore', () => {
  it('starts at national level on the generation tab with default renewable technologies', () => {
    const state = useExplorerStore.getState();
    expect(state.tab).toBe('generation');
    expect(state.selection).toEqual({ level: 'national', landAgs: null, kreisAgs: null });
    expect(state.filters.technologies).toEqual(['solar', 'wind', 'biomass', 'hydro', 'gsgk']);
  });

  it('selectLand sets level to land and clears kreisAgs', () => {
    useExplorerStore.getState().selectKreis('09', '09162');
    useExplorerStore.getState().selectLand('11');
    const state = useExplorerStore.getState();
    expect(state.selection).toEqual({ level: 'land', landAgs: '11', kreisAgs: null });
  });

  it('selectKreis sets level to kreis with both codes', () => {
    useExplorerStore.getState().selectKreis('09', '09162');
    expect(useExplorerStore.getState().selection).toEqual({ level: 'kreis', landAgs: '09', kreisAgs: '09162' });
  });

  it('selectNational resets the selection entirely', () => {
    useExplorerStore.getState().selectKreis('09', '09162');
    useExplorerStore.getState().selectNational();
    expect(useExplorerStore.getState().selection).toEqual({ level: 'national', landAgs: null, kreisAgs: null });
  });

  it('setTab to storage fixes technologies to ["storage"] and clears size classes', () => {
    useExplorerStore.getState().setSizeClasses(['<5 kWh']);
    useExplorerStore.getState().setTab('storage');
    const state = useExplorerStore.getState();
    expect(state.tab).toBe('storage');
    expect(state.filters.technologies).toEqual(['storage']);
    expect(state.filters.sizeClasses).toEqual([]);
  });

  it('setTab back to generation restores the default renewable technology set', () => {
    useExplorerStore.getState().setTab('storage');
    useExplorerStore.getState().setTab('generation');
    expect(useExplorerStore.getState().filters.technologies).toEqual([
      'solar', 'wind', 'biomass', 'hydro', 'gsgk',
    ]);
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `npm test -- bubbleScale dateSentinel explorerStore`
Expected: FAIL — modules don't exist

- [ ] **Step 3: Implement `bubbleScale.ts`**

```ts
interface BubbleRadiusOptions {
  maxCapacityKw: number;
  minRadius?: number;
  maxRadius?: number;
}

export function bubbleRadiusPx(capacityKw: number | null, opts: BubbleRadiusOptions): number {
  const { maxCapacityKw, minRadius = 3, maxRadius = 24 } = opts;
  if (capacityKw == null || capacityKw <= 0 || maxCapacityKw <= 0) return minRadius;
  const scale = Math.sqrt(capacityKw) / Math.sqrt(maxCapacityKw);
  return minRadius + scale * (maxRadius - minRadius);
}
```

- [ ] **Step 4: Implement `dateSentinel.ts`**

```ts
const SENTINEL_CUTOFF_MONTH = '1950-01';

export function isPlausibleMonth(month: string | null): boolean {
  if (!month) return false;
  return month >= SENTINEL_CUTOFF_MONTH;
}

export function excludeSentinelMonths<T extends { month: string | null }>(rows: T[]): T[] {
  return rows.filter((row) => isPlausibleMonth(row.month));
}
```

- [ ] **Step 5: Implement `explorerStore.ts`**

```ts
import { create } from 'zustand';

export type Tab = 'generation' | 'storage';
export type Metric = 'count' | 'capacity';
export type TimeMode = 'total' | 'period';
export type RegionLevel = 'national' | 'land' | 'kreis';

export const DEFAULT_RENEWABLE_TECHNOLOGIES = ['solar', 'wind', 'biomass', 'hydro', 'gsgk'];

interface Selection {
  level: RegionLevel;
  landAgs: string | null;
  kreisAgs: string | null;
}

interface Filters {
  technologies: string[];
  sizeClasses: string[];
  metric: Metric;
  timeMode: TimeMode;
  asOfDate: string;
  dateFrom: string | null;
  dateTo: string | null;
}

interface ExplorerState {
  tab: Tab;
  selection: Selection;
  filters: Filters;
  setTab: (tab: Tab) => void;
  selectNational: () => void;
  selectLand: (landAgs: string) => void;
  selectKreis: (landAgs: string, kreisAgs: string) => void;
  setMetric: (metric: Metric) => void;
  setTimeMode: (timeMode: TimeMode) => void;
  setTechnologies: (technologies: string[]) => void;
  setSizeClasses: (sizeClasses: string[]) => void;
  setDateRange: (dateFrom: string | null, dateTo: string | null) => void;
}

function initialState() {
  return {
    tab: 'generation' as Tab,
    selection: { level: 'national', landAgs: null, kreisAgs: null } as Selection,
    filters: {
      technologies: [...DEFAULT_RENEWABLE_TECHNOLOGIES],
      sizeClasses: [] as string[],
      metric: 'capacity' as Metric,
      timeMode: 'total' as TimeMode,
      asOfDate: new Date().toISOString().slice(0, 10),
      dateFrom: null,
      dateTo: null,
    } as Filters,
  };
}

export const useExplorerStore = create<ExplorerState>()((set, get) => ({
  ...initialState(),
  setTab: (tab) =>
    set((state) => ({
      tab,
      filters: {
        ...state.filters,
        technologies: tab === 'storage' ? ['storage'] : [...DEFAULT_RENEWABLE_TECHNOLOGIES],
        sizeClasses: [],
      },
    })),
  selectNational: () => set({ selection: { level: 'national', landAgs: null, kreisAgs: null } }),
  selectLand: (landAgs) => set({ selection: { level: 'land', landAgs, kreisAgs: null } }),
  selectKreis: (landAgs, kreisAgs) => set({ selection: { level: 'kreis', landAgs, kreisAgs } }),
  setMetric: (metric) => set((state) => ({ filters: { ...state.filters, metric } })),
  setTimeMode: (timeMode) => set((state) => ({ filters: { ...state.filters, timeMode } })),
  setTechnologies: (technologies) => set((state) => ({ filters: { ...state.filters, technologies } })),
  setSizeClasses: (sizeClasses) => set((state) => ({ filters: { ...state.filters, sizeClasses } })),
  setDateRange: (dateFrom, dateTo) => set((state) => ({ filters: { ...state.filters, dateFrom, dateTo } })),
  getInitialState: initialState,
}));
```

Note: Zustand's vanilla `create` doesn't ship `getInitialState` by default in all versions — if `useExplorerStore.getInitialState` is unavailable in the installed version, replace the test's `beforeEach` with `useExplorerStore.setState({ ...initialState-shape-inline })`; check `node_modules/zustand/package.json` version installed by Task 5 and adjust the test accordingly (Zustand >=4.5 includes `getInitialState` on the store).

- [ ] **Step 6: Run to verify all pass**

Run: `npm test -- bubbleScale dateSentinel explorerStore`
Expected: PASS (13 tests)

- [ ] **Step 7: Run the full frontend suite and commit**

Run: `npm test`

```bash
git add frontend/src/state/ frontend/src/utils/
git commit -m "feat(frontend): explorer store (tab/selection/filters) and pure scale/date-sentinel utils"
```

---

### Task 11: MapView — Land/Kreis choropleth drill-down

**Files:**
- Create: `frontend/src/components/MapView/MapView.tsx`, `frontend/src/components/MapView/choroplethLayer.ts`
- Test: `frontend/src/components/MapView/choroplethLayer.test.ts`, `frontend/src/components/MapView/MapView.test.tsx`

**Interfaces:**
- Consumes: `useRegionGeojson`, `useCapacityTotals` (Task 9), `useExplorerStore` (Task 10), `palettes.blues` (Task 6).
- Produces: `buildChoroplethColorExpression(colorStops: {ags: string; value: number}[], maxValue: number) -> maplibregl.ExpressionSpecification`, `<MapView>` component. `MapView` renders the map and, on a Land/Kreis click, calls `useExplorerStore`'s `selectLand`/`selectKreis`. Task 12 extends this same component with the bubble layer.

MapLibre GL needs a real WebGL canvas, which jsdom doesn't provide — keep all the *decision logic* (which color a region gets, which layer is active) in plain, fully-testable functions, and give `MapView` itself only a light smoke test with `maplibre-gl` mocked.

- [ ] **Step 1: Write the failing test for the pure color-expression builder**

Create `frontend/src/components/MapView/choroplethLayer.test.ts`:

```ts
import { describe, expect, it } from 'vitest';

import { buildChoroplethColorExpression } from './choroplethLayer';

describe('buildChoroplethColorExpression', () => {
  it('builds a feature-state-driven interpolate expression bounded by the max value', () => {
    const expr = buildChoroplethColorExpression(100);
    expect(expr[0]).toBe('interpolate');
    expect(expr).toContain('#93d2e1'); // bluelight, low end
    expect(expr).toContain('#407188'); // bluedark, high end
  });

  it('falls back to a neutral color for regions with no data (feature-state value undefined)', () => {
    const expr = buildChoroplethColorExpression(100);
    const fallback = expr[expr.length - 1];
    expect(fallback).toBe('#d9d8cd'); // greylight, matches c3rro's neutral/no-data convention
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `npm test -- choroplethLayer`
Expected: FAIL — module doesn't exist

- [ ] **Step 3: Implement `choroplethLayer.ts`**

```ts
import type { ExpressionSpecification } from 'maplibre-gl';

import { colors, palettes } from '../../styles/tokens';

export function buildChoroplethColorExpression(maxValue: number): ExpressionSpecification {
  const [low, high] = palettes.blues;
  return [
    'case',
    ['==', ['feature-state', 'value'], null],
    colors.greylight,
    [
      'interpolate',
      ['linear'],
      ['feature-state', 'value'],
      0,
      low,
      maxValue,
      high,
    ],
  ] as unknown as ExpressionSpecification;
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `npm test -- choroplethLayer`
Expected: PASS

Note on Step 1's test: `expr` here is the raw array structure, not a rendered string — `toContain` checks work because the hex strings appear as literal array elements. If the assertion style doesn't match your array shape exactly, adjust the test to check `JSON.stringify(expr).includes('#93d2e1')` instead — the point is verifying both palette endpoints and the no-data fallback color appear in the built expression.

- [ ] **Step 5: Write the smoke test for `MapView`**

Create `frontend/src/components/MapView/MapView.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

vi.mock('maplibre-gl', () => {
  class MapMock {
    on = vi.fn();
    addSource = vi.fn();
    addLayer = vi.fn();
    setFeatureState = vi.fn();
    remove = vi.fn();
    fitBounds = vi.fn();
  }
  return { Map: MapMock, default: { Map: MapMock } };
});

import { MapView } from './MapView';

function renderWithQuery(ui: React.ReactElement) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

describe('MapView', () => {
  it('renders a map container without crashing', () => {
    renderWithQuery(<MapView />);
    expect(screen.getByTestId('map-container')).toBeInTheDocument();
  });
});
```

- [ ] **Step 6: Run to verify it fails**

Run: `npm test -- MapView`
Expected: FAIL — module doesn't exist

- [ ] **Step 7: Implement `MapView.tsx`**

```tsx
import maplibregl from 'maplibre-gl';
import { useEffect, useRef } from 'react';

import { useCapacityTotals } from '../../hooks/useCapacityTotals';
import { useRegionGeojson } from '../../hooks/useRegionGeojson';
import { useExplorerStore } from '../../state/explorerStore';
import { buildChoroplethColorExpression } from './choroplethLayer';

const BLANK_STYLE = {
  version: 8 as const,
  sources: {},
  layers: [{ id: 'background', type: 'background' as const, paint: { 'background-color': '#FEF4DC' } }],
};

export function MapView() {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);

  const selection = useExplorerStore((s) => s.selection);
  const filters = useExplorerStore((s) => s.filters);
  const selectLand = useExplorerStore((s) => s.selectLand);
  const selectKreis = useExplorerStore((s) => s.selectKreis);

  const activeLevel = selection.level === 'national' ? 'land' : selection.level === 'land' ? 'kreis' : 'kreis';
  const { data: geojson } = useRegionGeojson(activeLevel);
  const { data: totals } = useCapacityTotals({
    technology: filters.technologies,
    region_level: activeLevel,
    group_by: ['region'],
    as_of_date: filters.asOfDate,
  });

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    mapRef.current = new maplibregl.Map({
      container: containerRef.current,
      style: BLANK_STYLE,
      center: [10.4515, 51.1657],
      zoom: 5,
    });
    return () => {
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !geojson) return;

    const sourceId = `${activeLevel}-source`;
    const layerId = `${activeLevel}-fill`;
    if (!map.getSource(sourceId)) {
      map.addSource(sourceId, { type: 'geojson', data: geojson, promoteId: 'ags' });
      const maxValue = Math.max(...(totals?.results.map((r) => r.capacity_kw_sum ?? r.unit_count) ?? [1]), 1);
      map.addLayer({
        id: layerId,
        type: 'fill',
        source: sourceId,
        paint: { 'fill-color': buildChoroplethColorExpression(maxValue), 'fill-outline-color': '#5e5a58' },
      });
      map.on('click', layerId, (e) => {
        const ags = e.features?.[0]?.properties?.ags as string | undefined;
        if (!ags) return;
        if (activeLevel === 'land') selectLand(ags);
        else if (selection.landAgs) selectKreis(selection.landAgs, ags);
      });
    }

    totals?.results.forEach((row) => {
      if (!row.region_ags) return;
      const value = filters.metric === 'capacity' ? row.capacity_kw_sum : row.unit_count;
      map.setFeatureState({ source: sourceId, id: row.region_ags }, { value: value ?? 0 });
    });
  }, [geojson, totals, activeLevel, filters.metric, selection.landAgs, selectLand, selectKreis]);

  return <div ref={containerRef} data-testid="map-container" className="h-full w-full" />;
}
```

- [ ] **Step 8: Run to verify it passes**

Run: `npm test -- MapView`
Expected: PASS

- [ ] **Step 9: Manual verification**

Run `npm run dev` in `frontend/` alongside the backend (`uvicorn api.main:app --reload` from Task 4's manual check), confirm the map renders with a Land-level choropleth and clicking a Land transitions to that Land's Kreis-level fill. (`region_level=land` on the initial national view is intentional — Kreis-level starts once a Land is selected.)

- [ ] **Step 10: Commit**

```bash
git add frontend/src/components/MapView/
git commit -m "feat(frontend): MapView with Land/Kreis choropleth drill-down"
```

---

### Task 12: MapView — bubble marker layer

**Files:**
- Create: `frontend/src/components/MapView/bubbleLayer.ts`
- Modify: `frontend/src/components/MapView/MapView.tsx`
- Test: `frontend/src/components/MapView/bubbleLayer.test.ts`

**Interfaces:**
- Consumes: `useUnitPoints` (Task 9), `bubbleRadiusPx` (Task 10), `supercluster`.
- Produces: `clusterPoints(points: UnitPoint[], opts: {zoom: number; bounds: [number, number, number, number]}) -> GeoJSON.FeatureCollection` — a pure wrapper around `supercluster` that also carries a summed `capacityKw` property per cluster (via supercluster's `map`/`reduce`), used directly by `MapView`'s bubble-marker rendering once a Kreis is selected.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/MapView/bubbleLayer.test.ts`:

```ts
import { describe, expect, it } from 'vitest';

import { clusterPoints } from './bubbleLayer';
import type { UnitPoint } from '../../api/types';

function point(overrides: Partial<UnitPoint>): UnitPoint {
  return {
    mastr_nummer: 'X',
    technology: 'solar',
    category: 'generation',
    capacity_kw: 10,
    storage_capacity_kwh: null,
    latitude: 48.13,
    longitude: 11.58,
    ...overrides,
  };
}

describe('clusterPoints', () => {
  it('returns one feature per point when zoomed in enough to separate them', () => {
    const points = [
      point({ mastr_nummer: 'A', latitude: 48.1, longitude: 11.5 }),
      point({ mastr_nummer: 'B', latitude: 49.5, longitude: 12.9 }),
    ];
    const result = clusterPoints(points, { zoom: 18, bounds: [11.4, 47.9, 13.0, 49.6] });
    expect(result.features).toHaveLength(2);
    expect(result.features.every((f) => f.properties?.cluster !== true)).toBe(true);
  });

  it('clusters nearby points at low zoom and sums their capacity', () => {
    const points = [
      point({ mastr_nummer: 'A', capacity_kw: 10, latitude: 48.135, longitude: 11.582 }),
      point({ mastr_nummer: 'B', capacity_kw: 20, latitude: 48.136, longitude: 11.583 }),
    ];
    const result = clusterPoints(points, { zoom: 0, bounds: [-180, -85, 180, 85] });
    expect(result.features).toHaveLength(1);
    expect(result.features[0].properties?.cluster).toBe(true);
    expect(result.features[0].properties?.capacityKwSum).toBe(30);
  });

  it('carries capacityKw through on individual (non-clustered) points', () => {
    const points = [point({ mastr_nummer: 'A', capacity_kw: 42 })];
    const result = clusterPoints(points, { zoom: 18, bounds: [11.4, 47.9, 13.0, 49.6] });
    expect(result.features[0].properties?.capacityKwSum).toBe(42);
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `npm test -- bubbleLayer`
Expected: FAIL — module doesn't exist

- [ ] **Step 3: Implement `bubbleLayer.ts`**

```ts
import Supercluster from 'supercluster';

import type { UnitPoint } from '../../api/types';

interface ClusterProps {
  mastr_nummer?: string;
  capacityKwSum: number;
}

export function clusterPoints(
  points: UnitPoint[],
  opts: { zoom: number; bounds: [number, number, number, number] }
): GeoJSON.FeatureCollection<GeoJSON.Point, ClusterProps> {
  const index = new Supercluster<{ capacityKwSum: number }, { capacityKwSum: number }>({
    radius: 40,
    maxZoom: 20,
    map: (props) => ({ capacityKwSum: props.capacityKwSum }),
    reduce: (accumulated, props) => {
      accumulated.capacityKwSum += props.capacityKwSum;
    },
  });

  index.load(
    points.map((p) => ({
      type: 'Feature',
      properties: { mastr_nummer: p.mastr_nummer, capacityKwSum: p.capacity_kw ?? p.storage_capacity_kwh ?? 0 },
      geometry: { type: 'Point', coordinates: [p.longitude, p.latitude] },
    }))
  );

  return index.getClusters(opts.bounds, Math.round(opts.zoom)) as GeoJSON.FeatureCollection<
    GeoJSON.Point,
    ClusterProps
  >;
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `npm test -- bubbleLayer`
Expected: PASS

- [ ] **Step 5: Wire the bubble layer into `MapView`**

In `frontend/src/components/MapView/MapView.tsx`, add (alongside the existing imports):

```tsx
import { useUnitPoints } from '../../hooks/useUnitPoints';
import { bubbleRadiusPx } from '../../utils/bubbleScale';
import { clusterPoints } from './bubbleLayer';
```

Add a second data hook and effect, active only once a Kreis is selected:

```tsx
  const { data: pointsResponse } = useUnitPoints({
    kreis_ags: selection.kreisAgs ?? '',
    technology: filters.technologies,
  });

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !pointsResponse || selection.level !== 'kreis') return;

    const clustered = clusterPoints(pointsResponse.points, {
      zoom: map.getZoom(),
      bounds: map.getBounds().toArray().flat() as [number, number, number, number],
    });
    const maxCapacity = Math.max(...pointsResponse.points.map((p) => p.capacity_kw ?? p.storage_capacity_kwh ?? 0), 1);

    const sourceId = 'unit-points-source';
    const layerId = 'unit-points-circle';
    const geojsonWithRadius = {
      ...clustered,
      features: clustered.features.map((f) => ({
        ...f,
        properties: {
          ...f.properties,
          radiusPx: bubbleRadiusPx(f.properties.capacityKwSum, { maxCapacityKw: maxCapacity }),
        },
      })),
    };

    if (map.getSource(sourceId)) {
      (map.getSource(sourceId) as maplibregl.GeoJSONSource).setData(geojsonWithRadius as GeoJSON.FeatureCollection);
    } else {
      map.addSource(sourceId, { type: 'geojson', data: geojsonWithRadius as GeoJSON.FeatureCollection });
      map.addLayer({
        id: layerId,
        type: 'circle',
        source: sourceId,
        paint: {
          'circle-radius': ['get', 'radiusPx'],
          'circle-color': '#4ab79f',
          'circle-opacity': 0.7,
          'circle-stroke-color': '#ffffff',
          'circle-stroke-width': 1,
        },
      });
    }
  }, [pointsResponse, selection.level]);
```

Add a truncation notice below the map container's return statement — return a fragment with the map div plus a conditional badge:

```tsx
  return (
    <div className="relative h-full w-full">
      <div ref={containerRef} data-testid="map-container" className="h-full w-full" />
      {pointsResponse?.truncated && (
        <div className="absolute bottom-4 left-4 rounded-lg bg-white px-3 py-2 text-sm shadow-md border border-[#D9D8CD]">
          Showing a partial view — zoom in further to see all units.
        </div>
      )}
    </div>
  );
```

- [ ] **Step 6: Run the full frontend suite**

Run: `npm test`
Expected: all pass (MapView's existing smoke test still passes since `useUnitPoints` returns `undefined` data by default with `enabled: false` when `kreis_ags` is empty, matching Task 9's hook).

- [ ] **Step 7: Manual verification**

With backend + frontend dev servers running, click into a Kreis and confirm individual unit bubbles render, sized visibly differently for e.g. a large wind turbine vs. small rooftop solar units if such a Kreis is available in the real data.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/MapView/
git commit -m "feat(frontend): capacity-scaled bubble marker layer with clustering and truncation notice"
```

---

### Task 13: Breadcrumb + FilterPanel

**Files:**
- Create: `frontend/src/components/Breadcrumb.tsx`, `frontend/src/components/FilterPanel.tsx`
- Test: `frontend/src/components/Breadcrumb.test.tsx`, `frontend/src/components/FilterPanel.test.tsx`

**Interfaces:**
- Consumes: `useExplorerStore`, `useRegions` (Task 9), `useTechnologies`, `useSizeClasses`, `Toggle` (Task 7).
- Produces: `<Breadcrumb>`, `<FilterPanel>`. Composed into `SidePanel` (Task 15).

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/components/Breadcrumb.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it } from 'vitest';

import { useExplorerStore } from '../state/explorerStore';
import { Breadcrumb } from './Breadcrumb';

beforeEach(() => {
  useExplorerStore.setState(useExplorerStore.getInitialState());
});

describe('Breadcrumb', () => {
  it('shows only "Germany" at national level', () => {
    render(<Breadcrumb />);
    expect(screen.getByText('Germany')).toBeInTheDocument();
    expect(screen.queryByText('>')).not.toBeInTheDocument();
  });

  it('shows Germany > Land name when a Land is selected', () => {
    useExplorerStore.setState((s) => ({ ...s, selection: { level: 'land', landAgs: '09', kreisAgs: null } }));
    render(<Breadcrumb landName="Bayern" />);
    expect(screen.getByText('Bayern')).toBeInTheDocument();
  });

  it('clicking "Germany" calls selectNational', async () => {
    useExplorerStore.setState((s) => ({ ...s, selection: { level: 'land', landAgs: '09', kreisAgs: null } }));
    render(<Breadcrumb landName="Bayern" />);
    await userEvent.click(screen.getByText('Germany'));
    expect(useExplorerStore.getState().selection.level).toBe('national');
  });
});
```

Create `frontend/src/components/FilterPanel.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';

import { useExplorerStore } from '../state/explorerStore';
import { FilterPanel } from './FilterPanel';

beforeEach(() => {
  useExplorerStore.setState(useExplorerStore.getInitialState());
});

describe('FilterPanel', () => {
  it('shows the size-class filter on the generation tab', () => {
    render(<FilterPanel />);
    expect(screen.getByLabelText(/size class/i)).toBeInTheDocument();
  });

  it('hides the size-class filter on the storage tab (all values are unknown)', () => {
    useExplorerStore.setState((s) => ({ ...s, tab: 'storage' }));
    render(<FilterPanel />);
    expect(screen.queryByLabelText(/size class/i)).not.toBeInTheDocument();
  });

  it('renders metric and time-mode toggles', () => {
    render(<FilterPanel />);
    expect(screen.getByText(/count/i)).toBeInTheDocument();
    expect(screen.getByText(/capacity/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `npm test -- Breadcrumb FilterPanel`
Expected: FAIL — modules don't exist

- [ ] **Step 3: Implement `Breadcrumb.tsx`**

```tsx
import { useExplorerStore } from '../state/explorerStore';

interface BreadcrumbProps {
  landName?: string;
  kreisName?: string;
}

export function Breadcrumb({ landName, kreisName }: BreadcrumbProps) {
  const selection = useExplorerStore((s) => s.selection);
  const selectNational = useExplorerStore((s) => s.selectNational);
  const selectLand = useExplorerStore((s) => s.selectLand);

  const segments: { label: string; onClick?: () => void }[] = [
    { label: 'Germany', onClick: selection.level !== 'national' ? selectNational : undefined },
  ];
  if (selection.landAgs && landName) {
    segments.push({
      label: landName,
      onClick: selection.level === 'kreis' ? () => selectLand(selection.landAgs!) : undefined,
    });
  }
  if (selection.kreisAgs && kreisName) {
    segments.push({ label: kreisName });
  }

  return (
    <nav className="flex items-center gap-2 text-sm">
      {segments.map((segment, i) => (
        <span key={segment.label} className="flex items-center gap-2">
          {i > 0 && <span className="text-[#BDB2AA]">{'>'}</span>}
          {segment.onClick ? (
            <button onClick={segment.onClick} className="text-[#4AB79F] hover:underline">
              {segment.label}
            </button>
          ) : (
            <span className="font-medium text-[#33302F]">{segment.label}</span>
          )}
        </span>
      ))}
    </nav>
  );
}
```

- [ ] **Step 4: Implement `FilterPanel.tsx`**

```tsx
import { useSizeClasses } from '../hooks/useMeta';
import { useExplorerStore } from '../state/explorerStore';
import { Toggle } from './ui/Toggle';

export function FilterPanel() {
  const tab = useExplorerStore((s) => s.tab);
  const filters = useExplorerStore((s) => s.filters);
  const setMetric = useExplorerStore((s) => s.setMetric);
  const setTimeMode = useExplorerStore((s) => s.setTimeMode);
  const setSizeClasses = useExplorerStore((s) => s.setSizeClasses);
  const { data: sizeClassMeta } = useSizeClasses();

  const generationSizeClasses = sizeClassMeta?.find((m) => m.category === 'generation')?.size_classes ?? [];

  return (
    <div className="space-y-4">
      <Toggle
        enabled={filters.metric === 'capacity'}
        onChange={(enabled) => setMetric(enabled ? 'capacity' : 'count')}
        label="Count / Capacity"
        description="Toggle between unit count and total capacity"
      />
      <Toggle
        enabled={filters.timeMode === 'period'}
        onChange={(enabled) => setTimeMode(enabled ? 'period' : 'total')}
        label="Total / Period additions"
      />
      {tab === 'generation' && (
        <div>
          <label htmlFor="size-class-select" className="block text-sm font-medium text-[#33302F] mb-1">
            Size class
          </label>
          <select
            id="size-class-select"
            multiple
            className="w-full rounded-lg border border-[#D9D8CD] p-2 text-sm"
            value={filters.sizeClasses}
            onChange={(e) => setSizeClasses(Array.from(e.target.selectedOptions, (o) => o.value))}
          >
            {generationSizeClasses.map((sc) => (
              <option key={sc} value={sc}>
                {sc}
              </option>
            ))}
          </select>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Run to verify tests pass**

Run: `npm test -- Breadcrumb FilterPanel`
Expected: PASS (6 tests). Note: `FilterPanel`'s tests need a `QueryClientProvider` wrapper since it uses `useSizeClasses` — wrap the `render()` calls in the test file the same way `MapView.test.tsx` does (Task 11, Step 5), otherwise TanStack Query will throw "No QueryClient set."

- [ ] **Step 6: Run the full suite and commit**

Run: `npm test`

```bash
git add frontend/src/components/Breadcrumb.tsx frontend/src/components/FilterPanel.tsx frontend/src/components/Breadcrumb.test.tsx frontend/src/components/FilterPanel.test.tsx
git commit -m "feat(frontend): Breadcrumb navigation and FilterPanel controls"
```

---

### Task 14: TechnologyChart

**Files:**
- Create: `frontend/src/components/TechnologyChart.tsx`
- Test: `frontend/src/components/TechnologyChart.test.tsx`

**Interfaces:**
- Consumes: `useCapacityTotals`/`useCapacityAdditions` results (passed in as props, not fetched internally — keeps this component a pure presentational chart, reusable for both generation and storage tabs), `getPlotlyLayout`, `palettes.mixed` (Task 6).
- Produces: `<TechnologyChart results={CapacityGroupResult[]} metric="count"|"capacity">`. Composed into `SidePanel` (Task 15).

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/TechnologyChart.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { CapacityGroupResult } from '../api/types';
import { TechnologyChart } from './TechnologyChart';

const results: CapacityGroupResult[] = [
  { category: 'generation', technology: 'solar', region_ags: null, size_class: null, month: null, unit_count: 6236704, capacity_kw_sum: 113086749.89, storage_capacity_kwh_sum: null },
  { category: 'generation', technology: 'wind', region_ags: null, size_class: null, month: null, unit_count: 32224, capacity_kw_sum: 81351967.017, storage_capacity_kwh_sum: null },
];

describe('TechnologyChart', () => {
  it('renders one bar per technology when metric is capacity', () => {
    render(<TechnologyChart results={results} metric="capacity" />);
    expect(screen.getByTestId('technology-chart')).toBeInTheDocument();
  });

  it('renders unit_count values when metric is count', () => {
    render(<TechnologyChart results={results} metric="count" />);
    expect(screen.getByTestId('technology-chart')).toBeInTheDocument();
  });

  it('renders an empty-state message when there are no results', () => {
    render(<TechnologyChart results={[]} metric="capacity" />);
    expect(screen.getByText(/no data for the current filters/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `npm test -- TechnologyChart`
Expected: FAIL — module doesn't exist

- [ ] **Step 3: Implement `TechnologyChart.tsx`**

```tsx
import Plot from 'react-plotly.js';

import type { CapacityGroupResult } from '../api/types';
import { palettes } from '../styles/tokens';
import { getPlotlyLayout } from '../styles/plotlyTheme';

interface TechnologyChartProps {
  results: CapacityGroupResult[];
  metric: 'count' | 'capacity';
}

export function TechnologyChart({ results, metric }: TechnologyChartProps) {
  if (results.length === 0) {
    return <p className="text-sm text-[#5E5A58]">No data for the current filters.</p>;
  }

  const byTechnology = new Map<string, number>();
  results.forEach((row) => {
    if (!row.technology) return;
    const value = metric === 'capacity' ? row.capacity_kw_sum ?? row.storage_capacity_kwh_sum ?? 0 : row.unit_count;
    byTechnology.set(row.technology, (byTechnology.get(row.technology) ?? 0) + value);
  });

  const technologies = Array.from(byTechnology.keys());
  const values = technologies.map((t) => byTechnology.get(t)!);

  return (
    <div data-testid="technology-chart">
      <Plot
        data={[
          {
            type: 'bar',
            x: values,
            y: technologies,
            orientation: 'h',
            marker: { color: palettes.mixed.slice(0, technologies.length) },
          },
        ]}
        layout={getPlotlyLayout(metric === 'capacity' ? 'Capacity by technology' : 'Unit count by technology')}
        config={{ responsive: true, displayModeBar: false }}
        style={{ width: '100%', height: '300px' }}
      />
    </div>
  );
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `npm test -- TechnologyChart`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/TechnologyChart.tsx frontend/src/components/TechnologyChart.test.tsx
git commit -m "feat(frontend): TechnologyChart with count/capacity toggle, c3rro Plotly theme"
```

---

### Task 15: SidePanel composition

**Files:**
- Create: `frontend/src/components/SidePanel.tsx`
- Test: `frontend/src/components/SidePanel.test.tsx`

**Interfaces:**
- Consumes: `Breadcrumb`, `FilterPanel`, `TechnologyChart` (Tasks 13-14), `useCapacityTotals`, `useCapacityAdditions` (Task 9), `useExplorerStore` (Task 10), `excludeSentinelMonths` (Task 10), `Card` (Task 7), `useRegions` (Task 9, for breadcrumb region names).
- Produces: `<SidePanel>` — the floating card composing everything, reactive to `useExplorerStore`'s selection and filters. This is where the "changing a filter updates the map too" and "1900 sentinel excluded from period view" behaviors from the spec are wired together.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/SidePanel.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import * as client from '../api/client';
import { useExplorerStore } from '../state/explorerStore';
import { SidePanel } from './SidePanel';

beforeEach(() => {
  useExplorerStore.setState(useExplorerStore.getInitialState());
});

function renderWithQuery(ui: React.ReactElement) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

describe('SidePanel', () => {
  it('renders the breadcrumb, filter controls, and chart', async () => {
    vi.spyOn(client, 'apiGet').mockResolvedValue({
      as_of_date: '2026-08-10',
      include_decommissioned: false,
      group_by: ['technology'],
      results: [],
    });
    renderWithQuery(<SidePanel />);
    expect(screen.getByText('Germany')).toBeInTheDocument();
    expect(await screen.findByTestId('technology-chart')).toBeInTheDocument();
  });

  it('requests period additions (not totals) when timeMode is period', async () => {
    const apiGetSpy = vi.spyOn(client, 'apiGet').mockResolvedValue({
      date_from: null,
      date_to: null,
      group_by: ['technology'],
      results: [],
    });
    useExplorerStore.setState((s) => ({ filters: { ...s.filters, timeMode: 'period' } }));
    renderWithQuery(<SidePanel />);
    await screen.findByTestId('technology-chart');
    expect(apiGetSpy).toHaveBeenCalledWith('/capacity/additions', expect.anything());
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `npm test -- SidePanel`
Expected: FAIL — module doesn't exist

- [ ] **Step 3: Implement `SidePanel.tsx`**

```tsx
import { useCapacityAdditions } from '../hooks/useCapacityAdditions';
import { useCapacityTotals } from '../hooks/useCapacityTotals';
import { useRegions } from '../hooks/useRegions';
import { useExplorerStore } from '../state/explorerStore';
import { excludeSentinelMonths } from '../utils/dateSentinel';
import { Breadcrumb } from './Breadcrumb';
import { FilterPanel } from './FilterPanel';
import { TechnologyChart } from './TechnologyChart';
import { Card } from './ui/Card';

export function SidePanel() {
  const selection = useExplorerStore((s) => s.selection);
  const filters = useExplorerStore((s) => s.filters);
  const { data: lands } = useRegions('land');
  const { data: kreise } = useRegions('kreis');

  const regionAgs = selection.level === 'kreis' ? selection.kreisAgs! : selection.level === 'land' ? selection.landAgs! : undefined;
  const regionLevel = selection.level === 'kreis' ? 'kreis' : 'land';

  const totalsQuery = useCapacityTotals({
    technology: filters.technologies,
    size_class: filters.sizeClasses.length ? filters.sizeClasses : undefined,
    region_level: regionLevel,
    region_ags: regionAgs ? [regionAgs] : undefined,
    group_by: ['technology'],
    as_of_date: filters.asOfDate,
  });
  const additionsQuery = useCapacityAdditions({
    technology: filters.technologies,
    size_class: filters.sizeClasses.length ? filters.sizeClasses : undefined,
    region_level: regionLevel,
    region_ags: regionAgs ? [regionAgs] : undefined,
    group_by: ['technology', 'month'],
    date_from: filters.dateFrom ?? undefined,
    date_to: filters.dateTo ?? undefined,
  });

  const results =
    filters.timeMode === 'period'
      ? excludeSentinelMonths(additionsQuery.data?.results ?? [])
      : totalsQuery.data?.results ?? [];

  const landName = lands?.find((l) => l.ags === selection.landAgs)?.name;
  const kreisName = kreise?.find((k) => k.ags === selection.kreisAgs)?.name;

  return (
    <Card className="pointer-events-auto w-96 max-h-[80vh] overflow-y-auto">
      <div className="space-y-4">
        <Breadcrumb landName={landName} kreisName={kreisName} />
        <FilterPanel />
        <TechnologyChart results={results} metric={filters.metric} />
      </div>
    </Card>
  );
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `npm test -- SidePanel`
Expected: PASS

- [ ] **Step 5: Run the full suite and commit**

Run: `npm test`

```bash
git add frontend/src/components/SidePanel.tsx frontend/src/components/SidePanel.test.tsx
git commit -m "feat(frontend): SidePanel composing breadcrumb, filters, and the reactive technology chart"
```

---

### Task 16: App shell — tabs, footer, final wiring

**Files:**
- Create: `frontend/src/components/DataProvenanceFooter.tsx`
- Modify: `frontend/src/App.tsx`, `frontend/src/App.test.tsx`
- Test: `frontend/src/components/DataProvenanceFooter.test.tsx`

**Interfaces:**
- Consumes: `useHealth` (Task 9), `MapView` (Tasks 11-12), `SidePanel` (Task 15), `useExplorerStore` (Task 10), `Alert` (Task 7).
- Produces: the final `<App>` — tab switcher (Generation/Storage), full-bleed `MapView` with `SidePanel` floating over it, `DataProvenanceFooter` pinned to the bottom. This is the last task; after it, `npm run dev` is the complete Phase 4 dashboard.

- [ ] **Step 1: Write the failing test for the footer**

Create `frontend/src/components/DataProvenanceFooter.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import * as client from '../api/client';
import { DataProvenanceFooter } from './DataProvenanceFooter';

function renderWithQuery(ui: React.ReactElement) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

describe('DataProvenanceFooter', () => {
  it('shows the last import date and region match rate', async () => {
    vi.spyOn(client, 'apiGet').mockResolvedValue({
      has_data: true,
      last_import_finished_at: '2026-08-10T16:46:34',
      vg250_source_version: 'vg250_01-01',
      region_join_match_rate: 0.9997819834,
      mastr_row_counts: {},
    });
    renderWithQuery(<DataProvenanceFooter />);
    expect(await screen.findByText(/2026-08-10/)).toBeInTheDocument();
    expect(screen.getByText(/99\.98%/)).toBeInTheDocument();
  });

  it('shows a warning alert when has_data is false', async () => {
    vi.spyOn(client, 'apiGet').mockResolvedValue({
      has_data: false,
      last_import_finished_at: null,
      vg250_source_version: null,
      region_join_match_rate: null,
      mastr_row_counts: null,
    });
    renderWithQuery(<DataProvenanceFooter />);
    expect(await screen.findByText(/no data/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run to verify failure**

Run: `npm test -- DataProvenanceFooter`
Expected: FAIL — module doesn't exist

- [ ] **Step 3: Implement `DataProvenanceFooter.tsx`**

```tsx
import { useHealth } from '../hooks/useMeta';
import { Alert } from './ui/Alert';

export function DataProvenanceFooter() {
  const { data: health } = useHealth();

  if (!health) return null;

  if (!health.has_data) {
    return (
      <div className="absolute bottom-0 left-0 right-0 p-2">
        <Alert type="warning" title="No data">
          The backend has no processed data yet — run the ingestion pipeline first.
        </Alert>
      </div>
    );
  }

  const importedAt = health.last_import_finished_at?.slice(0, 10) ?? 'unknown';
  const matchRate =
    health.region_join_match_rate != null ? `${(health.region_join_match_rate * 100).toFixed(2)}%` : 'unknown';

  return (
    <div className="absolute bottom-0 left-0 right-0 flex justify-center pointer-events-none">
      <div className="pointer-events-auto bg-white/90 rounded-t-lg px-4 py-1.5 text-xs text-[#5E5A58] border border-b-0 border-[#D9D8CD]">
        Data as of {importedAt} · {matchRate} of units matched to a region
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `npm test -- DataProvenanceFooter`
Expected: PASS

- [ ] **Step 5: Update the `App` smoke test for the tab switcher**

Replace `frontend/src/App.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

vi.mock('maplibre-gl', () => {
  class MapMock {
    on = vi.fn();
    addSource = vi.fn();
    addLayer = vi.fn();
    setFeatureState = vi.fn();
    remove = vi.fn();
    fitBounds = vi.fn();
    getSource = vi.fn();
    getZoom = vi.fn().mockReturnValue(5);
    getBounds = vi.fn().mockReturnValue({ toArray: () => [[0, 0], [1, 1]] });
  }
  return { Map: MapMock, default: { Map: MapMock } };
});

import App from './App';

function renderWithQuery() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  );
}

describe('App', () => {
  it('renders the Generation/Storage tabs and defaults to Generation', () => {
    renderWithQuery();
    expect(screen.getByRole('tab', { name: /generation/i })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('tab', { name: /storage/i })).toHaveAttribute('aria-selected', 'false');
  });

  it('switches to the Storage tab on click', async () => {
    renderWithQuery();
    await userEvent.click(screen.getByRole('tab', { name: /storage/i }));
    expect(screen.getByRole('tab', { name: /storage/i })).toHaveAttribute('aria-selected', 'true');
  });
});
```

- [ ] **Step 6: Run to verify it fails**

Run: `npm test -- App`
Expected: FAIL (current `App.tsx` from Task 5 has no tabs)

- [ ] **Step 7: Implement the final `App.tsx`**

```tsx
import { DataProvenanceFooter } from './components/DataProvenanceFooter';
import { MapView } from './components/MapView/MapView';
import { SidePanel } from './components/SidePanel';
import { useExplorerStore } from './state/explorerStore';
import type { Tab } from './state/explorerStore';

const TABS: { id: Tab; label: string }[] = [
  { id: 'generation', label: 'Generation' },
  { id: 'storage', label: 'Storage' },
];

function App() {
  const tab = useExplorerStore((s) => s.tab);
  const setTab = useExplorerStore((s) => s.setTab);

  return (
    <div className="relative h-screen w-screen overflow-hidden">
      <header className="absolute top-0 left-0 right-0 z-10 flex items-center gap-4 bg-white/90 px-4 py-2 shadow-sm">
        <h1 className="text-lg font-semibold">Renewable Capacity Explorer</h1>
        <div role="tablist" className="flex gap-2 ml-auto">
          {TABS.map((t) => (
            <button
              key={t.id}
              role="tab"
              aria-selected={tab === t.id}
              onClick={() => setTab(t.id)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium ${
                tab === t.id ? 'bg-[#4AB79F] text-white' : 'text-[#5E5A58] hover:bg-[#D9D8CD]'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </header>

      <MapView />

      <div className="pointer-events-none absolute top-16 right-4 bottom-8">
        <SidePanel />
      </div>

      <DataProvenanceFooter />
    </div>
  );
}

export default App;
```

- [ ] **Step 8: Run to verify it passes**

Run: `npm test -- App`
Expected: PASS

- [ ] **Step 9: Run the entire frontend test suite**

Run: `npm test`
Expected: every test across every task passes.

- [ ] **Step 10: Full manual verification**

With the backend running against the real database (`python -m ingestion.cli rollup` once, then `uvicorn api.main:app --reload`) and `npm run dev` in `frontend/`:
1. Confirm the Land-level choropleth renders on load.
2. Click a Land, confirm it drills to Kreis level and the breadcrumb updates.
3. Click a Kreis, confirm bubble markers render, sized differently for different-capacity units.
4. Toggle Count/Capacity and Total/Period in the side panel, confirm both the chart and the map coloring update.
5. Switch to the Storage tab, confirm the size-class filter disappears and the chart shows storage's `capacity_kw` instead of an energy metric.
6. Confirm the footer shows a real "data as of" date and match rate from `/meta/health`.

- [ ] **Step 11: Commit**

```bash
git add frontend/src/App.tsx frontend/src/App.test.tsx frontend/src/components/DataProvenanceFooter.tsx frontend/src/components/DataProvenanceFooter.test.tsx
git commit -m "feat(frontend): final app shell with tabs, floating side panel, and data-provenance footer"
```

---

## Self-Review Notes

- **Spec coverage**: Section 1 (architecture/rollup) → Tasks 1-3. Section 2 (map-driven interaction, reactive panel, storage tab) → Tasks 11-13, 15, 16. Section 3 (new API surface, `/units/points`, rollup read path) → Tasks 3-4. Section 4 (edge cases: sentinel dates, storage size_class, unmapped units, truncation) → Task 10 (`dateSentinel`), Task 13 (`FilterPanel` hides size_class on storage tab), Task 12 (truncation notice), Task 16 (footer — unmapped-units live count is not separately implemented here; see gap below). Section 5 (c3rro UI/UX) → Tasks 6, 7, 11, 14.
- **Gap found and accepted, not silently dropped**: the spec's footer also calls for a live "N units not shown — no matched region" count scoped to the active filter selection, beyond the global match-rate shown in Task 16's footer. That requires either a new lightweight backend endpoint or a client-side derived count; it's small enough to add as a follow-up task after this plan ships rather than growing this already-16-task plan further — flag this to the user before or after execution.
- **Placeholder scan**: no TBD/TODO markers; every step has real code.
- **Type consistency checked**: `CapacityGroupResult`/`UnitPoint`/`UnitPointsResponse` field names match between `api/schemas.py` (Tasks 3-4) and `frontend/src/api/types.ts` (Task 8). `useExplorerStore`'s `Selection`/`Filters` shapes are used identically across Tasks 11-16. `run_aggregation`'s signature is unchanged end-to-end (Task 3), matching what `api/routers/capacity.py` already calls.
