import json
import sqlite3
import textwrap
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import urlopen

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from core.asset import Asset, postprocess_excluded_institutions
from core.ror import drop_rows_without_coordinates, resolve_ror_metadata
from assets.openalex_annotation_common import (
    add_annotation_symbols_to_labels,
    figure_notes_for_df,
)
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

REPO_ROOT = Path(__file__).resolve().parents[2]


ROR_API_BASE = "https://api.ror.org/v2/organizations/"
ROR_CACHE_FILENAME = "ror_geo_cache.csv"
CANTON_FILE_CANDIDATES = [
    "ch_cantons.geojson",
    "ch_cantons.gpkg",
    "swiss_cantons.geojson",
    "swiss_cantons.gpkg",
    "swissBOUNDARIES3D_1_5_LV95_LN02.gpkg",
]
CANTON_LAYER_HINTS = ("kanton", "canton", "adm1")

TOP_N = 10
DOMAIN_REPORT = "ethdomain"
COUNTING_MODE = "fractional"  # full | fractional; controls ranking/topN and active count column
EXCLUDE_ETHDOMAIN_MEMBER_UNITS = True
APPLY_CHILD_INSTITUTION_POSTPROCESSING = True

FONTFAMILY = "DejaVu Sans"
FONTSIZE_STANDARD = 13
FONTSIZE_TITLE = 18
FIGURE_NOTE_FONT_SIZE = 6
FIGURE_NOTE_TEXT_COLOR = "#4A4A4A"
FIGURE_NOTE_WRAP_WIDTH = 145
FIGURE_NOTE_X = 0.015
FIGURE_NOTE_Y = 0.015

RC_PARAMS = {
    "font.family": FONTFAMILY,
    "font.size": FONTSIZE_STANDARD,
    "axes.titlesize": FONTSIZE_TITLE,
    "axes.facecolor": "white",
    "figure.facecolor": "white",
}

# Point style controls
POINT_BASE_SIZE = 18
POINT_BASE_COLOR = "#4D7DBF"
POINT_BASE_ALPHA = 0.58
POINT_BASE_EDGE_COLOR = "none"
POINT_BASE_EDGE_WIDTH = 0.0

POINT_TOP_SIZE = 60
POINT_TOP_COLOR = "#215CAF"
POINT_TOP_ALPHA = 0.86
POINT_TOP_EDGE_COLOR = "white"
POINT_TOP_EDGE_WIDTH = 0.9

# Top institution label controls
LABEL_TOP_INSTITUTIONS = True
LABEL_USE_ROR_ACRONYM = True
LABEL_FALLBACK_TO_NAME = True
LABEL_FONT_SIZE = 7
LABEL_TEXT_COLOR = "#0F2E59"
LABEL_BOX_FACE = "white"
LABEL_BOX_ALPHA = 0.8
LABEL_OFFSET_POINTS = [
    (8, 8),
    (8, -8),
    (-8, 8),
    (-8, -8),
    (10, 0),
    (-10, 0),
    (0, 10),
    (0, -10),
    (14, 6),
    (14, -6),
    (-14, 6),
    (-14, -6),
]

SWISS_FILL_COLOR = "#EBEEF3"
SWISS_BORDER_COLOR = "#A9B4C0"
CANTON_BORDER_COLOR = "#C8CFD8"

MAP_CRS = "EPSG:2056"


def get_inst_label(inst: str) -> str:
    params = unit_params_dict.get(inst, {})
    return params.get("InstShort") or params.get("InstNameNonTex") or inst.upper()


def get_active_count_column(counting_mode: str = COUNTING_MODE) -> str:
    if counting_mode == "full":
        return "collaboration_count_full"
    if counting_mode == "fractional":
        return "collaboration_count_frac"
    raise ValueError("COUNTING_MODE must be 'full' or 'fractional'")


def get_sort_columns(counting_mode: str = COUNTING_MODE) -> tuple[list[str], list[bool]]:
    if counting_mode == "full":
        return (
            [
                "collaboration_count_full",
                "collaboration_count_frac",
                "institution_name",
                "institution_id",
            ],
            [False, False, True, True],
        )
    if counting_mode == "fractional":
        return (
            [
                "collaboration_count_frac",
                "collaboration_count_full",
                "institution_name",
                "institution_id",
            ],
            [False, False, True, True],
        )
    raise ValueError("COUNTING_MODE must be 'full' or 'fractional'")


def should_exclude_report_institutions(inst: str) -> bool:
    if inst == DOMAIN_REPORT:
        return EXCLUDE_ETHDOMAIN_MEMBER_UNITS
    return True


def query_collaboration_institutions_ch(inst: str, y0: int, y1: int) -> str:
    active_count_column = get_active_count_column()
    order_by_cols, ascending = get_sort_columns()
    order_by_sql = ", ".join(
        f"{col} {'ASC' if is_ascending else 'DESC'}"
        for col, is_ascending in zip(order_by_cols, ascending, strict=True)
    )
    exclusion_clause = ""
    if should_exclude_report_institutions(inst):
        exclusion_clause = f"""
              AND wii.institution_id NOT IN (
                  SELECT institution_id
                  FROM reports.report_institutions_ids
                  WHERE report_name = '{inst}'
              )"""

    return f"""
        WITH inst_pubs AS (
            SELECT DISTINCT rm.work_id
            FROM reports.report_membership rm
            JOIN core.work w
              ON w.work_id = rm.work_id
            WHERE rm.report_name = '{inst}'
              AND w.publication_year BETWEEN {y0} AND {y1}
        ),

        collab_links AS (
            SELECT DISTINCT
                wii.institution_id,
                di.ror,
                di.name AS institution_name,
                ip.work_id,
                wii.weight_frac
            FROM inst_pubs ip
            JOIN marts.work_institution_info wii
              ON wii.work_id = ip.work_id
            JOIN core.dim_institution di
              ON di.institution_id = wii.institution_id
            JOIN core.dim_country dc
              ON dc.country_id = di.country_id
            WHERE dc.country_code = 'CH'{exclusion_clause}
        ),

        collab_institutions AS (
            SELECT
                institution_id,
                ror,
                institution_name,
                COUNT(DISTINCT work_id) AS collaboration_count_full,
                SUM(weight_frac) AS collaboration_count_frac
            FROM collab_links
            GROUP BY 1, 2, 3
        )

        SELECT
            institution_id,
            ror,
            institution_name,
            collaboration_count_full,
            ROUND(collaboration_count_frac, 6) AS collaboration_count_frac,
            {active_count_column} AS collaboration_count,
            ROW_NUMBER() OVER (
                ORDER BY {order_by_sql}
            ) AS rank_desc
        FROM collab_institutions
        ORDER BY {order_by_sql};
    """


def parse_ror_id(ror_url: str) -> str | None:
    if not isinstance(ror_url, str) or not ror_url.strip():
        return None
    parsed = urlparse(ror_url.strip())
    ror_id = parsed.path.strip("/").split("/")[-1]
    return ror_id or None


def load_ror_cache(cache_path: Path) -> pd.DataFrame:
    if not cache_path.is_file():
        return pd.DataFrame(columns=["ror_id", "lat", "lon", "acronym"])

    cache_df = pd.read_csv(cache_path)
    for col in ["ror_id", "lat", "lon", "acronym"]:
        if col not in cache_df.columns:
            cache_df[col] = np.nan

    cache_df = cache_df[["ror_id", "lat", "lon", "acronym"]].copy()
    cache_df["ror_id"] = cache_df["ror_id"].astype(str)
    cache_df["lat"] = pd.to_numeric(cache_df["lat"], errors="coerce")
    cache_df["lon"] = pd.to_numeric(cache_df["lon"], errors="coerce")
    cache_df["acronym"] = cache_df["acronym"].astype("string")
    cache_df = cache_df.drop_duplicates(subset=["ror_id"], keep="last")
    return cache_df


def extract_ror_acronym(payload: dict) -> str | None:
    names = payload.get("names") or []
    for item in names:
        types = [str(t).lower() for t in (item.get("types") or [])]
        if "acronym" in types:
            value = str(item.get("value") or "").strip()
            if value:
                return value

    acronyms = payload.get("acronyms") or []
    if isinstance(acronyms, list):
        for value in acronyms:
            v = str(value).strip()
            if v:
                return v

    return None


def fetch_ror_metadata(ror_id: str) -> tuple[float, float, str | None]:
    url = f"{ROR_API_BASE}{ror_id}"
    try:
        with urlopen(url, timeout=8) as response:
            payload = json.load(response)
    except (HTTPError, URLError, TimeoutError, OSError, ValueError):
        return np.nan, np.nan, None

    acronym = extract_ror_acronym(payload)

    locations = payload.get("locations") or []
    if not locations:
        return np.nan, np.nan, acronym

    details = locations[0].get("geonames_details") or {}
    lat = details.get("lat")
    lon = details.get("lng")
    if lat is None or lon is None:
        return np.nan, np.nan, acronym

    try:
        return float(lat), float(lon), acronym
    except (TypeError, ValueError):
        return np.nan, np.nan, acronym


def resolve_ror_coordinates(ror_ids: list[str], cache_path: Path) -> pd.DataFrame:
    return resolve_ror_metadata(
        ror_ids,
        local_cache_path=cache_path,
        include_acronym=True,
        context=asset.base_dir.name,
    )

def select_gpkg_layer(path: Path) -> str | None:
    try:
        con = sqlite3.connect(str(path))
        rows = con.execute(
            "SELECT table_name FROM gpkg_contents WHERE data_type = 'features'"
        ).fetchall()
        con.close()
    except Exception:
        return None

    layer_names = [str(r[0]) for r in rows if r and r[0]]
    if not layer_names:
        return None

    for hint in CANTON_LAYER_HINTS:
        for layer in layer_names:
            if hint in layer.lower():
                return layer

    return layer_names[0]


def load_canton_and_switzerland_map() -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    search_dirs = [asset.base_dir, REPO_ROOT / "core" / "maps"]

    for base_dir in search_dirs:
        for filename in CANTON_FILE_CANDIDATES:
            path = base_dir / filename
            if not path.is_file():
                continue

            layer_name = select_gpkg_layer(path) if path.suffix.lower() == ".gpkg" else None

            try:
                cantons = (
                    gpd.read_file(path, layer=layer_name)
                    if layer_name
                    else gpd.read_file(path)
                )
            except Exception:
                continue

            if cantons.empty:
                continue

            cantons = cantons[["geometry"]].copy()
            cantons = cantons[cantons.geometry.notna() & ~cantons.geometry.is_empty].copy()
            if cantons.empty:
                continue

            if cantons.crs is None:
                cantons = cantons.set_crs(MAP_CRS)

            swiss_union = cantons.geometry.unary_union
            switzerland = gpd.GeoDataFrame(geometry=[swiss_union], crs=cantons.crs)

            layer_info = f" (layer: {layer_name})" if layer_name else ""
            print(f"Using canton boundaries from: {path.name}{layer_info}")
            return cantons.reset_index(drop=True), switzerland.reset_index(drop=True)

    raise FileNotFoundError(
        "No canton boundary file found. Expected one of: "
        + ", ".join(CANTON_FILE_CANDIDATES)
    )


def pick_label_text(acronym: object, name: object) -> str:
    acronym_text = str(acronym).strip() if pd.notna(acronym) else ""
    if LABEL_USE_ROR_ACRONYM and acronym_text and acronym_text.lower() != "nan":
        return acronym_text

    if LABEL_FALLBACK_TO_NAME:
        return str(name).strip()

    return ""


def prepare_plot_df(raw_df: pd.DataFrame, ror_cache_path: Path, apply_postprocessing: bool = True) -> pd.DataFrame:
    out = raw_df.copy()
    active_count_column = get_active_count_column()
    sort_columns, sort_ascending = get_sort_columns()

    if apply_postprocessing and APPLY_CHILD_INSTITUTION_POSTPROCESSING:
        out = postprocess_excluded_institutions(out, institution_id_col="institution_id")

    out["collaboration_count_full"] = pd.to_numeric(
        out.get("collaboration_count_full"), errors="coerce"
    ).fillna(0).astype(int)
    out["collaboration_count_frac"] = pd.to_numeric(
        out.get("collaboration_count_frac"), errors="coerce"
    ).fillna(0.0)
    out["collaboration_count"] = pd.to_numeric(
        out.get("collaboration_count"), errors="coerce"
    ).fillna(out[active_count_column])
    out = out[out[active_count_column] > 0].copy()
    out["institution_name"] = out["institution_name"].fillna("Unknown institution").astype(str)

    out = out.sort_values(sort_columns, ascending=sort_ascending).reset_index(drop=True)
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
        if "acronym_cache" in out.columns:
            out["acronym"] = out["acronym_cache"]
        out = out.drop(
            columns=[
                c
                for c in ["lat_cache", "lon_cache", "acronym_cache"]
                if c in out.columns
            ]
        )
    else:
        out["lat"] = np.nan
        out["lon"] = np.nan
        out["acronym"] = np.nan

    out["latitude"] = pd.to_numeric(out["lat"], errors="coerce")
    out["longitude"] = pd.to_numeric(out["lon"], errors="coerce")
    mode_label = "prepost" if not apply_postprocessing else "post"
    out = drop_rows_without_coordinates(
        out,
        lat_col="latitude",
        lon_col="longitude",
        context=f"{asset.base_dir.name}:{mode_label}",
    )

    renamed_sort_columns = ["name" if col == "institution_name" else col for col in sort_columns]
    out = out.sort_values(renamed_sort_columns, ascending=sort_ascending).reset_index(drop=True)
    out["rank_desc"] = out.index + 1
    out["topN"] = out["rank_desc"] <= TOP_N
    out["label_text"] = out.apply(
        lambda r: pick_label_text(r.get("acronym"), r.get("name")), axis=1
    )
    out = add_annotation_symbols_to_labels(out)

    out = out.sort_values(["rank_desc", "name", "institution_id"], ascending=[True, True, True]).reset_index(
        drop=True
    )
    return out


def build_points_gdf(plot_df: pd.DataFrame) -> gpd.GeoDataFrame:
    sel = plot_df.dropna(subset=["longitude", "latitude"]).copy()
    return gpd.GeoDataFrame(
        sel,
        geometry=gpd.points_from_xy(sel["longitude"], sel["latitude"]),
        crs="EPSG:4326",
    )


def filter_points_to_switzerland(
    points_gdf: gpd.GeoDataFrame,
    switzerland: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    if points_gdf.empty:
        return points_gdf

    swiss = switzerland.to_crs(points_gdf.crs)
    swiss_union = swiss.geometry.unary_union
    return points_gdf[points_gdf.geometry.within(swiss_union)].copy()


def add_non_overlapping_labels(ax: mpl.axes.Axes, top_points: gpd.GeoDataFrame) -> None:
    if top_points.empty:
        return

    fig = ax.figure
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    axes_bbox = ax.get_window_extent(renderer=renderer)

    placed_bboxes: list = []

    top_points_sorted = top_points.sort_values(["rank_desc", "name", "institution_id"], ascending=[True, True, True])
    for _, row in top_points_sorted.iterrows():
        label = str(row.get("label_text", "")).strip()
        if not label:
            continue

        best_score = None
        best_ann = None
        best_bbox = None

        for dx, dy in LABEL_OFFSET_POINTS:
            ann = ax.annotate(
                label,
                xy=(row.geometry.x, row.geometry.y),
                xytext=(dx, dy),
                textcoords="offset points",
                ha="left" if dx >= 0 else "right",
                va="bottom" if dy >= 0 else "top",
                fontsize=LABEL_FONT_SIZE,
                color=LABEL_TEXT_COLOR,
                bbox={
                    "boxstyle": "round,pad=0.15",
                    "facecolor": LABEL_BOX_FACE,
                    "alpha": LABEL_BOX_ALPHA,
                    "edgecolor": "none",
                },
                zorder=6,
            )

            bbox = ann.get_window_extent(renderer=renderer).expanded(1.04, 1.18)
            overlap_count = sum(1 for b in placed_bboxes if bbox.overlaps(b))

            outside_penalty = (
                max(0.0, axes_bbox.x0 - bbox.x0)
                + max(0.0, bbox.x1 - axes_bbox.x1)
                + max(0.0, axes_bbox.y0 - bbox.y0)
                + max(0.0, bbox.y1 - axes_bbox.y1)
            )

            score = overlap_count * 1_000_000 + outside_penalty

            if best_score is None or score < best_score:
                if best_ann is not None:
                    best_ann.remove()
                best_score = score
                best_ann = ann
                best_bbox = bbox
            else:
                ann.remove()

            if score == 0:
                break

        if best_ann is not None and best_bbox is not None:
            placed_bboxes.append(best_bbox)


def plot_geo_national(
    points_gdf: gpd.GeoDataFrame,
    switzerland: gpd.GeoDataFrame,
    cantons: gpd.GeoDataFrame,
    inst_label: str,
    annotation_notes: list[str] | None = None,
) -> mpl.figure.Figure:
    with mpl.rc_context(RC_PARAMS):
        fig, ax = plt.subplots(figsize=(8, 9), dpi=300)

        ch_map = switzerland.to_crs(MAP_CRS)
        cantons_map = cantons.to_crs(MAP_CRS)

        ch_map.plot(
            ax=ax,
            color=SWISS_FILL_COLOR,
            edgecolor=SWISS_BORDER_COLOR,
            linewidth=1.0,
            zorder=1,
        )

        cantons_map.boundary.plot(
            ax=ax,
            color=CANTON_BORDER_COLOR,
            linewidth=0.6,
            alpha=0.9,
            zorder=2,
        )

        points_proj = points_gdf.to_crs(MAP_CRS)
        top_points = points_proj.iloc[0:0].copy()
        if not points_proj.empty:
            points_proj.plot(
                ax=ax,
                marker="o",
                markersize=POINT_BASE_SIZE,
                color=POINT_BASE_COLOR,
                alpha=POINT_BASE_ALPHA,
                edgecolors=POINT_BASE_EDGE_COLOR,
                linewidth=POINT_BASE_EDGE_WIDTH,
                label="collaborating institution",
                zorder=3,
            )

            top_points = points_proj[points_proj["topN"]]
            if not top_points.empty:
                top_points.plot(
                    ax=ax,
                    marker="o",
                    markersize=POINT_TOP_SIZE,
                    color=POINT_TOP_COLOR,
                    alpha=POINT_TOP_ALPHA,
                    edgecolor="none",
                    linewidth=0,
                    label=f"Top {TOP_N} collaborating institutions",
                    zorder=4,
                )
                top_points.plot(
                    ax=ax,
                    marker="o",
                    markersize=POINT_TOP_SIZE,
                    color=POINT_TOP_COLOR,
                    alpha=POINT_TOP_ALPHA,
                    edgecolors=POINT_TOP_EDGE_COLOR,
                    linewidth=POINT_TOP_EDGE_WIDTH,
                    zorder=5,
                )

        if LABEL_TOP_INSTITUTIONS and not top_points.empty:
            add_non_overlapping_labels(ax, top_points)

        x0, y0, x1, y1 = ch_map.total_bounds
        x_pad = (x1 - x0) * 0.06
        y_pad = (y1 - y0) * 0.06
        ax.set_xlim(x0 - x_pad, x1 + x_pad)
        ax.set_ylim(y0 - y_pad, y1 + y_pad)

        ax.set_axis_off()

        if annotation_notes:
            note_text = "\n".join(
                textwrap.fill(note, width=FIGURE_NOTE_WRAP_WIDTH)
                for note in annotation_notes
            )
            ax.text(
                FIGURE_NOTE_X,
                FIGURE_NOTE_Y,
                note_text,
                transform=ax.transAxes,
                ha="left",
                va="bottom",
                fontsize=FIGURE_NOTE_FONT_SIZE,
                color=FIGURE_NOTE_TEXT_COLOR,
                bbox={
                    "boxstyle": "round,pad=0.25",
                    "facecolor": "white",
                    "alpha": 0.50,
                    "edgecolor": "none",
                },
                zorder=7,
            )

    return fig


canton_map, switzerland_map = load_canton_and_switzerland_map()
ror_cache_path = asset.base_dir / ROR_CACHE_FILENAME

for inst, con in asset.iterate_institutions():
    # 1) Extract raw SQL data.
    raw_df = asset.extract(
        con=con,
        inst=inst,
        query=query_collaboration_institutions_ch(inst, asset.year_first, asset.year_last),
        out_name="data_raw.csv",
    )

    # 2) Transform to plot-ready table.
    plot_df_prepost = prepare_plot_df(raw_df, ror_cache_path, apply_postprocessing=False)
    plot_df = prepare_plot_df(raw_df, ror_cache_path, apply_postprocessing=True)

    points_gdf = build_points_gdf(plot_df)
    points_gdf = filter_points_to_switzerland(points_gdf, switzerland_map)
    # 3) Draw figure.
    annotation_notes = []
    if "topN" in points_gdf.columns:
        annotation_notes = figure_notes_for_df(points_gdf[points_gdf["topN"]])
    fig = plot_geo_national(
        points_gdf,
        switzerland_map,
        canton_map,
        get_inst_label(inst),
        annotation_notes=annotation_notes,
    )

    out = asset.inst_dir(inst)
    plot_df_prepost.to_csv(out / "data_prepost.csv", index=False)
    plot_df.to_csv(out / "data.csv", index=False)
    plot_df.to_csv(out / "data_for_plot.csv", index=False)

    fig.savefig(out / "figure.svg", dpi=300, bbox_inches="tight")
    fig.savefig(out / "figure.png", dpi=300, bbox_inches="tight", facecolor="white")
    fig.savefig(out / "figure.pdf", dpi=300, bbox_inches="tight")
    plt.close(fig)
