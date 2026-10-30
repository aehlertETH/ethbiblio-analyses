from __future__ import annotations

from utility import get_indicator_catalog_dict
from core.asset import Asset
from core.subfield_profile_matplotlib import build_panel_figure

import matplotlib
matplotlib.use("Agg")

import math
import matplotlib.pyplot as plt
import pandas as pd


try:
    asset = Asset(script_file=__file__)
except NameError:
    asset = Asset(script_file="assets/5_1_researchProfileSubfieldsFieldGrowthImpact/")


indicator_catalog_dict = get_indicator_catalog_dict()


MIN_OUTPUT_SHARE = 0.01
MIN_OUTPUT_FRAC = 50.0

BASELINE_START = 2014
BASELINE_END = 2019
RECENT_START = 2020
RECENT_END = 2023

IMPACT_MIN_RELIABLE_N = 20.0
IMPACT_PP_PARITY = 0.10
IMPACT_PP_SCALE = 1.0 / IMPACT_PP_PARITY
IMPACT_LIMIT_HEADROOM_FACTOR = 1.02

# Optional institution filter.
# - unset / None / [] / [""] => run all institutions
# - non-empty list => run only listed institution codes
RENDER_ONLY_INSTITUTIONS = [""]


EXPORT_COLUMNS = [
    "subfield",
    "subfield_category",
    "P_FULL",
    "P_FRAC",
    "R_FULL_FRAC",
    "P_FRAC_share",
    "GROWTH_FIELD_FULL",
    "GROWTH_FIELD_FULL_percentage",
    "MNCS_FRAC",
    "PP_TOPTEN_FRAC",
]


FIGURE_STYLE_OVERRIDES = {
    "colors": {
        "volume_full": "#d9dee8",
        "volume_full_edge": "#ABB4C2",
        "volume_full_alpha": 0.95,
        "volume_frac": "#215CAF",
        "volume_frac_edge": "#003289",
        "volume_frac_alpha": 0.80,
        "growth_field": "#d6dee9",
        "growth_field_edge": "#9aa8bc",
        "growth_field_alpha": 0.95,
        "impact_mncs": "#d9dee8",
        "impact_mncs_edge": "#ABB4C2",
        "impact_mncs_alpha": 0.95,
        "impact_pp": "#215CAF",
        "impact_pp_edge": "#003289",
        "impact_pp_alpha": 0.80,
        "ratio_reference": "#000000",
        "axis": "#b0b0b0",
        "grid": "#d7d7d7",
        "tick_mark": "#8a8a8a",
        "tick_label": "#000000",
        "subfield_label": "#000000",
        "value_label": "#000000",
        "text_main": "#000000",
        "field_text": "#000000",
        "subtitle_volume": "#000000",
        "subtitle_growth": "#000000",
        "subtitle_impact": "#000000",
        "secondary_growth": "#000000",
        "secondary_impact": "#000000",
        "ratio_reference_text": "#000000",
    },
    "layout": {
        "fig_width": 14.1,
        "min_fig_height": 7.2,
        "height_base": 2.0,
        "height_per_row": 0.26,
        "row_step": 0.90,
        "xpad_factor": {"volume": 1.02, "growth": 1.01, "impact": 1.00},
        "gutter_ratio": {"volume": 0.05, "growth": 0.08, "impact": 0.04},
        "x_extra_right_ratio": {"volume": 0.00, "growth": 0.02, "impact": 0.00},
        "label_pad_ratio": {"volume": 0.010, "growth": 0.010, "impact": 0.010},
        "label_right_margin_ratio": {"volume": 0.03, "growth": 0.03, "impact": 0.02},
        "text_clip_on": {"volume": False, "growth": False, "impact": False},
        "draw_text_last": True,
        "deferred_text_zorder": 30.0,
        "value_text_zorder": 8.0,
        "x_tick_rotation": {"volume": -25, "growth": -25, "impact": -25},
        "x_tick_ha": {"volume": "center", "growth": "center", "impact": "center"},
        "x_tick_rotation_mode": "default",
        "x_tick_pad": {"volume": 2.0, "growth": 4.0, "impact": 2.0},
        "emphasize_labeled_x_ticks": True,
        "x_tick_mark_color": "tick_mark",
        "x_tick_mark_width": 0.95,
        "x_tick_mark_length": 4.2,
        "x_tick_mark_direction": "out",
        "x_tick_mark_hide_unlabeled": True,
        "x_tick_mark_unlabeled_alpha": 0.30,
        "x_tick_mark_unlabeled_length_ratio": 0.20,
        "emphasize_labeled_gridlines": True,
        "x_grid_labeled_color": "tick_mark",
        "x_grid_labeled_linewidth": 0.70,
        "x_grid_labeled_alpha": 0.55,
        "x_grid_unlabeled_color": "grid",
        "x_grid_unlabeled_linewidth": 0.65,
        "x_grid_unlabeled_alpha": 1.0,
        "auto_reduce_x_tick_labels": True,
        "x_tick_label_min_gap_px": 8.0,
        "keep_first_last_tick_labels": True,
        "y_inner_pad": 0.08,
        "y_inner_pad_top": 0.12,
        "y_inner_pad_bottom": 0.08,
        "axis_label_fontsize": 12,
        "axis_label_pad": 8,
        "axis_label_pad_by_panel": {"volume": 12, "growth": 12, "impact": 8},
        "show_axis_labels": False,
        "show_primary_axis_labels": False,
        "show_secondary_axis_labels": False,
        "secondary_label_y": -0.10,
        "secondary_label_fontsize": 13,
        "panel_subtitle_y": {"volume": 1.04, "growth": 1.04, "impact": 1.09},
        "panel_subtitle_va": {"volume": "top", "growth": "top", "impact": "top"},
        "panel_subtitle_fontsize": 14,
        "panel_subtitle_draw_last": True,
        "row_block_separator_every": 5,
        "row_block_separator_color": "#c7c7c7",
        "row_block_separator_linewidth": 0.75,
        "row_block_separator_alpha": 0.95,
        "row_block_separator_linestyle": "-",
        "row_block_separator_zorder": 2.2,
        "row_block_separator_include_subfield_labels": True,
        "subfield_fontsize": 14,
        "subfield_label_linespacing": 0.95,
        "subfield_wrap_width": 42,
        "subfield_wrap_break_long_words": False,
        "subfield_wrap_max_lines": 2,
        "subfield_autofit_left": True,
        "subfield_autofit_pad": 0.008,
        "subfield_autofit_left_max": 0.46,
        "value_label_fontsize": 12,
        "reference_label_fontsize": 10,
        "show_subfield_header": True,
        "subfield_header_x": -0.55,
        "subfield_header_y": 1.04,
        "subfield_header_coords": "axes",
        "subfield_header_ha": "left",
        "subfield_header_va": "top",
        "subfield_header_fontsize": 14,
        "show_legend": True,
        "legend_fontsize": 14,
        "legend_anchor": [0.02, 0.012],
        "legend_mode": "panel_stacks",
        "legend_panel_anchor_y": -0.010,
        "legend_panel_anchor_x_offset": 0.000,
        "legend_panel_loc": "lower left",
        "subplots_adjust": {
            "left": 0.225,
            "right": 0.945,
            "top": 0.925,
            "bottom": 0.125,
            "wspace": 0.03,
        },
    },
    "messages": {
        "empty": "No subfield-level research profile data available.",
    },
}


FIGURE_FORMAT = {
    "growth_tick_step": 0.25,
    "growth_tick_decimals": 2,
    "growth_value_decimals": 0,
    "impact_mncs_tick_step": 0.50,
    "impact_mncs_tick_decimals": 1,
    "impact_pp_tick_step": 0.05,
    "impact_pp_tick_decimals": 0,
}


FIGURE_VOLUME_SHARE_LABEL = {
    "enabled": True,
    "decimals": 0,
    "as_percent": True,
    "pad_ratio": 0.010,
    "right_margin_ratio": 0.08,
    "draw_last": True,
    "clip_on": False,
}


FIGURE_LAYOUT_PANEL_WIDTHS = [1.18, 1.22, 1.10]
FIGURE_BAR_HEIGHTS = {
    "volume_full": 0.66,
    "volume_frac": 0.38,
    "growth_field": 0.66,
    "impact_mncs": 0.62,
    "impact_pp": 0.36,
}


def _round_up(value: float, step: float) -> float:
    if step <= 0:
        return value
    return step * math.ceil(value / step)


def _normalize_symbol_tex(symbol_tex: str) -> str:
    symbol = str(symbol_tex).strip()
    if not symbol:
        return ""
    symbol = symbol.replace("\\lbrack", "[")
    symbol = symbol.replace("\\rbrack", "]")
    symbol = symbol.replace("\\mbox{-}", "-")
    return symbol


def _catalog_symbol(indicator_id: str, fallback_symbol: str) -> str:
    symbol = (indicator_catalog_dict.get(indicator_id, {}) or {}).get("symbol_tex", "")
    symbol_norm = _normalize_symbol_tex(symbol)
    if symbol_norm:
        return symbol_norm
    return _normalize_symbol_tex(fallback_symbol)


def _math(symbol_tex: str) -> str:
    symbol = _normalize_symbol_tex(symbol_tex)
    if not symbol:
        return ""
    return f"${symbol}$"


def _growth_window_label() -> str:
    return f""


def _impact_axis_limit(plot_df: pd.DataFrame, step: float) -> float:
    mncs = pd.to_numeric(plot_df["MNCS_FRAC"], errors="coerce")
    pptop10_scaled = pd.to_numeric(plot_df["PP_TOPTEN_FRAC_SCALED"], errors="coerce")

    max_mncs = float(mncs.max()) if mncs.notna().any() else 1.0
    max_pp_scaled = float(pptop10_scaled.max()) if pptop10_scaled.notna().any() else 1.0
    max_required = max(1.0, max_mncs, max_pp_scaled)

    return max_required * IMPACT_LIMIT_HEADROOM_FACTOR


def _build_runtime_figure_spec(plot_df: pd.DataFrame) -> dict:
    layout = FIGURE_STYLE_OVERRIDES["layout"]
    fmt = FIGURE_FORMAT

    symbol_volume_full = _catalog_symbol("P_FULL", r"\\mathrm{P}_{\\mathrm{full}}")
    symbol_volume_frac = _catalog_symbol("P_FRAC", r"\\mathrm{P}_{\\mathrm{frac}}")
    symbol_mncs = _catalog_symbol("C_MNCS_FRAC", r"\\mathrm{MNCS}_{\\mathrm{frac}}")
    symbol_pp = _catalog_symbol("PP_TOPTEN_FRAC", r"\\mathrm{PP}[\\mathrm{top}\\,10\\%]_{\\mathrm{frac}}")

    volume_label_decimals = int(FIGURE_VOLUME_SHARE_LABEL.get("decimals", 0))
    volume_label_template = f"{{P_FRAC_share:.{volume_label_decimals}%}}"

    growth_field_label_template = f"{{GROWTH_FIELD_FULL_pp:+.{int(fmt['growth_value_decimals'])}f}}%"

    impact_primary_limit = _impact_axis_limit(plot_df, step=float(fmt["impact_mncs_tick_step"]))
    impact_secondary_limit = impact_primary_limit / IMPACT_PP_SCALE

    return {
        "subfield_column": "subfield_label",
        "subfield_header": "Subfields",
        "legend": {
            "show": bool(layout["show_legend"]),
            "anchor": list(layout["legend_anchor"]),
            "fontsize": float(layout["legend_fontsize"]),
            "mode": str(layout.get("legend_mode", "flat")),
            "panel_anchor_y": float(layout.get("legend_panel_anchor_y", 0.012)),
            "panel_anchor_x_offset": float(layout.get("legend_panel_anchor_x_offset", 0.0)),
            "panel_loc": str(layout.get("legend_panel_loc", "lower left")),
        },
        "panels": [
            {
                "id": "volume",
                "width_ratio": FIGURE_LAYOUT_PANEL_WIDTHS[0],
                "axes": {
                    "primary": {
                        "label": _math(symbol_volume_frac),
                        "tick_mode": "count_auto",
                        "count_is_full": False,
                        "show_grid": True,
                        "position": "bottom",
                    }
                },
                "subtitle": {"text": "Output", "color": "subtitle_volume"},
                "secondary_label": {"text": "", "color": "secondary_growth"},
                "traces": [
                    {
                        "id": "volume_full",
                        "type": "barh",
                        "axis": "primary",
                        "column": "P_FULL",
                        "color": "volume_full",
                        "edgecolor": "volume_full_edge",
                        "alpha": "volume_full_alpha",
                        "height": FIGURE_BAR_HEIGHTS["volume_full"],
                        "legend_label": _math(symbol_volume_full),
                    },
                    {
                        "id": "volume_frac",
                        "type": "barh",
                        "axis": "primary",
                        "column": "P_FRAC",
                        "color": "volume_frac",
                        "edgecolor": "volume_frac_edge",
                        "alpha": "volume_frac_alpha",
                        "height": FIGURE_BAR_HEIGHTS["volume_frac"],
                        "legend_label": _math(symbol_volume_frac),
                        "value_label": {
                            "enabled": bool(FIGURE_VOLUME_SHARE_LABEL.get("enabled", False)),
                            "template": volume_label_template,
                            "color": "value_label",
                            "pad_ratio": float(FIGURE_VOLUME_SHARE_LABEL.get("pad_ratio", 0.010)),
                            "right_margin_ratio": float(FIGURE_VOLUME_SHARE_LABEL.get("right_margin_ratio", 0.08)),
                            "draw_last": bool(FIGURE_VOLUME_SHARE_LABEL.get("draw_last", True)),
                            "clip_on": bool(FIGURE_VOLUME_SHARE_LABEL.get("clip_on", False)),
                        },
                    },
                ],
            },
            {
                "id": "growth",
                "width_ratio": FIGURE_LAYOUT_PANEL_WIDTHS[1],
                "axes": {
                    "primary": {
                        "label": "",
                        "tick_mode": "step",
                        "tick_step": float(fmt["growth_tick_step"]),
                        "tick_decimals": int(fmt["growth_tick_decimals"]),
                        "tick_as_percent": False,
                        "min_plot_limit": 1.05,
                        "show_grid": True,
                        "position": "bottom",
                    }
                },
                "subtitle": {"text": "Global field growth", "color": "subtitle_growth"},
                "secondary_label": {"text": _growth_window_label(), "color": "secondary_growth"},
                "traces": [
                    {
                        "id": "growth_field",
                        "type": "barh",
                        "axis": "primary",
                        "column": "GROWTH_FIELD_FULL",
                        "color": "growth_field",
                        "edgecolor": "growth_field_edge",
                        "alpha": "growth_field_alpha",
                        "height": FIGURE_BAR_HEIGHTS["growth_field"],
                        "legend_label": "Global field growth (4y)",
                        "value_label": {
                            "enabled": True,
                            "template": growth_field_label_template,
                            "color": "value_label",
                        },
                    },
                ],
                "reference_lines": [
                    {
                        "axis": "primary",
                        "x": 1.0,
                        "linestyle": "--",
                        "linewidth": 1.3,
                        "color": "ratio_reference",
                        "label_template": "{x:.2f}",
                        "label_position": "bottom",
                        "label_pad_axes": 0.02,
                        "label_clamp_margin_axes": 0.01,
                        "label_rotation": 90,
                        "label_fontsize": 10,
                        "label_color": "ratio_reference_text",
                        "lock_within_axes": True,
                        "draw_last": False,
                    }
                ],
            },
            {
                "id": "impact",
                "width_ratio": FIGURE_LAYOUT_PANEL_WIDTHS[2],
                "axes": {
                    "primary": {
                        "label": _math(symbol_mncs),
                        "tick_mode": "step",
                        "tick_step": float(fmt["impact_mncs_tick_step"]),
                        "tick_decimals": int(fmt["impact_mncs_tick_decimals"]),
                        "tick_label_every_n": 1,
                        "auto_reduce_tick_labels": False,
                        "tick_as_percent": False,
                        "min_plot_limit": impact_primary_limit,
                        "xpad_factor": 1.0,
                        "gutter_ratio": 0.04,
                        "extra_right_ratio": 0.0,
                        "round_plot_limit_to_tick": False,
                        "show_grid": True,
                        "position": "bottom",
                    },
                    "secondary": {
                        "label": _math(symbol_pp),
                        "tick_mode": "step",
                        "tick_step": float(fmt["impact_pp_tick_step"]),
                        "tick_decimals": int(fmt["impact_pp_tick_decimals"]),
                        "tick_label_every_n": 1,
                        "auto_reduce_tick_labels": False,
                        "tick_pad": 0.5,
                        "tick_as_percent": True,
                        "min_plot_limit": impact_secondary_limit,
                        "xpad_factor": 1.0,
                        "gutter_ratio": 0.04,
                        "extra_right_ratio": 0.0,
                        "round_plot_limit_to_tick": False,
                        "show_grid": False,
                        "position": "top",
                    },
                },
                "subtitle": {
                    "text": "Impact",
                    "color": "subtitle_impact",
                    "anchor": "top_ticks",
                    "anchor_axis": "secondary",
                    "gap_px": 4.0,
                    "va": "bottom",
                },
                "secondary_label": {"text": "", "color": "secondary_impact"},
                "traces": [
                    {
                        "id": "impact_mncs",
                        "type": "barh",
                        "axis": "primary",
                        "column": "MNCS_FRAC",
                        "color": "impact_mncs",
                        "edgecolor": "impact_mncs_edge",
                        "alpha": "impact_mncs_alpha",
                        "height": FIGURE_BAR_HEIGHTS["impact_mncs"],
                        "legend_label": _math(symbol_mncs),
                        "value_label": {"enabled": False, "template": "{MNCS_FRAC:.2f}", "color": "value_label"},
                    },
                    {
                        "id": "impact_pp",
                        "type": "barh",
                        "axis": "secondary",
                        "column": "PP_TOPTEN_FRAC",
                        "color": "impact_pp",
                        "edgecolor": "impact_pp_edge",
                        "alpha": "impact_pp_alpha",
                        "height": FIGURE_BAR_HEIGHTS["impact_pp"],
                        "legend_label": _math(symbol_pp),
                        "value_label": {"enabled": True, "template": "{value:.0%} ({MNCS_FRAC:.2f})", "color": "value_label"},
                    },
                ],
                "reference_lines": [
                    {
                        "axis": "primary",
                        "x": 1.0,
                        "linestyle": "--",
                        "linewidth": 1.3,
                        "color": "ratio_reference",
                        "label_template": "{x:.2f}",
                        "label_position": "bottom",
                        "label_pad_axes": 0.02,
                        "label_clamp_margin_axes": 0.01,
                        "label_rotation": 90,
                        "label_fontsize": 10,
                        "label_color": "ratio_reference_text",
                        "lock_within_axes": True,
                        "draw_last": False,
                    },
                    {
                        "axis": "secondary",
                        "x": IMPACT_PP_PARITY,
                        "linestyle": "--",
                        "linewidth": 1.3,
                        "color": "ratio_reference",
                        "label_template": "{x:.0%}",
                        "label_position": "top",
                        "label_pad_axes": 0.02,
                        "label_clamp_margin_axes": 0.01,
                        "label_rotation": 90,
                        "label_fontsize": 10,
                        "label_color": "ratio_reference_text",
                        "lock_within_axes": True,
                        "draw_last": False,
                    },
                ],
            },
        ],
    }


def query_function(
    inst: str,
    y0: int,
    y1: int,
    min_share: float,
    min_frac: float,
    baseline_start: int,
    baseline_end: int,
    recent_start: int,
    recent_end: int,
    impact_min_reliable_n: float,
) -> str:
    baseline_years = baseline_end - baseline_start + 1
    recent_years = recent_end - recent_start + 1

    return f"""
        WITH report_works AS (
            SELECT DISTINCT
                rm.work_id,
                w.subfield,
                w.publication_year,
                wm.n_institutions_on_work,
                wm.norm_vs_mean,
                wm.is_top10,
                wm.cohort_is_reliable
            FROM reports.report_membership rm
            JOIN core.work w
              ON w.work_id = rm.work_id
            JOIN marts.work_metrics wm
              ON wm.work_id = rm.work_id
            WHERE rm.report_name = '{inst}'
              AND w.publication_year BETWEEN {y0} AND {y1}
              AND w.subfield IS NOT NULL
              AND wm.n_institutions_on_work > 0
        ),

        subfield_volume AS (
            SELECT
                subfield,
                COUNT(*) AS P_FULL,
                SUM(1.0 / n_institutions_on_work) AS P_FRAC
            FROM report_works
            GROUP BY subfield
        ),

        selected_subfields AS (
            SELECT
                subfield,
                P_FULL,
                P_FRAC,
                P_FRAC::DOUBLE / NULLIF(SUM(P_FRAC) OVER (), 0) AS P_FRAC_share
            FROM subfield_volume
            QUALIFY P_FRAC_share >= {min_share} AND P_FRAC >= {min_frac}
        ),

        subfield_labels AS (
            SELECT
                subfield,
                ANY_VALUE(subfield_name) AS subfield_name
            FROM core.topics_tree
            GROUP BY subfield
        ),

        field_yearly AS (
            SELECT
                ss.subfield,
                w.publication_year,
                COUNT(*) AS P_FIELD_FULL_YEAR
            FROM selected_subfields ss
            JOIN core.work w
              ON w.subfield = ss.subfield
            WHERE w.publication_year BETWEEN {y0} AND {y1}
            GROUP BY ss.subfield, w.publication_year
        ),

        field_growth AS (
            SELECT
                subfield,
                SUM(CASE WHEN publication_year BETWEEN {baseline_start} AND {baseline_end} THEN P_FIELD_FULL_YEAR ELSE 0 END) AS baseline_field_full,
                SUM(CASE WHEN publication_year BETWEEN {recent_start} AND {recent_end} THEN P_FIELD_FULL_YEAR ELSE 0 END) AS recent_field_full
            FROM field_yearly
            GROUP BY subfield
        ),

        impact_agg AS (
            SELECT
                ss.subfield,

                SUM(
                    CASE
                        WHEN rw.cohort_is_reliable = TRUE AND rw.norm_vs_mean IS NOT NULL
                            THEN rw.norm_vs_mean * (1.0 / rw.n_institutions_on_work)
                        ELSE 0.0
                    END
                ) AS mncs_num,

                SUM(
                    CASE
                        WHEN rw.cohort_is_reliable = TRUE AND rw.norm_vs_mean IS NOT NULL
                            THEN 1.0 / rw.n_institutions_on_work
                        ELSE 0.0
                    END
                ) AS mncs_den,

                SUM(
                    CASE
                        WHEN rw.cohort_is_reliable = TRUE AND rw.is_top10 = TRUE
                            THEN 1.0 / rw.n_institutions_on_work
                        ELSE 0.0
                    END
                ) AS pp_num,

                SUM(
                    CASE
                        WHEN rw.cohort_is_reliable = TRUE
                            THEN 1.0 / rw.n_institutions_on_work
                        ELSE 0.0
                    END
                ) AS pp_den
            FROM selected_subfields ss
            JOIN report_works rw
              ON rw.subfield = ss.subfield
            GROUP BY ss.subfield
        )

        SELECT
            ss.subfield,
            COALESCE(sl.subfield_name, CAST(ss.subfield AS VARCHAR)) AS subfield_category,
            ss.P_FULL,
            ss.P_FRAC,
            CASE
                WHEN ss.P_FRAC > 0
                    THEN ss.P_FULL::DOUBLE / ss.P_FRAC
                ELSE NULL
            END AS R_FULL_FRAC,
            ROUND(ss.P_FRAC_share, 6) AS P_FRAC_share,

            CASE
                WHEN COALESCE(fg.baseline_field_full, 0) > 0
                    THEN (COALESCE(fg.recent_field_full, 0)::DOUBLE / {recent_years})
                         / (COALESCE(fg.baseline_field_full, 0)::DOUBLE / {baseline_years})
                ELSE NULL
            END AS GROWTH_FIELD_FULL,

            CASE
                WHEN COALESCE(fg.baseline_field_full, 0) > 0
                    THEN (
                        (
                            (COALESCE(fg.recent_field_full, 0)::DOUBLE / {recent_years})
                            / (COALESCE(fg.baseline_field_full, 0)::DOUBLE / {baseline_years})
                        ) - 1.0
                    )
                ELSE NULL
            END AS GROWTH_FIELD_FULL_percentage,

            CASE
                WHEN ia.mncs_den >= {impact_min_reliable_n}
                    THEN ia.mncs_num / NULLIF(ia.mncs_den, 0.0)
                ELSE NULL
            END AS MNCS_FRAC,

            CASE
                WHEN ia.pp_den >= {impact_min_reliable_n}
                    THEN ia.pp_num / NULLIF(ia.pp_den, 0.0)
                ELSE NULL
            END AS PP_TOPTEN_FRAC

        FROM selected_subfields ss
        LEFT JOIN subfield_labels sl
          ON sl.subfield = ss.subfield
        LEFT JOIN field_growth fg
          ON fg.subfield = ss.subfield
        LEFT JOIN impact_agg ia
          ON ia.subfield = ss.subfield
        ORDER BY ss.P_FRAC DESC, subfield_category;
    """


def build_plot_df(raw_df: pd.DataFrame) -> pd.DataFrame:
    df = raw_df.copy()

    if "R_FULL_FRAC" not in df.columns and "P_FULL" in df.columns and "P_FRAC" in df.columns:
        p_full_tmp = pd.to_numeric(df["P_FULL"], errors="coerce")
        p_frac_tmp = pd.to_numeric(df["P_FRAC"], errors="coerce")
        df["R_FULL_FRAC"] = p_full_tmp / p_frac_tmp.replace(0, pd.NA)

    numeric_cols = [
        "P_FULL",
        "P_FRAC",
        "R_FULL_FRAC",
        "P_FRAC_share",
        "GROWTH_FIELD_FULL",
        "GROWTH_FIELD_FULL_percentage",
        "MNCS_FRAC",
        "PP_TOPTEN_FRAC",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df[df["P_FULL"].notna() & df["P_FRAC"].notna()].copy()

    # Keep storage format compatible with FORMAT_PERCENT_* helpers:
    # 0.713 -> 71.3% (not 71.3 -> 7130%).
    if "GROWTH_FIELD_FULL" in df.columns:
        df["GROWTH_FIELD_FULL_percentage"] = pd.to_numeric(
            df["GROWTH_FIELD_FULL"], errors="coerce"
        ) - 1.0

    # Plot labels in percentage points for readability.
    df["GROWTH_FIELD_FULL_pp"] = df["GROWTH_FIELD_FULL_percentage"] * 100.0

    # Scaled helper used only for synchronized impact axis limits (MNCS 1 == PPtop10 10%).
    df["PP_TOPTEN_FRAC_SCALED"] = df["PP_TOPTEN_FRAC"] * IMPACT_PP_SCALE

    df["subfield_label"] = df["subfield_category"].astype(str)
    df = df.sort_values("P_FRAC", ascending=False)
    return df


render_only_raw = globals().get("RENDER_ONLY_INSTITUTIONS", None)
selected_institutions = None
if render_only_raw not in (None, ""):
    if isinstance(render_only_raw, str):
        render_only_raw = [render_only_raw]

    selected_institutions = {
        str(inst_name).strip()
        for inst_name in render_only_raw
        if str(inst_name).strip()
    }
    if not selected_institutions:
        selected_institutions = None


for inst, con in asset.iterate_institutions():
    if selected_institutions is not None and inst not in selected_institutions:
        continue

    raw_df = asset.extract(
        con=con,
        inst=inst,
        #force=True,
        query=query_function(
            inst=inst,
            y0=asset.year_first,
            y1=asset.year_last,
            min_share=MIN_OUTPUT_SHARE,
            min_frac=MIN_OUTPUT_FRAC,
            baseline_start=BASELINE_START,
            baseline_end=BASELINE_END,
            recent_start=RECENT_START,
            recent_end=RECENT_END,
            impact_min_reliable_n=IMPACT_MIN_RELIABLE_N,
        ),
    )

    plot_df = build_plot_df(raw_df)
    runtime_spec = _build_runtime_figure_spec(plot_df)

    out = asset.inst_dir(inst)
    export_df = plot_df[[c for c in EXPORT_COLUMNS if c in plot_df.columns]].copy()
    for col in [
        "P_FULL",
        "P_FRAC",
        "R_FULL_FRAC",
        "P_FRAC_share",
        "GROWTH_FIELD_FULL",
        "GROWTH_FIELD_FULL_percentage",
        "MNCS_FRAC",
        "PP_TOPTEN_FRAC",
    ]:
        if col in export_df.columns:
            export_df[col] = pd.to_numeric(export_df[col], errors="coerce").round(8)
    export_df.to_csv(out / "data.csv", index=False)

    fig, layout_debug_df = build_panel_figure(
        plot_df,
        runtime_spec,
        style_preset="subfield_profile_v1",
        style_overrides=FIGURE_STYLE_OVERRIDES,
    )
    fig.savefig(out / "figure.png", dpi=220)
    fig.savefig(out / "figure.svg")
    fig.savefig(out / "figure.pdf")
    layout_debug_df.to_csv(out / "layout_debug.csv", index=False)

    plt.close(fig)
