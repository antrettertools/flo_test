"""Smoke-test: confirm a downloaded VG250(-EW) dataset has AGS-coded regions
and can be converted to GeoJSON for the map layer.

Confirmed against BKG's official VG250/VG250-EW documentation (Stand
27.02.2026): the Kreis layer is VG250_KRS (table/layer name vg250_krs in
Geopackage) and the Bundesland layer is VG250_LAN (vg250_lan), both carrying
an AGS attribute directly. Prefer the VG250-EW variant and the Geopackage
format if given the choice on BKG's download page -- VG250-EW adds EWZ
(population) and KFL (area, km2) to every region for free, and Geopackage is
a single file per product instead of five shapefile sidecars per layer.

Manual prerequisite (can't be scripted -- BKG's portal is blocked from the
Claude sandbox that wrote this script, so the exact current download URL/page
layout could not be confirmed from there):

    1. Open https://gdz.bkg.bund.de/index.php/default/open-data/verwaltungsgebiete-1-250-000-stand-01-01-vg250-01-01.html
       (or the VG250-EW product page linked from the same catalog)
    2. Download the Geopackage package (EPSG:25832 / UTM32, ETRS89).
    3. Unzip it if it arrives as a zip.

Then run:

    pip install geopandas pyogrio
    python scripts/verify_vg250.py <path-to-vg250.gpkg-or-unzipped-folder>
"""
import glob
import os
import sys


def find_layer(root: str, gpkg_layer: str, shp_patterns: list[str]):
    """Return (source, layer_or_None) for either a .gpkg file or a folder of shapefiles."""
    if root.lower().endswith(".gpkg"):
        return root, gpkg_layer

    for pattern in shp_patterns:
        matches = glob.glob(os.path.join(root, "**", pattern), recursive=True)
        if matches:
            return matches[0], None

    gpkg_matches = glob.glob(os.path.join(root, "**", "*.gpkg"), recursive=True)
    if gpkg_matches:
        return gpkg_matches[0], gpkg_layer

    return None, None


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python scripts/verify_vg250.py <path-to-vg250.gpkg-or-unzipped-folder>")
        sys.exit(1)

    root = sys.argv[1]
    try:
        import geopandas as gpd
    except ImportError as e:
        print(f"FAIL: could not import geopandas ({e}).")
        print("-> Run: pip install geopandas pyogrio")
        sys.exit(1)

    levels = {
        "kreise": ("vg250_krs", ["*KRS*.shp", "*NUTS250_N3*.shp"]),
        "bundeslaender": ("vg250_lan", ["*LAN*.shp", "*NUTS250_N1*.shp"]),
    }

    any_found = False
    for level, (gpkg_layer, shp_patterns) in levels.items():
        source, layer = find_layer(root, gpkg_layer, shp_patterns)
        if source is None:
            print(f"MISSING: no shapefile or geopackage found for {level} under {root}")
            continue
        any_found = True

        gdf = gpd.read_file(source, layer=layer) if layer else gpd.read_file(source)
        print(f"\n{level}: loaded {source}" + (f" (layer={layer})" if layer else ""))
        print(f"  rows: {len(gdf)}")
        print(f"  columns: {list(gdf.columns)}")

        if "GF" in gdf.columns:
            before = len(gdf)
            gdf = gdf[gdf["GF"] == 4]
            print(f"  filtered GF==4 (land boundary only): {before} -> {len(gdf)} rows")

        ags_cols = [c for c in gdf.columns if "AGS" in c.upper() or "ARS" in c.upper()]
        print(f"  AGS/ARS-like columns: {ags_cols}")
        if ags_cols:
            print(f"  sample values: {gdf[ags_cols[0]].head(3).tolist()}")
        else:
            print("  WARNING: no AGS/ARS column found -- inspect `columns` above for the real field name.")

        for pop_col in ("EWZ", "KFL"):
            if pop_col in gdf.columns:
                print(f"  found {pop_col} (VG250-EW extra attribute) -- sample: {gdf[pop_col].head(3).tolist()}")

        gdf = gdf.to_crs(epsg=4326)
        out_dir = "data"
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"{level}.geo.json")
        gdf.to_file(out_path, driver="GeoJSON")
        print(f"  wrote {out_path}")

    if not any_found:
        print("\nFAIL: no matching shapefiles/geopackage found. Check the downloaded folder structure and re-run.")
        sys.exit(2)

    print("\nAll checks passed. Report the output above (columns + AGS field name, EWZ/KFL presence) so we can lock in the region-join design.")


if __name__ == "__main__":
    main()
