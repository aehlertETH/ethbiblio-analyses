import textwrap
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import ConnectionPatch, Rectangle
from matplotlib.transforms import Bbox
import numpy as np
import pandas as pd
from shapely.geometry import box

from core.asset import Asset, postprocess_excluded_institutions
from core.ror import drop_rows_without_coordinates, parse_ror_id, resolve_ror_metadata
from utility import get_unit_params_dict

try:
    import geopandas as gpd
except ModuleNotFoundError as exc:
    raise ModuleNotFoundError(
        "Missing dependency 'geopandas'. Install map dependencies with "
        "'pip install -r requirements.maps.txt'."
    ) from exc


asset = Asset(script_file=__file__)
unit_params_dict = get_unit_params_dict()


SOURCE_UNIT_ASSET = asset.base_dir.parent / "X_X_collaborationTopPartners"
SOURCE_ETHDOMAIN_ASSET = asset.base_dir.parent / "X_X_collaborationTopPartnersETHDOMAIN"
DOMAIN_REPORT = "ethdomain"
NATIONAL_COUNTRY_CODE = "CH"
NATIONAL_COUNTRY_CODE_ISO3 = "CHE"
ROR_CACHE_FILENAME = "ror_geo_cache.csv"

TOP_N = 10

FONTFAMILY = "DejaVu Sans"
FONTSIZE_STANDARD = 14
FONTSIZE_ANNOTATION = 12
FONTSIZE_TITLE = 20
LINESPACING_FOOTNOTE = 1.5

RC_PARAMS = {
    "font.family": FONTFAMILY,
    "font.size": FONTSIZE_STANDARD,
    "axes.titlesize": FONTSIZE_TITLE,
    "axes.facecolor": "white",
    "figure.facecolor": "white",
}

FOOTNOTE = ""

LAND_COLOR = "#EDEDED"
COLOR_MAIN = "#215CAF"
MARKER_COLOR = "#4D7DBF"
COUNTRY_BORDER_COLOR = "white"
COUNTRY_BORDER_WIDTH = 0.5

# Point style controls
POINT_BASE_SIZE = 2
POINT_BASE_COLOR = MARKER_COLOR
POINT_BASE_ALPHA = 0.65
POINT_BASE_EDGE_COLOR = None
POINT_BASE_EDGE_WIDTH = 0

POINT_TOP_SIZE = 26
POINT_TOP_COLOR = COLOR_MAIN
POINT_TOP_ALPHA = 0.85
POINT_TOP_EDGE_COLOR = "white"
POINT_TOP_EDGE_WIDTH = 1

MARKER_PROPS = {
    "marker": "o",
    "markersize": POINT_BASE_SIZE,
    "color": POINT_BASE_COLOR,
    "alpha": POINT_BASE_ALPHA,
    "edgecolors": POINT_BASE_EDGE_COLOR,
    "linewidth": POINT_BASE_EDGE_WIDTH,
}

HIGHLIGHT_PROPS = {
    "marker": "o",
    "markersize": POINT_TOP_SIZE,
    "color": POINT_TOP_COLOR,
    "alpha": POINT_TOP_ALPHA,
    "edgecolor": None,
    "linewidth": 0,
}

HIGHLIGHT_EDGES_PROPS = {
    "marker": "o",
    "markersize": POINT_TOP_SIZE,
    "color": POINT_TOP_COLOR,
    "alpha": POINT_TOP_ALPHA,
    "edgecolors": POINT_TOP_EDGE_COLOR,
    "linewidth": POINT_TOP_EDGE_WIDTH,
}
ROBINSON_PROJ4 = "+proj=robin +lon_0=0 +datum=WGS84 +units=m +no_defs"
WORLD_EXTENT = (-180, -60, 180, 90)
ZOOM_EXTENT = (-10, 35.8, 21.5, 61)  # (xmin_lon, ymin_lat, xmax_lon, ymax_lat)
INSET_AX_BOUNDS = (
    -0.095,
    0.004,
    0.5,
    0.5,
)  # (left, bottom, width, height) in parent axes
EXPORT_BBOX_FRACTION = (
    0.04,
    0.00,
    0.96,
    1.00,
)  # (left, bottom, right, top) crop within tight figure bbox


def get_inst_label(inst: str) -> str:
    params = unit_params_dict.get(inst, {})
    return params.get("InstShort") or params.get("InstNameNonTex") or inst.upper()


def source_raw_path_for_inst(inst: str) -> Path:
    """
    Meta-asset dependency:
    - units -> X_X_collaborationTopPartners/<inst>/data_raw_partners.csv
    - ethdomain -> X_X_collaborationTopPartnersETHDOMAIN/ethdomain/data_raw_partners.csv
    """
    base = SOURCE_ETHDOMAIN_ASSET if inst == DOMAIN_REPORT else SOURCE_UNIT_ASSET
    return base / inst / "data_raw_partners.csv"


def load_source_raw_df(inst: str) -> pd.DataFrame:
    path = source_raw_path_for_inst(inst)
    if not path.exists():
        raise FileNotFoundError(
            "International geo meta asset depends on canonical top-partner assets. "
            f"Missing: {path}"
        )

    df = pd.read_csv(path)
    if "country_code" not in df.columns:
        df["country_code"] = ""
    codes = df["country_code"].astype("string").fillna("").str.upper()

    for col in ["FLAG_IS_CORE_UNIT", "FLAG_IS_CHILD_OF_CORE_UNIT", "FLAG_IS_ETHDOMAIN_INST"]:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    return df.loc[
        codes.ne(NATIONAL_COUNTRY_CODE)
        & df["FLAG_IS_CORE_UNIT"].eq(0)
        & df["FLAG_IS_CHILD_OF_CORE_UNIT"].eq(0)
        & df["FLAG_IS_ETHDOMAIN_INST"].eq(0)
    ].copy()


def query_institution_metadata(institution_ids: list[int]) -> str:
    if not institution_ids:
        return """
            SELECT
                CAST(NULL AS BIGINT) AS institution_id,
                CAST(NULL AS VARCHAR) AS ror,
                CAST(NULL AS VARCHAR) AS institution_name,
                CAST(NULL AS VARCHAR) AS country_code,
                CAST(NULL AS VARCHAR) AS country_name
            WHERE FALSE
        """

    ids_sql = ", ".join(str(int(i)) for i in institution_ids)
    return f"""
        SELECT
            di.institution_id,
            di.ror,
            di.name AS institution_name,
            dc.country_code,
            COALESCE(oac.display_name, dc.country_code) AS country_name
        FROM core.dim_institution di
        LEFT JOIN core.dim_country dc
          ON dc.country_id = di.country_id
        LEFT JOIN augmented.openalex_countries oac
          ON oac.code = dc.country_code
        WHERE di.institution_id IN ({ids_sql})
    """


def fetch_institution_metadata(con, institution_ids: list[int]) -> pd.DataFrame:
    ids = sorted(
        {
            int(v)
            for v in pd.to_numeric(pd.Series(institution_ids), errors="coerce").dropna().tolist()
        }
    )
    if not ids:
        return pd.DataFrame(
            columns=["institution_id", "ror", "institution_name", "country_code", "country_name"]
        )
    return con.execute(query_institution_metadata(ids)).df()


def build_plot_input(source_df: pd.DataFrame, metadata_df: pd.DataFrame) -> pd.DataFrame:
    out = source_df.copy()
    out["institution_id"] = pd.to_numeric(out["institution_id"], errors="coerce")
    out = out[out["institution_id"].notna()].copy()
    out["institution_id"] = out["institution_id"].astype(int)

    metadata = metadata_df.copy()
    metadata["institution_id"] = pd.to_numeric(metadata["institution_id"], errors="coerce")
    metadata = metadata[metadata["institution_id"].notna()].copy()
    metadata["institution_id"] = metadata["institution_id"].astype(int)
    metadata = metadata.drop_duplicates(subset=["institution_id"], keep="first")
    metadata = metadata.rename(
        columns={
            "institution_name": "institution_name_meta",
            "country_code": "country_code_meta",
        }
    )

    out = out.merge(metadata, on="institution_id", how="left")
    out["institution_name"] = out["institution_name_meta"].fillna(out["institution_name"])
    out["country_code"] = out["country_code_meta"].fillna(out["country_code"])
    out["country_name"] = out["country_name"].fillna(out["country_code"])
    out["collaboration_count"] = pd.to_numeric(out["frac_count"], errors="coerce")

    return out[
        [
            "institution_id",
            "ror",
            "institution_name",
            "country_code",
            "country_name",
            "collaboration_count",
        ]
    ].copy()


def resolve_ror_coordinates(ror_ids: list[str], cache_path: Path) -> pd.DataFrame:
    return resolve_ror_metadata(
        ror_ids,
        local_cache_path=cache_path,
        include_acronym=False,
        context=asset.base_dir.name,
    )


def swiss_geometry(world_50: gpd.GeoDataFrame):
    mask = pd.Series(False, index=world_50.index)

    if "map_iso2_code" in world_50.columns:
        mask = mask | world_50["map_iso2_code"].astype("string").str.upper().eq(
            NATIONAL_COUNTRY_CODE
        )
    if "map_iso3_code" in world_50.columns:
        mask = mask | world_50["map_iso3_code"].astype("string").str.upper().eq(
            NATIONAL_COUNTRY_CODE_ISO3
        )
    if "map_country_name" in world_50.columns:
        mask = mask | world_50["map_country_name"].astype("string").str.lower().eq(
            "switzerland"
        )

    swiss = world_50.loc[mask]
    if swiss.empty:
        return None
    return swiss.geometry.unary_union


def drop_points_located_in_switzerland(
    df: pd.DataFrame, world_50: gpd.GeoDataFrame
) -> pd.DataFrame:
    out = df.copy()
    if out.empty:
        return out
    if "latitude" not in out.columns or "longitude" not in out.columns:
        return out

    swiss = swiss_geometry(world_50)
    if swiss is None:
        return out

    coord_mask = out["latitude"].notna() & out["longitude"].notna()
    if not coord_mask.any():
        return out

    points = gpd.GeoSeries(
        gpd.points_from_xy(
            out.loc[coord_mask, "longitude"],
            out.loc[coord_mask, "latitude"],
        ),
        index=out.index[coord_mask],
        crs="EPSG:4326",
    )
    in_switzerland = points.apply(swiss.covers)
    if not in_switzerland.any():
        return out

    return out.loc[~out.index.isin(in_switzerland[in_switzerland].index)].copy()


def load_world_map(path: Path) -> gpd.GeoDataFrame:
    world = gpd.read_file(path)

    iso3_candidates = ["ISO_A3_EH", "ADM0_A3", "ISO_A3", "SOV_A3"]
    iso2_candidates = ["ISO_A2_EH", "ISO_A2"]
    name_candidates = ["NAME_EN", "NAME", "ADMIN"]

    iso3_col = next((c for c in iso3_candidates if c in world.columns), None)
    iso2_col = next((c for c in iso2_candidates if c in world.columns), None)
    name_col = next((c for c in name_candidates if c in world.columns), None)

    if not iso3_col or not name_col:
        raise ValueError(
            "Expected ISO/name columns were not found in Natural Earth map file."
        )

    cols = [name_col, iso3_col, "geometry"]
    rename = {name_col: "map_country_name", iso3_col: "map_iso3_code"}
    if iso2_col:
        cols.insert(2, iso2_col)
        rename[iso2_col] = "map_iso2_code"

    out = world[cols].rename(columns=rename)
    if "map_iso2_code" not in out.columns:
        out["map_iso2_code"] = None
    return out


def load_world_maps() -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    repo_root = Path(__file__).resolve().parents[2]

    candidates_50 = [
        asset.base_dir / "ne_50m_admin_0_countries.zip",
        repo_root / "core" / "maps" / "ne_50m_admin_0_countries.zip",
    ]
    candidates_110 = [
        asset.base_dir / "ne_110m_admin_0_countries.zip",
        repo_root / "core" / "maps" / "ne_110m_admin_0_countries.zip",
    ]

    p50 = next((p for p in candidates_50 if p.is_file()), None)
    p110 = next((p for p in candidates_110 if p.is_file()), None)

    missing: list[str] = []
    if p50 is None:
        missing.append(" or ".join(str(p) for p in candidates_50))
    if p110 is None:
        missing.append(" or ".join(str(p) for p in candidates_110))
    if missing:
        raise FileNotFoundError(
            "Missing Natural Earth map file(s): " + "; ".join(missing)
        )

    return load_world_map(p50), load_world_map(p110)


def prepare_plot_df(
    raw_df: pd.DataFrame,
    world_50: gpd.GeoDataFrame,
    ror_cache_path: Path,
    apply_postprocessing: bool = True,
) -> pd.DataFrame:
    out = raw_df.copy()
    if apply_postprocessing:
        out = postprocess_excluded_institutions(
            out, institution_id_col="institution_id"
        )

    out["collaboration_count"] = pd.to_numeric(
        out["collaboration_count"], errors="coerce"
    ).fillna(0.0)
    out = out[out["collaboration_count"] > 0].copy()
    out["institution_name"] = (
        out["institution_name"].fillna("Unknown institution").astype(str)
    )

    out = out.sort_values(
        ["collaboration_count", "institution_name", "institution_id"],
        ascending=[False, True, True],
    ).reset_index(drop=True)
    out = out.rename(columns={"institution_name": "name"})
    out["ror_id"] = out["ror"].apply(parse_ror_id)

    ror_ids = sorted(out["ror_id"].dropna().astype(str).unique().tolist())
    if ror_ids:
        cache_df = resolve_ror_coordinates(ror_ids, ror_cache_path)
        out = out.merge(cache_df, on="ror_id", how="left", suffixes=("", "_cache"))
        if "lat_cache" in out.columns:
            out["lat"] = out["lat_cache"]
        if "lon_cache" in out.columns:
            out["lon"] = out["lon_cache"]
        out = out.drop(
            columns=[c for c in ["lat_cache", "lon_cache"] if c in out.columns]
        )
    else:
        out["lat"] = np.nan
        out["lon"] = np.nan

    out["latitude"] = pd.to_numeric(out["lat"], errors="coerce")
    out["longitude"] = pd.to_numeric(out["lon"], errors="coerce")
    mode_label = "prepost" if not apply_postprocessing else "post"
    out = drop_rows_without_coordinates(
        out,
        lat_col="latitude",
        lon_col="longitude",
        context=f"{asset.base_dir.name}:{mode_label}",
    )
    out = drop_points_located_in_switzerland(out, world_50)

    out = out.sort_values(
        ["collaboration_count", "name", "institution_id"], ascending=[False, True, True]
    ).reset_index(drop=True)
    out["rank_desc"] = out.index + 1
    out["topN"] = out["rank_desc"] <= TOP_N

    iso_map = (
        world_50[["map_iso2_code", "map_iso3_code"]]
        .dropna()
        .drop_duplicates(subset=["map_iso2_code"], keep="first")
        .rename(columns={"map_iso2_code": "country_code", "map_iso3_code": "iso3_code"})
    )
    out = out.merge(iso_map, on="country_code", how="left")

    out = out.sort_values(
        ["rank_desc", "name", "institution_id"], ascending=[True, True, True]
    ).reset_index(drop=True)
    out = out.reset_index()
    return out


def build_points_gdf(plot_df: pd.DataFrame) -> gpd.GeoDataFrame:
    sel = plot_df.dropna(subset=["longitude", "latitude"]).copy()
    return gpd.GeoDataFrame(
        sel,
        geometry=gpd.points_from_xy(sel["longitude"], sel["latitude"]),
        crs="EPSG:4326",
    )


def build_choropleth_maps(
    points_gdf: gpd.GeoDataFrame,
    world_50: gpd.GeoDataFrame,
    world_110: gpd.GeoDataFrame,
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    collab_iso3 = set(points_gdf["iso3_code"].dropna().astype(str).tolist())

    m50 = world_50.assign(is_collab=lambda x: x["map_iso3_code"].isin(collab_iso3))
    m110 = world_110.assign(is_collab=lambda x: x["map_iso3_code"].isin(collab_iso3))
    return m50, m110


def draw_base_countries(
    ax: mpl.axes.Axes,
    map_50: gpd.GeoDataFrame,
    map_110: gpd.GeoDataFrame,
    extent: tuple[float, float, float, float],
    scale: str = "110",
    if_choro: bool = False,
    choro_cmap: mpl.colors.Colormap | None = None,
) -> None:
    extent_norm = normalize_extent(extent)
    natearth = map_50 if scale == "50" else map_110

    if if_choro:
        choro_props = {
            "edgecolor": COUNTRY_BORDER_COLOR,
            "linewidth": COUNTRY_BORDER_WIDTH,
            "cmap": choro_cmap,
            "column": "is_collab",
        }
        natearth.clip(extent_norm).to_crs(ROBINSON_PROJ4).plot(ax=ax, **choro_props)
    else:
        bglayer_props = {
            "color": LAND_COLOR,
            "edgecolor": COUNTRY_BORDER_COLOR,
            "linewidth": COUNTRY_BORDER_WIDTH,
        }
        natearth.clip(extent_norm).to_crs(ROBINSON_PROJ4).plot(ax=ax, **bglayer_props)


def draw_equal_points(
    ax: mpl.axes.Axes, gdf_sel: gpd.GeoDataFrame, project: bool = True, **plot_props
) -> None:
    if gdf_sel.empty:
        return
    plot_gdf = gdf_sel.to_crs(ROBINSON_PROJ4) if project else gdf_sel
    plot_gdf.plot(ax=ax, **plot_props)


def normalize_extent(
    extent: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    if len(extent) != 4:
        raise ValueError(
            "Extent must be a tuple of four numeric values: (xmin, ymin, xmax, ymax)."
        )

    xmin, ymin, xmax, ymax = [float(v) for v in extent]
    xmin, xmax = sorted((xmin, xmax))
    ymin, ymax = sorted((ymin, ymax))

    if xmin == xmax or ymin == ymax:
        raise ValueError(f"Extent is empty after normalization: {extent!r}")

    return xmin, ymin, xmax, ymax


def projected_extent(
    extent: tuple[float, float, float, float], crs: str = ROBINSON_PROJ4
) -> tuple[float, float, float, float]:
    xmin, ymin, xmax, ymax = normalize_extent(extent)
    bbox = gpd.GeoDataFrame(
        geometry=[box(xmin, ymin, xmax, ymax)], crs="EPSG:4326"
    ).to_crs(crs)
    x0, y0, x1, y1 = bbox.total_bounds
    return float(x0), float(y0), float(x1), float(y1)


def export_bbox_inches(
    fig: mpl.figure.Figure, crop_frac: tuple[float, float, float, float]
) -> Bbox:
    left, bottom, right, top = crop_frac
    left, right = sorted((float(left), float(right)))
    bottom, top = sorted((float(bottom), float(top)))

    if not (0 <= left < right <= 1 and 0 <= bottom < top <= 1):
        raise ValueError(
            f"Invalid EXPORT_BBOX_FRACTION: {crop_frac!r}. Expected 0<=left<right<=1 and 0<=bottom<top<=1."
        )

    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    tight_bbox = fig.get_tightbbox(renderer)

    if tight_bbox is None:
        fig_w, fig_h = fig.get_size_inches()
        tight_bbox = Bbox.from_extents(0, 0, fig_w, fig_h)

    x0, y0, x1, y1 = tight_bbox.extents
    w = x1 - x0
    h = y1 - y0
    return Bbox.from_extents(
        x0 + left * w, y0 + bottom * h, x0 + right * w, y0 + top * h
    )


def add_footnote(ax: mpl.axes.Axes, text: str) -> None:
    ax.annotate(
        text,
        xy=(1, -0.08),
        xycoords="axes fraction",
        ha="right",
        va="top",
        fontsize=FONTSIZE_ANNOTATION,
        linespacing=LINESPACING_FOOTNOTE,
    )


def plot_geo_wide(
    points_gdf: gpd.GeoDataFrame,
    map_50: gpd.GeoDataFrame,
    map_110: gpd.GeoDataFrame,
    inst_label: str,
) -> mpl.figure.Figure:
    choro_cmap = mpl.colors.LinearSegmentedColormap.from_list(
        "choro_bg", [(0.0, LAND_COLOR), (1.0, "#d3deef")]
    )

    with mpl.rc_context(RC_PARAMS):
        fig, ax = plt.subplots(figsize=(12, 10), dpi=450)
        zoom_extent_proj = projected_extent(ZOOM_EXTENT)

        draw_base_countries(
            ax, map_50, map_110, WORLD_EXTENT, if_choro=True, choro_cmap=choro_cmap
        )

        draw_equal_points(
            ax, points_gdf, **MARKER_PROPS, label="Collaborating institution"
        )
        draw_equal_points(
            ax,
            points_gdf[points_gdf["topN"]],
            **HIGHLIGHT_PROPS,
            label=f"Top {TOP_N} collaborating institutions",
        )
        draw_equal_points(ax, points_gdf[points_gdf["topN"]], **HIGHLIGHT_EDGES_PROPS)

        if ax.collections:
            ax.collections[-1].set_facecolor("none")

        iax1 = ax.inset_axes(INSET_AX_BOUNDS, xticks=[], yticks=[])

        zoom_box_proj = box(*zoom_extent_proj)
        map110_zoom = map_110.to_crs(ROBINSON_PROJ4).clip(zoom_box_proj)
        points_zoom = points_gdf.to_crs(ROBINSON_PROJ4).clip(zoom_box_proj)
        points_zoom_top = (
            points_gdf[points_gdf["topN"]].to_crs(ROBINSON_PROJ4).clip(zoom_box_proj)
        )

        choro_props = {
            "edgecolor": COUNTRY_BORDER_COLOR,
            "linewidth": COUNTRY_BORDER_WIDTH,
            "cmap": choro_cmap,
            "column": "is_collab",
        }
        map110_zoom.plot(ax=iax1, **choro_props)
        draw_equal_points(iax1, points_zoom, project=False, **MARKER_PROPS)
        draw_equal_points(iax1, points_zoom_top, project=False, **HIGHLIGHT_PROPS)
        draw_equal_points(iax1, points_zoom_top, project=False, **HIGHLIGHT_EDGES_PROPS)

        x0, y0, x1, y1 = zoom_extent_proj
        iax1.set_xlim(x0, x1)
        iax1.set_ylim(y0, y1)
        iax1.margins(0)

        ax.set_axis_off()
        conn_style = {"edgecolor": "black", "linewidth": 0.5, "alpha": 1}

        zoom_rect = Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, **conn_style)
        ax.add_patch(zoom_rect)

        connector_lower = ConnectionPatch(
            xyA=(x1, y0),
            coordsA=ax.transData,
            axesA=ax,
            xyB=(1, 0),
            coordsB=iax1.transAxes,
            axesB=iax1,
            **conn_style,
        )
        connector_upper = ConnectionPatch(
            xyA=(x0, y1),
            coordsA=ax.transData,
            axesA=ax,
            xyB=(0, 1),
            coordsB=iax1.transAxes,
            axesB=iax1,
            **conn_style,
        )
        ax.add_artist(connector_lower)
        ax.add_artist(connector_upper)

        iax1.patch.set_edgecolor(conn_style["edgecolor"])
        iax1.patch.set_linewidth(conn_style["linewidth"])
        iax1.patch.set_alpha(conn_style["alpha"])
        iax1.patch.set_facecolor("none")

        # legend = ax.legend(
        # bbox_to_anchor=(1, 0.95),
        # loc="upper left",
        # fontsize=FONTSIZE_STANDARD,
        # handlelength=0.5,
        # borderpad=0,
        # frameon=False,
        # )

        # inst_info = f"{points_gdf.shape[0]} institutions in {points_gdf['country_code'].nunique()} countries"
        # inst_info = ""
        # ax.set_title(
        #     f"Collaborating institutions of {inst_label}: {inst_info}",
        #     pad=FONTSIZE_TITLE * 1.25,
        #     x=0.42,
        # )

        footnote_expanded = FOOTNOTE.replace("<br>", "\n")
        add_footnote(ax, footnote_expanded)

        # _ = legend

    return fig


def main() -> None:
    world_50, world_110 = load_world_maps()
    ror_cache_path = asset.base_dir / ROR_CACHE_FILENAME

    for inst, con in asset.iterate_institutions():
        # 1) Reuse the external-partner calculations from the table asset and enrich
        # them only with metadata needed for geocoding and labeling.
        source_df = load_source_raw_df(inst)
        metadata_df = fetch_institution_metadata(con, source_df["institution_id"].tolist())
        raw_df = build_plot_input(source_df, metadata_df)

        # 2) Transform to plot-ready table.
        plot_df_prepost = prepare_plot_df(
            raw_df, world_50, ror_cache_path, apply_postprocessing=False
        )
        plot_df = prepare_plot_df(
            raw_df, world_50, ror_cache_path, apply_postprocessing=True
        )
        points_gdf = build_points_gdf(plot_df)
        map50_plot, map110_plot = build_choropleth_maps(points_gdf, world_50, world_110)

        # 3) Draw figure.
        fig = plot_geo_wide(points_gdf, map50_plot, map110_plot, get_inst_label(inst))

        out = asset.inst_dir(inst)
        raw_df.to_csv(out / "data_raw.csv", index=False)
        plot_df_prepost.to_csv(out / "data_prepost.csv", index=False)
        plot_df.to_csv(out / "data.csv", index=False)
        plot_df.to_csv(out / "data_for_plot.csv", index=False)

        export_bbox = export_bbox_inches(fig, EXPORT_BBOX_FRACTION)
        fig.savefig(out / "figure.svg", dpi=300, bbox_inches=export_bbox)
        fig.savefig(out / "figure.png", dpi=300, bbox_inches=export_bbox, facecolor="white")
        fig.savefig(out / "figure.pdf", dpi=300, bbox_inches=export_bbox)
        plt.close(fig)


if __name__ == "__main__":
    main()
