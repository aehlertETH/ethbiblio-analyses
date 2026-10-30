from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import ConnectionPatch, Rectangle
from matplotlib.transforms import Bbox
from shapely.geometry import box

from core.asset import Asset
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


# ---------------------------------------------------------------------------
# Indicator and period settings
# ---------------------------------------------------------------------------
COUNTING_MODE = "full"  # full | fractional
RECENT_WINDOW_YEARS_OVERRIDE = None  # None -> uses asset.year_range_moving

MIN_SHARE_THRESHOLD = 0.005  # 0.5%
MIN_VOLUME_THRESHOLD = 10.0
FILTER_LOGIC = "or"  # or | and

TOP_GAIN_N = 5
TOP_LOSS_N = 5

IND_P_RECENT = "P_COLLAB_COUNTRY_RECENT_FULL"
IND_P_BASELINE = "P_COLLAB_COUNTRY_BASELINE_FULL"
IND_PP_RECENT = "PP_COLLAB_COUNTRY_SHARE_RECENT_FULL"
IND_PP_BASELINE = "PP_COLLAB_COUNTRY_SHARE_BASELINE_FULL"
IND_DPP_CHANGE = "DPP_COLLAB_COUNTRY_SHARE_CHANGE_FULL"

# ---------------------------------------------------------------------------
# Visual settings (aligned to geo assets)
# ---------------------------------------------------------------------------
LAND_COLOR = "#f7f7f7"
COLOR_POS = "#215CAF"  # strong blue from existing geo assets
COLOR_ZERO = "#ececec"  # zero class (slightly darker than land)
COLOR_NEG = "#b2182b"


COUNTRY_BORDER_COLOR = "white"
COUNTRY_BORDER_WIDTH = 0.5

# User-editable color binning in percentage points (pp)
# Add/remove values in COLOR_BIN_LIMITS_PP to increase/decrease number of bins.
# Caps define saturation: values beyond caps keep endpoint colors.
COLOR_CAP_MIN_PP = -3.0
COLOR_CAP_MAX_PP = 3.0
COLOR_BIN_LIMITS_PP = [-2.0, -1.0, -0.5, 0.0, 0.5, 1.0, 2.0]
COLORBAR_SHRINK = 0.35
COLORBAR_PAD = 0.006
COLORBAR_FRACTION = 0.030
# Legend (colorbar) fine layout controls in figure-relative coordinates.
# Move left with negative x, right with positive x.
COLORBAR_POS_DX = -0.055
COLORBAR_POS_DY = 0.0
# Scale legend box after creation (1.0 keeps current size).
COLORBAR_SCALE_W = 1.0
COLORBAR_SCALE_H = 1.0

ROBINSON_PROJ4 = "+proj=robin +lon_0=0 +datum=WGS84 +units=m +no_defs"
EXTENT_WORLD = (-180, -60, 180, 90)
ZOOM_EXTENT = (-10, 35.8, 21.5, 61)  # (xmin_lon, ymin_lat, xmax_lon, ymax_lat)
INSET_AX_BOUNDS = (-0.095, 0.004, 0.5, 0.5)  # (left, bottom, width, height) in parent axes
# Final export crop controls (relative to tight figure bounding box).
EXPORT_CROP_LEFT = 0.035
EXPORT_CROP_BOTTOM = 0.00
EXPORT_CROP_RIGHT = 0.985
EXPORT_CROP_TOP = 0.96
EXPORT_BBOX_FRACTION = (EXPORT_CROP_LEFT, EXPORT_CROP_BOTTOM, EXPORT_CROP_RIGHT, EXPORT_CROP_TOP)


def get_recent_window_years() -> int:
    if RECENT_WINDOW_YEARS_OVERRIDE is not None:
        return max(1, int(RECENT_WINDOW_YEARS_OVERRIDE))
    return max(1, int(asset.year_range_moving))


def get_period_bounds() -> tuple[int, int, int, int]:
    recent_window = get_recent_window_years()
    recent_end = int(asset.year_last)
    recent_start = max(int(asset.year_first), recent_end - recent_window + 1)
    baseline_start = int(asset.year_first)
    baseline_end = recent_start - 1
    return recent_start, recent_end, baseline_start, baseline_end


def query_collaboration_country_links(
    inst: str,
    y0: int,
    y1: int,
    recent_start: int,
    recent_end: int,
    baseline_start: int,
    baseline_end: int,
) -> str:
    return f"""
        WITH inst_pubs AS (
            SELECT DISTINCT
                rm.work_id,
                w.publication_year AS publication_year
            FROM reports.report_membership rm
            JOIN core.work w
              ON w.work_id = rm.work_id
            WHERE rm.report_name = '{inst}'
              AND w.publication_year BETWEEN {y0} AND {y1}
        ),

        partner_institutions AS (
            SELECT DISTINCT
                ip.work_id,
                ip.publication_year,
                wii.institution_id
            FROM inst_pubs ip
            JOIN marts.work_institution_info wii
              ON wii.work_id = ip.work_id
            WHERE wii.institution_id NOT IN (
                SELECT institution_id
                FROM reports.report_institutions_ids
                WHERE report_name = '{inst}'
            )
        ),

        collab_links AS (
            SELECT DISTINCT
                pi.work_id,
                pi.publication_year,
                dc.country_code,
                COALESCE(oac.display_name, dc.country_code) AS country_name
            FROM partner_institutions pi
            JOIN core.dim_institution di
              ON di.institution_id = pi.institution_id
            JOIN core.dim_country dc
              ON dc.country_id = di.country_id
            LEFT JOIN augmented.openalex_countries oac
              ON oac.code = dc.country_code
            WHERE dc.country_code IS NOT NULL
        ),

        output_totals AS (
            SELECT
                COUNT(DISTINCT work_id) AS p_output_full,
                COUNT(
                    DISTINCT CASE
                        WHEN publication_year BETWEEN {recent_start} AND {recent_end}
                        THEN work_id
                    END
                ) AS p_output_full_recent,
                COUNT(
                    DISTINCT CASE
                        WHEN publication_year BETWEEN {baseline_start} AND {baseline_end}
                        THEN work_id
                    END
                ) AS p_output_full_baseline
            FROM inst_pubs
        ),

        partner_counts AS (
            SELECT
                work_id,
                COUNT(*) AS n_partner_countries
            FROM collab_links
            GROUP BY work_id
        )

        SELECT
            cl.work_id,
            cl.publication_year,
            cl.country_code,
            cl.country_name,
            pc.n_partner_countries,
            ot.p_output_full,
            ot.p_output_full_recent,
            ot.p_output_full_baseline
        FROM collab_links cl
        JOIN partner_counts pc
          ON pc.work_id = cl.work_id
        CROSS JOIN output_totals ot
        ORDER BY cl.publication_year, cl.country_code, cl.work_id;
    """


def find_world_map_paths() -> tuple[Path, Path]:
    repo_root = Path(__file__).resolve().parents[2]

    p50_candidates = [
        asset.base_dir / "ne_50m_admin_0_countries.zip",
        repo_root / "core" / "maps" / "ne_50m_admin_0_countries.zip",
    ]
    p110_candidates = [
        asset.base_dir / "ne_110m_admin_0_countries.zip",
        repo_root / "core" / "maps" / "ne_110m_admin_0_countries.zip",
    ]

    p50 = next((p for p in p50_candidates if p.is_file()), None)
    p110 = next((p for p in p110_candidates if p.is_file()), None)

    if p50 is None or p110 is None:
        raise FileNotFoundError(
            "Natural Earth map not found. Looked for: "
            + ", ".join(str(p) for p in p50_candidates + p110_candidates)
        )

    return p50, p110


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


def load_world_maps() -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    p50, p110 = find_world_map_paths()
    return load_world_map(p50), load_world_map(p110)


def compute_country_change(raw_df: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "row_order",
        "country_code",
        "country_name",
        "volume_recent",
        "volume_baseline",
        "share_recent",
        "share_baseline",
        "delta_share",
        "delta_pp",
        "max_share",
        "max_volume",
        "is_in_scope",
        "counting_mode",
        "recent_start",
        "recent_end",
        "baseline_start",
        "baseline_end",
    ]
    if raw_df.empty:
        return pd.DataFrame(columns=cols)

    df = raw_df.copy()
    df["publication_year"] = pd.to_numeric(df["publication_year"], errors="coerce")
    df["n_partner_countries"] = pd.to_numeric(df["n_partner_countries"], errors="coerce")
    df = df.dropna(subset=["publication_year", "country_code"]).copy()
    df["publication_year"] = df["publication_year"].astype(int)
    df["country_code"] = df["country_code"].astype(str)
    df["country_name"] = df["country_name"].fillna(df["country_code"]).astype(str)
    df["n_partner_countries"] = df["n_partner_countries"].fillna(1).clip(lower=1)
    df["p_output_full_recent"] = pd.to_numeric(df["p_output_full_recent"], errors="coerce")
    df["p_output_full_baseline"] = pd.to_numeric(df["p_output_full_baseline"], errors="coerce")

    if COUNTING_MODE == "fractional":
        df["weight"] = 1.0 / df["n_partner_countries"]
    else:
        df["weight"] = 1.0

    recent_start, recent_end, baseline_start, baseline_end = get_period_bounds()

    recent = df[(df["publication_year"] >= recent_start) & (df["publication_year"] <= recent_end)].copy()

    if baseline_end >= baseline_start:
        baseline = df[(df["publication_year"] >= baseline_start) & (df["publication_year"] <= baseline_end)].copy()
    else:
        baseline = df.iloc[0:0].copy()

    recent_agg = (
        recent.groupby(["country_code", "country_name"], as_index=False)["weight"]
        .sum()
        .rename(columns={"weight": "volume_recent"})
    )
    baseline_agg = (
        baseline.groupby(["country_code", "country_name"], as_index=False)["weight"]
        .sum()
        .rename(columns={"weight": "volume_baseline"})
    )

    out = recent_agg.merge(
        baseline_agg,
        on=["country_code", "country_name"],
        how="outer",
    )

    out["volume_recent"] = pd.to_numeric(out["volume_recent"], errors="coerce").fillna(0.0)
    out["volume_baseline"] = pd.to_numeric(out["volume_baseline"], errors="coerce").fillna(0.0)

    # Match X_X_collaborationTopCountries semantics:
    # work-country presence in the numerator, total output in the denominator.
    total_recent = float(df["p_output_full_recent"].dropna().iloc[0]) if df["p_output_full_recent"].notna().any() else 0.0
    total_baseline = (
        float(df["p_output_full_baseline"].dropna().iloc[0]) if df["p_output_full_baseline"].notna().any() else 0.0
    )

    out["share_recent"] = out["volume_recent"] / total_recent if total_recent > 0 else 0.0
    out["share_baseline"] = out["volume_baseline"] / total_baseline if total_baseline > 0 else 0.0

    out["delta_share"] = out["share_recent"] - out["share_baseline"]
    out["delta_pp"] = 100.0 * out["delta_share"]
    out["max_share"] = out[["share_recent", "share_baseline"]].max(axis=1)
    out["max_volume"] = out[["volume_recent", "volume_baseline"]].max(axis=1)

    if FILTER_LOGIC.lower() == "and":
        out["is_in_scope"] = (out["max_share"] >= MIN_SHARE_THRESHOLD) & (out["max_volume"] >= MIN_VOLUME_THRESHOLD)
    else:
        out["is_in_scope"] = (out["max_share"] >= MIN_SHARE_THRESHOLD) | (out["max_volume"] >= MIN_VOLUME_THRESHOLD)

    out["counting_mode"] = COUNTING_MODE
    out["recent_start"] = recent_start
    out["recent_end"] = recent_end
    out["baseline_start"] = baseline_start
    out["baseline_end"] = baseline_end

    out = out.sort_values(["delta_pp", "share_recent", "volume_recent", "country_name", "country_code"], ascending=[False, False, False, True, True]).reset_index(drop=True)
    out["row_order"] = out.index + 1
    return out[cols]


def attach_iso3(country_change_df: pd.DataFrame, world_map: gpd.GeoDataFrame) -> pd.DataFrame:
    df = country_change_df.copy()
    iso_map = (
        world_map[["map_iso2_code", "map_iso3_code"]]
        .dropna()
        .drop_duplicates(subset=["map_iso2_code"], keep="first")
        .rename(columns={"map_iso2_code": "country_code", "map_iso3_code": "iso3_code"})
    )
    return df.merge(iso_map, on="country_code", how="left")


def build_plot_gdf(country_change_df: pd.DataFrame, world_map: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    df = attach_iso3(country_change_df, world_map)
    df["delta_pp_plot"] = df["delta_pp"].where(df["is_in_scope"], pd.NA)

    gdf = world_map.merge(df, left_on="map_iso3_code", right_on="iso3_code", how="left")
    gdf["country_name"] = gdf["country_name"].fillna(gdf["map_country_name"])
    return gdf


def _blend_hex(color_a: str, color_b: str, t: float) -> str:
    t = max(0.0, min(1.0, float(t)))
    a = mpl.colors.to_rgb(color_a)
    b = mpl.colors.to_rgb(color_b)
    mix = tuple(a_i + t * (b_i - a_i) for a_i, b_i in zip(a, b))
    return mpl.colors.to_hex(mix)


def get_color_boundaries_pp() -> list[float]:
    cap_min = float(COLOR_CAP_MIN_PP)
    cap_max = float(COLOR_CAP_MAX_PP)
    if cap_min >= cap_max:
        raise ValueError("COLOR_CAP_MIN_PP must be smaller than COLOR_CAP_MAX_PP.")

    inner = sorted({float(v) for v in COLOR_BIN_LIMITS_PP if cap_min < float(v) < cap_max})
    boundaries = [cap_min] + inner + [cap_max]

    if len(boundaries) < 2:
        raise ValueError("At least two color boundaries are required.")

    return boundaries


def build_binned_colormap_and_norm() -> tuple[mpl.colors.Colormap, mpl.colors.BoundaryNorm, list[float]]:
    boundaries = get_color_boundaries_pp()
    cap_min = boundaries[0]
    cap_max = boundaries[-1]

    bin_colors: list[str] = []
    for i in range(len(boundaries) - 1):
        low = boundaries[i]
        high = boundaries[i + 1]
        mid = 0.5 * (low + high)

        if mid < 0:
            t = (mid - cap_min) / (0.0 - cap_min) if cap_min < 0 else 1.0
            bin_colors.append(_blend_hex(COLOR_NEG, COLOR_ZERO, t))
        elif mid > 0:
            t = mid / cap_max if cap_max > 0 else 1.0
            bin_colors.append(_blend_hex(COLOR_ZERO, COLOR_POS, t))
        else:
            bin_colors.append(COLOR_ZERO)

    cmap = mpl.colors.ListedColormap(bin_colors)
    cmap.set_under(bin_colors[0])
    cmap.set_over(bin_colors[-1])

    norm = mpl.colors.BoundaryNorm(boundaries, cmap.N, clip=False)
    return cmap, norm, boundaries


def normalize_extent(extent: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    if len(extent) != 4:
        raise ValueError("Extent must be a tuple of four numeric values: (xmin, ymin, xmax, ymax).")

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
    return Bbox.from_extents(x0 + left * w, y0 + bottom * h, x0 + right * w, y0 + top * h)


def apply_colorbar_layout(cbar: mpl.colorbar.Colorbar) -> None:
    pos = cbar.ax.get_position()
    cbar.ax.set_position([
        pos.x0 + COLORBAR_POS_DX,
        pos.y0 + COLORBAR_POS_DY,
        pos.width * COLORBAR_SCALE_W,
        pos.height * COLORBAR_SCALE_H,
    ])


def plot_map(gdf_world: gpd.GeoDataFrame, gdf_zoom: gpd.GeoDataFrame, inst: str) -> mpl.figure.Figure:
    cmap, norm, boundaries = build_binned_colormap_and_norm()
    recent_start, recent_end, baseline_start, baseline_end = get_period_bounds()

    plot_kwargs = {
        "column": "delta_pp_plot",
        "cmap": cmap,
        "norm": norm,
        "legend": False,
        "edgecolor": COUNTRY_BORDER_COLOR,
        "linewidth": COUNTRY_BORDER_WIDTH,
        "missing_kwds": {
            "color": LAND_COLOR,
            "edgecolor": COUNTRY_BORDER_COLOR,
            "linewidth": COUNTRY_BORDER_WIDTH,
        },
    }

    with mpl.rc_context({"font.size": 10, "axes.facecolor": "white", "figure.facecolor": "white"}):
        fig, ax = plt.subplots(figsize=(12, 10), dpi=450)

        gdf_world.clip(EXTENT_WORLD).to_crs(ROBINSON_PROJ4).plot(ax=ax, **plot_kwargs)

        zoom_extent_proj = projected_extent(ZOOM_EXTENT)
        zoom_box_proj = box(*zoom_extent_proj)

        iax1 = ax.inset_axes(INSET_AX_BOUNDS, xticks=[], yticks=[])
        gdf_zoom.to_crs(ROBINSON_PROJ4).clip(zoom_box_proj).plot(ax=iax1, **plot_kwargs)

        x0, y0, x1, y1 = zoom_extent_proj
        iax1.set_xlim(x0, x1)
        iax1.set_ylim(y0, y1)
        iax1.margins(0)
        iax1.set_xticks([])
        iax1.set_yticks([])

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

        cbar = fig.colorbar(
            mpl.cm.ScalarMappable(norm=norm, cmap=cmap),
            ax=ax,
            orientation="vertical",
            shrink=COLORBAR_SHRINK,
            pad=COLORBAR_PAD,
            fraction=COLORBAR_FRACTION,
            extend="both",
            drawedges=True,
            label=(
                f"Change in share of total output\n"
                f"involving each country\n"
                f"from {baseline_start}-{baseline_end} to {recent_start}-{recent_end}\n"
                "(in percentage points)"
            ),
            ticks=boundaries,
        )
        cbar.outline.set_linewidth(0)
        cbar.dividers.set(edgecolor=COUNTRY_BORDER_COLOR, linewidth=COUNTRY_BORDER_WIDTH)
        apply_colorbar_layout(cbar)

        ax.set_axis_off()
        ax.set_title("")

    return fig


def plot_top_changes_bar(country_change_df: pd.DataFrame, inst: str) -> mpl.figure.Figure:
    recent_start, recent_end, baseline_start, baseline_end = get_period_bounds()

    scope_df = country_change_df[country_change_df["is_in_scope"]].copy()

    if scope_df.empty:
        with mpl.rc_context({"font.size": 11, "axes.facecolor": "white", "figure.facecolor": "white"}):
            fig, ax = plt.subplots(figsize=(12, 6), dpi=300)
            ax.text(0.5, 0.5, "No countries pass threshold filters.", ha="center", va="center")
            ax.set_axis_off()
            return fig

    gains = scope_df.sort_values(["delta_pp", "share_recent", "volume_recent", "country_name", "country_code"], ascending=[False, False, False, True, True]).head(TOP_GAIN_N)
    losses = scope_df.sort_values(["delta_pp", "share_recent", "volume_recent", "country_name", "country_code"], ascending=[True, False, False, True, True]).head(TOP_LOSS_N)

    bar_df = pd.concat([losses, gains], ignore_index=True)
    bar_df = bar_df.drop_duplicates(subset=["country_code"], keep="last")
    bar_df = bar_df.sort_values(["delta_pp", "country_name", "country_code"], ascending=[True, True, True]).reset_index(drop=True)

    colors = bar_df["delta_pp"].apply(lambda v: COLOR_POS if v >= 0 else COLOR_NEG)

    with mpl.rc_context({"font.size": 10, "axes.facecolor": "white", "figure.facecolor": "white"}):
        fig, ax = plt.subplots(figsize=(12, 7), dpi=300)

        bars = ax.barh(bar_df["country_name"], bar_df["delta_pp"], color=colors)
        ax.axvline(0, color="#666666", linewidth=1.2)
        ax.grid(axis="x", color="#d0d0d0", linewidth=0.8)
        ax.set_axisbelow(True)

        ax.set_xlabel("Change in total output share (pp)")
        ax.set_ylabel("")
        ax.set_title(
            f"Top {TOP_GAIN_N} gains and top {TOP_LOSS_N} reductions in total output share\n"
            f"from {baseline_start}-{baseline_end} to {recent_start}-{recent_end}"
        )

        labels = [f"{v:+.2f} pp" for v in bar_df["delta_pp"]]
        ax.bar_label(bars, labels=labels, padding=3, fontsize=9)

        for spine in ["top", "right", "left"]:
            ax.spines[spine].set_visible(False)

        fig.tight_layout()

    return fig


# ---------------------------------------------------------------------------
# Run asset
# ---------------------------------------------------------------------------
world_map_50, world_map_110 = load_world_maps()

recent_start, recent_end, baseline_start, baseline_end = get_period_bounds()

for inst, con in asset.iterate_institutions():
    raw_df = asset.extract(
        con=con,
        inst=inst,
        query=query_collaboration_country_links(
            inst,
            asset.year_first,
            asset.year_last,
            recent_start,
            recent_end,
            baseline_start,
            baseline_end,
        ),
        out_name="data_raw.csv",
    )

    country_change_df = compute_country_change(raw_df)
    gdf_50 = build_plot_gdf(country_change_df, world_map_50)
    gdf_110 = build_plot_gdf(country_change_df, world_map_110)

    out = asset.inst_dir(inst)

    export_df = country_change_df[[
        "row_order",
        "country_code",
        "country_name",
        "is_in_scope",
        "counting_mode",
        "recent_start",
        "recent_end",
        "baseline_start",
        "baseline_end",
    ]].copy()
    export_df[IND_P_RECENT] = country_change_df["volume_recent"]
    export_df[IND_P_BASELINE] = country_change_df["volume_baseline"]
    export_df[IND_PP_RECENT] = country_change_df["share_recent"]
    export_df[IND_PP_BASELINE] = country_change_df["share_baseline"]
    export_df[IND_DPP_CHANGE] = country_change_df["delta_pp"]

    export_df.to_csv(out / "data.csv", index=False)
    country_change_df.to_csv(out / "data_for_plot.csv", index=False)

    top_changes_df = (
        export_df[export_df["is_in_scope"]]
        .sort_values("row_order", ascending=True)
        .reset_index(drop=True)
    )
    top_changes_df.to_csv(out / "data_top_changes.csv", index=False)

    fig_map = plot_map(gdf_50, gdf_110, inst)
    export_bbox = export_bbox_inches(fig_map, EXPORT_BBOX_FRACTION)
    fig_map.savefig(out / "figure.svg", dpi=300, bbox_inches=export_bbox)
    fig_map.savefig(out / "figure.png", dpi=300, bbox_inches=export_bbox, facecolor="white")
    fig_map.savefig(out / "figure.pdf", dpi=300, bbox_inches=export_bbox)
    plt.close(fig_map)

    fig_bar = plot_top_changes_bar(country_change_df, inst)
    fig_bar.savefig(out / "figure_bar.svg", dpi=300, bbox_inches="tight")
    fig_bar.savefig(out / "figure_bar.png", dpi=300, bbox_inches="tight", facecolor="white")
    fig_bar.savefig(out / "figure_bar.pdf", dpi=300, bbox_inches="tight")
    plt.close(fig_bar)
