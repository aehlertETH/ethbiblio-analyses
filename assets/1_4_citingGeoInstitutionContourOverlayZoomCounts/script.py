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
from pyproj import Transformer

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
# Indicator settings
# ---------------------------------------------------------------------------
IND_C_INST_LINKS = "C_CITING_INST_GEO_LINKS_FULL"
IND_PP_INST_SHARE = "PP_CITING_INST_GEO_SHARE_FULL"

# ---------------------------------------------------------------------------
# INTERPRETATION subset export settings
# ---------------------------------------------------------------------------
INTERPRETATION_SUBSET_FILENAME = "data_interpretation_subset.csv"
INTERPRETATION_SUBSET_MAX_ROWS = 20
INTERPRETATION_SUBSET_TOP_VOLUME_POOL = 200
INTERPRETATION_SUBSET_MIN_LIFT_RATIO = 1.25
INTERPRETATION_REGION_SUBSET_FILENAME = "data_interpretation_region_subset.csv"
INTERPRETATION_REGION_MAX_ROWS = 12
INTERPRETATION_REGION_MIN_SURFACE_TARGET_SHARE_PCT = 0.50
INTERPRETATION_REGION_TOP_COUNTRY_COUNT = 3
INTERPRETATION_REGION_TOP_INSTITUTION_COUNT = 10
SELF_INSTITUTION_IDS = {
    # Canonical OpenAlex institution ids for focal units.
    "empa": 71824836,
    "epfl": 5124864,
    "psi": 2802229908,
    "wsl": 2800262456,
    "ethz": 35440088,
    "eawag": 63664421,
}

# ---------------------------------------------------------------------------
# Benchmark toggles (user-adjustable)
# ---------------------------------------------------------------------------
REFERENCE_MODE = "global"  # "eth_domain" | "global"
ETH_DOMAIN_REPORT = "ethdomain"
EXCLUDE_TARGET_FROM_ETH_DOMAIN_BENCHMARK = True
ETH_DOMAIN_BENCHMARK_FALLBACK_TO_GLOBAL = True
SHARED_CACHE_INST = "_shared"
COUNTING_MODE = "full"  # "full" | "fractional"
GLOBAL_BENCHMARK_CACHE_NAME = f"data_raw_global_benchmark_{COUNTING_MODE}.csv"
TARGET_RAW_CACHE_NAME = f"data_raw_target_{COUNTING_MODE}.csv"
DUCKDB_THREADS: int | None = 4
DUCKDB_DISABLE_PRESERVE_INSERTION_ORDER = True

# Display modes:
# - "relative_fill": option 1 (relative contour surface)
# - "absolute_plus_overlay": option 2 (absolute contour + over-expected overlay)
DISPLAY_MODE = "absolute_plus_overlay"

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
COUNTRY_BORDER_COLOR = "#4f4f4f"
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
    "#f7f7f7",
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
CONTOUR_MIN_FRAC_OF_VMAX = 0.0005
ABSOLUTE_APPLY_MIN_THRESHOLD_MASK = True
CONTOUR_VMAX_QUANTILE = 0.99
CONTOUR_FILL_ALPHA = 0.34
CONTOUR_LINE_ALPHA = 0.28
CONTOUR_LINE_COLOR = "white"
CONTOUR_LINE_WIDTH = 0.22

# Relative contour settings (option 1)
RELATIVE_LEVEL_COUNT = 18
COLOR_LEVELS_DROP_LOWEST_K = (
    0  # absolute: drop lowest k; relative: drop k inner bands per side
)
RELATIVE_VABS_QUANTILE = 0.98
RELATIVE_FIXED_VABS: float | None = None
RELATIVE_EPS_FRAC_OF_MAX = 0.01
RELATIVE_MIN_TOTAL_FRAC_OF_MAX = CONTOUR_MIN_FRAC_OF_VMAX
RELATIVE_APPLY_MASS_THRESHOLD_MASK = ABSOLUTE_APPLY_MIN_THRESHOLD_MASK
RELATIVE_FILL_ALPHA = 0.55
RELATIVE_ZERO_LINE = True
RELATIVE_ZERO_LINE_COLOR = "#202020"
RELATIVE_ZERO_LINE_WIDTH = 0.55
RELATIVE_ZERO_LINE_ALPHA = 0.95
RELATIVE_CONTOUR_LINES = False
RELATIVE_CONTOUR_LINE_COLOR = "#2a2a2a"
RELATIVE_CONTOUR_LINE_WIDTH = 0.20
RELATIVE_CONTOUR_LINE_ALPHA = 0.35

# Option 2 overlay settings
OVERLAY_STYLE = "contour"  # contour | hatch | both | none
DRAW_ADDITIONAL_OVERLAY_LINES_ALWAYS = True
OVERLAY_INCLUDE_NEGATIVE = False
OVERLAY_POS_THRESHOLDS_LOG2 = [0.322, 0.585, 1.000]  # x1.25, x1.5, x2.0
OVERLAY_NEG_THRESHOLDS_LOG2 = [-0.322, -0.585, -1.000]
OVERLAY_POS_COLOR = "#111111"
OVERLAY_NEG_COLOR = "#555555"
OVERLAY_LINE_WIDTH = 0.6
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
COLORBAR_POS_DX = -0.055
COLORBAR_POS_DY = 0.00
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


def normalize_reference_mode(mode: str) -> str:
    val = str(mode).strip().lower()
    if val not in {"eth_domain", "global"}:
        raise ValueError("REFERENCE_MODE must be 'eth_domain' or 'global'.")
    return val


def normalize_counting_mode(mode: str) -> str:
    val = str(mode).strip().lower()
    if val not in {"full", "fractional"}:
        raise ValueError("COUNTING_MODE must be 'full' or 'fractional'.")
    return val


def is_fractional_counting_mode() -> bool:
    return normalize_counting_mode(COUNTING_MODE) == "fractional"


def effective_reference_mode(inst: str) -> str:
    mode = normalize_reference_mode(REFERENCE_MODE)
    if (
        mode == "eth_domain"
        and EXCLUDE_TARGET_FROM_ETH_DOMAIN_BENCHMARK
        and inst == ETH_DOMAIN_REPORT
        and ETH_DOMAIN_BENCHMARK_FALLBACK_TO_GLOBAL
    ):
        return "global"
    return mode


def benchmark_label(mode: str) -> str:
    if mode == "eth_domain":
        if EXCLUDE_TARGET_FROM_ETH_DOMAIN_BENCHMARK:
            return "ETH Domain benchmark (excluding focal unit)"
        return "ETH Domain benchmark"
    return "global benchmark"


def institution_aggregate_sql(citing_work_edge_counts_cte: str, count_alias: str) -> str:
    mode = normalize_counting_mode(COUNTING_MODE)
    contribution_expr = "cwe.n_edges"
    if mode == "fractional":
        contribution_expr = "cwe.n_edges / NULLIF(ic.n_inst, 0)"

    return f"""
        SELECT
            di.institution_id,
            di.ror,
            di.name AS institution_name,
            dc.country_code,
            COALESCE(oac.display_name, dc.country_code) AS country_name,
            SUM({contribution_expr}) AS {count_alias}
        FROM {citing_work_edge_counts_cte} cwe
        JOIN marts.work_institution_info wii
          ON wii.work_id = cwe.citing_work_id
        JOIN core.dim_institution di
          ON di.institution_id = wii.institution_id
        LEFT JOIN core.dim_country dc
          ON dc.country_id = di.country_id
        LEFT JOIN augmented.openalex_countries oac
          ON oac.code = dc.country_code
        LEFT JOIN (
            SELECT
                wii2.work_id AS citing_work_id,
                COUNT(DISTINCT wii2.institution_id) AS n_inst
            FROM marts.work_institution_info wii2
            JOIN {citing_work_edge_counts_cte} cwe2
              ON cwe2.citing_work_id = wii2.work_id
            GROUP BY wii2.work_id
        ) ic
          ON ic.citing_work_id = cwe.citing_work_id
        WHERE dc.country_code IS NOT NULL
        GROUP BY
            di.institution_id,
            di.ror,
            di.name,
            dc.country_code,
            COALESCE(oac.display_name, dc.country_code)
    """


def query_target_citing_institutions(inst: str, y0: int, y1: int) -> str:
    target_agg_sql = institution_aggregate_sql(
        "target_citing_work_edge_counts", "target_links_full"
    )
    return f"""
        WITH target_pubs AS (
            SELECT DISTINCT rm.work_id
            FROM reports.report_membership rm
            JOIN core.work w
              ON w.work_id = rm.work_id
            WHERE rm.report_name = '{inst}'
              AND w.publication_year BETWEEN {y0} AND {y1}
        ),

        target_citing_work_edge_counts AS (
            SELECT
                r.citing_id AS citing_work_id,
                COUNT(DISTINCT r.cited_id) AS n_edges
            FROM core.refs r
            JOIN target_pubs tp
              ON tp.work_id = r.cited_id
            GROUP BY r.citing_id
        )

        {target_agg_sql}
        ORDER BY target_links_full DESC, institution_name ASC, institution_id ASC;
    """


def query_global_benchmark_citing_institutions(y0: int, y1: int) -> str:
    benchmark_agg_sql = institution_aggregate_sql(
        "benchmark_citing_work_edge_counts", "benchmark_links_full"
    )
    return f"""
        WITH benchmark_pubs AS (
            SELECT DISTINCT w.work_id
            FROM core.work w
            WHERE w.publication_year BETWEEN {y0} AND {y1}
        ),

        benchmark_citing_work_edge_counts AS (
            SELECT
                r.citing_id AS citing_work_id,
                COUNT(DISTINCT r.cited_id) AS n_edges
            FROM core.refs r
            JOIN benchmark_pubs bp
              ON bp.work_id = r.cited_id
            GROUP BY r.citing_id
        )

        {benchmark_agg_sql}
        ORDER BY benchmark_links_full DESC, institution_name ASC, institution_id ASC;
    """


def query_citing_institutions_with_benchmark(
    inst: str, y0: int, y1: int, mode: str
) -> str:
    target_agg_sql = institution_aggregate_sql(
        "target_citing_work_edge_counts", "target_links_full"
    )
    benchmark_agg_sql = institution_aggregate_sql(
        "benchmark_citing_work_edge_counts", "benchmark_links_full"
    )

    if mode == "global":
        benchmark_pubs_sql = f"""
            SELECT DISTINCT w.work_id
            FROM core.work w
            WHERE w.publication_year BETWEEN {y0} AND {y1}
        """
    else:
        exclusion_sql = (
            "AND tp.work_id IS NULL" if EXCLUDE_TARGET_FROM_ETH_DOMAIN_BENCHMARK else ""
        )
        benchmark_pubs_sql = f"""
            SELECT DISTINCT rm.work_id
            FROM reports.report_membership rm
            JOIN core.work w
              ON w.work_id = rm.work_id
            LEFT JOIN target_pubs tp
              ON tp.work_id = rm.work_id
            WHERE rm.report_name = '{ETH_DOMAIN_REPORT}'
              AND w.publication_year BETWEEN {y0} AND {y1}
              {exclusion_sql}
        """

    return f"""
        WITH target_pubs AS (
            SELECT DISTINCT rm.work_id
            FROM reports.report_membership rm
            JOIN core.work w
              ON w.work_id = rm.work_id
            WHERE rm.report_name = '{inst}'
              AND w.publication_year BETWEEN {y0} AND {y1}
        ),

        benchmark_pubs AS (
            {benchmark_pubs_sql}
        ),

        target_citing_work_edge_counts AS (
            SELECT
                r.citing_id AS citing_work_id,
                COUNT(DISTINCT r.cited_id) AS n_edges
            FROM core.refs r
            JOIN target_pubs tp
              ON tp.work_id = r.cited_id
            GROUP BY r.citing_id
        ),

        benchmark_citing_work_edge_counts AS (
            SELECT
                r.citing_id AS citing_work_id,
                COUNT(DISTINCT r.cited_id) AS n_edges
            FROM core.refs r
            JOIN benchmark_pubs bp
              ON bp.work_id = r.cited_id
            GROUP BY r.citing_id
        ),

        target_agg AS (
            {target_agg_sql}
        ),

        benchmark_agg AS (
            {benchmark_agg_sql}
        )

        SELECT
            COALESCE(t.institution_id, b.institution_id) AS institution_id,
            COALESCE(t.ror, b.ror) AS ror,
            COALESCE(t.institution_name, b.institution_name) AS institution_name,
            COALESCE(t.country_code, b.country_code) AS country_code,
            COALESCE(t.country_name, b.country_name) AS country_name,
            COALESCE(t.target_links_full, 0) AS target_links_full,
            COALESCE(b.benchmark_links_full, 0) AS benchmark_links_full
        FROM target_agg t
        FULL OUTER JOIN benchmark_agg b
          ON t.institution_id = b.institution_id
        ORDER BY target_links_full DESC, benchmark_links_full DESC, institution_name ASC, institution_id ASC;
    """


def combine_target_and_benchmark(
    target_df: pd.DataFrame, benchmark_df: pd.DataFrame
) -> pd.DataFrame:
    target_cols = [
        "institution_id",
        "ror",
        "institution_name",
        "country_code",
        "country_name",
        "target_links_full",
    ]
    benchmark_cols = [
        "institution_id",
        "ror",
        "institution_name",
        "country_code",
        "country_name",
        "benchmark_links_full",
    ]

    left = target_df.copy()
    right = benchmark_df.copy()

    for col in target_cols:
        if col not in left.columns:
            left[col] = np.nan
    for col in benchmark_cols:
        if col not in right.columns:
            right[col] = np.nan

    left = left[target_cols].copy()
    right = right[benchmark_cols].copy()

    left["institution_id"] = pd.to_numeric(left["institution_id"], errors="coerce")
    right["institution_id"] = pd.to_numeric(right["institution_id"], errors="coerce")

    merged = left.merge(
        right, on="institution_id", how="outer", suffixes=("_target", "_benchmark")
    )

    out = pd.DataFrame(
        {
            "institution_id": merged["institution_id"],
            "ror": merged["ror_target"].combine_first(merged["ror_benchmark"]),
            "institution_name": merged["institution_name_target"].combine_first(
                merged["institution_name_benchmark"]
            ),
            "country_code": merged["country_code_target"].combine_first(
                merged["country_code_benchmark"]
            ),
            "country_name": merged["country_name_target"].combine_first(
                merged["country_name_benchmark"]
            ),
            "target_links_full": pd.to_numeric(
                merged["target_links_full"], errors="coerce"
            ).fillna(0.0),
            "benchmark_links_full": pd.to_numeric(
                merged["benchmark_links_full"], errors="coerce"
            ).fillna(0.0),
        }
    )

    out = out.sort_values(
        [
            "target_links_full",
            "benchmark_links_full",
            "institution_name",
            "institution_id",
        ],
        ascending=[False, False, True, True],
    ).reset_index(drop=True)
    return out


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
        "Natural Earth map not found. Looked for: "
        + ", ".join(str(c) for c in candidates)
    )


def load_world_map(path: Path) -> gpd.GeoDataFrame:
    world = gpd.read_file(path)

    iso3_candidates = ["ISO_A3_EH", "ADM0_A3", "ISO_A3", "SOV_A3"]
    iso2_candidates = ["ISO_A2_EH", "ISO_A2"]
    name_candidates = ["NAME_EN", "NAME", "ADMIN"]

    iso3_col = next(
        (column for column in iso3_candidates if column in world.columns), None
    )
    iso2_col = next(
        (column for column in iso2_candidates if column in world.columns), None
    )
    name_col = next(
        (column for column in name_candidates if column in world.columns), None
    )

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


def extend_ror_cache_if_enabled(
    plot_df: pd.DataFrame, cache_df: pd.DataFrame, local_cache_path: Path
) -> pd.DataFrame:
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

    gdf = gpd.GeoDataFrame(
        df[["country_code"]], geometry=df["geometry"], crs="EPSG:4326"
    )
    gdf_metric = gdf.to_crs("EPSG:3857")
    centroids_metric = gdf_metric.geometry.centroid
    centroids = gpd.GeoSeries(centroids_metric, crs="EPSG:3857").to_crs("EPSG:4326")

    out = pd.DataFrame(
        {
            "country_code": gdf["country_code"].values,
            "centroid_lat": centroids.y.values,
            "centroid_lon": centroids.x.values,
        }
    )
    out = out.drop_duplicates(subset=["country_code"], keep="first")
    return out


def resolve_asset_ror_cache(raw_by_inst: dict[str, pd.DataFrame]) -> pd.DataFrame:
    ror_ids_set: set[str] = set()
    for raw_df in raw_by_inst.values():
        if raw_df.empty or "ror" not in raw_df.columns:
            continue
        ids = raw_df["ror"].apply(parse_ror_id)
        ids = ids[ids.notna()].astype(str).str.strip()
        ids = ids[ids != ""]
        ror_ids_set.update(ids.tolist())

    ror_ids = sorted(ror_ids_set)
    if not ror_ids:
        return pd.DataFrame(columns=["ror_id", "lat", "lon"])

    local_cache_path = asset.base_dir / ROR_CACHE_FILENAME
    return resolve_ror_metadata(
        ror_ids,
        local_cache_path=local_cache_path,
        include_acronym=False,
        context=f"{asset.base_dir.name}:asset-cache",
    )


def prepare_plot_df(
    raw_df: pd.DataFrame,
    world_map: gpd.GeoDataFrame,
    ref_mode: str,
    apply_postprocessing: bool = True,
    ror_cache_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
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
        "target_links_full",
        "benchmark_links_full",
        "target_share",
        "benchmark_share",
        "target_share_pct",
        "benchmark_share_pct",
        "delta_share_pp",
        "lift_ratio",
        "lift_log2",
        "total_target_links",
        "total_benchmark_links",
        "benchmark_mode",
    ]
    if raw_df.empty:
        return pd.DataFrame(columns=cols)

    df = raw_df.copy()
    if apply_postprocessing:
        df = postprocess_excluded_institutions(df, institution_id_col="institution_id")
    df["institution_id"] = pd.to_numeric(df["institution_id"], errors="coerce")
    df["institution_name"] = (
        df["institution_name"].fillna("Unknown institution").astype(str)
    )
    df["country_code"] = df["country_code"].astype(str)
    df["country_name"] = df["country_name"].fillna(df["country_code"]).astype(str)
    df["target_links_full"] = pd.to_numeric(
        df["target_links_full"], errors="coerce"
    ).fillna(0.0)
    df["benchmark_links_full"] = pd.to_numeric(
        df["benchmark_links_full"], errors="coerce"
    ).fillna(0.0)
    df = df[(df["target_links_full"] > 0) | (df["benchmark_links_full"] > 0)].copy()

    df["ror_id"] = df["ror"].apply(parse_ror_id)

    mode_label = "prepost" if not apply_postprocessing else "post"
    ror_ids = sorted(df["ror_id"].dropna().astype(str).unique().tolist())
    if ror_cache_df is not None:
        if ror_ids:
            cache_df = ror_cache_df[ror_cache_df["ror_id"].isin(ror_ids)][
                ["ror_id", "lat", "lon"]
            ].copy()
        else:
            cache_df = pd.DataFrame(columns=["ror_id", "lat", "lon"])
    else:
        local_cache_path = asset.base_dir / ROR_CACHE_FILENAME
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

    total_target_links = float(df["target_links_full"].sum())
    total_benchmark_links = float(df["benchmark_links_full"].sum())
    df["target_share"] = (
        df["target_links_full"] / total_target_links if total_target_links > 0 else 0.0
    )
    df["benchmark_share"] = (
        df["benchmark_links_full"] / total_benchmark_links
        if total_benchmark_links > 0
        else 0.0
    )
    df["target_share_pct"] = 100.0 * df["target_share"]
    df["benchmark_share_pct"] = 100.0 * df["benchmark_share"]
    df["delta_share_pp"] = df["target_share_pct"] - df["benchmark_share_pct"]

    eps_share = 1e-12
    df["lift_ratio"] = (df["target_share"] + eps_share) / (
        df["benchmark_share"] + eps_share
    )
    df["lift_log2"] = np.log2(df["lift_ratio"])

    df["total_target_links"] = total_target_links
    df["total_benchmark_links"] = total_benchmark_links
    df["benchmark_mode"] = ref_mode

    df = df.sort_values(
        [
            "target_links_full",
            "target_share",
            "benchmark_links_full",
            "institution_name",
            "institution_id",
        ],
        ascending=[False, False, False, True, True],
    ).reset_index(drop=True)
    df["row_order"] = df.index + 1

    return df[cols]


def classify_lift_band(lift_ratio: float) -> str:
    if pd.isna(lift_ratio):
        return ""
    if lift_ratio >= 2.0:
        return ">=2.0x"
    if lift_ratio >= 1.5:
        return "1.5x-2.0x"
    if lift_ratio >= 1.25:
        return "1.25x-1.5x"
    return "1.0x-1.25x"


def _format_top_values(values: pd.Series, limit: int) -> str:
    s = values.dropna().astype(str).str.strip()
    s = s[s != ""]
    if s.empty:
        return ""
    return "; ".join(s.head(int(limit)).tolist())


def _build_region_label(country_names: pd.Series) -> str:
    top = _format_top_values(country_names, INTERPRETATION_REGION_TOP_COUNTRY_COUNT)
    if top:
        return f"{top} cluster"
    return "Over-benchmark citation cluster"


def build_interpretation_subset(export_df: pd.DataFrame, inst: str) -> pd.DataFrame:
    cols = [
        "subset_rank",
        "volume_rank",
        "institution_name",
        "country_name",
        "target_links_full",
        "target_share_pct",
        "benchmark_share_pct",
        "delta_share_pp",
        "lift_ratio",
        "lift_band",
    ]
    if export_df.empty:
        return pd.DataFrame(columns=cols)

    df = export_df.copy()
    df["institution_id"] = pd.to_numeric(df["institution_id"], errors="coerce")
    df["row_order"] = pd.to_numeric(df["row_order"], errors="coerce")
    for col in [
        "target_links_full",
        "target_share_pct",
        "benchmark_share_pct",
        "delta_share_pp",
        "lift_ratio",
    ]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    self_id = SELF_INSTITUTION_IDS.get(inst)
    if self_id is not None:
        df = df[df["institution_id"] != self_id].copy()

    df = df[df["row_order"] <= INTERPRETATION_SUBSET_TOP_VOLUME_POOL].copy()
    df = df[df["lift_ratio"] >= INTERPRETATION_SUBSET_MIN_LIFT_RATIO].copy()
    df = (
        df.sort_values(
            ["lift_ratio", "target_links_full", "delta_share_pp", "institution_name"],
            ascending=[False, False, False, True],
        )
        .head(INTERPRETATION_SUBSET_MAX_ROWS)
        .copy()
    )

    df["subset_rank"] = np.arange(1, len(df) + 1)
    df["volume_rank"] = df["row_order"].round().astype(int)
    if is_fractional_counting_mode():
        df["target_links_full"] = df["target_links_full"].round(3)
    else:
        df["target_links_full"] = df["target_links_full"].round().astype(int)
    df["target_share_pct"] = df["target_share_pct"].round(4)
    df["benchmark_share_pct"] = df["benchmark_share_pct"].round(4)
    df["delta_share_pp"] = df["delta_share_pp"].round(3)
    df["lift_ratio"] = df["lift_ratio"].round(3)
    df["lift_band"] = df["lift_ratio"].apply(classify_lift_band)

    return df[cols].copy()


def build_interpretation_region_subset(
    export_df: pd.DataFrame, inst: str
) -> pd.DataFrame:
    cols = [
        "region_rank",
        "region_label",
        "center_lat",
        "center_lon",
        "surface_target_share_pct",
        "surface_benchmark_share_pct",
        "surface_delta_pp",
        "surface_weighted_lift_ratio",
        "surface_peak_lift_ratio",
        "anchor_institutions_n",
        "anchor_target_links_full",
        "anchor_target_share_pct",
        "anchor_benchmark_share_pct",
        "dominant_countries",
        "anchor_institutions",
    ]
    if export_df.empty:
        return pd.DataFrame(columns=cols)

    df = export_df.copy()
    for col in [
        "institution_id",
        "row_order",
        "lat",
        "lon",
        "target_links_full",
        "benchmark_links_full",
        "target_share_pct",
        "benchmark_share_pct",
        "lift_ratio",
    ]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(
        subset=["lat", "lon", "target_share_pct", "benchmark_share_pct"]
    ).copy()
    if df.empty:
        return pd.DataFrame(columns=cols)

    self_id = SELF_INSTITUTION_IDS.get(inst)
    if self_id is not None:
        df = df[df["institution_id"] != self_id].copy()
    if df.empty:
        return pd.DataFrame(columns=cols)

    transformer = Transformer.from_crs("EPSG:4326", ROBINSON_PROJ4, always_xy=True)
    inverse_transformer = Transformer.from_crs(
        ROBINSON_PROJ4, "EPSG:4326", always_xy=True
    )
    x_proj, y_proj = transformer.transform(
        df["lon"].to_numpy(dtype=float),
        df["lat"].to_numpy(dtype=float),
    )

    extent_proj = projected_extent(EXTENT_WORLD)
    xx, yy, z_target = compute_surface_from_weights(
        x_proj,
        y_proj,
        df["target_share_pct"].to_numpy(dtype=float),
        extent_proj,
        grid_x=CONTOUR_GRID_X,
        grid_y=CONTOUR_GRID_Y,
        smooth_sigma=CONTOUR_SMOOTH_SIGMA,
        auto_square_cells=CONTOUR_AUTO_SQUARE_CELLS,
        isotropic_smoothing=CONTOUR_AUTO_ISOTROPIC_SMOOTHING,
        min_grid_cells=MIN_CONTOUR_GRID_CELLS,
    )
    _, _, z_benchmark = compute_surface_from_weights(
        x_proj,
        y_proj,
        df["benchmark_share_pct"].to_numpy(dtype=float),
        extent_proj,
        grid_x=CONTOUR_GRID_X,
        grid_y=CONTOUR_GRID_Y,
        smooth_sigma=CONTOUR_SMOOTH_SIGMA,
        auto_square_cells=CONTOUR_AUTO_SQUARE_CELLS,
        isotropic_smoothing=CONTOUR_AUTO_ISOTROPIC_SMOOTHING,
        min_grid_cells=MIN_CONTOUR_GRID_CELLS,
    )

    lift_log2, mass_mask = compute_relative_lift(z_target, z_benchmark)
    component_mask = (~mass_mask) & (lift_log2 >= min(OVERLAY_POS_THRESHOLDS_LOG2))
    component_labels = label_large_components(
        component_mask, OVERLAY_MIN_COMPONENT_CELLS
    )
    if int(component_labels.max()) <= 0:
        return pd.DataFrame(columns=cols)

    xmin, ymin, xmax, ymax = [float(v) for v in extent_proj]
    nrows, ncols = component_labels.shape
    cell_size_x = max(1e-9, (xmax - xmin) / float(ncols))
    cell_size_y = max(1e-9, (ymax - ymin) / float(nrows))

    anchor_df = df[df["row_order"] <= INTERPRETATION_SUBSET_TOP_VOLUME_POOL].copy()
    anchor_df["component_id"] = 0
    if not anchor_df.empty:
        anchor_x, anchor_y = transformer.transform(
            anchor_df["lon"].to_numpy(dtype=float),
            anchor_df["lat"].to_numpy(dtype=float),
        )
        for idx, (px, py) in zip(anchor_df.index, zip(anchor_x, anchor_y)):
            col = int(np.floor((px - xmin) / cell_size_x))
            row = int(np.floor((py - ymin) / cell_size_y))
            col = int(np.clip(col, 0, ncols - 1))
            row = int(np.clip(row, 0, nrows - 1))
            component_id = int(component_labels[row, col])

            if component_id == 0:
                for radius in (1, 2):
                    row0 = max(0, row - radius)
                    row1 = min(nrows, row + radius + 1)
                    col0 = max(0, col - radius)
                    col1 = min(ncols, col + radius + 1)
                    window = component_labels[row0:row1, col0:col1]
                    hits = np.argwhere(window > 0)
                    if hits.size == 0:
                        continue
                    distances = (hits[:, 0] + row0 - row) ** 2 + (
                        hits[:, 1] + col0 - col
                    ) ** 2
                    best = hits[int(np.argmin(distances))]
                    component_id = int(window[best[0], best[1]])
                    if component_id > 0:
                        break

            anchor_df.at[idx, "component_id"] = component_id

    rows: list[dict[str, object]] = []
    for component_id in range(1, int(component_labels.max()) + 1):
        mask = component_labels == component_id
        surface_target_share_pct = float(np.nansum(z_target[mask]))
        if surface_target_share_pct < float(
            INTERPRETATION_REGION_MIN_SURFACE_TARGET_SHARE_PCT
        ):
            continue

        anchors = anchor_df[anchor_df["component_id"] == component_id].copy()
        if anchors.empty:
            continue

        surface_benchmark_share_pct = float(np.nansum(z_benchmark[mask]))
        surface_delta_pp = surface_target_share_pct - surface_benchmark_share_pct
        component_lift_ratio = np.exp2(lift_log2[mask])
        weights = np.maximum(z_target[mask], 1e-12)
        surface_weighted_lift_ratio = float(
            np.average(component_lift_ratio, weights=weights)
        )
        surface_peak_lift_ratio = float(np.nanmax(component_lift_ratio))

        center_x = float(np.average(xx[mask], weights=weights))
        center_y = float(np.average(yy[mask], weights=weights))
        center_lon, center_lat = inverse_transformer.transform(center_x, center_y)

        anchors = anchors.sort_values(
            ["target_links_full", "lift_ratio", "institution_name"],
            ascending=[False, False, True],
        )
        anchors_display = anchors.copy()
        anchors_display["rank_volume"] = anchors_display["target_links_full"].rank(
            method="min", ascending=False
        )
        anchors_display["rank_lift"] = anchors_display["lift_ratio"].rank(
            method="min", ascending=False
        )
        anchors_display["rank_sum"] = (
            anchors_display["rank_volume"] + anchors_display["rank_lift"]
        )
        anchors_display = anchors_display.sort_values(
            [
                "rank_sum",
                "rank_volume",
                "rank_lift",
                "target_links_full",
                "lift_ratio",
                "institution_name",
            ],
            ascending=[True, True, True, False, False, True],
        )

        dominant_countries = (
            anchors.groupby("country_name", dropna=False)["target_links_full"]
            .sum()
            .sort_values(ascending=False)
            .reset_index()["country_name"]
        )

        rows.append(
            {
                "region_label": _build_region_label(dominant_countries),
                "center_lat": round(float(center_lat), 3),
                "center_lon": round(float(center_lon), 3),
                "surface_target_share_pct": round(surface_target_share_pct, 3),
                "surface_benchmark_share_pct": round(surface_benchmark_share_pct, 3),
                "surface_delta_pp": round(surface_delta_pp, 3),
                "surface_weighted_lift_ratio": round(surface_weighted_lift_ratio, 3),
                "surface_peak_lift_ratio": round(surface_peak_lift_ratio, 3),
                "anchor_institutions_n": int(len(anchors)),
                "anchor_target_links_full": (
                    round(float(anchors["target_links_full"].sum()), 3)
                    if is_fractional_counting_mode()
                    else int(round(float(anchors["target_links_full"].sum())))
                ),
                "anchor_target_share_pct": round(
                    float(anchors["target_share_pct"].sum()), 3
                ),
                "anchor_benchmark_share_pct": round(
                    float(anchors["benchmark_share_pct"].sum()), 3
                ),
                "dominant_countries": _format_top_values(
                    dominant_countries,
                    INTERPRETATION_REGION_TOP_COUNTRY_COUNT,
                ),
                "anchor_institutions": _format_top_values(
                    anchors_display["institution_name"],
                    INTERPRETATION_REGION_TOP_INSTITUTION_COUNT,
                ),
            }
        )

    if not rows:
        return pd.DataFrame(columns=cols)

    out = pd.DataFrame(rows)
    out = out.sort_values(
        [
            "surface_target_share_pct",
            "surface_peak_lift_ratio",
            "anchor_target_links_full",
            "region_label",
        ],
        ascending=[False, False, False, True],
    ).head(INTERPRETATION_REGION_MAX_ROWS)
    out = out.reset_index(drop=True)
    out.insert(0, "region_rank", np.arange(1, len(out) + 1))
    return out[cols].copy()


def build_points_gdf(plot_df: pd.DataFrame) -> gpd.GeoDataFrame:
    sel = plot_df.dropna(subset=["lon", "lat"]).copy()
    return gpd.GeoDataFrame(
        sel,
        geometry=gpd.points_from_xy(sel["lon"], sel["lat"]),
        crs="EPSG:4326",
    )


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
        x0 + left * w,
        y0 + bottom * h,
        x0 + right * w,
        y0 + top * h,
    )


def apply_colorbar_layout(cbar: mpl.colorbar.Colorbar) -> None:
    pos = cbar.ax.get_position()
    cbar.ax.set_position(
        [
            pos.x0 + COLORBAR_POS_DX,
            pos.y0 + COLORBAR_POS_DY,
            pos.width * COLORBAR_SCALE_W,
            pos.height * COLORBAR_SCALE_H,
        ]
    )


def apply_qualitative_colorbar(
    cbar: mpl.colorbar.Colorbar,
    low_label: str,
    high_label: str,
) -> None:
    vmin, vmax = cbar.mappable.get_clim()
    cbar.set_ticks([vmin, vmax])
    cbar.set_ticklabels([low_label, high_label])
    cbar.ax.tick_params(labelsize=COLORBAR_TICK_FONTSIZE)
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
        (-1, -1),
        (-1, 0),
        (-1, 1),
        (0, -1),
        (0, 1),
        (1, -1),
        (1, 0),
        (1, 1),
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


def label_large_components(mask: np.ndarray, min_cells: int) -> np.ndarray:
    arr = np.asarray(mask, dtype=bool)
    min_cells = int(max(1, min_cells))
    if min_cells <= 1 and np.any(arr):
        return arr.astype(int)

    out = np.zeros(arr.shape, dtype=int)
    visited = np.zeros_like(arr, dtype=bool)
    nrows, ncols = arr.shape
    neighbors = [
        (-1, -1),
        (-1, 0),
        (-1, 1),
        (0, -1),
        (0, 1),
        (1, -1),
        (1, 0),
        (1, 1),
    ]
    label = 0

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

            if len(component) < min_cells:
                continue

            label += 1
            for rr, cc in component:
                out[rr, cc] = label

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
    return mpl.colors.LinearSegmentedColormap.from_list(
        "citing_absolute", ABSOLUTE_COLORS, N=256
    )


def build_relative_cmap() -> mpl.colors.Colormap:
    return mpl.colors.LinearSegmentedColormap.from_list(
        "citing_relative", RELATIVE_COLORS, N=256
    )


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


def smooth_2d_gaussian(
    z: np.ndarray, sigma_x: float, sigma_y: float | None = None
) -> np.ndarray:
    sigma_x = float(max(0.0, sigma_x))
    if sigma_y is None:
        sigma_y = sigma_x
    sigma_y = float(max(0.0, sigma_y))

    if sigma_x <= 0 and sigma_y <= 0:
        return z

    out = np.asarray(z, dtype=float)

    if sigma_x > 0:
        kernel_x = gaussian_kernel_1d(sigma_x)
        out = np.apply_along_axis(
            lambda m: np.convolve(m, kernel_x, mode="same"), axis=1, arr=out
        )

    if sigma_y > 0:
        kernel_y = gaussian_kernel_1d(sigma_y)
        out = np.apply_along_axis(
            lambda m: np.convolve(m, kernel_y, mode="same"), axis=0, arr=out
        )

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


def normalize_extent(
    extent: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    if len(extent) != 4:
        raise ValueError(
            "Extent must be a tuple of 4 values: (xmin, ymin, xmax, ymax)."
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
    max_ref = float(max(np.nanmax(z_target), np.nanmax(z_benchmark), 1e-12))
    eps = max(1e-12, float(RELATIVE_EPS_FRAC_OF_MAX) * max_ref)

    total_mass = z_target + z_benchmark
    if RELATIVE_APPLY_MASS_THRESHOLD_MASK:
        threshold = float(RELATIVE_MIN_TOTAL_FRAC_OF_MAX) * float(np.nanmax(total_mass))
        mask = total_mass <= threshold
    else:
        mask = np.zeros_like(total_mass, dtype=bool)

    lift_log2 = np.log2((z_target + eps) / (z_benchmark + eps))
    return lift_log2, mask


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
    elif ABSOLUTE_APPLY_MIN_THRESHOLD_MASK:
        vmin = float(min_frac_of_vmax) * vmax
    else:
        vmin = 0.0

    if not np.isfinite(vmin) or not np.isfinite(vmax) or vmax <= vmin:
        return None, None, None

    levels = get_contour_levels_param(
        vmin, vmax, int(level_count), level_spacing, levels_custom
    )
    levels = drop_lowest_absolute_levels(levels, COLOR_LEVELS_DROP_LOWEST_K)
    if levels.size < 2:
        levels = np.linspace(
            vmin, vmax, max(6, int(level_count) if int(level_count) > 1 else 6)
        )
        levels = drop_lowest_absolute_levels(levels, COLOR_LEVELS_DROP_LOWEST_K)
    if levels.size < 2:
        levels = np.linspace(vmin, vmax, 2)

    if fixed_vmin is not None or ABSOLUTE_APPLY_MIN_THRESHOLD_MASK:
        z_masked = np.ma.masked_less_equal(z_target, vmin)
    else:
        z_masked = np.ma.array(z_target, mask=np.zeros_like(z_target, dtype=bool))

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
) -> tuple[
    mpl.contour.QuadContourSet | None,
    float | None,
    np.ndarray | None,
    np.ndarray | None,
]:
    lift_log2, mask = compute_relative_lift(z_target, z_benchmark)
    valid = lift_log2[~mask]
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
    z_masked = np.ma.masked_where(mask, lift_log2)

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

    return contourf, vabs, lift_log2, mask


def draw_over_expected_overlay(
    ax: mpl.axes.Axes,
    xx: np.ndarray,
    yy: np.ndarray,
    z_target: np.ndarray,
    z_benchmark: np.ndarray,
) -> None:
    if OVERLAY_STYLE == "none":
        return

    lift_log2, mass_mask = compute_relative_lift(z_target, z_benchmark)
    z_lift = np.ma.masked_where(mass_mask, lift_log2)

    pos_levels = sorted(float(v) for v in OVERLAY_POS_THRESHOLDS_LOG2)
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
    ref_mode: str,
) -> mpl.figure.Figure:
    with mpl.rc_context(
        {"font.size": 10, "axes.facecolor": "white", "figure.facecolor": "white"}
    ):
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
        target_weights = points_proj["target_share_pct"].to_numpy()
        benchmark_weights = points_proj["benchmark_share_pct"].to_numpy()

        world_extent_proj = tuple(float(v) for v in world_proj.total_bounds)
        xx_w, yy_w, z_target_w = compute_surface_from_weights(
            x,
            y,
            target_weights,
            world_extent_proj,
            grid_x=CONTOUR_GRID_X,
            grid_y=CONTOUR_GRID_Y,
            smooth_sigma=CONTOUR_SMOOTH_SIGMA,
            auto_square_cells=CONTOUR_AUTO_SQUARE_CELLS,
            isotropic_smoothing=CONTOUR_AUTO_ISOTROPIC_SMOOTHING,
            min_grid_cells=MIN_CONTOUR_GRID_CELLS,
        )
        _, _, z_benchmark_w = compute_surface_from_weights(
            x,
            y,
            benchmark_weights,
            world_extent_proj,
            grid_x=CONTOUR_GRID_X,
            grid_y=CONTOUR_GRID_Y,
            smooth_sigma=CONTOUR_SMOOTH_SIGMA,
            auto_square_cells=CONTOUR_AUTO_SQUARE_CELLS,
            isotropic_smoothing=CONTOUR_AUTO_ISOTROPIC_SMOOTHING,
            min_grid_cells=MIN_CONTOUR_GRID_CELLS,
        )

        contourf_world = None
        world_vmin = None
        world_vmax = None
        world_vabs = None

        mode = str(DISPLAY_MODE).strip().lower()
        if mode == "relative_fill":
            contourf_world, world_vabs, _, _ = draw_relative_contours(
                ax,
                xx_w,
                yy_w,
                z_target_w,
                z_benchmark_w,
                level_count=RELATIVE_LEVEL_COUNT,
                fill_alpha=RELATIVE_FILL_ALPHA,
                fixed_vabs=None,
            )
        else:
            contourf_world, world_vmin, world_vmax = draw_absolute_contours(
                ax,
                xx_w,
                yy_w,
                z_target_w,
                level_count=CONTOUR_LEVEL_COUNT,
                level_spacing=CONTOUR_LEVEL_SPACING,
                levels_custom=CONTOUR_LEVELS_CUSTOM,
                min_frac_of_vmax=CONTOUR_MIN_FRAC_OF_VMAX,
                vmax_quantile=CONTOUR_VMAX_QUANTILE,
                fill_alpha=CONTOUR_FILL_ALPHA,
                line_alpha=CONTOUR_LINE_ALPHA,
                line_width=CONTOUR_LINE_WIDTH,
                line_color=CONTOUR_LINE_COLOR,
                cmap=build_absolute_cmap(),
                fixed_vmin=None,
                fixed_vmax=None,
            )

        if DRAW_ADDITIONAL_OVERLAY_LINES_ALWAYS and OVERLAY_STYLE != "none":
            draw_over_expected_overlay(ax, xx_w, yy_w, z_target_w, z_benchmark_w)

        if contourf_world is None:
            ax.text(
                0.5,
                0.5,
                "No positive intensity after smoothing.",
                ha="center",
                va="center",
                transform=ax.transAxes,
            )
            if COUNTRY_BORDER_ON_TOP:
                draw_world_borders(ax, world_proj)
            ax.set_axis_off()
            ax.set_title("")
            return fig

        if mode == "relative_fill":
            cbar_label = "Relative incoming citation intensity"
            low_lab = "Moderate"
            high_lab = "High"
        else:
            cbar_label = "Incoming citation intensity"
            low_lab = "Moderate"
            high_lab = "High"

        cbar = fig.colorbar(
            contourf_world,
            ax=ax,
            orientation="vertical",
            shrink=COLORBAR_SHRINK,
            pad=COLORBAR_PAD,
            fraction=COLORBAR_FRACTION,
            extend="both" if mode == "relative_fill" else "max",
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
                    label=f"Relative citation concentration above {benchmark_label(ref_mode)} (contours at 1.25x, 1.5x, 2x)",
                )
            ]
            if OVERLAY_INCLUDE_NEGATIVE:
                handles.append(
                    Line2D(
                        [0],
                        [0],
                        color=OVERLAY_NEG_COLOR,
                        lw=OVERLAY_LINE_WIDTH,
                        linestyle=OVERLAY_NEG_LINESTYLE,
                        label=f"Below {benchmark_label(ref_mode)} contour",
                    )
                )
            ax.legend(
                handles=handles,
                loc="lower right",
                frameon=False,
                fontsize=8,
                bbox_to_anchor=(0.95, 0.01),
            )

        # Zoom inset
        # Zoom inset
        zoom_extent_proj = projected_extent(ZOOM_EXTENT)
        x0, y0, x1, y1 = zoom_extent_proj

        iax = ax.inset_axes(INSET_AX_BOUNDS, xticks=[], yticks=[])
        zoom_box = box(*zoom_extent_proj)
        world_zoom_proj = world_proj.clip(zoom_box)
        draw_world_fill(iax, world_zoom_proj)

        xx_z, yy_z, z_target_z = compute_surface_from_weights(
            x,
            y,
            target_weights,
            zoom_extent_proj,
            grid_x=ZOOM_CONTOUR_GRID_X,
            grid_y=ZOOM_CONTOUR_GRID_Y,
            smooth_sigma=ZOOM_CONTOUR_SMOOTH_SIGMA,
            auto_square_cells=CONTOUR_AUTO_SQUARE_CELLS,
            isotropic_smoothing=CONTOUR_AUTO_ISOTROPIC_SMOOTHING,
            min_grid_cells=MIN_CONTOUR_GRID_CELLS,
        )
        _, _, z_benchmark_z = compute_surface_from_weights(
            x,
            y,
            benchmark_weights,
            zoom_extent_proj,
            grid_x=ZOOM_CONTOUR_GRID_X,
            grid_y=ZOOM_CONTOUR_GRID_Y,
            smooth_sigma=ZOOM_CONTOUR_SMOOTH_SIGMA,
            auto_square_cells=CONTOUR_AUTO_SQUARE_CELLS,
            isotropic_smoothing=CONTOUR_AUTO_ISOTROPIC_SMOOTHING,
            min_grid_cells=MIN_CONTOUR_GRID_CELLS,
        )
        if mode == "relative_fill":
            fixed_vabs = None
            if not ZOOM_RELATIVE_USE_LOCAL_SCALE:
                fixed_vabs = world_vabs
            draw_relative_contours(
                iax,
                xx_z,
                yy_z,
                z_target_z,
                z_benchmark_z,
                level_count=ZOOM_RELATIVE_LEVEL_COUNT,
                fill_alpha=ZOOM_CONTOUR_FILL_ALPHA,
                fixed_vabs=fixed_vabs,
            )
        else:
            fixed_vmin = None if ZOOM_USE_LOCAL_SCALE else world_vmin
            fixed_vmax = None if ZOOM_USE_LOCAL_SCALE else world_vmax
            draw_absolute_contours(
                iax,
                xx_z,
                yy_z,
                z_target_z,
                level_count=ZOOM_CONTOUR_LEVEL_COUNT,
                level_spacing=ZOOM_CONTOUR_LEVEL_SPACING,
                levels_custom=ZOOM_CONTOUR_LEVELS_CUSTOM,
                min_frac_of_vmax=ZOOM_CONTOUR_MIN_FRAC_OF_VMAX,
                vmax_quantile=ZOOM_CONTOUR_VMAX_QUANTILE,
                fill_alpha=ZOOM_CONTOUR_FILL_ALPHA,
                line_alpha=ZOOM_CONTOUR_LINE_ALPHA,
                line_width=ZOOM_CONTOUR_LINE_WIDTH,
                line_color=ZOOM_CONTOUR_LINE_COLOR,
                cmap=build_absolute_cmap(),
                fixed_vmin=fixed_vmin,
                fixed_vmax=fixed_vmax,
            )

        if DRAW_ADDITIONAL_OVERLAY_LINES_ALWAYS and OVERLAY_STYLE != "none":
            draw_over_expected_overlay(iax, xx_z, yy_z, z_target_z, z_benchmark_z)

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

raw_by_inst: dict[str, pd.DataFrame] = {}
ref_mode_by_inst = {inst: effective_reference_mode(inst) for inst in asset.institutions}

con = asset.connect()
try:
    if DUCKDB_THREADS is not None and int(DUCKDB_THREADS) > 0:
        con.execute(f"SET threads={int(DUCKDB_THREADS)}")
    if DUCKDB_DISABLE_PRESERVE_INSERTION_ORDER:
        con.execute("SET preserve_insertion_order=false")

    shared_global_benchmark_df = pd.DataFrame()
    if any(mode == "global" for mode in ref_mode_by_inst.values()):
        shared_global_benchmark_df = asset.extract(
            con=con,
            inst=SHARED_CACHE_INST,
            query=query_global_benchmark_citing_institutions(
                asset.year_first, asset.year_last
            ),
            out_name=GLOBAL_BENCHMARK_CACHE_NAME,
            force=False,
        )

    for inst in asset.institutions:
        ref_mode = ref_mode_by_inst[inst]
        out = asset.inst_dir(inst)

        if ref_mode == "global":
            target_df = asset.extract(
                con=con,
                inst=inst,
                query=query_target_citing_institutions(
                    inst, asset.year_first, asset.year_last
                ),
                out_name=TARGET_RAW_CACHE_NAME,
                force=False,
            )
            raw_df = combine_target_and_benchmark(target_df, shared_global_benchmark_df)
        else:
            raw_df = asset.extract(
                con=con,
                inst=inst,
                query=query_citing_institutions_with_benchmark(
                    inst, asset.year_first, asset.year_last, ref_mode
                ),
                out_name=f"data_raw_{ref_mode}_{normalize_counting_mode(COUNTING_MODE)}.csv",
                force=False,
            )

        raw_df.to_csv(out / "data_raw.csv", index=False)
        raw_by_inst[inst] = raw_df
finally:
    con.close()

asset_ror_cache_df = resolve_asset_ror_cache(raw_by_inst)

for inst in asset.institutions:
    ref_mode = ref_mode_by_inst[inst]
    raw_df = raw_by_inst.get(inst, pd.DataFrame())

    plot_df_prepost = prepare_plot_df(
        raw_df,
        world_map,
        ref_mode,
        apply_postprocessing=False,
        ror_cache_df=asset_ror_cache_df,
    )
    plot_df = prepare_plot_df(
        raw_df,
        world_map,
        ref_mode,
        apply_postprocessing=True,
        ror_cache_df=asset_ror_cache_df,
    )
    points_gdf = build_points_gdf(plot_df)

    out = asset.inst_dir(inst)
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
            "target_links_full",
            "benchmark_links_full",
            "target_share",
            "benchmark_share",
            "target_share_pct",
            "benchmark_share_pct",
            "delta_share_pp",
            "lift_ratio",
            "lift_log2",
            "total_target_links",
            "total_benchmark_links",
            "benchmark_mode",
        ]
    ].copy()
    export_df_prepost[IND_C_INST_LINKS] = export_df_prepost["target_links_full"]
    export_df_prepost[IND_PP_INST_SHARE] = export_df_prepost["target_share"]

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
            "target_links_full",
            "benchmark_links_full",
            "target_share",
            "benchmark_share",
            "target_share_pct",
            "benchmark_share_pct",
            "delta_share_pp",
            "lift_ratio",
            "lift_log2",
            "total_target_links",
            "total_benchmark_links",
            "benchmark_mode",
        ]
    ].copy()
    export_df[IND_C_INST_LINKS] = export_df["target_links_full"]
    export_df[IND_PP_INST_SHARE] = export_df["target_share"]
    interpretation_subset_df = build_interpretation_subset(export_df, inst)
    interpretation_region_subset_df = build_interpretation_region_subset(
        export_df, inst
    )

    export_df_prepost.to_csv(out / "data_prepost.csv", index=False)
    export_df.to_csv(out / "data.csv", index=False)
    interpretation_subset_df.to_csv(out / INTERPRETATION_SUBSET_FILENAME, index=False)
    interpretation_region_subset_df.to_csv(
        out / INTERPRETATION_REGION_SUBSET_FILENAME, index=False
    )
    plot_df.to_csv(out / "data_for_plot.csv", index=False)

    fig = plot_map_zoom(world_map, points_gdf, inst=inst, ref_mode=ref_mode)
    export_bbox = export_bbox_inches(fig, EXPORT_BBOX_FRACTION)
    fig.savefig(out / "figure.svg", dpi=300, bbox_inches=export_bbox)
    fig.savefig(out / "figure.png", dpi=300, bbox_inches=export_bbox, facecolor="white")
    fig.savefig(out / "figure.pdf", dpi=300, bbox_inches=export_bbox)
    plt.close(fig)
