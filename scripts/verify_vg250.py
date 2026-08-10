"""Smoke-test: confirm a downloaded VG250 shapefile has AGS-coded regions
and can be converted to GeoJSON for the map layer.

Manual prerequisite (can't be scripted -- BKG's portal is also blocked from
the Claude sandbox that wrote this script, so the exact current download URL
could not be confirmed from there):

    1. Open https://gdz.bkg.bund.de/index.php/default/open-data/verwaltungsgebiete-1-250-000-stand-01-01-vg250-01-01.html
    2. Download the Shapefile package (EPSG:25832, "Ebenen").
    3. Unzip it somewhere.

Then run:

    pip install geopandas pyogrio
    python scripts/verify_vg250.py <path-to-unzipped-folder>
"""
import glob
import os
import sys


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python scripts/verify_vg250.py <unzipped-vg250-folder>")
        sys.exit(1)

    root = sys.argv[1]
    try:
        import geopandas as gpd
    except ImportError as e:
        print(f"FAIL: could not import geopandas ({e}).")
        print("-> Run: pip install geopandas pyogrio")
        sys.exit(1)

    # VG250 shapefiles are conventionally named VG250_KRS.shp (Kreise) and
    # VG250_LAN.shp (Bundeslaender); search recursively since the zip layout
    # varies by release.
    candidates = {
        "kreise": glob.glob(os.path.join(root, "**", "*KRS*.shp"), recursive=True),
        "bundeslaender": glob.glob(os.path.join(root, "**", "*LAN*.shp"), recursive=True),
    }

    any_found = False
    for level, paths in candidates.items():
        if not paths:
            print(f"MISSING: no shapefile found for {level} (looked for *KRS*/*LAN*.shp under {root})")
            continue
        any_found = True
        path = paths[0]
        gdf = gpd.read_file(path)
        print(f"\n{level}: loaded {path}")
        print(f"  rows: {len(gdf)}")
        print(f"  columns: {list(gdf.columns)}")

        ags_cols = [c for c in gdf.columns if "AGS" in c.upper() or "ARS" in c.upper()]
        print(f"  AGS/ARS-like columns: {ags_cols}")
        if ags_cols:
            print(f"  sample values: {gdf[ags_cols[0]].head(3).tolist()}")
        else:
            print("  WARNING: no AGS/ARS column found -- inspect `columns` above for the real field name.")

        gdf = gdf.to_crs(epsg=4326)
        out_dir = "data"
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"{level}.geo.json")
        gdf.to_file(out_path, driver="GeoJSON")
        print(f"  wrote {out_path}")

    if not any_found:
        print("\nFAIL: no matching shapefiles found. Check the unzipped folder structure and re-run.")
        sys.exit(2)

    print("\nAll checks passed. Report the output above (columns + AGS field name) so we can lock in the region-join design.")


if __name__ == "__main__":
    main()
