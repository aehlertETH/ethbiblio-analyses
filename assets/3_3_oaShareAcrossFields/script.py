from __future__ import annotations

from utility import get_unit_params_dict, get_indicator_catalog_dict
from core.asset import Asset
from core.subfield_profile_matplotlib import build_panel_figure

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd


try:
    asset = Asset(script_file=__file__)
except NameError:
    asset = Asset(script_file="assets/3_3_oaShareAcrossFields/")


# Load naming conventions from data/...csv files
unit_params_dict = get_unit_params_dict()
indicator_catalog_dict = get_indicator_catalog_dict()


MIN_OUTPUT_SHARE = 0.02  # keep fields with at least 1% of P_FULL or P_FRAC (see next variable)
MIN_OUTPUT_SHARE_TYPE = "P_FRAC_share"
MIN_OUTPUT_FRAC = 50.0
COUNT_MODE = "frac"  # set to "frac" for fractional benchmark mode whether statistics are calced in FULL or FRAC counts).

# Optional institution filter.
# - unset / None / [] / [""] => run all institutions
# - non-empty list => run only listed institution codes
RENDER_ONLY_INSTITUTIONS = [""]

ROUND_COLUMNS_DATA_CSV = [
    "P_FRAC",
    "OA_P_INST_FRAC",
    "OA_PP_INST_FULL",
    "OA_PP_FIELD_FULL",
    "OA_PP_FIELD_FRAC",
    "R_OA_FULL",
    "R_OA_FRAC",
    "OA_PP_INST",
    "OA_PP_FIELD",
    "RPP_OA",
    "delta_oa_pp",
]


# Centralized style overrides for the shared preset.
FIGURE_STYLE_OVERRIDES = {
    "colors": {
        "volume_full": "#d9dee8",
        "volume_full_edge": "#ABB4C2",
        "volume_full_alpha": 0.95,
        "volume_frac": "#215CAF",
        "volume_frac_edge": "#003289",
        "volume_frac_alpha": 0.78,
        "share_inst": "#215CAF",
        "share_inst_edge": "#003289",
        "share_inst_alpha": 0.72,
        "share_field": "#c5cbd6",
        "share_field_edge": "#97a1b0",
        "share_field_alpha": 0.92,
        "ratio": "#923243",
        "ratio_edge": "#64081D",
        "ratio_alpha": 0.90,
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
        "subtitle_share": "#000000",
        "secondary_volume": "#000000",
        "secondary_share": "#000000",
        "ratio_reference_text": "#000000",
    },
    "layout": {
        "fig_width": 13.9,
        "min_fig_height": 7.2,
        "height_base": 1.9,
        "height_per_row": 0.25,
        "row_step": 0.90,
        "xpad_factor": {"volume": 1.04, "share": 1.02, "ratio": 1.02},
        "gutter_ratio": {"volume": 0.10, "share": 0.16, "ratio": 0.12},
        "x_extra_right_ratio": {"volume": 0.00, "share": 0.05, "ratio": 0.03},
        "label_pad_ratio": {"share": 0.012, "ratio": 0.012},
        "label_right_margin_ratio": {"share": 0.018, "ratio": 0.018},
        "text_clip_on": {"share": False, "ratio": False},
        "draw_text_last": True,
        "deferred_text_zorder": 30.0,
        "value_text_zorder": 8.0,
        "x_tick_rotation": {"volume": -25, "share": -25, "ratio": -25},
        "x_tick_ha": {"volume": "center", "share": "center", "ratio": "center"},
        "x_tick_rotation_mode": "default",
        "x_tick_pad": {"volume": 2.0, "share": 4.0, "ratio": 2.0},
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
        "ratio_min_plot_limit": 1.05,
        "axis_label_fontsize": 12,
        "axis_label_pad": 8,
        "axis_label_pad_by_panel": {"volume": 12, "share": 12, "ratio": 8},
        "show_axis_labels": False,
        "show_primary_axis_labels": False,
        "show_secondary_axis_labels": False,
        "secondary_label_y": -0.10,
        "secondary_label_fontsize": 13,
        "panel_subtitle_y": 1.004,
        "panel_subtitle_va": "bottom",
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
        "subfield_header_x": 0.165,
        "subfield_header_y": 0.97,
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
            "right": 0.995,
            "top": 0.965,
            "bottom": 0.145,
            "wspace": 0.03,
        },
    },
    "messages": {
        "empty": "No field-level OA benchmark data available.",
    },
}

# Panel-level numeric format preferences used to build axis/label templates.
FIGURE_FORMAT = {
    "share_tick_step": 0.10,
    "share_tick_decimals": 0,
    "share_tick_as_percent": True,
    "share_value_decimals": 0,
    "share_value_as_percent": True,
    "delta_pp_decimals": 0,
    "ratio_tick_step": 0.50,
    "ratio_tick_decimals": 2,
    "ratio_value_decimals": 2,
}

# Panel-1 share-of-total labels.
# anchor_trace:
# - "count_mode": anchor to P_FULL in full mode, P_FRAC in frac mode
# - "volume_full" or "volume_frac": force anchor to one trace
FIGURE_VOLUME_SHARE_LABEL = {
    "enabled": True,
    "anchor_trace": "count_mode",
    "decimals": 0,
    "as_percent": True,
    "pad_ratio": 0.010,
    "right_margin_ratio": 0.08,
    "draw_last": True,
    "clip_on": False,
}

FIGURE_LAYOUT_PANEL_WIDTHS = [1.22, 1.23, 1.00]
FIGURE_BAR_HEIGHTS = {
    "volume_full": 0.66,
    "volume_frac": 0.38,
    "share_field": 0.66,
    "share_inst": 0.38,
    "ratio": 0.38,
}
FIGURE_RATIO_REFERENCE = {
    "x": 1.0,
    "linewidth": 1.4,
    "label_fontsize": 12,
    "label_rotation": 90,
    "label_position": "bottom",  # "bottom" | "top"
    "label_pad_axes": 0.02,      # distance from top/bottom axis edge (axes coords)
    "label_clamp_margin_axes": 0.01,
    "label_lock_within_axes": True,
    "label_draw_last": False,
}
FIGURE_LABEL_IDS = {
    "volume_full": "P_FULL",
    "volume_frac": "P_FRAC",
    "share_full": "OA_PP_FULL",
    "share_frac": "OA_PP_FRAC",
    "ratio": "RPP_OA",
}
FIGURE_RATIO_SYMBOL_TEX = r"\mathrm{RPP}\lbrack\mathrm{OA}\rbrack"


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


def _with_context_superscript(symbol_tex: str, context: str) -> str:
    symbol = _normalize_symbol_tex(symbol_tex)
    suffixes = (r"_{\mathrm{full}}", r"_{\mathrm{frac}}")
    for suffix in suffixes:
        if symbol.endswith(suffix):
            return f"{symbol[:-len(suffix)]}^{{\\mathrm{{{context}}}}}{suffix}"
    return f"{{{symbol}}}^{{\\mathrm{{{context}}}}}"


def _inst_short_label(inst: str) -> str:
    unit_info = (unit_params_dict.get(inst, {}) or {})
    inst_short = str(unit_info.get("InstShort", "")).strip()
    if inst_short:
        return inst_short
    return str(inst).strip()


def _build_runtime_figure_spec(count_mode: str, inst_short: str | None = None) -> dict:
    # Figure-spec grammar and advanced examples are documented in:
    # core/README_subfield_profile_matplotlib.md
    mode = str(count_mode).strip().lower()
    if mode not in {"full", "frac"}:
        raise ValueError(f"Unsupported COUNT_MODE='{count_mode}'. Use 'full' or 'frac'.")

    layout = FIGURE_STYLE_OVERRIDES["layout"]
    fmt = FIGURE_FORMAT

    symbol_volume_full = _catalog_symbol(FIGURE_LABEL_IDS["volume_full"], r"\mathrm{P}_{\mathrm{full}}")
    symbol_volume_frac = _catalog_symbol(FIGURE_LABEL_IDS["volume_frac"], r"\mathrm{P}_{\mathrm{frac}}")
    share_id = FIGURE_LABEL_IDS["share_full"] if mode == "full" else FIGURE_LABEL_IDS["share_frac"]
    symbol_share_base = _catalog_symbol(share_id, r"\mathrm{PP}[\mathrm{OA}]")
    symbol_share_inst = _with_context_superscript(symbol_share_base, "inst")
    symbol_share_field = _with_context_superscript(symbol_share_base, "field")
    symbol_ratio = _catalog_symbol(FIGURE_LABEL_IDS["ratio"], FIGURE_RATIO_SYMBOL_TEX)
    inst_label_for_subtitle = str(inst_short).strip() if inst_short else "institution"

    share_value_decimals = int(fmt["share_value_decimals"])
    share_value_tpl = (
        f"{{value:.{share_value_decimals}%}}"
        if bool(fmt["share_value_as_percent"])
        else f"{{value:.{share_value_decimals}f}}"
    )
    delta_tpl = f"{{delta_oa_pp:+.{int(fmt['delta_pp_decimals'])}f}}"
    share_label_template = f"{share_value_tpl} ({delta_tpl}pp)"
    ratio_label_template = f"{{value:.{int(fmt['ratio_value_decimals'])}f}}"

    volume_label_cfg = FIGURE_VOLUME_SHARE_LABEL
    volume_anchor_raw = str(volume_label_cfg.get("anchor_trace", "count_mode")).strip().lower()
    if volume_anchor_raw == "count_mode":
        volume_anchor_trace = "volume_full" if mode == "full" else "volume_frac"
    elif volume_anchor_raw in {"volume_full", "volume_frac"}:
        volume_anchor_trace = volume_anchor_raw
    else:
        raise ValueError(
            "FIGURE_VOLUME_SHARE_LABEL['anchor_trace'] must be 'count_mode', 'volume_full', or 'volume_frac'."
        )

    volume_share_col = "P_FULL_share" if volume_anchor_trace == "volume_full" else "P_FRAC_share"
    volume_label_decimals = int(volume_label_cfg.get("decimals", 0))
    volume_label_template = (
        f"{{{volume_share_col}:.{volume_label_decimals}%}}"
        if bool(volume_label_cfg.get("as_percent", True))
        else f"{{{volume_share_col}:.{volume_label_decimals}f}}"
    )

    spec = {
        "subfield_column": "field_label",
        "subfield_header": "Fields",
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
                        "label": _math(symbol_volume_full),
                        "tick_mode": "count_auto",
                        "count_is_full": bool(mode == "full"),
                        "show_grid": True,
                        "position": "bottom",
                    }
                },
                "subtitle": {
                    "text": "Output",
                    "color": "subtitle_volume",
                },
                "secondary_label": {
                    "text": "",
                    "color": "secondary_volume",
                },
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
                        "value_label": {
                            "enabled": bool(volume_label_cfg.get("enabled", False) and volume_anchor_trace == "volume_full"),
                            "template": volume_label_template,
                            "color": "value_label",
                            "pad_ratio": float(volume_label_cfg.get("pad_ratio", 0.010)),
                            "right_margin_ratio": float(volume_label_cfg.get("right_margin_ratio", 0.08)),
                            "draw_last": bool(volume_label_cfg.get("draw_last", True)),
                            "clip_on": bool(volume_label_cfg.get("clip_on", False)),
                        },
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
                            "enabled": bool(volume_label_cfg.get("enabled", False) and volume_anchor_trace == "volume_frac"),
                            "template": volume_label_template,
                            "color": "value_label",
                            "pad_ratio": float(volume_label_cfg.get("pad_ratio", 0.010)),
                            "right_margin_ratio": float(volume_label_cfg.get("right_margin_ratio", 0.08)),
                            "draw_last": bool(volume_label_cfg.get("draw_last", True)),
                            "clip_on": bool(volume_label_cfg.get("clip_on", False)),
                        },
                    },
                ],
            },
            {
                "id": "share",
                "width_ratio": FIGURE_LAYOUT_PANEL_WIDTHS[1],
                "axes": {
                    "primary": {
                        "label": _math(symbol_share_inst),
                        "tick_mode": "step",
                        "tick_step": float(fmt["share_tick_step"]),
                        "tick_decimals": int(fmt["share_tick_decimals"]),
                        "tick_as_percent": bool(fmt["share_tick_as_percent"]),
                        "show_grid": True,
                        "position": "bottom",
                    }
                },
                "subtitle": {
                    "text": "Open-access share",
                    "color": "subtitle_share",
                },
                "secondary_label": {
                    "text": _math(symbol_share_field) if bool(layout.get("show_secondary_axis_labels", True)) else "",
                    "color": "secondary_share",
                },
                "traces": [
                    {
                        "id": "share_field",
                        "type": "barh",
                        "axis": "primary",
                        "column": "OA_PP_FIELD",
                        "color": "share_field",
                        "edgecolor": "share_field_edge",
                        "alpha": "share_field_alpha",
                        "height": FIGURE_BAR_HEIGHTS["share_field"],
                        "legend_label": _math(symbol_share_field),
                    },
                    {
                        "id": "share_inst",
                        "type": "barh",
                        "axis": "primary",
                        "column": "OA_PP_INST",
                        "color": "share_inst",
                        "edgecolor": "share_inst_edge",
                        "alpha": "share_inst_alpha",
                        "height": FIGURE_BAR_HEIGHTS["share_inst"],
                        "legend_label": _math(symbol_share_inst),
                        "value_label": {
                            "enabled": True,
                            "template": share_label_template,
                            "color": "value_label",
                        },
                    },
                ],
            },
            {
                "id": "ratio",
                "width_ratio": FIGURE_LAYOUT_PANEL_WIDTHS[2],
                "axes": {
                    "primary": {
                        "label": _math(symbol_ratio),
                        "tick_mode": "step",
                        "tick_step": float(fmt["ratio_tick_step"]),
                        "tick_decimals": int(fmt["ratio_tick_decimals"]),
                        "tick_as_percent": False,
                        "min_plot_limit": float(layout["ratio_min_plot_limit"]),
                        "show_grid": True,
                        "position": "bottom",
                    }
                },
                "subtitle": {
                    "text": "Relative OA performance",
                    "color": "subtitle_share",
                },
                "traces": [
                    {
                        "id": "ratio",
                        "type": "barh",
                        "axis": "primary",
                        "column": "RPP_OA",
                        "color": "ratio",
                        "edgecolor": "ratio_edge",
                        "alpha": "ratio_alpha",
                        "height": FIGURE_BAR_HEIGHTS["ratio"],
                        "legend_label": _math(symbol_ratio),
                        "value_label": {
                            "enabled": True,
                            "template": ratio_label_template,
                            "color": "value_label",
                        },
                    }
                ],
                "reference_lines": [
                    {
                        "axis": "primary",
                        "x": float(FIGURE_RATIO_REFERENCE["x"]),
                        "linestyle": "--",
                        "linewidth": float(FIGURE_RATIO_REFERENCE["linewidth"]),
                        "color": "ratio_reference",
                        "label_template": "{x:.2f}",
                        "label_position": str(FIGURE_RATIO_REFERENCE["label_position"]),
                        "label_pad_axes": float(FIGURE_RATIO_REFERENCE["label_pad_axes"]),
                        "label_clamp_margin_axes": float(FIGURE_RATIO_REFERENCE["label_clamp_margin_axes"]),
                        "label_rotation": float(FIGURE_RATIO_REFERENCE["label_rotation"]),
                        "label_fontsize": float(FIGURE_RATIO_REFERENCE["label_fontsize"]),
                        "label_color": "ratio_reference_text",
                        "lock_within_axes": bool(FIGURE_RATIO_REFERENCE["label_lock_within_axes"]),
                        "draw_last": bool(FIGURE_RATIO_REFERENCE["label_draw_last"]),
                    }
                ],
            },
        ],
    }

    # Example: 2-panel variant (keep only first two panels).
    # spec["panels"] = spec["panels"][:2]
    #
    # Example: dual-axis panel (MNCS + PP[top10]) in one panel.
    # spec["panels"].append({
    #     "id": "impact_dual",
    #     "width_ratio": 1.00,
    #     "axes": {
    #         "primary": {"label": r"$\\mathrm{MNCS}$", "tick_mode": "step", "tick_step": 0.20, "tick_decimals": 2},
    #         "secondary": {
    #             "label": r"$\\mathrm{PP}[\\mathrm{Top}\\,10\\%]$",
    #             "tick_mode": "step",
    #             "tick_step": 0.05,
    #             "tick_decimals": 0,
    #             "tick_as_percent": True,
    #             "position": "top",
    #         },
    #     },
    #     "traces": [
    #         {"id": "mncs", "type": "barh", "axis": "primary", "column": "MNCS", "color": "#4f81bd", "edgecolor": "#4f81bd", "alpha": 0.85, "height": 0.56},
    #         {"id": "pptop10", "type": "barh", "axis": "secondary", "column": "PP_TOP10", "color": "#9bbb59", "edgecolor": "#9bbb59", "alpha": 0.45, "height": 0.36},
    #     ],
    # })
    return spec



def query_function(inst: str, y0: int, y1: int, min_share_type: str, min_share: float, min_frac: float) -> str:
    return f"""
        WITH report_works AS (
            SELECT DISTINCT
                rm.work_id,
                tt.field,
                w.publication_year,
                w.open_access_oa_status_is_closed,
                w.open_access_oa_status_is_bronze,
                wm.n_institutions_on_work
            FROM reports.report_membership rm
            JOIN core.work w
              ON w.work_id = rm.work_id
            JOIN marts.work_citation_metrics wm
              ON wm.work_id = rm.work_id
            LEFT JOIN core.topics_tree tt
              ON tt.subfield = w.subfield
            WHERE rm.report_name = '{inst}'
              AND w.publication_year BETWEEN {y0} AND {y1}
              AND tt.field IS NOT NULL
              AND wm.n_institutions_on_work > 0
        ),

        field_size AS (
            SELECT
                field,
                COUNT(*) AS P_FULL,
                ROUND(SUM(1.0 / n_institutions_on_work), 2) AS P_FRAC
            FROM report_works
            GROUP BY field
        ),

        selected_fields AS (
            SELECT
                field,
                P_FULL,
                P_FRAC,
                P_FULL::DOUBLE / NULLIF(SUM(P_FULL) OVER (), 0) AS P_FULL_share,
                P_FRAC::DOUBLE / NULLIF(SUM(P_FRAC) OVER (), 0) AS P_FRAC_share
            FROM field_size
            QUALIFY {min_share_type} >= {min_share} AND P_FRAC >= {min_frac}
        ),

        field_labels AS (
            SELECT
                ANY_VALUE(field) AS field,
                ANY_VALUE(field_name) AS field_name
            FROM core.topics_tree
            GROUP BY field
        ),

        field_oa_inst AS (
            SELECT
                sf.field,
                COUNT(*) FILTER (
                    WHERE NOT (
                        rw.open_access_oa_status_is_closed = TRUE
                        OR rw.open_access_oa_status_is_bronze = TRUE
                    )
                ) AS OA_P_FULL_inst,
                ROUND(SUM(
                    CASE
                        WHEN NOT (
                            rw.open_access_oa_status_is_closed = TRUE
                            OR rw.open_access_oa_status_is_bronze = TRUE
                        )
                            THEN 1.0 / rw.n_institutions_on_work
                        ELSE 0.0
                    END
                ), 2) AS OA_P_INST_FRAC
            FROM selected_fields sf
            JOIN report_works rw
              ON rw.field = sf.field
            GROUP BY sf.field
        ),

        field_oa_world AS (
            SELECT
                tt.field,
                COUNT(*) AS field_P_FULL,
                SUM(1.0 / wm.n_institutions_on_work) AS field_P_FRAC,
                COUNT(*) FILTER (
                    WHERE NOT (
                        w.open_access_oa_status_is_closed = TRUE
                        OR w.open_access_oa_status_is_bronze = TRUE
                    )
                ) AS field_OA_P_FULL,
                SUM(
                    CASE
                        WHEN NOT (
                            w.open_access_oa_status_is_closed = TRUE
                            OR w.open_access_oa_status_is_bronze = TRUE
                        )
                            THEN 1.0 / wm.n_institutions_on_work
                        ELSE 0.0
                    END
                ) AS field_OA_P_FRAC
            FROM core.work w
            JOIN marts.work_citation_metrics wm
              ON wm.work_id = w.work_id
            JOIN core.topics_tree tt
              ON tt.subfield = w.subfield
            JOIN selected_fields sf
              ON sf.field = tt.field
            WHERE w.publication_year BETWEEN {y0} AND {y1}
              AND wm.n_institutions_on_work > 0
            GROUP BY tt.field
        )

        SELECT
            sf.field,
            COALESCE(fl.field_name, CAST(sf.field AS VARCHAR)) AS field_category,
            COALESCE(fl.field_name, '') AS field_name,

            sf.P_FULL,
            ROUND(sf.P_FULL_share, 4) AS P_FULL_share,
            sf.P_FRAC,
            ROUND(sf.P_FRAC_share, 4) AS P_FRAC_share,
            COALESCE(foi.OA_P_FULL_inst, 0) AS OA_P_FULL_inst,
            COALESCE(foi.OA_P_INST_FRAC, 0.0) AS OA_P_INST_FRAC,

            ROUND(CASE
                WHEN sf.P_FULL > 0
                    THEN COALESCE(foi.OA_P_FULL_inst, 0)::DOUBLE / sf.P_FULL
                ELSE NULL
            END, 3) AS OA_PP_INST_FULL,

            ROUND(CASE
                WHEN sf.P_FRAC > 0
                    THEN COALESCE(foi.OA_P_INST_FRAC, 0.0)::DOUBLE / sf.P_FRAC
                ELSE NULL
            END, 3) AS OA_PP_INST_FRAC,

            ROUND(CASE
                WHEN fow.field_P_FULL > 0
                    THEN fow.field_OA_P_FULL::DOUBLE / fow.field_P_FULL
                ELSE NULL
            END, 3) AS OA_PP_FIELD_FULL,

            ROUND(CASE
                WHEN fow.field_P_FRAC > 0
                    THEN fow.field_OA_P_FRAC::DOUBLE / fow.field_P_FRAC
                ELSE NULL
            END, 3) AS OA_PP_FIELD_FRAC,

            ROUND(CASE
                WHEN sf.P_FULL > 0
                 AND fow.field_P_FULL > 0
                 AND (fow.field_OA_P_FULL::DOUBLE / fow.field_P_FULL) > 0
                    THEN (COALESCE(foi.OA_P_FULL_inst, 0)::DOUBLE / sf.P_FULL)
                         / (fow.field_OA_P_FULL::DOUBLE / fow.field_P_FULL)
                ELSE NULL
            END, 3) AS R_OA_FULL,

            ROUND(CASE
                WHEN sf.P_FRAC > 0
                 AND fow.field_P_FRAC > 0
                 AND (fow.field_OA_P_FRAC::DOUBLE / fow.field_P_FRAC) > 0
                    THEN (COALESCE(foi.OA_P_INST_FRAC, 0.0)::DOUBLE / sf.P_FRAC)
                         / (fow.field_OA_P_FRAC::DOUBLE / fow.field_P_FRAC)
                ELSE NULL
            END, 3) AS R_OA_FRAC
        FROM selected_fields sf
        LEFT JOIN field_oa_inst foi
          ON foi.field = sf.field
        LEFT JOIN field_labels fl
          ON fl.field = sf.field
        LEFT JOIN field_oa_world fow
          ON fow.field = sf.field
        ORDER BY sf.P_FULL DESC, field_category;
    """


def build_plot_df(raw_df: pd.DataFrame, count_mode: str) -> tuple[pd.DataFrame, str]:
    mode = str(count_mode).strip().lower()
    if mode not in {"full", "frac"}:
        raise ValueError(f"Unsupported COUNT_MODE='{count_mode}'. Use 'full' or 'frac'.")

    df = raw_df.copy()

    numeric_cols = [
        "P_FULL",
        "P_FULL_share",
        "P_FRAC",
        "P_FRAC_share",
        "OA_P_FULL_inst",
        "OA_P_INST_FRAC",
        "OA_PP_INST_FULL",
        "OA_PP_INST_FRAC",
        "OA_PP_FIELD_FULL",
        "OA_PP_FIELD_FRAC",
        "R_OA_FULL",
        "R_OA_FRAC",
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    share_inst_col = "OA_PP_INST_FULL" if mode == "full" else "OA_PP_INST_FRAC"
    share_field_col = "OA_PP_FIELD_FULL" if mode == "full" else "OA_PP_FIELD_FRAC"
    ratio_col = "R_OA_FULL" if mode == "full" else "R_OA_FRAC"

    df["OA_PP_INST"] = df[share_inst_col]
    df["OA_PP_FIELD"] = df[share_field_col]
    df["RPP_OA"] = df[ratio_col]
    df["delta_oa_pp"] = (df["OA_PP_INST"] - df["OA_PP_FIELD"]) * 100.0

    # Keep only rows where all requested metrics can be shown.
    df = df[
        df["P_FULL"].notna()
        & df["P_FRAC"].notna()
        & df["OA_PP_INST"].notna()
        & df["OA_PP_FIELD"].notna()
        & df["RPP_OA"].notna()
    ].copy()

    df["field_label"] = df["field_category"].astype(str)

    # Largest fields first.
    df = df.sort_values("P_FRAC", ascending=False)
    return df, mode


# inst is the institution name, con is the connection to the database (if needed)
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
        force=True,
        query=query_function(
            inst=inst,
            y0=asset.year_first,
            y1=asset.year_last,
            min_share_type=MIN_OUTPUT_SHARE_TYPE,
            min_share=MIN_OUTPUT_SHARE,
            min_frac=MIN_OUTPUT_FRAC,
        ),
    )

    plot_df, resolved_mode = build_plot_df(raw_df, count_mode=COUNT_MODE)
    runtime_spec = _build_runtime_figure_spec(
        resolved_mode,
        inst_short=_inst_short_label(inst),
    )

    out = asset.inst_dir(inst)
    export_df = plot_df.copy()
    for col in ROUND_COLUMNS_DATA_CSV:
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
