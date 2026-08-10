# Phase 4: Dashboard UI Design

Status: approved by user, ready for implementation planning
Branch: `claude/bundesnetzagentur-renewable-research-9fc1gh`

## Context

Phases 1-3 are complete: ingestion pipeline (`ingestion/`), schema (`db/`), and a
read-only FastAPI service (`api/`) over a real MaStR + VG250 dataset
(`data/processed/mastr_analytics.db`, ~9.5M rows). `architecture-plan.md`
sketched a MapLibre choropleth frontend before any real data existed. This
spec replaces that sketch with a design informed by actually querying the
real data (Phase A discovery, see below) and a structured design conversation
with the user (Phase B, `superpowers:brainstorming`).

No frontend code exists yet — this spec defines what gets built.

## Phase A discovery findings

These findings directly shaped the design decisions below; they're recorded
here so the rationale doesn't get lost.

- **Data is real and sane**: `region_join_match_rate` = 99.98%. Solar's
  cumulative total (113 GW) and Bayern's lead in regional solar capacity
  both plausibility-check against published BNetzA/Fraunhofer figures.
- **Count vs. capacity diverge sharply by technology**: solar is 6.24M units
  for 113 GW (~18 kW avg — mass rooftop adoption); wind is 32k units for
  81 GW (~2.5 MW avg — few large installations). This divergence is the
  single most interesting thing in the dataset and isn't visible in BNetzA's
  own published aggregates. It's the core analytical hook for this design.
- **Storage has no usable energy-capacity metric.** `storage_capacity_kwh`
  (MaStR field `NutzbareSpeicherkapazitaet`) is null for all 2,714,827
  storage rows in the raw bulk export — confirmed at the source, not an
  ingestion bug. The `storage_eeg` table (also ingested) has no capacity
  fields either, only subsidy/registration metadata. Storage can only be
  shown by `capacity_kw` (power rating) and unit count, never kWh.
  Consequence: storage gets its own view, not shoehorned into the same
  chart type as generation.
- **`commissioning_date` has a `1900-01-01` sentinel value** as its minimum
  — almost certainly a placeholder, not a real installation. Must be
  excluded from month-bucketed trend/additions charts (a stray bar at 1900
  would be misleading) but doesn't affect cumulative totals (a unit with
  that date still correctly counts as "already commissioned").
- **Region-join gaps are small overall (0.02%) but uneven** — wind is
  4.4% unmatched vs. <1% for other technologies. Unmapped units must stay
  visible (a footer count), not silently vanish from the map.
- **Aggregation performance is a real constraint, not a hypothetical one.**
  Unfiltered/broadly-filtered queries over the ~9.5M-row `capacity_unit`
  table took 60-140s even after moving the database off OneDrive sync
  (`data/` now lives at `C:\data\flo_test`, junctioned back into the repo
  — see Section 3). `architecture-plan.md` called a materialized rollup an
  "explicit fallback only if profiling shows it's needed." Profiling now
  shows it's needed for any interactive, filter-driven view.
- **Dataset includes non-renewable technologies** (`combustion`: 79 GW,
  `nuclear`: negligible, 6 units) because MaStR registers all generation,
  not just renewables. Decided: filterable context, renewables the default.
- **Two bugs found and fixed during discovery** (commits `d8494a1`,
  `ac541a2`): ingestion performance (chunked streaming + batched upserts,
  needed to make the real bulk run feasible) and a `size_class` bucketing
  bug where `NaN` capacity values (pandas' representation of an all-null
  SQL column) fell through to the open-ended top bucket instead of
  returning "unknown." Both fixed, tested, and the already-materialized bad
  data corrected (2,714,827 storage rows' `size_class` reset from
  `>=10 MWh` to `NULL`).

## Audience & priorities

Primary audience: **technical / energy-policy users** — comfortable with
domain terms (Kreis/Land, MaStR, kW vs. kWh), want flexible cross-cutting
exploration rather than a guided/simplified narrative.

Core value proposition (decided through discovery, not assumed upfront):
surface things BNetzA's own published aggregates don't — Kreis-level
detail, and especially the count-vs-capacity divergence per technology.

## Design

### 1. Architecture & stack

- **Frontend**: React + TypeScript + Vite (per `architecture-plan.md`'s
  original scaffold — nothing built yet, no reason to deviate). TanStack
  Query for data fetching. Zustand for filter/selection state. MapLibre GL
  JS for the map (the Kreis/Land GeoJSON is already produced by ingestion).
  Plotly.js for the technology comparison chart, themed via the existing
  `docs/c3rro_style/c3rro_theme.js` `C3Theme.getPlotlyLayout`.
- **New backend piece**: a materialized rollup table, `capacity_rollup`,
  built alongside `capacity_unit` during `ingestion.cli build`. Keyed by
  `(category, technology, region_level, region_ags, year_month, size_class)`
  with `unit_count` and `capacity_sum` columns (generation kW / storage kW
  — see Section on storage below for why not kWh). Populated as an
  additional step in `build_db.py`'s existing upsert pass — no separate
  scheduling concern, matches the existing "re-sync is manual/local-trigger
  only" model.
- **API read path**: `/capacity/totals` and `/capacity/additions` keep
  their current request/response shape. Internally, they read from
  `capacity_rollup` when the request is coarse enough (region + technology
  + month-level date bucketing, no `size_class` cut finer than what the
  rollup stores) and fall back to a live `capacity_unit` scan otherwise.
  No frontend-visible API break.
- **Data location**: `data/` now lives at `C:\data\flo_test` with an NTFS
  junction at `flo_test\data`, so all existing relative-path defaults
  (`ingestion/config.py`, README commands, this doc's own instructions)
  keep working unchanged. This alone cut a representative slow query from
  137s to 59s; the rollup table addresses the remainder.

### 2. Interaction model — map-driven exploration

The map is the primary navigation surface, not a secondary widget.

- **Drill-down**: full-screen map, national extent, Land-level choropleth
  by default (colored by the active metric). Click a Land → transitions to
  its Kreis-level choropleth. Click a Kreis → transitions to individual
  units rendered as **capacity-scaled bubble markers** (radius ∝
  √capacity_kw, from `latitude`/`longitude` — not uniform dots), which
  decluster as you zoom in. A breadcrumb (`Germany > Bayern > München
  (Kreis)`) allows jumping back up without re-navigating the map.
- No Gemeinde-level boundary polygons exist (VG250's Gemeinde layer,
  ~10,990 polygons, was never ingested — explicitly deferred in the
  original plan). The bubble-marker layer is the Gemeinde-equivalent
  granularity, using data already available (`latitude`/`longitude`),
  without requiring new ingestion scope.
- **Reactive side panel**: whatever's selected on the map (national / a
  Land / a Kreis / a marker view) drives a linked panel: technology
  comparison chart (count vs. capacity toggle — this is where the core
  divergence finding is surfaced directly), a time toggle (cumulative
  total as of a date vs. additions in a period, reusing
  `/capacity/totals` / `/capacity/additions` as-is), and filters
  (technology — defaults to renewables, combustion/nuclear selectable;
  size class). Changing a filter or metric updates the map's coloring too
  — one linked view, not two separate ones.
- **Storage tab**: identical map-driven drill-down pattern, but its own
  metric set (power `kW`, unit count only — no capacity/energy toggle,
  since that metric doesn't exist for storage per the discovery finding).
  No `size_class` filter on this tab (100% of storage rows have `NULL`
  size_class post-fix — a filter with only an "unknown" option is noise).
- **Footer**: persistent data-provenance strip from `/meta/health` —
  "data as of [date], N% of units matched to a region" — plus a live count
  of currently-unmapped units in the active filter selection, so gaps stay
  visible rather than silently disappearing from the map.

### 3. New API surface

- **`GET /units/points`** (new): lightweight point records (`id`, `lat`,
  `lon`, `capacity_kw` or `storage_capacity_kwh`, `technology`) for the
  bubble-marker layer, scoped to a region + active filters. This is a live
  `capacity_unit` query, not rollup-backed — but it's always filtered to a
  single Kreis at minimum, which hits the existing
  `(kreis_ags, technology)` index and stays fast regardless of national
  table size (the slow queries measured in discovery were all
  unfiltered/national-scope; single-Kreis queries were not tested but are
  expected to be fast given the index and are the first thing to verify in
  implementation). Capped at a few thousand points per request; if a
  Kreis's filtered point count exceeds the cap, the response includes a
  truncation flag and the panel prompts "zoom in further" rather than
  silently dropping data.
- **`capacity_rollup` table**: schema as described in Section 1. Not
  directly exposed as a new endpoint — existing `/capacity/*` endpoints
  read from it internally.
- All other existing endpoints (`/regions`, `/regions/{level}/geojson`,
  `/meta/*`, `/units`, `/units/{mastr_nummer}`) are used as-is, unchanged.

### 4. Edge cases

- **1900-01-01 sentinel dates**: excluded specifically from month-bucketed
  additions/trend charts (a filter on `commissioning_date >= 1950-01-01`
  applied only in that chart's query, not elsewhere) — cumulative totals
  are unaffected since "commissioned by as-of-date" is still correctly
  true for these units.
- **Storage `size_class`**: always `NULL` post-fix (Phase A discovery) —
  no size-class filter shown on the storage tab.
- **Unmapped units** (kreis_ags/land_ags NULL): excluded from the map
  layers (nothing to render without coordinates) but counted in the
  footer's live "N units not shown" indicator, scoped to the active filter
  selection.
- **Truncated point layer**: see Section 3 — explicit truncation flag,
  never silent data loss.

### 5. UI/UX design (c3rro style system)

Following the existing brand system in `docs/c3rro_style/` exactly — this
is an established identity, not a fresh design exercise.

- **Color mapping**: choropleth fill uses the `blues` sequential ramp
  (`bluelight → bluedark`, from `c3rro_theme.js` `C3_PALETTES`) for data
  magnitude — deliberately not `main`, which opens on `bluegreen`. Brand
  teal (`bluegreen #4AB79F`) is reserved entirely for interactive/selected
  state (hover, active breadcrumb segment, selected toggle) — never used
  for data encoding, so "clickable" and "data value" stay visually
  distinct. The technology
  comparison chart uses the `mixed` 8-color categorical palette — one
  color per technology (solar/wind/biomass/hydro/nuclear/gsgk/combustion/
  storage maps cleanly to its 8 entries). Data-quality flags (unmapped
  units, truncated point layers) use the existing `Alert`/`Badge`
  warning/info variants unchanged.
- **Typography**: Jost for headings, the breadcrumb, and large numbers
  (matches existing `Card`/`MetricCard` title treatment in
  `c3rro_design_system.tsx`); Lato for body text, filter labels, axis and
  tooltip text — direct reuse of the established type roles.
- **Components**: reuse the existing `Card`, `Badge`, `Toggle`, `Alert`,
  `MetricCard` components from `c3rro_design_system.tsx` as the UI
  building blocks for the side panel, rather than building new ones.
- **Layout**: full-bleed map as the base layer — the map is the page, not
  a bordered widget in a grid. A translucent `Card`-styled panel floats
  docked to one side, containing the breadcrumb, metric/time toggles, and
  the linked technology chart. Reinforces the map-as-navigation model from
  Section 2 rather than competing with it for space.
- **Signature element**: capacity-scaled bubble markers (Section 2) are
  the one deliberate visual choice — they make the count-vs-capacity
  divergence (the dataset's core finding) visible on the map itself, at a
  glance, not just in the side chart. Everything else stays disciplined
  and on-brand rather than introducing further novelty.

## Testing

- **Backend**: extends the existing fixture-driven pattern
  (`tests/ingestion`, `tests/api`, `tests/common`) — new tests for the
  `capacity_rollup` builder and `/units/points` against synthetic
  fixtures, no real downloads needed, consistent with how Phases 1-3 were
  tested.
- **Frontend**: Vitest + React Testing Library for the map-driven state
  transitions (breadcrumb navigation, drill-down level changes, the linked
  panel reacting to map selection). API responses mocked, not hitting a
  live server.

## Out of scope / explicitly deferred

- Gemeinde-level boundary polygons (VG250 Gemeinde layer ingestion) —
  bubble markers cover this granularity for v1 without the added ingestion
  scope.
- Animated time slider, EEG tariff join, Postgres+Alembic, scheduled
  re-sync, density metric via VG250-EW — all already deferred in
  `architecture-plan.md` and unaffected by this design.
- Server-side grid/hex-bin aggregation for extremely dense Kreise — the
  point-cap-and-truncate approach (Section 3) is the v1 answer; grid
  binning is a reasonable future step only if a specific Kreis proves the
  cap too restrictive in practice.
