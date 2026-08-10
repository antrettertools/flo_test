"""Transforms a downloaded VG250(-EW) Geopackage/Shapefile into:
  - static GeoJSON boundary files for the frontend map (GF==4 filtered, EPSG:4326)
  - Region rows (ags, level, name, parent_ags) for the database

Confirmed against a real local VG250 download: VG250_KRS/VG250_LAN (or
vg250_krs/vg250_lan in Geopackage) carry a direct AGS attribute, and GF==4
is the real land boundary (GF==2 is a duplicate sea-facing polygon some
coastal Kreise carry, and must be filtered out).

The pure transform functions (filter_land_boundary, to_geojson_frame,
to_region_rows) are unit-tested against small synthetic GeoDataFrames. File
I/O (_find_source, _load_level, transform_vg250) requires a real downloaded
dataset and is exercised only in Phase 2, on the user's machine.
"""
from __future__ import annotations

import glob
import os
from pathlib import Path

import geopandas as gpd

from ingestion.config import PROCESSED_DIR, VG250_KREIS_LAYER, VG250_LAND_LAYER


def filter_land_boundary(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Drop the duplicate GF==2 (sea-facing) polygon some coastal Kreise carry."""
    if "GF" in gdf.columns:
        return gdf[gdf["GF"] == 4].copy()
    return gdf


def to_geojson_frame(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Trim to the properties the frontend map actually needs."""
    return gdf[["AGS", "GEN", "geometry"]].rename(columns={"AGS": "ags", "GEN": "name"})


def to_region_rows(kreise: gpd.GeoDataFrame, bundeslaender: gpd.GeoDataFrame) -> list[dict]:
    rows: list[dict] = []
    for _, r in bundeslaender.iterrows():
        rows.append({"ags": r["AGS"], "level": "land", "name": r["GEN"], "parent_ags": None})
    for _, r in kreise.iterrows():
        rows.append(
            {"ags": r["AGS"], "level": "kreis", "name": r["GEN"], "parent_ags": r["AGS"][:2]}
        )
    return rows


def _find_source(root: str, gpkg_layer: str, shp_patterns: list[str]) -> tuple[str, str | None]:
    if root.lower().endswith(".gpkg"):
        return root, gpkg_layer
    for pattern in shp_patterns:
        matches = glob.glob(os.path.join(root, "**", pattern), recursive=True)
        if matches:
            return matches[0], None
    gpkg_matches = glob.glob(os.path.join(root, "**", "*.gpkg"), recursive=True)
    if gpkg_matches:
        return gpkg_matches[0], gpkg_layer
    raise FileNotFoundError(f"No shapefile or geopackage found under {root} for layer {gpkg_layer}")


def _load_level(root: str, gpkg_layer: str, shp_patterns: list[str]) -> gpd.GeoDataFrame:
    source, layer = _find_source(root, gpkg_layer, shp_patterns)
    gdf = gpd.read_file(source, layer=layer) if layer else gpd.read_file(source)
    gdf = filter_land_boundary(gdf)
    return gdf.to_crs(epsg=4326)


def transform_vg250(root: str, output_dir: Path = PROCESSED_DIR) -> dict[str, gpd.GeoDataFrame]:
    """Load, filter, reproject VG250 Kreis+Land layers and write GeoJSON assets."""
    output_dir.mkdir(parents=True, exist_ok=True)

    kreise = _load_level(root, VG250_KREIS_LAYER, ["*KRS*.shp"])
    bundeslaender = _load_level(root, VG250_LAND_LAYER, ["*LAN*.shp"])

    to_geojson_frame(kreise).to_file(output_dir / "kreise.geo.json", driver="GeoJSON")
    to_geojson_frame(bundeslaender).to_file(output_dir / "bundeslaender.geo.json", driver="GeoJSON")

    return {"kreise": kreise, "bundeslaender": bundeslaender}
