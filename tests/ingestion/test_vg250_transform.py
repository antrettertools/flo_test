import geopandas as gpd
from shapely.geometry import Polygon

from ingestion.vg250_transform import filter_land_boundary, to_geojson_frame, to_region_rows


def _poly() -> Polygon:
    return Polygon([(0, 0), (0, 1), (1, 1), (1, 0)])


def test_filter_land_boundary_drops_gf_2_sea_duplicate():
    gdf = gpd.GeoDataFrame(
        {"AGS": ["01001", "01001"], "GEN": ["Flensburg", "Flensburg"], "GF": [4, 2]},
        geometry=[_poly(), _poly()],
    )

    filtered = filter_land_boundary(gdf)

    assert len(filtered) == 1
    assert filtered.iloc[0]["GF"] == 4


def test_filter_land_boundary_noop_without_gf_column():
    gdf = gpd.GeoDataFrame({"AGS": ["01001"], "GEN": ["Flensburg"]}, geometry=[_poly()])

    filtered = filter_land_boundary(gdf)

    assert len(filtered) == 1


def test_to_geojson_frame_trims_and_renames_columns():
    gdf = gpd.GeoDataFrame(
        {"AGS": ["01001"], "GEN": ["Flensburg"], "GF": [4], "BEZ": ["Kreis"]}, geometry=[_poly()]
    )

    trimmed = to_geojson_frame(gdf)

    assert list(trimmed.columns) == ["ags", "name", "geometry"]
    assert trimmed.iloc[0]["ags"] == "01001"


def test_to_region_rows_derives_kreis_parent_ags_from_land():
    kreise = gpd.GeoDataFrame({"AGS": ["01001"], "GEN": ["Flensburg"]}, geometry=[_poly()])
    laender = gpd.GeoDataFrame({"AGS": ["01"], "GEN": ["Schleswig-Holstein"]}, geometry=[_poly()])

    rows = to_region_rows(kreise, laender)

    kreis_row = next(r for r in rows if r["level"] == "kreis")
    land_row = next(r for r in rows if r["level"] == "land")
    assert kreis_row == {"ags": "01001", "level": "kreis", "name": "Flensburg", "parent_ags": "01"}
    assert land_row == {"ags": "01", "level": "land", "name": "Schleswig-Holstein", "parent_ags": None}
