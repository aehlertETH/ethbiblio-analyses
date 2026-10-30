import math

import matplotlib
matplotlib.use("Agg")

import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

from core.asset import Asset
from utility import get_indicator_catalog_dict


RAW_EXPORT_NAME = "export.csv"
YEARLY_EXPORT_NAME = "yearly_data.csv"
MA_YEAR_COL = "MA_year"

N_BOOTSTRAP = 1000
STABILITY_LEVEL = 0.95
BOOTSTRAP_SEED = 42
BOOTSTRAP_BATCH_SIZE = 50

MNCS_VALUE_COL = "mncs_norm_vs_mean"
MNCS_N_INST_COL = "mncs_n_institutions_on_work"
MNCS_RELIABLE_COL = "mncs_cohort_is_reliable"

PP_VALUE_COL = "pptop10_is_top10"
PP_N_INST_COL = "pptop10_n_institutions_on_work"
PP_RELIABLE_COL = "pptop10_cohort_is_reliable"

MNCS_COLOR = "#0F6B85"
PPTOP10_COLOR = "#923243"
MNCS_ALPHA = 0.90
PPTOP10_ALPHA = 0.90
MNCS_BAND_ALPHA = 0.22
PPTOP10_BAND_ALPHA = 0.22

FONT_SIZE_MAIN = 11

AXIS_COLOR = "#BDBDBD"
GRIDLINE_COLOR = "#D6D6D6"
REFERENCE_LINE_COLOR = "#9C9C9C"
TEXT_COLOR = "#222222"

FONT_CANDIDATES = ["Arial", "Helvetica", "Liberation Sans", "DejaVu Sans"]


def _configure_matplotlib_style() -> str:
    available = {f.name for f in fm.fontManager.ttflist}
    primary_font = next((name for name in FONT_CANDIDATES if name in available), "DejaVu Sans")
    sans_fonts = [primary_font] + [name for name in FONT_CANDIDATES if name != primary_font]

    matplotlib.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": sans_fonts,
            "font.size": 10,
            "text.color": TEXT_COLOR,
            "axes.labelcolor": TEXT_COLOR,
            "axes.edgecolor": AXIS_COLOR,
            "axes.linewidth": 1.0,
            "xtick.color": GRIDLINE_COLOR,
            "ytick.color": GRIDLINE_COLOR,
            "mathtext.fontset": "custom",
            "mathtext.rm": primary_font,
            "mathtext.it": f"{primary_font}:italic",
            "mathtext.bf": f"{primary_font}:bold",
            "mathtext.sf": primary_font,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.facecolor": "white",
        }
    )
    return primary_font


_MATH_FONT = _configure_matplotlib_style()

def q_mncs_pptop10_raw(inst: str, y0: int, y1: int) -> str:
    return f"""
        SELECT
            report.work_id,
            w.publication_year AS year,
            m.norm_vs_mean AS {MNCS_VALUE_COL},
            m.n_institutions_on_work AS {MNCS_N_INST_COL},
            m.cohort_is_reliable AS {MNCS_RELIABLE_COL},
            CASE WHEN wm.is_top10 = 1 THEN 1 ELSE 0 END AS {PP_VALUE_COL},
            wm.n_institutions_on_work AS {PP_N_INST_COL},
            wm.cohort_is_reliable AS {PP_RELIABLE_COL}
        FROM reports.report_membership AS report
        INNER JOIN core.work AS w
            ON w.work_id = report.work_id
        LEFT JOIN marts.work_citation_metrics AS m
            ON m.work_id = report.work_id
        LEFT JOIN marts.work_metrics AS wm
            ON wm.work_id = report.work_id
        WHERE w.publication_year BETWEEN {y0} AND {y1}
          AND report.report_name = '{inst}';
    """


def _label_from_symbol(symbol_tex: str, fallback: str) -> str:
    symbol = str(symbol_tex).strip()
    if not symbol:
        return fallback
    return f"${symbol}$"


def _format_ma_label(v: str) -> str:
    s = str(v)
    if "-" not in s:
        return s
    y0, y1 = s.split("-", 1)
    return f"{y0}-\n{y1}"


def _as_bool(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)
    lowered = series.astype(str).str.strip().str.lower()
    return lowered.isin(["1", "true", "t", "yes", "y"])


def _weighted_mean(values: np.ndarray, weights: np.ndarray) -> float:
    if values.size == 0 or weights.size == 0:
        return float("nan")
    denominator = weights.sum()
    if denominator == 0:
        return float("nan")
    return float(np.dot(values, weights) / denominator)


def _bootstrap_weighted_means(
    values: np.ndarray,
    weights: np.ndarray,
    *,
    n_bootstrap: int,
    rng: np.random.Generator,
    batch_size: int,
) -> np.ndarray:
    stats = np.full(n_bootstrap, np.nan, dtype=float)
    if values.size == 0 or weights.size == 0:
        return stats

    n_rows = values.size
    offset = 0

    while offset < n_bootstrap:
        n_draws = min(batch_size, n_bootstrap - offset)
        idx = rng.integers(0, n_rows, size=(n_draws, n_rows))

        sampled_values = values[idx]
        sampled_weights = weights[idx]

        numerators = (sampled_values * sampled_weights).sum(axis=1)
        denominators = sampled_weights.sum(axis=1)

        stats[offset : offset + n_draws] = np.divide(
            numerators,
            denominators,
            out=np.full(n_draws, np.nan, dtype=float),
            where=denominators != 0,
        )
        offset += n_draws

    return stats


def _quantile_bounds(draws: np.ndarray, ci_level: float) -> tuple[float, float]:
    valid = draws[np.isfinite(draws)]
    if valid.size == 0:
        return float("nan"), float("nan")

    alpha = 1.0 - ci_level
    lower = float(np.quantile(valid, alpha / 2.0))
    upper = float(np.quantile(valid, 1.0 - alpha / 2.0))
    return lower, upper


def _prepare_raw_df(raw_df: pd.DataFrame) -> pd.DataFrame:
    df = raw_df.copy()

    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df = df.dropna(subset=["year"]).copy()
    df["year"] = df["year"].astype(int)

    numeric_cols = [
        MNCS_VALUE_COL,
        MNCS_N_INST_COL,
        PP_VALUE_COL,
        PP_N_INST_COL,
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df[MNCS_RELIABLE_COL] = _as_bool(df[MNCS_RELIABLE_COL])
    df[PP_RELIABLE_COL] = _as_bool(df[PP_RELIABLE_COL])

    return df


def _compute_yearly_bootstrap(
    raw_df: pd.DataFrame,
) -> tuple[
    pd.DataFrame,
    dict[int, np.ndarray],
    dict[int, np.ndarray],
    dict[int, float],
    dict[int, float],
]:
    years = sorted(raw_df["year"].dropna().astype(int).unique())
    rng = np.random.default_rng(BOOTSTRAP_SEED)

    rows: list[dict[str, float | int]] = []
    mncs_draws_by_year: dict[int, np.ndarray] = {}
    pp_draws_by_year: dict[int, np.ndarray] = {}
    mncs_weight_sum_by_year: dict[int, float] = {}
    pp_weight_sum_by_year: dict[int, float] = {}

    for year in years:
        year_df = raw_df.loc[raw_df["year"] == year].copy()

        mncs_mask = (
            year_df[MNCS_RELIABLE_COL]
            & year_df[MNCS_N_INST_COL].notna()
            & (year_df[MNCS_N_INST_COL] > 0)
            & year_df[MNCS_VALUE_COL].notna()
        )
        mncs_values = year_df.loc[mncs_mask, MNCS_VALUE_COL].to_numpy(dtype=float)
        mncs_weights = 1.0 / year_df.loc[mncs_mask, MNCS_N_INST_COL].to_numpy(dtype=float)
        mncs_weight_sum_by_year[year] = float(mncs_weights.sum())

        mncs_point = _weighted_mean(mncs_values, mncs_weights)
        mncs_draws = _bootstrap_weighted_means(
            mncs_values,
            mncs_weights,
            n_bootstrap=N_BOOTSTRAP,
            rng=rng,
            batch_size=BOOTSTRAP_BATCH_SIZE,
        )
        mncs_lower, mncs_upper = _quantile_bounds(mncs_draws, STABILITY_LEVEL)
        mncs_draws_by_year[year] = mncs_draws

        pp_mask = (
            year_df[PP_RELIABLE_COL]
            & year_df[PP_N_INST_COL].notna()
            & (year_df[PP_N_INST_COL] > 0)
            & year_df[PP_VALUE_COL].notna()
        )
        pp_values = year_df.loc[pp_mask, PP_VALUE_COL].to_numpy(dtype=float)
        pp_weights = 1.0 / year_df.loc[pp_mask, PP_N_INST_COL].to_numpy(dtype=float)
        pp_weight_sum_by_year[year] = float(pp_weights.sum())

        pp_point = _weighted_mean(pp_values, pp_weights)
        pp_draws = _bootstrap_weighted_means(
            pp_values,
            pp_weights,
            n_bootstrap=N_BOOTSTRAP,
            rng=rng,
            batch_size=BOOTSTRAP_BATCH_SIZE,
        )
        pp_lower, pp_upper = _quantile_bounds(pp_draws, STABILITY_LEVEL)
        pp_draws_by_year[year] = pp_draws

        rows.append(
            {
                "year": year,
                "C_MNCS_FRAC": round(mncs_point, 6) if np.isfinite(mncs_point) else float("nan"),
                "C_MNCS_FRAC_LOWER": round(mncs_lower, 6) if np.isfinite(mncs_lower) else float("nan"),
                "C_MNCS_FRAC_UPPER": round(mncs_upper, 6) if np.isfinite(mncs_upper) else float("nan"),
                "PP_TOPTEN_FRAC": round(pp_point, 6) if np.isfinite(pp_point) else float("nan"),
                "PP_TOPTEN_FRAC_LOWER": round(pp_lower, 6) if np.isfinite(pp_lower) else float("nan"),
                "PP_TOPTEN_FRAC_UPPER": round(pp_upper, 6) if np.isfinite(pp_upper) else float("nan"),
                "n_obs_mncs": round(float(mncs_weights.sum()), 6),
                "n_obs_pptop10": round(float(pp_weights.sum()), 6),
                "n_obs_mncs_frac": round(float(mncs_weights.sum()), 6),
                "n_obs_pptop10_frac": round(float(pp_weights.sum()), 6),
                "n_obs_mncs_full": int(mncs_values.size),
                "n_obs_pptop10_full": int(pp_values.size),
            }
        )

    yearly_df = pd.DataFrame(rows).sort_values("year").reset_index(drop=True)
    return (
        yearly_df,
        mncs_draws_by_year,
        pp_draws_by_year,
        mncs_weight_sum_by_year,
        pp_weight_sum_by_year,
    )


def _window_weighted_point(
    raw_df: pd.DataFrame,
    *,
    y0: int,
    y1: int,
    value_col: str,
    n_inst_col: str,
    reliable_col: str,
) -> float:
    window = raw_df[(raw_df["year"] >= y0) & (raw_df["year"] <= y1)]
    if window.empty:
        return float("nan")

    mask = (
        window[reliable_col]
        & window[n_inst_col].notna()
        & (window[n_inst_col] > 0)
        & window[value_col].notna()
    )
    if not mask.any():
        return float("nan")

    values = window.loc[mask, value_col].to_numpy(dtype=float)
    weights = 1.0 / window.loc[mask, n_inst_col].to_numpy(dtype=float)
    return _weighted_mean(values, weights)


def build_ma_df(
    raw_df: pd.DataFrame,
    yearly_df: pd.DataFrame,
    mncs_draws_by_year: dict[int, np.ndarray],
    pp_draws_by_year: dict[int, np.ndarray],
    mncs_weight_sum_by_year: dict[int, float],
    pp_weight_sum_by_year: dict[int, float],
    ma_window: int,
) -> pd.DataFrame:
    columns = [
        MA_YEAR_COL,
        "C_MNCS_FRAC",
        "C_MNCS_FRAC_LOWER",
        "C_MNCS_FRAC_UPPER",
        "PP_TOPTEN_FRAC",
        "PP_TOPTEN_FRAC_LOWER",
        "PP_TOPTEN_FRAC_UPPER",
    ]

    if yearly_df.empty:
        return pd.DataFrame(columns=columns)

    years = sorted(yearly_df["year"].dropna().astype(int).unique())
    if not years:
        return pd.DataFrame(columns=columns)

    start_years = [y for y in years if y + (ma_window - 1) <= max(years)]

    rows: list[dict[str, float | str]] = []
    for y0 in start_years:
        y1 = y0 + (ma_window - 1)

        mncs_point = _window_weighted_point(
            raw_df,
            y0=y0,
            y1=y1,
            value_col=MNCS_VALUE_COL,
            n_inst_col=MNCS_N_INST_COL,
            reliable_col=MNCS_RELIABLE_COL,
        )
        pp_point = _window_weighted_point(
            raw_df,
            y0=y0,
            y1=y1,
            value_col=PP_VALUE_COL,
            n_inst_col=PP_N_INST_COL,
            reliable_col=PP_RELIABLE_COL,
        )

        mncs_draws_and_weights = [
            (mncs_draws_by_year[year], mncs_weight_sum_by_year.get(year, 0.0))
            for year in range(y0, y1 + 1)
            if year in mncs_draws_by_year
        ]
        mncs_draws_and_weights = [(d, w) for d, w in mncs_draws_and_weights if w > 0]
        if mncs_draws_and_weights:
            draws = np.vstack([d for d, _w in mncs_draws_and_weights])
            weights = np.array([w for _d, w in mncs_draws_and_weights], dtype=float)
            mncs_window_draws = np.average(draws, axis=0, weights=weights)
            mncs_lower, mncs_upper = _quantile_bounds(mncs_window_draws, STABILITY_LEVEL)
        else:
            mncs_lower, mncs_upper = float("nan"), float("nan")

        pp_draws_and_weights = [
            (pp_draws_by_year[year], pp_weight_sum_by_year.get(year, 0.0))
            for year in range(y0, y1 + 1)
            if year in pp_draws_by_year
        ]
        pp_draws_and_weights = [(d, w) for d, w in pp_draws_and_weights if w > 0]
        if pp_draws_and_weights:
            draws = np.vstack([d for d, _w in pp_draws_and_weights])
            weights = np.array([w for _d, w in pp_draws_and_weights], dtype=float)
            pp_window_draws = np.average(draws, axis=0, weights=weights)
            pp_lower, pp_upper = _quantile_bounds(pp_window_draws, STABILITY_LEVEL)
        else:
            pp_lower, pp_upper = float("nan"), float("nan")

        rows.append(
            {
                MA_YEAR_COL: f"{y0}-{y1}",
                "C_MNCS_FRAC": round(mncs_point, 6) if np.isfinite(mncs_point) else float("nan"),
                "C_MNCS_FRAC_LOWER": round(mncs_lower, 6) if np.isfinite(mncs_lower) else float("nan"),
                "C_MNCS_FRAC_UPPER": round(mncs_upper, 6) if np.isfinite(mncs_upper) else float("nan"),
                "PP_TOPTEN_FRAC": round(pp_point, 6) if np.isfinite(pp_point) else float("nan"),
                "PP_TOPTEN_FRAC_LOWER": round(pp_lower, 6) if np.isfinite(pp_lower) else float("nan"),
                "PP_TOPTEN_FRAC_UPPER": round(pp_upper, 6) if np.isfinite(pp_upper) else float("nan"),
            }
        )

    return pd.DataFrame(rows, columns=columns)


def _scaled_series(df: pd.DataFrame) -> pd.Series:
    mncs_cols = ["C_MNCS_FRAC", "C_MNCS_FRAC_LOWER", "C_MNCS_FRAC_UPPER"]
    pp_cols = ["PP_TOPTEN_FRAC", "PP_TOPTEN_FRAC_LOWER", "PP_TOPTEN_FRAC_UPPER"]

    mncs = pd.to_numeric(df[mncs_cols].stack(), errors="coerce")
    pp_scaled = pd.to_numeric(df[pp_cols].stack(), errors="coerce") * 10.0

    vals = pd.concat([mncs, pp_scaled], ignore_index=True)
    vals = vals[pd.notna(vals) & (vals > 0)]
    return vals


def _global_axis_bounds(frames: dict[str, pd.DataFrame]) -> tuple[float, float]:
    all_vals: list[float] = [1.0]
    for df in frames.values():
        all_vals.extend(_scaled_series(df).tolist())

    if not all_vals:
        return 0.4, 2.0

    min_val = min(all_vals)
    max_val = max(all_vals)

    if min_val <= 0:
        min_val = min(v for v in all_vals if v > 0)

    required_upper = max(max_val, 1.0 / min_val)

    y_max = math.ceil((required_upper * 1.02) / 0.2) * 0.2

    reciprocal = 1.0 / y_max
    y_min = math.floor((reciprocal + 1e-9) / 0.2) * 0.2
    y_min = max(0.2, y_min)

    if y_min >= y_max:
        y_min = max(0.2, y_max - 0.2)

    return round(y_min, 2), round(y_max, 2)


def _tick_values(y_min: float, y_max: float, step: float = 0.2) -> list[float]:
    vals: list[float] = []
    start = math.ceil((y_min - 1e-9) / step) * step
    v = start
    while v <= y_max + 1e-9:
        vals.append(round(v, 2))
        v += step
    return vals


def plot_function(
    df: pd.DataFrame,
    y_min: float,
    y_max: float,
    mncs_label: str,
    pp_label: str,
) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(8.2, 4.5))

    if df.empty:
        ax.text(
            0.5,
            0.5,
            "No MA bootstrap data available.",
            transform=ax.transAxes,
            ha="center",
            va="center",
        )
        ax.set_axis_off()
        return fig

    plot_df = df.copy().reset_index(drop=True)
    plot_df["x_pos"] = np.arange(len(plot_df))
    plot_df["x_label"] = plot_df[MA_YEAR_COL].map(_format_ma_label)

    if len(plot_df) == 1:
        x_range = [-0.5, 0.5]
    else:
        x_range = [-0.1, len(plot_df) - 0.9]

    tick_vals = _tick_values(y_min, y_max, step=0.2)
    if not tick_vals:
        tick_vals = [round(y_min, 2), round(y_max, 2)]

    x_vals = plot_df["x_pos"].to_numpy(dtype=float)
    mncs = pd.to_numeric(plot_df["C_MNCS_FRAC"], errors="coerce").to_numpy(dtype=float)
    mncs_lower = pd.to_numeric(plot_df["C_MNCS_FRAC_LOWER"], errors="coerce").to_numpy(dtype=float)
    mncs_upper = pd.to_numeric(plot_df["C_MNCS_FRAC_UPPER"], errors="coerce").to_numpy(dtype=float)
    pp = pd.to_numeric(plot_df["PP_TOPTEN_FRAC"], errors="coerce").to_numpy(dtype=float)
    pp_lower = pd.to_numeric(plot_df["PP_TOPTEN_FRAC_LOWER"], errors="coerce").to_numpy(dtype=float)
    pp_upper = pd.to_numeric(plot_df["PP_TOPTEN_FRAC_UPPER"], errors="coerce").to_numpy(dtype=float)

    ax.fill_between(
        x_vals,
        mncs_lower,
        mncs_upper,
        color=MNCS_COLOR,
        alpha=MNCS_BAND_ALPHA,
        linewidth=0,
        zorder=1,
    )
    (mncs_line,) = ax.plot(
        x_vals,
        mncs,
        color=MNCS_COLOR,
        alpha=MNCS_ALPHA,
        linewidth=2.2,
        marker="o",
        markersize=6.5,
        label=mncs_label,
        zorder=3,
    )

    ax2 = ax.twinx()
    ax2.fill_between(
        x_vals,
        pp_lower,
        pp_upper,
        color=PPTOP10_COLOR,
        alpha=PPTOP10_BAND_ALPHA,
        linewidth=0,
        zorder=1,
    )
    (pp_line,) = ax2.plot(
        x_vals,
        pp,
        color=PPTOP10_COLOR,
        alpha=PPTOP10_ALPHA,
        linewidth=2.2,
        marker="o",
        markersize=6.5,
        label=pp_label,
        zorder=3,
    )

    for y in tick_vals:
        if abs(y - 1.0) < 1e-9:
            continue
        ax.axhline(
            y=y,
            linestyle="-",
            color=GRIDLINE_COLOR,
            linewidth=1.0,
            alpha=1.0,
            zorder=0,
        )

    ax.axhline(
        y=1.0,
        linestyle="--",
        color=REFERENCE_LINE_COLOR,
        linewidth=2.2,
        zorder=2,
    )

    ax.set_xlim(x_range)
    ax.set_ylim(y_min, y_max)
    ax2.set_ylim(y_min / 10.0, y_max / 10.0)

    ax.set_xticks(x_vals)
    ax.set_xticklabels(plot_df["x_label"])
    ax.set_xlabel("Year", fontsize=FONT_SIZE_MAIN, labelpad=3)

    ax.set_yticks(tick_vals)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.1f"))
    ax2.set_yticks([round(v / 10.0, 4) for v in tick_vals])
    ax2.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1.0, decimals=0))

    ax.set_ylabel(mncs_label, fontsize=FONT_SIZE_MAIN, labelpad=5)
    ax2.set_ylabel(pp_label, fontsize=FONT_SIZE_MAIN, labelpad=5)

    ax.grid(False)
    ax2.grid(False)

    ax.tick_params(
        axis="both",
        which="major",
        color=GRIDLINE_COLOR,
        labelcolor=TEXT_COLOR,
        labelsize=9,
        length=3,
        width=0.9,
    )
    ax2.tick_params(
        axis="y",
        which="major",
        color=GRIDLINE_COLOR,
        labelcolor=TEXT_COLOR,
        labelsize=9,
        length=3,
        width=0.9,
    )

    for spine in ["left", "bottom", "top"]:
        ax.spines[spine].set_color(AXIS_COLOR)
    ax.spines["right"].set_visible(False)
    ax2.spines["right"].set_color(AXIS_COLOR)
    for spine in ["left", "bottom", "top"]:
        ax2.spines[spine].set_visible(False)

    ax.legend(
        handles=[mncs_line, pp_line],
        labels=[mncs_label, pp_label],
        loc="upper left",
        bbox_to_anchor=(0.0, -0.12),
        ncol=2,
        frameon=False,
        fontsize=FONT_SIZE_MAIN,
        handlelength=1.8,
        columnspacing=1.0,
        handletextpad=0.5,
        borderaxespad=0.0,
    )
    fig.subplots_adjust(left=0.07, right=0.92, top=0.97, bottom=0.15)

    return fig


asset = Asset(script_file=__file__)
indicator_catalog_dict = get_indicator_catalog_dict()

mncs_symbol = (indicator_catalog_dict.get("C_MNCS_FRAC", {}) or {}).get("symbol_tex", "")
pp_symbol = (indicator_catalog_dict.get("PP_TOPTEN_FRAC", {}) or {}).get("symbol_tex", "")
MNCS_LABEL = _label_from_symbol(mncs_symbol, "MNCS")
PP_LABEL = _label_from_symbol(pp_symbol, "PP[top10%]")

ma_window = max(1, int(asset.year_range_moving))

frames: dict[str, pd.DataFrame] = {}
for inst, con in asset.iterate_institutions():
    raw_df = asset.extract(
        con=con,
        inst=inst,
        query=q_mncs_pptop10_raw(inst, asset.year_first, asset.year_last),
        out_name=RAW_EXPORT_NAME,
    )

    prepared_df = _prepare_raw_df(raw_df)
    (
        yearly_df,
        mncs_draws_by_year,
        pp_draws_by_year,
        mncs_weight_sum_by_year,
        pp_weight_sum_by_year,
    ) = _compute_yearly_bootstrap(prepared_df)
    ma_df = build_ma_df(
        prepared_df,
        yearly_df,
        mncs_draws_by_year,
        pp_draws_by_year,
        mncs_weight_sum_by_year,
        pp_weight_sum_by_year,
        ma_window,
    )

    frames[inst] = ma_df

    out = asset.inst_dir(inst)
    yearly_df.to_csv(out / YEARLY_EXPORT_NAME, index=False)
    ma_df.to_csv(out / "data.csv", index=False)

global_y_min, global_y_max = _global_axis_bounds(frames)

for inst in asset.institutions:
    ma_df = frames.get(
        inst,
        pd.DataFrame(
            columns=[
                MA_YEAR_COL,
                "C_MNCS_FRAC",
                "C_MNCS_FRAC_LOWER",
                "C_MNCS_FRAC_UPPER",
                "PP_TOPTEN_FRAC",
                "PP_TOPTEN_FRAC_LOWER",
                "PP_TOPTEN_FRAC_UPPER",
            ]
        ),
    )

    fig = plot_function(ma_df, global_y_min, global_y_max, MNCS_LABEL, PP_LABEL)

    out = asset.inst_dir(inst)
    fig.savefig(out / "figure.svg")
    fig.savefig(out / "figure.png", dpi=220)
    fig.savefig(out / "figure.pdf")
    plt.close(fig)





