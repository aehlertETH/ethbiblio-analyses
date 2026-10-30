
import json
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import urlopen

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import ConnectionPatch, Patch, Rectangle
from matplotlib.transforms import Bbox

from shapely.geometry import box

from core.asset import Asset, postprocess_excluded_institutions
from core.ror import drop_rows_without_coordinates, resolve_ror_metadata

try:
    import geopandas as gpd
except ModuleNotFoundError as exc:
    raise ModuleNotFoundError(
        "Missing dependency 'geopandas'. Install map dependencies with "
        "'pip install -r requirements.maps.txt'."
    ) from exc


asset = Asset(script_file=__file__)

# ---------------------------------------------------------------------------
# IMPORTANT setting
# ---------------------------------------------------------------------------
# If True: compute only ethdomain and write those outputs into all unit folders.
# If False: run normal per-unit computation and write each unit's own outputs.
FORCE_ETHDOMAIN_OUTPUTS_FOR_ALL_UNITS = True

# ---------------------------------------------------------------------------
# Indicator settings
# ---------------------------------------------------------------------------
IND_C_INST_OPEN_LINKS = "C_CITING_INST_GEO_OA_OPEN_LINKS_FULL"
IND_C_INST_CLOSED_LINKS = "C_CITING_INST_GEO_OA_CLOSED_LINKS_FULL"
IND_PP_INST_OPEN_SHARE = "PP_CITING_INST_GEO_OA_OPEN_SHARE_FULL"
IND_PP_INST_CLOSED_SHARE = "PP_CITING_INST_GEO_OA_CLOSED_SHARE_FULL"
IND_DPP_INST_OPEN_MINUS_CLOSED = "DPP_CITING_INST_GEO_OA_OPEN_MINUS_CLOSED_FULL"
IND_LOG2_INST_OPEN_OVER_CLOSED = "LOG2_CITING_INST_GEO_OA_OPEN_OVER_CLOSED_SHARE_FULL"

# ---------------------------------------------------------------------------
# OA comparison settings
# ---------------------------------------------------------------------------
# OA status is aligned with existing OA assets:
# - closed: closed or bronze
# - open: all other OA statuses
OA_CLOSED_CONDITION = (
    "COALESCE(w.open_access_oa_status_is_closed, FALSE) = TRUE "
    "OR COALESCE(w.open_access_oa_status_is_bronze, FALSE) = TRUE"
)


# ---------------------------------------------------------------------------
# Geocoding settings
# ---------------------------------------------------------------------------
ROR_API_BASE = "https://api.ror.org/v2/organizations/"
ROR_CACHE_FILENAME = "ror_geo_cache.csv"
ALLOW_ROR_API_FETCH = False


# ---------------------------------------------------------------------------
# Visual settings
# ---------------------------------------------------------------------------
LAND_COLOR = "#f7f7f7"
COUNTRY_FILL_COLOR = LAND_COLOR
COUNTRY_FILL_ALPHA = 1.00
COUNTRY_BORDER_COLOR = "#000000"
COUNTRY_BORDER_WIDTH = 0.30
COUNTRY_BORDER_ALPHA = 0.70
COUNTRY_BORDER_ON_TOP = True
COUNTRY_BORDER_ZORDER = 7

ABSOLUTE_COLORS = [
    "#253494",
    "#2c7fb8",
    "#41b6c4",
    "#7fcdbb",
    "#c7e9b4",
    "#ffffcc",
    "#fdae61",
    "#f46d43",
    "#d73027",
]

RELATIVE_COLORS = [
    "#b2182b",
    "#ef8a62",
    "#fddbc7",
    "#FFFFFF",
    "#d1e5f0",
    "#67a9cf",
    "#2166ac",
]

# Shared contour grid controls
CONTOUR_GRID_X = 440
CONTOUR_GRID_Y = 240
CONTOUR_SMOOTH_SIGMA = 1.25
CONTOUR_AUTO_SQUARE_CELLS = True
CONTOUR_AUTO_ISOTROPIC_SMOOTHING = True
MIN_CONTOUR_GRID_CELLS = 24

# Absolute contour settings (base layer)
CONTOUR_LEVEL_COUNT = 18
CONTOUR_LEVEL_SPACING = "geometric"  # geometric | linear
CONTOUR_LEVELS_CUSTOM: list[float] = []
CONTOUR_MIN_FRAC_OF_VMAX = 0.00001
ABSOLUTE_APPLY_MIN_THRESHOLD_MASK = True
CONTOUR_VMAX_QUANTILE = 0.99
CONTOUR_FILL_ALPHA = 0.34
CONTOUR_LINE_ALPHA = 0.28
CONTOUR_LINE_COLOR = "white"
CONTOUR_LINE_WIDTH = 0.22

# Relative contour settings (option 1)
RELATIVE_LEVEL_COUNT = 18
COLOR_LEVELS_DROP_LOWEST_K = 0  # absolute: drop lowest k; relative: drop k inner bands per side
RELATIVE_VABS_QUANTILE = 0.98
RELATIVE_FIXED_VABS: float | None = None
RELATIVE_EPS_FRAC_OF_MAX = 0.01
RELATIVE_MIN_TOTAL_FRAC_OF_MAX = CONTOUR_MIN_FRAC_OF_VMAX
RELATIVE_APPLY_MASS_THRESHOLD_MASK = ABSOLUTE_APPLY_MIN_THRESHOLD_MASK
RELATIVE_FILL_ALPHA = 0.55
RELATIVE_ZERO_LINE = False
RELATIVE_ZERO_LINE_COLOR = "#202020"
RELATIVE_ZERO_LINE_WIDTH = 0.55
RELATIVE_ZERO_LINE_ALPHA = 0.95
RELATIVE_CONTOUR_LINES = False
RELATIVE_CONTOUR_LINE_COLOR = "#2a2a2a"
RELATIVE_CONTOUR_LINE_WIDTH = 0.20
RELATIVE_CONTOUR_LINE_ALPHA = 0.35

# Option 2 overlay settings
OVERLAY_STYLE = "contour"  # contour | hatch | both | none
DRAW_ADDITIONAL_OVERLAY_LINES_ALWAYS = False
OVERLAY_INCLUDE_NEGATIVE = False
OVERLAY_POS_THRESHOLDS_LOG2 = [0.322, 0.585, 1.000]  # x1.25, x1.5, x2.0
OVERLAY_FORCE_ZERO_LEVEL = False
OVERLAY_IGNORE_MASS_MASK = False
OVERLAY_NEG_THRESHOLDS_LOG2 = [-0.322, -0.585, -1.000]
OVERLAY_POS_COLOR = "#111111"
OVERLAY_NEG_COLOR = "#555555"
OVERLAY_LINE_WIDTH = 0.38
OVERLAY_LINE_ALPHA = 0.85
OVERLAY_POS_LINESTYLE = "solid"
OVERLAY_NEG_LINESTYLE = "solid"
OVERLAY_POS_HATCH = "////"
OVERLAY_NEG_HATCH = "\\\\"
OVERLAY_HATCH_ALPHA = 0.0
OVERLAY_MIN_COMPONENT_CELLS = 10

# Colorbar / layout
COLORBAR_SHRINK = 0.36
COLORBAR_PAD = 0.005
COLORBAR_FRACTION = 0.03
COLORBAR_POS_DX = -0.025
COLORBAR_POS_DY = -0.01
COLORBAR_SCALE_W = 1.00
COLORBAR_SCALE_H = 1.00
COLORBAR_TICK_ROTATION = 90
COLORBAR_TICK_FONTSIZE = 7

ROBINSON_PROJ4 = "+proj=robin +lon_0=0 +datum=WGS84 +units=m +no_defs"
EXTENT_WORLD = (-180, -60, 180, 90)
ZOOM_EXTENT = (-10, 35.8, 21.5, 61)
INSET_AX_BOUNDS = (-0.095, 0.004, 0.5, 0.5)

# Zoom area selection (box around selected map region + connector lines)
ZOOM_SELECTION_COLOR = "#000000"
ZOOM_SELECTION_LINEWIDTH = 0.60
ZOOM_SELECTION_ALPHA = 1.0
ZOOM_SELECTION_ZORDER = 11

# Inset frame (box around the inset panel itself)
INSET_FRAME_COLOR = "#000000"
INSET_FRAME_LINEWIDTH = 1.0
INSET_FRAME_ALPHA = 1.0
INSET_FRAME_ZORDER = 13

# Broader/less detailed inset controls
ZOOM_CONTOUR_GRID_X = 360
ZOOM_CONTOUR_GRID_Y = 210
ZOOM_CONTOUR_SMOOTH_SIGMA = 2.60
ZOOM_CONTOUR_LEVEL_COUNT = 9
ZOOM_CONTOUR_LEVEL_SPACING = "geometric"
ZOOM_CONTOUR_LEVELS_CUSTOM: list[float] = []
ZOOM_CONTOUR_MIN_FRAC_OF_VMAX = 0.02
ZOOM_CONTOUR_VMAX_QUANTILE = 0.99
ZOOM_CONTOUR_FILL_ALPHA = 0.40
ZOOM_CONTOUR_LINE_ALPHA = 0.30
ZOOM_CONTOUR_LINE_COLOR = "white"
ZOOM_CONTOUR_LINE_WIDTH = 0.24
ZOOM_USE_LOCAL_SCALE = True

ZOOM_RELATIVE_LEVEL_COUNT = 11
ZOOM_RELATIVE_USE_LOCAL_SCALE = True

# Final export crop controls
EXPORT_CROP_LEFT = 0.035
EXPORT_CROP_BOTTOM = 0.00
EXPORT_CROP_RIGHT = 0.985
EXPORT_CROP_TOP = 0.96
EXPORT_BBOX_FRACTION = (
    EXPORT_CROP_LEFT,
    EXPORT_CROP_BOTTOM,
    EXPORT_CROP_RIGHT,
    EXPORT_CROP_TOP,
)


def query_citing_institutions_open_vs_closed(inst: str, y0: int, y1: int) -> str:
    return f"""
        WITH target_pubs AS (
            SELECT DISTINCT
                rm.work_id,
                CASE
                    WHEN {OA_CLOSED_CONDITION}
                    THEN 'closed'
                    ELSE 'open'
                END AS oa_status
            FROM reports.report_membership rm
            JOIN core.work w
              ON w.work_id = rm.work_id
            WHERE rm.report_name = '{inst}'
              AND w.publication_year BETWEEN {y0} AND {y1}
        ),

        citing_works AS (
            SELECT DISTINCT
                r.citing_id AS citing_work_id,
                tp.oa_status
            FROM core.refs r
            JOIN target_pubs tp
              ON tp.work_id = r.cited_id
        ),

        citing_inst_links AS (
            SELECT DISTINCT
                cw.citing_work_id,
                cw.oa_status,
                di.institution_id,
                di.ror,
                di.name AS institution_name,
                dc.country_code,
                COALESCE(oac.display_name, dc.country_code) AS country_name
            FROM citing_works cw
            JOIN marts.work_institution_info wii
              ON wii.work_id = cw.citing_work_id
            JOIN core.dim_institution di
              ON di.institution_id = wii.institution_id
            LEFT JOIN core.dim_country dc
              ON dc.country_id = di.country_id
            LEFT JOIN augmented.openalex_countries oac
              ON oac.code = dc.country_code
            WHERE dc.country_code IS NOT NULL
        ),

        agg AS (
            SELECT
                institution_id,
                ror,
                institution_name,
                country_code,
                country_name,
                COUNT(DISTINCT CASE WHEN oa_status = 'open' THEN citing_work_id END) AS open_links_full,
                COUNT(DISTINCT CASE WHEN oa_status = 'closed' THEN citing_work_id END) AS closed_links_full
            FROM citing_inst_links
            GROUP BY institution_id, ror, institution_name, country_code, country_name
        )

        SELECT
            institution_id,
            ror,
            institution_name,
            country_code,
            country_name,
            open_links_full,
            closed_links_full
        FROM agg
        ORDER BY open_links_full DESC, closed_links_full DESC, institution_name ASC, institution_id ASC;
    """


def find_world_map_path() -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    candidates = [
        asset.base_dir / "ne_50m_admin_0_countries.zip",
        repo_root / "core" / "maps" / "ne_50m_admin_0_countries.zip",
        asset.base_dir / "ne_110m_admin_0_countries.zip",
        repo_root / "core" / "maps" / "ne_110m_admin_0_countries.zip",
    ]
    for path in candidates:
        if path.is_file():
            return path
    raise FileNotFoundError(
        "Natural Earth map not found. Looked for: " + ", ".join(str(c) for c in candidates)
    )


def load_world_map(path: Path) -> gpd.GeoDataFrame:
    world = gpd.read_file(path)

    iso3_candidates = ["ISO_A3_EH", "ADM0_A3", "ISO_A3", "SOV_A3"]
    iso2_candidates = ["ISO_A2_EH", "ISO_A2"]
    name_candidates = ["NAME_EN", "NAME", "ADMIN"]

    iso3_col = next((column for column in iso3_candidates if column in world.columns), None)
    iso2_col = next((column for column in iso2_candidates if column in world.columns), None)
    name_col = next((column for column in name_candidates if column in world.columns), None)

    if not iso3_col or not name_col:
        raise ValueError("Expected ISO/name columns were not found in Natural Earth map file.")

    cols = [name_col, iso3_col, "geometry"]
    rename = {name_col: "map_country_name", iso3_col: "map_iso3_code"}
    if iso2_col:
        cols.insert(2, iso2_col)
        rename[iso2_col] = "map_iso2_code"

    out = world[cols].rename(columns=rename)
    if "map_iso2_code" not in out.columns:
        out["map_iso2_code"] = None
    return out


def parse_ror_id(ror_url: str) -> str | None:
    if not isinstance(ror_url, str) or not ror_url.strip():
        return None
    parsed = urlparse(ror_url.strip())
    ror_id = parsed.path.strip("/").split("/")[-1]
    return ror_id or None


def load_ror_cache(cache_paths: list[Path]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for cache_path in cache_paths:
        if not cache_path.is_file():
            continue
        try:
            df = pd.read_csv(cache_path)
        except Exception:
            continue
        for col in ["ror_id", "lat", "lon"]:
            if col not in df.columns:
                df[col] = np.nan
        df = df[["ror_id", "lat", "lon"]].copy()
        df["ror_id"] = df["ror_id"].astype(str)
        df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
        df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
        frames.append(df)

    if not frames:
        return pd.DataFrame(columns=["ror_id", "lat", "lon"])

    out = pd.concat(frames, ignore_index=True)
    out = out.drop_duplicates(subset=["ror_id"], keep="first")
    return out


def fetch_ror_coordinates(ror_id: str) -> tuple[float, float]:
    url = f"{ROR_API_BASE}{ror_id}"
    try:
        with urlopen(url, timeout=12) as response:
            payload = json.load(response)
    except (HTTPError, URLError, TimeoutError, OSError, ValueError):
        return np.nan, np.nan

    locations = payload.get("locations") or []
    if not locations:
        return np.nan, np.nan

    details = locations[0].get("geonames_details") or {}
    lat = details.get("lat")
    lon = details.get("lng")
    if lat is None or lon is None:
        return np.nan, np.nan

    try:
        return float(lat), float(lon)
    except (TypeError, ValueError):
        return np.nan, np.nan


def extend_ror_cache_if_enabled(plot_df: pd.DataFrame, cache_df: pd.DataFrame, local_cache_path: Path) -> pd.DataFrame:
    if not ALLOW_ROR_API_FETCH:
        return cache_df

    ror_ids = sorted(plot_df["ror_id"].dropna().astype(str).unique().tolist())
    if not ror_ids:
        return cache_df

    known = set(cache_df["ror_id"].dropna().astype(str).tolist())
    missing = sorted(set(ror_ids) - known)
    if not missing:
        return cache_df

    fetched_rows: list[dict] = []
    for i, ror_id in enumerate(missing, start=1):
        lat, lon = fetch_ror_coordinates(ror_id)
        fetched_rows.append({"ror_id": ror_id, "lat": lat, "lon": lon})
        if i % 100 == 0:
            print(f"ROR geocoding: fetched {i}/{len(missing)} ids")
        time.sleep(0.05)

    if fetched_rows:
        fetched_df = pd.DataFrame(fetched_rows)
        cache_df = pd.concat([cache_df, fetched_df], ignore_index=True)
        cache_df = cache_df.drop_duplicates(subset=["ror_id"], keep="last")
        cache_df = cache_df.sort_values("ror_id")
        local_cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_df.to_csv(local_cache_path, index=False)

    return cache_df


def build_country_centroids(world_map: gpd.GeoDataFrame) -> pd.DataFrame:
    df = world_map[["map_iso2_code", "geometry"]].copy()
    df = df.dropna(subset=["map_iso2_code", "geometry"]).copy()
    df["country_code"] = df["map_iso2_code"].astype(str)
    df = df[df["country_code"].str.len() == 2].copy()

    gdf = gpd.GeoDataFrame(df[["country_code"]], geometry=df["geometry"], crs="EPSG:4326")
    gdf_metric = gdf.to_crs("EPSG:3857")
    centroids_metric = gdf_metric.geometry.centroid
    centroids = gpd.GeoSeries(centroids_metric, crs="EPSG:3857").to_crs("EPSG:4326")

    out = pd.DataFrame({
        "country_code": gdf["country_code"].values,
        "centroid_lat": centroids.y.values,
        "centroid_lon": centroids.x.values,
    })
    out = out.drop_duplicates(subset=["country_code"], keep="first")
    return out


def prepare_plot_df(raw_df: pd.DataFrame, world_map: gpd.GeoDataFrame, apply_postprocessing: bool = True) -> pd.DataFrame:
    cols = [
        "row_order",
        "institution_id",
        "institution_name",
        "country_code",
        "country_name",
        "ror",
        "ror_id",
        "lat",
        "lon",
        "geo_source",
        "open_links_full",
        "closed_links_full",
        "open_share",
        "closed_share",
        "open_share_pct",
        "closed_share_pct",
        "open_minus_closed_pp",
        "open_over_closed_ratio",
        "open_over_closed_log2",
        "total_open_links",
        "total_closed_links",
    ]
    if raw_df.empty:
        return pd.DataFrame(columns=cols)

    df = raw_df.copy()
    if apply_postprocessing:
        df = postprocess_excluded_institutions(df, institution_id_col="institution_id")
    df["institution_id"] = pd.to_numeric(df["institution_id"], errors="coerce")
    df["institution_name"] = df["institution_name"].fillna("Unknown institution").astype(str)
    df["country_code"] = df["country_code"].astype(str)
    df["country_name"] = df["country_name"].fillna(df["country_code"]).astype(str)
    df["open_links_full"] = pd.to_numeric(df["open_links_full"], errors="coerce").fillna(0.0)
    df["closed_links_full"] = pd.to_numeric(df["closed_links_full"], errors="coerce").fillna(0.0)
    df = df[(df["open_links_full"] > 0) | (df["closed_links_full"] > 0)].copy()

    df["ror_id"] = df["ror"].apply(parse_ror_id)

    local_cache_path = asset.base_dir / ROR_CACHE_FILENAME
    mode_label = "prepost" if not apply_postprocessing else "post"
    ror_ids = sorted(df["ror_id"].dropna().astype(str).unique().tolist())
    if ror_ids:
        cache_df = resolve_ror_metadata(
            ror_ids,
            local_cache_path=local_cache_path,
            include_acronym=False,
            context=f"{asset.base_dir.name}:{mode_label}",
        )
    else:
        cache_df = pd.DataFrame(columns=["ror_id", "lat", "lon"])

    df = df.merge(cache_df, on="ror_id", how="left")
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    df["geo_source"] = "ror_lookup"
    df = drop_rows_without_coordinates(
        df,
        lat_col="lat",
        lon_col="lon",
        context=f"{asset.base_dir.name}:{mode_label}",
    )

    total_open_links = float(df["open_links_full"].sum())
    total_closed_links = float(df["closed_links_full"].sum())
    df["open_share"] = df["open_links_full"] / total_open_links if total_open_links > 0 else 0.0
    df["closed_share"] = df["closed_links_full"] / total_closed_links if total_closed_links > 0 else 0.0
    df["open_share_pct"] = 100.0 * df["open_share"]
    df["closed_share_pct"] = 100.0 * df["closed_share"]
    df["open_minus_closed_pp"] = df["open_share_pct"] - df["closed_share_pct"]

    eps_share = 1e-12
    df["open_over_closed_ratio"] = (df["open_share"] + eps_share) / (df["closed_share"] + eps_share)
    df["open_over_closed_log2"] = np.log2(df["open_over_closed_ratio"])

    df["total_open_links"] = total_open_links
    df["total_closed_links"] = total_closed_links

    df = df.sort_values(
        ["open_over_closed_log2", "open_share", "open_links_full", "institution_name", "institution_id"],
        ascending=[False, False, False, True, True],
    ).reset_index(drop=True)
    df["row_order"] = df.index + 1

    return df[cols]


def build_points_gdf(plot_df: pd.DataFrame) -> gpd.GeoDataFrame:
    sel = plot_df.dropna(subset=["lon", "lat"]).copy()
    return gpd.GeoDataFrame(
        sel,
        geometry=gpd.points_from_xy(sel["lon"], sel["lat"]),
        crs="EPSG:4326",
    )


def export_bbox_inches(fig: mpl.figure.Figure, crop_frac: tuple[float, float, float, float]) -> Bbox:
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
        x0 + left * w,
        y0 + bottom * h,
        x0 + right * w,
        y0 + top * h,
    )


def apply_colorbar_layout(cbar: mpl.colorbar.Colorbar) -> None:
    pos = cbar.ax.get_position()
    cbar.ax.set_position([
        pos.x0 + COLORBAR_POS_DX,
        pos.y0 + COLORBAR_POS_DY,
        pos.width * COLORBAR_SCALE_W,
        pos.height * COLORBAR_SCALE_H,
    ])


def apply_qualitative_colorbar(
    cbar: mpl.colorbar.Colorbar,
    low_label: str,
    high_label: str,
    mid_label: str | None = None,
) -> None:
    vmin, vmax = cbar.mappable.get_clim()
    if mid_label is None:
        cbar.set_ticks([vmin, vmax])
        cbar.set_ticklabels([low_label, high_label])
    else:
        cbar.set_ticks([vmin, 0.0, vmax])
        cbar.set_ticklabels([low_label, mid_label, high_label])

    # Keep labels, hide only tick marks.
    cbar.ax.tick_params(labelsize=COLORBAR_TICK_FONTSIZE, length=7, width=0)
    for tick in cbar.ax.get_yticklabels():
        tick.set_rotation(COLORBAR_TICK_ROTATION)
        tick.set_va("center")
        tick.set_ha("center")
def keep_large_components(mask: np.ndarray, min_cells: int) -> np.ndarray:
    arr = np.asarray(mask, dtype=bool)
    min_cells = int(max(1, min_cells))
    if min_cells <= 1 or not np.any(arr):
        return arr

    out = np.zeros_like(arr, dtype=bool)
    visited = np.zeros_like(arr, dtype=bool)
    nrows, ncols = arr.shape
    neighbors = [
        (-1, -1), (-1, 0), (-1, 1),
        (0, -1),           (0, 1),
        (1, -1),  (1, 0),  (1, 1),
    ]

    for r in range(nrows):
        for c in range(ncols):
            if visited[r, c] or not arr[r, c]:
                continue
            stack = [(r, c)]
            visited[r, c] = True
            component: list[tuple[int, int]] = []

            while stack:
                rr, cc = stack.pop()
                component.append((rr, cc))
                for dr, dc in neighbors:
                    nr, nc = rr + dr, cc + dc
                    if nr < 0 or nr >= nrows or nc < 0 or nc >= ncols:
                        continue
                    if visited[nr, nc] or not arr[nr, nc]:
                        continue
                    visited[nr, nc] = True
                    stack.append((nr, nc))

            if len(component) >= min_cells:
                for rr, cc in component:
                    out[rr, cc] = True

    return out


def draw_world_fill(ax: mpl.axes.Axes, world_proj: gpd.GeoDataFrame) -> None:
    world_proj.plot(
        ax=ax,
        color=COUNTRY_FILL_COLOR,
        edgecolor="none",
        linewidth=0,
        alpha=COUNTRY_FILL_ALPHA,
        zorder=1,
    )
    if not COUNTRY_BORDER_ON_TOP:
        draw_world_borders(ax, world_proj)


def draw_world_borders(ax: mpl.axes.Axes, world_proj: gpd.GeoDataFrame) -> None:
    world_proj.plot(
        ax=ax,
        color="none",
        edgecolor=COUNTRY_BORDER_COLOR,
        linewidth=COUNTRY_BORDER_WIDTH,
        alpha=COUNTRY_BORDER_ALPHA,
        zorder=COUNTRY_BORDER_ZORDER,
    )


def build_absolute_cmap() -> mpl.colors.Colormap:
    return mpl.colors.LinearSegmentedColormap.from_list("citing_absolute", ABSOLUTE_COLORS, N=256)


def build_relative_cmap() -> mpl.colors.Colormap:
    return mpl.colors.LinearSegmentedColormap.from_list("citing_relative", RELATIVE_COLORS, N=256)


def gaussian_kernel_1d(sigma: float) -> np.ndarray:
    sigma = float(max(0.0, sigma))
    if sigma <= 0:
        return np.array([1.0], dtype=float)
    radius = max(1, int(round(3.0 * sigma)))
    x = np.arange(-radius, radius + 1, dtype=float)
    kernel = np.exp(-(x * x) / (2.0 * sigma * sigma))
    kernel_sum = float(kernel.sum())
    if kernel_sum > 0:
        kernel /= kernel_sum
    return kernel


def smooth_2d_gaussian(z: np.ndarray, sigma_x: float, sigma_y: float | None = None) -> np.ndarray:
    sigma_x = float(max(0.0, sigma_x))
    if sigma_y is None:
        sigma_y = sigma_x
    sigma_y = float(max(0.0, sigma_y))

    if sigma_x <= 0 and sigma_y <= 0:
        return z

    out = np.asarray(z, dtype=float)

    if sigma_x > 0:
        kernel_x = gaussian_kernel_1d(sigma_x)
        out = np.apply_along_axis(lambda m: np.convolve(m, kernel_x, mode="same"), axis=1, arr=out)

    if sigma_y > 0:
        kernel_y = gaussian_kernel_1d(sigma_y)
        out = np.apply_along_axis(lambda m: np.convolve(m, kernel_y, mode="same"), axis=0, arr=out)

    return out


def resolve_grid_shape_for_extent(
    extent_proj: tuple[float, float, float, float],
    grid_x: int,
    grid_y: int,
    *,
    auto_square_cells: bool,
    min_cells: int,
) -> tuple[int, int]:
    xmin, ymin, xmax, ymax = [float(v) for v in extent_proj]
    width = max(1e-9, abs(xmax - xmin))
    height = max(1e-9, abs(ymax - ymin))

    gx = max(int(grid_x), int(min_cells))
    gy = max(int(grid_y), int(min_cells))

    if not auto_square_cells:
        return gx, gy

    long_side_cells = max(gx, gy)
    if width >= height:
        gx = long_side_cells
        gy = max(int(min_cells), int(round(long_side_cells * (height / width))))
    else:
        gy = long_side_cells
        gx = max(int(min_cells), int(round(long_side_cells * (width / height))))

    return gx, gy


def normalize_extent(extent: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    if len(extent) != 4:
        raise ValueError("Extent must be a tuple of 4 values: (xmin, ymin, xmax, ymax).")
    xmin, ymin, xmax, ymax = [float(v) for v in extent]
    xmin, xmax = sorted((xmin, xmax))
    ymin, ymax = sorted((ymin, ymax))
    if xmin == xmax or ymin == ymax:
        raise ValueError(f"Extent is empty after normalization: {extent!r}")
    return xmin, ymin, xmax, ymax


def projected_extent(extent: tuple[float, float, float, float], crs: str = ROBINSON_PROJ4) -> tuple[float, float, float, float]:
    xmin, ymin, xmax, ymax = normalize_extent(extent)
    bbox = gpd.GeoDataFrame(geometry=[box(xmin, ymin, xmax, ymax)], crs="EPSG:4326").to_crs(crs)
    x0, y0, x1, y1 = bbox.total_bounds
    return float(x0), float(y0), float(x1), float(y1)


def get_contour_levels_param(
    vmin: float,
    vmax: float,
    level_count: int,
    level_spacing: str,
    levels_custom: list[float] | None,
) -> np.ndarray:
    if not np.isfinite(vmin) or not np.isfinite(vmax) or vmax <= vmin:
        return np.array([], dtype=float)

    if levels_custom:
        levels = np.array([float(v) for v in levels_custom], dtype=float)
        levels = levels[np.isfinite(levels)]
        levels = levels[(levels > 0) & (levels >= vmin) & (levels <= vmax)]
        levels = np.unique(np.sort(levels))
        if levels.size >= 2:
            return levels

    if int(level_count) < 2:
        return np.array([], dtype=float)

    spacing = str(level_spacing).strip().lower()
    if spacing == "geometric" and vmin > 0:
        return np.geomspace(vmin, vmax, int(level_count), dtype=float)

    return np.linspace(vmin, vmax, int(level_count), dtype=float)


def drop_lowest_absolute_levels(levels: np.ndarray, drop_k: int) -> np.ndarray:
    arr = np.asarray(levels, dtype=float)
    arr = arr[np.isfinite(arr)]
    arr = np.unique(np.sort(arr))
    k = max(0, int(drop_k))
    if k <= 0:
        return arr
    if arr.size <= k + 1:
        return arr
    return arr[k:]


def drop_inner_relative_levels(levels: np.ndarray, drop_k: int) -> np.ndarray:
    arr = np.asarray(levels, dtype=float)
    arr = arr[np.isfinite(arr)]
    arr = np.unique(np.sort(arr))
    k = max(0, int(drop_k))
    if k <= 0:
        return arr

    neg = arr[arr < 0]
    pos = arr[arr > 0]
    has_zero = np.any(arr == 0.0)
    max_drop = min(max(0, neg.size - 1), max(0, pos.size - 1))
    k_eff = min(k, max_drop)
    if k_eff <= 0:
        return arr

    neg_trim = neg[:-k_eff] if neg.size > k_eff else neg
    pos_trim = pos[k_eff:] if pos.size > k_eff else pos

    out_parts = [neg_trim]
    if has_zero:
        out_parts.append(np.array([0.0]))
    out_parts.append(pos_trim)
    out = np.concatenate(out_parts)
    out = np.unique(np.sort(out))
    if out.size < 3:
        return arr
    return out

def compute_surface_from_weights(
    x: np.ndarray,
    y: np.ndarray,
    weights: np.ndarray,
    extent_proj: tuple[float, float, float, float],
    *,
    grid_x: int,
    grid_y: int,
    smooth_sigma: float,
    auto_square_cells: bool,
    isotropic_smoothing: bool,
    min_grid_cells: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    xmin, ymin, xmax, ymax = [float(v) for v in extent_proj]

    grid_x_eff, grid_y_eff = resolve_grid_shape_for_extent(
        extent_proj,
        int(grid_x),
        int(grid_y),
        auto_square_cells=bool(auto_square_cells),
        min_cells=int(min_grid_cells),
    )

    hist, x_edges, y_edges = np.histogram2d(
        x,
        y,
        bins=[grid_x_eff, grid_y_eff],
        range=[[xmin, xmax], [ymin, ymax]],
        weights=weights,
    )

    cell_size_x = max(1e-9, (xmax - xmin) / float(grid_x_eff))
    cell_size_y = max(1e-9, (ymax - ymin) / float(grid_y_eff))

    sigma_x = float(smooth_sigma)
    if isotropic_smoothing:
        sigma_y = sigma_x * (cell_size_x / cell_size_y)
    else:
        sigma_y = sigma_x

    sigma_y = max(0.01, float(sigma_y))

    z = hist.T
    z = smooth_2d_gaussian(z, sigma_x=sigma_x, sigma_y=sigma_y)

    x_centers = 0.5 * (x_edges[:-1] + x_edges[1:])
    y_centers = 0.5 * (y_edges[:-1] + y_edges[1:])
    xx, yy = np.meshgrid(x_centers, y_centers)
    return xx, yy, z


def compute_relative_lift(
    z_target: np.ndarray,
    z_benchmark: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    total_mass = z_target + z_benchmark
    if RELATIVE_APPLY_MASS_THRESHOLD_MASK:
        threshold = float(RELATIVE_MIN_TOTAL_FRAC_OF_MAX) * float(max(np.nanmax(total_mass), 1e-12))
        mask = total_mass <= threshold
    else:
        mask = np.zeros_like(total_mass, dtype=bool)

    max_ref = float(max(np.nanmax(z_target), np.nanmax(z_benchmark), 1e-12))
    eps = max(1e-12, float(RELATIVE_EPS_FRAC_OF_MAX) * max_ref)
    ratio_log2 = np.log2((z_target + eps) / (z_benchmark + eps))
    return ratio_log2, mask


def draw_absolute_contours(
    ax: mpl.axes.Axes,
    xx: np.ndarray,
    yy: np.ndarray,
    z_target: np.ndarray,
    *,
    level_count: int,
    level_spacing: str,
    levels_custom: list[float],
    min_frac_of_vmax: float,
    vmax_quantile: float,
    fill_alpha: float,
    line_alpha: float,
    line_width: float,
    line_color: str,
    cmap: mpl.colors.Colormap,
    fixed_vmin: float | None = None,
    fixed_vmax: float | None = None,
) -> tuple[mpl.contour.QuadContourSet | None, float | None, float | None]:
    positive = z_target[z_target > 0]
    if positive.size == 0:
        return None, None, None

    if fixed_vmax is not None:
        vmax = float(fixed_vmax)
    else:
        vmax = float(np.nanquantile(positive, float(vmax_quantile)))
        if not np.isfinite(vmax) or vmax <= 0:
            vmax = float(np.nanmax(positive))

    if fixed_vmin is not None:
        vmin = float(fixed_vmin)
    else:
        vmin = float(min_frac_of_vmax) * vmax

    if not np.isfinite(vmin) or not np.isfinite(vmax) or vmax <= vmin:
        return None, None, None

    levels = get_contour_levels_param(vmin, vmax, int(level_count), level_spacing, levels_custom)
    levels = drop_lowest_absolute_levels(levels, COLOR_LEVELS_DROP_LOWEST_K)
    if levels.size < 2:
        levels = np.linspace(vmin, vmax, max(6, int(level_count) if int(level_count) > 1 else 6))
        levels = drop_lowest_absolute_levels(levels, COLOR_LEVELS_DROP_LOWEST_K)
    if levels.size < 2:
        levels = np.linspace(vmin, vmax, 2)

    z_masked = np.ma.masked_less_equal(z_target, vmin)

    contourf = ax.contourf(
        xx,
        yy,
        z_masked,
        levels=levels,
        cmap=cmap,
        alpha=float(fill_alpha),
        antialiased=True,
        extend="max",
        zorder=3,
    )

    ax.contour(
        xx,
        yy,
        z_masked,
        levels=levels,
        colors=line_color,
        linewidths=float(line_width),
        alpha=float(line_alpha),
        zorder=4,
    )

    return contourf, float(vmin), float(vmax)


def draw_relative_contours(
    ax: mpl.axes.Axes,
    xx: np.ndarray,
    yy: np.ndarray,
    z_target: np.ndarray,
    z_benchmark: np.ndarray,
    *,
    level_count: int,
    fill_alpha: float,
    fixed_vabs: float | None = None,
) -> tuple[mpl.contour.QuadContourSet | None, float | None, np.ndarray | None, np.ndarray | None]:
    ratio_log2, mask = compute_relative_lift(z_target, z_benchmark)
    valid = ratio_log2[~mask]
    valid = valid[np.isfinite(valid)]
    if valid.size == 0:
        return None, None, None, None

    if fixed_vabs is not None:
        vabs = float(fixed_vabs)
    elif RELATIVE_FIXED_VABS is not None:
        vabs = float(RELATIVE_FIXED_VABS)
    else:
        vabs = float(np.nanquantile(np.abs(valid), float(RELATIVE_VABS_QUANTILE)))

    if not np.isfinite(vabs) or vabs <= 0:
        vabs = float(np.nanmax(np.abs(valid)))

    if not np.isfinite(vabs) or vabs <= 0:
        return None, None, None, None

    n_levels = max(7, int(level_count))
    levels = np.linspace(-vabs, vabs, n_levels)
    levels = drop_inner_relative_levels(levels, COLOR_LEVELS_DROP_LOWEST_K)
    if levels.size < 3:
        levels = np.linspace(-vabs, vabs, n_levels)
    z_masked = np.ma.masked_where(mask, ratio_log2)

    contourf = ax.contourf(
        xx,
        yy,
        z_masked,
        levels=levels,
        cmap=build_relative_cmap(),
        alpha=float(fill_alpha),
        antialiased=True,
        extend="both",
        zorder=3,
    )

    if RELATIVE_CONTOUR_LINES:
        ax.contour(
            xx,
            yy,
            z_masked,
            levels=levels,
            colors=RELATIVE_CONTOUR_LINE_COLOR,
            linewidths=RELATIVE_CONTOUR_LINE_WIDTH,
            linestyles="solid",
            alpha=RELATIVE_CONTOUR_LINE_ALPHA,
            zorder=4,
        )

    if RELATIVE_ZERO_LINE:
        ax.contour(
            xx,
            yy,
            z_masked,
            levels=[0.0],
            colors=RELATIVE_ZERO_LINE_COLOR,
            linewidths=RELATIVE_ZERO_LINE_WIDTH,
            alpha=RELATIVE_ZERO_LINE_ALPHA,
            zorder=4,
        )

    return contourf, vabs, ratio_log2, mask


def draw_over_expected_overlay(
    ax: mpl.axes.Axes,
    xx: np.ndarray,
    yy: np.ndarray,
    z_target: np.ndarray,
    z_benchmark: np.ndarray,
) -> None:
    if OVERLAY_STYLE == "none":
        return

    ratio_log2, mass_mask = compute_relative_lift(z_target, z_benchmark)
    if OVERLAY_IGNORE_MASS_MASK:
        z_lift = np.ma.array(ratio_log2, mask=np.zeros_like(ratio_log2, dtype=bool))
    else:
        z_lift = np.ma.masked_where(mass_mask, ratio_log2)

    pos_levels = sorted(float(v) for v in OVERLAY_POS_THRESHOLDS_LOG2)
    if OVERLAY_FORCE_ZERO_LEVEL and 0.0 not in pos_levels:
        pos_levels = sorted([0.0, *pos_levels])
    if pos_levels:
        ax.contour(
            xx,
            yy,
            z_lift,
            levels=pos_levels,
            colors=OVERLAY_POS_COLOR,
            linewidths=OVERLAY_LINE_WIDTH,
            linestyles=OVERLAY_POS_LINESTYLE,
            alpha=OVERLAY_LINE_ALPHA,
            zorder=9,
        )

    if OVERLAY_INCLUDE_NEGATIVE:
        neg_levels = sorted(float(v) for v in OVERLAY_NEG_THRESHOLDS_LOG2)
        if neg_levels:
            ax.contour(
                xx,
                yy,
                z_lift,
                levels=neg_levels,
                colors=OVERLAY_NEG_COLOR,
                linewidths=OVERLAY_LINE_WIDTH,
                linestyles=OVERLAY_NEG_LINESTYLE,
                alpha=OVERLAY_LINE_ALPHA,
                zorder=9,
            )


def plot_map_zoom(
    world_map: gpd.GeoDataFrame,
    points_gdf: gpd.GeoDataFrame,
    *,
    inst: str,
) -> mpl.figure.Figure:
    with mpl.rc_context({"font.size": 10, "axes.facecolor": "white", "figure.facecolor": "white"}):
        fig, ax = plt.subplots(figsize=(12, 10), dpi=450)

        world_proj = world_map.clip(EXTENT_WORLD).to_crs(ROBINSON_PROJ4)
        draw_world_fill(ax, world_proj)

        if points_gdf.empty:
            ax.text(
                0.5,
                0.5,
                "No geolocated citing institutions available.",
                ha="center",
                va="center",
                transform=ax.transAxes,
            )
            if COUNTRY_BORDER_ON_TOP:
                draw_world_borders(ax, world_proj)
            ax.set_axis_off()
            ax.set_title("")
            return fig

        points_proj = points_gdf.to_crs(ROBINSON_PROJ4)
        x = points_proj.geometry.x.to_numpy()
        y = points_proj.geometry.y.to_numpy()
        open_weights = points_proj["open_share_pct"].to_numpy()
        closed_weights = points_proj["closed_share_pct"].to_numpy()

        world_extent_proj = tuple(float(v) for v in world_proj.total_bounds)
        xx_w, yy_w, z_open_w = compute_surface_from_weights(
            x,
            y,
            open_weights,
            world_extent_proj,
            grid_x=CONTOUR_GRID_X,
            grid_y=CONTOUR_GRID_Y,
            smooth_sigma=CONTOUR_SMOOTH_SIGMA,
            auto_square_cells=CONTOUR_AUTO_SQUARE_CELLS,
            isotropic_smoothing=CONTOUR_AUTO_ISOTROPIC_SMOOTHING,
            min_grid_cells=MIN_CONTOUR_GRID_CELLS,
        )
        _, _, z_closed_w = compute_surface_from_weights(
            x,
            y,
            closed_weights,
            world_extent_proj,
            grid_x=CONTOUR_GRID_X,
            grid_y=CONTOUR_GRID_Y,
            smooth_sigma=CONTOUR_SMOOTH_SIGMA,
            auto_square_cells=CONTOUR_AUTO_SQUARE_CELLS,
            isotropic_smoothing=CONTOUR_AUTO_ISOTROPIC_SMOOTHING,
            min_grid_cells=MIN_CONTOUR_GRID_CELLS,
        )

        contourf_world, world_vabs, _, _ = draw_relative_contours(
            ax,
            xx_w,
            yy_w,
            z_open_w,
            z_closed_w,
            level_count=RELATIVE_LEVEL_COUNT,
            fill_alpha=RELATIVE_FILL_ALPHA,
            fixed_vabs=None,
        )

        if DRAW_ADDITIONAL_OVERLAY_LINES_ALWAYS and OVERLAY_STYLE != "none":
            draw_over_expected_overlay(ax, xx_w, yy_w, z_open_w, z_closed_w)

        if contourf_world is None:
            ax.text(
                0.5,
                0.5,
                "No open/closed contrast after smoothing.",
                ha="center",
                va="center",
                transform=ax.transAxes,
            )
            if COUNTRY_BORDER_ON_TOP:
                draw_world_borders(ax, world_proj)
            ax.set_axis_off()
            ax.set_title("")
            return fig

        cbar_label = (
            "Relative incoming citation shares normalised by OA\n"
            "(log2[Open share / Closed share])"
        )
        low_lab = "Closed-access citations\noverrepresented"
        high_lab = "Open-access citations\noverrepresented"

        cbar = fig.colorbar(
            contourf_world,
            ax=ax,
            orientation="vertical",
            shrink=COLORBAR_SHRINK,
            pad=COLORBAR_PAD,
            fraction=COLORBAR_FRACTION,
            extend="both",
            label=cbar_label,
        )
        cbar.outline.set_linewidth(0)
        apply_colorbar_layout(cbar)
        apply_qualitative_colorbar(cbar, low_lab, high_lab)

        if DRAW_ADDITIONAL_OVERLAY_LINES_ALWAYS and OVERLAY_STYLE != "none":
            handles = [
                Line2D(
                    [0],
                    [0],
                    color=OVERLAY_POS_COLOR,
                    lw=OVERLAY_LINE_WIDTH,
                    linestyle=OVERLAY_POS_LINESTYLE,
                    label="Open above Closed contour",
                )
            ]
            ax.legend(
                handles=handles,
                loc="lower left",
                frameon=False,
                fontsize=8,
                bbox_to_anchor=(0.01, 0.01),
            )

        # Zoom inset
        zoom_extent_proj = projected_extent(ZOOM_EXTENT)
        x0, y0, x1, y1 = zoom_extent_proj

        iax = ax.inset_axes(INSET_AX_BOUNDS, xticks=[], yticks=[])
        zoom_box = box(*zoom_extent_proj)
        world_zoom_proj = world_proj.clip(zoom_box)
        draw_world_fill(iax, world_zoom_proj)

        xx_z, yy_z, z_open_z = compute_surface_from_weights(
            x,
            y,
            open_weights,
            zoom_extent_proj,
            grid_x=ZOOM_CONTOUR_GRID_X,
            grid_y=ZOOM_CONTOUR_GRID_Y,
            smooth_sigma=ZOOM_CONTOUR_SMOOTH_SIGMA,
            auto_square_cells=CONTOUR_AUTO_SQUARE_CELLS,
            isotropic_smoothing=CONTOUR_AUTO_ISOTROPIC_SMOOTHING,
            min_grid_cells=MIN_CONTOUR_GRID_CELLS,
        )
        _, _, z_closed_z = compute_surface_from_weights(
            x,
            y,
            closed_weights,
            zoom_extent_proj,
            grid_x=ZOOM_CONTOUR_GRID_X,
            grid_y=ZOOM_CONTOUR_GRID_Y,
            smooth_sigma=ZOOM_CONTOUR_SMOOTH_SIGMA,
            auto_square_cells=CONTOUR_AUTO_SQUARE_CELLS,
            isotropic_smoothing=CONTOUR_AUTO_ISOTROPIC_SMOOTHING,
            min_grid_cells=MIN_CONTOUR_GRID_CELLS,
        )

        fixed_vabs = None
        if not ZOOM_RELATIVE_USE_LOCAL_SCALE:
            fixed_vabs = world_vabs
        draw_relative_contours(
            iax,
            xx_z,
            yy_z,
            z_open_z,
            z_closed_z,
            level_count=ZOOM_RELATIVE_LEVEL_COUNT,
            fill_alpha=ZOOM_CONTOUR_FILL_ALPHA,
            fixed_vabs=fixed_vabs,
        )

        if DRAW_ADDITIONAL_OVERLAY_LINES_ALWAYS and OVERLAY_STYLE != "none":
            draw_over_expected_overlay(iax, xx_z, yy_z, z_open_z, z_closed_z)

        iax.set_xlim(x0, x1)
        iax.set_ylim(y0, y1)
        iax.margins(0)

        conn_style = {
            "edgecolor": ZOOM_SELECTION_COLOR,
            "linewidth": ZOOM_SELECTION_LINEWIDTH,
            "alpha": ZOOM_SELECTION_ALPHA,
        }
        zoom_rect = Rectangle(
            (x0, y0),
            x1 - x0,
            y1 - y0,
            fill=False,
            zorder=ZOOM_SELECTION_ZORDER,
            **conn_style,
        )
        ax.add_patch(zoom_rect)

        connector_lower = ConnectionPatch(
            xyA=(x1, y0),
            coordsA=ax.transData,
            axesA=ax,
            xyB=(1, 0),
            coordsB=iax.transAxes,
            axesB=iax,
            zorder=ZOOM_SELECTION_ZORDER,
            clip_on=False,
            **conn_style,
        )
        connector_upper = ConnectionPatch(
            xyA=(x0, y1),
            coordsA=ax.transData,
            axesA=ax,
            xyB=(0, 1),
            coordsB=iax.transAxes,
            axesB=iax,
            zorder=ZOOM_SELECTION_ZORDER,
            clip_on=False,
            **conn_style,
        )
        ax.add_artist(connector_lower)
        ax.add_artist(connector_upper)

        iax.patch.set_edgecolor("none")
        iax.patch.set_linewidth(0)
        iax.patch.set_alpha(1.0)
        iax.patch.set_facecolor("none")

        inset_frame = Rectangle(
            (0, 0),
            1,
            1,
            transform=iax.transAxes,
            fill=False,
            edgecolor=INSET_FRAME_COLOR,
            linewidth=INSET_FRAME_LINEWIDTH,
            alpha=INSET_FRAME_ALPHA,
            zorder=INSET_FRAME_ZORDER,
            clip_on=False,
        )
        iax.add_patch(inset_frame)

        if COUNTRY_BORDER_ON_TOP:
            draw_world_borders(iax, world_zoom_proj)
            draw_world_borders(ax, world_proj)

        iax.set_axis_off()
        ax.set_axis_off()
        ax.set_title("")

    return fig


world_map_path = find_world_map_path()
world_map = load_world_map(world_map_path)

for inst, con in asset.iterate_institutions():
    if FORCE_ETHDOMAIN_OUTPUTS_FOR_ALL_UNITS and inst != "ethdomain":
        continue

    raw_df = asset.extract(
        con=con,
        inst=inst,
        query=query_citing_institutions_open_vs_closed(inst, asset.year_first, asset.year_last),
        out_name="data_raw.csv",
    )

    plot_df_prepost = prepare_plot_df(raw_df, world_map, apply_postprocessing=False)
    plot_df = prepare_plot_df(raw_df, world_map, apply_postprocessing=True)
    points_gdf = build_points_gdf(plot_df)

    export_df_prepost = plot_df_prepost[
        [
            "row_order",
            "institution_id",
            "institution_name",
            "country_code",
            "country_name",
            "geo_source",
            "lat",
            "lon",
            "open_links_full",
            "closed_links_full",
            "open_share",
            "closed_share",
            "open_share_pct",
            "closed_share_pct",
            "open_minus_closed_pp",
            "open_over_closed_ratio",
            "open_over_closed_log2",
            "total_open_links",
            "total_closed_links",
        ]
    ].copy()
    export_df_prepost[IND_C_INST_OPEN_LINKS] = export_df_prepost["open_links_full"]
    export_df_prepost[IND_C_INST_CLOSED_LINKS] = export_df_prepost["closed_links_full"]
    export_df_prepost[IND_PP_INST_OPEN_SHARE] = export_df_prepost["open_share"]
    export_df_prepost[IND_PP_INST_CLOSED_SHARE] = export_df_prepost["closed_share"]
    export_df_prepost[IND_DPP_INST_OPEN_MINUS_CLOSED] = export_df_prepost["open_minus_closed_pp"]
    export_df_prepost[IND_LOG2_INST_OPEN_OVER_CLOSED] = export_df_prepost["open_over_closed_log2"]

    export_df = plot_df[
        [
            "row_order",
            "institution_id",
            "institution_name",
            "country_code",
            "country_name",
            "geo_source",
            "lat",
            "lon",
            "open_links_full",
            "closed_links_full",
            "open_share",
            "closed_share",
            "open_share_pct",
            "closed_share_pct",
            "open_minus_closed_pp",
            "open_over_closed_ratio",
            "open_over_closed_log2",
            "total_open_links",
            "total_closed_links",
        ]
    ].copy()
    export_df[IND_C_INST_OPEN_LINKS] = export_df["open_links_full"]
    export_df[IND_C_INST_CLOSED_LINKS] = export_df["closed_links_full"]
    export_df[IND_PP_INST_OPEN_SHARE] = export_df["open_share"]
    export_df[IND_PP_INST_CLOSED_SHARE] = export_df["closed_share"]
    export_df[IND_DPP_INST_OPEN_MINUS_CLOSED] = export_df["open_minus_closed_pp"]
    export_df[IND_LOG2_INST_OPEN_OVER_CLOSED] = export_df["open_over_closed_log2"]

    fig = plot_map_zoom(world_map, points_gdf, inst=inst)
    export_bbox = export_bbox_inches(fig, EXPORT_BBOX_FRACTION)

    if FORCE_ETHDOMAIN_OUTPUTS_FOR_ALL_UNITS:
        out_institutions = asset.institutions
    else:
        out_institutions = [inst]

    for out_inst in out_institutions:
        out = asset.inst_dir(out_inst)
        export_df_prepost.to_csv(out / "data_prepost.csv", index=False)
        export_df.to_csv(out / "data.csv", index=False)
        plot_df.to_csv(out / "data_for_plot.csv", index=False)
        raw_df.to_csv(out / "data_raw.csv", index=False)
        fig.savefig(out / "figure.svg", dpi=300, bbox_inches=export_bbox)
        fig.savefig(out / "figure.png", dpi=300, bbox_inches=export_bbox, facecolor="white")
        fig.savefig(out / "figure.pdf", dpi=300, bbox_inches=export_bbox)
    plt.close(fig)
