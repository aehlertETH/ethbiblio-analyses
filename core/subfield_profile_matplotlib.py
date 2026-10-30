from __future__ import annotations

import math
import textwrap
from copy import deepcopy
from string import Formatter
from typing import Any

import matplotlib.patches as mpatches
import matplotlib.lines as mlines
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

from core.number_format import format_half_up


_STYLE_PRESETS: dict[str, dict[str, Any]] = {
    "subfield_profile_v1": {
        "colors": {
            "axis": "#b0b0b0",
            "grid": "#d7d7d7",
            "tick_label": "#4a4a4a",
            "tick_mark": "#7a7a7a",
            "grid_labeled": "#8a8a8a",
            "subfield_label": "#202020",
            "text_main": "#202020",
            "field_text": "#202020",
            "value_label": "#202020",
            "subtitle_default": "#202020",
            "secondary_label": "#202020",
            "ratio_reference": "#666666",
            "ratio_reference_text": "#666666",
            "volume_full": "#d9dee8",
            "volume_full_edge": "#d9dee8",
            "volume_full_alpha": 0.95,
            "volume_frac": "#215CAF",
            "volume_frac_edge": "#215CAF",
            "volume_frac_alpha": 0.78,
            "share_field": "#c5cbd6",
            "share_field_edge": "#97a1b0",
            "share_field_alpha": 0.92,
            "share_inst": "#215CAF",
            "share_inst_edge": "#215CAF",
            "share_inst_alpha": 0.72,
            "ratio": "#923243",
            "ratio_edge": "#923243",
            "ratio_alpha": 0.90,
        },
        "layout": {
            "fig_width": 14.9,
            "min_fig_height": 7.2,
            "height_base": 1.9,
            "height_per_row": 0.31,
            "default_width_ratio": 1.0,
            "bar_height_default": 0.6,
            "row_step": 1.05,
            "xpad_factor": 1.02,
            "gutter_ratio": 0.10,
            "x_extra_right_ratio": 0.0,
            "label_pad_ratio": 0.018,
            "label_right_margin_ratio": 0.02,
            "text_clip_on": True,
            "draw_text_last": False,
            "deferred_text_zorder": 30.0,
            "value_text_zorder": 8.0,
            "x_tick_rotation": 0.0,
            "x_tick_ha": "center",
            "x_tick_rotation_mode": "default",
            "x_tick_pad": 2.0,
            "emphasize_labeled_x_ticks": False,
            "x_tick_mark_color": "tick_mark",
            "x_tick_mark_width": 0.85,
            "x_tick_mark_length": 4.0,
            "x_tick_mark_direction": "out",
            "x_tick_mark_hide_unlabeled": True,
            "x_tick_mark_unlabeled_alpha": 0.35,
            "x_tick_mark_unlabeled_length_ratio": 0.25,
            "emphasize_labeled_gridlines": False,
            "x_grid_labeled_color": "grid_labeled",
            "x_grid_labeled_linewidth": 0.80,
            "x_grid_labeled_alpha": 1.0,
            "x_grid_unlabeled_color": "grid",
            "x_grid_unlabeled_linewidth": 0.65,
            "x_grid_unlabeled_alpha": 1.0,
            "auto_reduce_x_tick_labels": False,
            "x_tick_label_min_gap_px": 6.0,
            "x_tick_label_every_n": None,
            "keep_first_last_tick_labels": True,
            "y_inner_pad": 0.10,
            "axis_label_fontsize": 12,
            "axis_label_pad": 8,
            "axis_label_pad_by_panel": {},
            "show_axis_labels": True,
            "show_primary_axis_labels": True,
            "show_secondary_axis_labels": True,
            "subfield_fontsize": 10,
            "subfield_label_linespacing": 1.0,
            "subfield_wrap_width": None,
            "subfield_wrap_break_long_words": False,
            "subfield_wrap_max_lines": 2,
            "subfield_autofit_left": False,
            "subfield_autofit_pad": 0.008,
            "subfield_autofit_left_min": None,
            "subfield_autofit_left_max": 0.52,
            "panel_subtitle_y": 0.985,
            "panel_subtitle_va": "top",
            "panel_subtitle_fontsize": 9.0,
            "panel_subtitle_draw_last": False,
            "secondary_label_y": -0.08,
            "secondary_label_fontsize": 11.0,
            "secondary_label_draw_last": False,
            "row_block_separator_every": None,
            "row_block_separator_color": "grid",
            "row_block_separator_linewidth": 0.75,
            "row_block_separator_alpha": 0.95,
            "row_block_separator_linestyle": "-",
            "row_block_separator_zorder": 2.2,
            "row_block_separator_include_subfield_labels": True,
            "row_block_separator_left_pad": 0.0,
            "row_block_separator_right_pad": 0.0,
            "value_label_fontsize": 10,
            "reference_label_fontsize": 10,
            "show_subfield_header": False,
            "subfield_header_x": 0.145,
            "subfield_header_y": 0.93,
            "subfield_header_coords": "figure",
            "subfield_header_ha": "center",
            "subfield_header_va": "bottom",
            "subfield_header_fontsize": 12,
            "show_legend": False,
            "legend_anchor": [0.02, 0.012],
            "legend_fontsize": 9.0,
            "legend_patch_linewidth": 0.9,
            "legend_mode": "flat",
            "legend_panel_anchor_y": 0.012,
            "legend_panel_anchor_x_offset": 0.0,
            "legend_panel_loc": "lower left",
            "subplots_adjust": {
                "left": 0.285,
                "right": 0.985,
                "top": 0.905,
                "bottom": 0.125,
                "wspace": 0.03,
            },
        },
        "messages": {
            "empty": "No subfield-level data available.",
        },
    }
}

_SPECIAL_TEMPLATE_FIELDS = {"value", "value_pct", "x"}


class _HalfUpFloat(float):
    def __format__(self, spec: str) -> str:
        body, conversion = spec[:-1], spec[-1:]
        if conversion not in {"f", "%"} or "." not in body:
            return super().__format__(spec)

        decimals_text = body.rsplit(".", 1)[1]
        if not decimals_text.isdigit():
            return super().__format__(spec)
        decimals = int(decimals_text)

        value = float(self)
        if conversion == "%":
            value *= 100.0
        text = format_half_up(value, decimals, signed="+" in body)
        if conversion == "%":
            text = f"{text}%"
        return text


def _label_context_value(value: object) -> object:
    if isinstance(value, (bool, str)):
        return value
    if isinstance(value, (int, float, np.integer, np.floating)) and not pd.isna(value):
        return _HalfUpFloat(value)
    return value


def _round_up(value: float, step: float) -> float:
    if step <= 0:
        return value
    return step * math.ceil(value / step)


def _count_tick_step(max_value: float, is_full_count: bool) -> float:
    if is_full_count:
        if max_value >= 8000:
            return 2000
        if max_value >= 3000:
            return 1000
        if max_value >= 1200:
            return 500
        return 250

    if max_value >= 3000:
        return 500
    if max_value >= 1500:
        return 250
    if max_value >= 600:
        return 100
    if max_value >= 300:
        return 50
    if max_value >= 120:
        return 20
    if max_value >= 60:
        return 10
    return 5


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def _style_axis(ax, *, grid_color: str, axis_color: str, label_color: str, show_grid: bool) -> None:
    ax.set_facecolor("white")
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_color(axis_color)
        spine.set_linewidth(0.7)
    if show_grid:
        ax.grid(axis="x", color=grid_color, linewidth=0.65)
    else:
        ax.grid(False)
    ax.tick_params(color=axis_color, labelcolor=label_color, width=0.65, length=0)


def _panel_option_value(option: Any, panel_id: str, default: Any) -> Any:
    if isinstance(option, dict):
        return option.get(panel_id, default)
    if option is None:
        return default
    return option


def _resolve_color(value: Any, colors: dict[str, Any], default: Any = None) -> Any:
    if value is None:
        return default
    if isinstance(value, str):
        if value in colors:
            return colors[value]
        if mcolors.is_color_like(value):
            return value
        return default
    return value


def _resolve_float(value: Any, *, context: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{context} must be numeric, got {value!r}.") from exc


def _required_dict(obj: Any, *, context: str) -> dict[str, Any]:
    if not isinstance(obj, dict):
        raise ValueError(f"{context} must be a dict.")
    return obj


def _required_list(obj: Any, *, context: str) -> list[Any]:
    if not isinstance(obj, list):
        raise ValueError(f"{context} must be a list.")
    return obj


def _template_fields(template: str) -> set[str]:
    fields: set[str] = set()
    for _, field_name, _, _ in Formatter().parse(template):
        if field_name:
            fields.add(field_name)
    return fields


def _wrap_label(
    text: str,
    *,
    width: int | None,
    break_long_words: bool,
    max_lines: int,
) -> str:
    if width is None or width <= 0:
        return text

    chunks = textwrap.wrap(
        text,
        width=width,
        break_long_words=break_long_words,
        break_on_hyphens=False,
    )
    if not chunks:
        return text

    if max_lines > 0 and len(chunks) > max_lines:
        chunks = chunks[:max_lines]
        tail = chunks[-1]
        if len(tail) >= 3:
            chunks[-1] = f"{tail[:-3]}..."
        else:
            chunks[-1] = f"{tail}..."

    return "\n".join(chunks)


def _coerce_positive_int_or_none(value: Any, *, context: str) -> int | None:
    if value is None:
        return None

    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{context} must be an integer or None, got {value!r}.") from exc

    return parsed if parsed > 0 else None


def _autofit_subfield_left_margin(
    fig: plt.Figure,
    *,
    subfield_ax: Any,
    layout: dict[str, Any],
) -> None:
    if not bool(layout.get("subfield_autofit_left", False)):
        return

    labels = [tick for tick in subfield_ax.get_yticklabels() if tick.get_visible() and tick.get_text()]
    if not labels:
        return

    current_left = float(fig.subplotpars.left)
    pad = _resolve_float(layout.get("subfield_autofit_pad", 0.008), context="layout.subfield_autofit_pad")
    left_min_raw = layout.get("subfield_autofit_left_min", current_left)
    left_min = current_left if left_min_raw is None else _resolve_float(left_min_raw, context="layout.subfield_autofit_left_min")
    left_max = _resolve_float(layout.get("subfield_autofit_left_max", 0.52), context="layout.subfield_autofit_left_max")

    if left_max <= left_min:
        return

    try:
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
    except Exception:
        return

    min_x0 = min(
        tick.get_window_extent(renderer=renderer).transformed(fig.transFigure.inverted()).x0
        for tick in labels
    )
    if min_x0 >= pad:
        return

    needed_left = current_left + (pad - min_x0)
    new_left = min(left_max, max(left_min, needed_left))
    if new_left <= current_left + 1e-6:
        return

    fig.subplots_adjust(left=new_left)


def _validate_numeric_column(plot_df: pd.DataFrame, column: str, *, context: str) -> None:
    if column not in plot_df.columns:
        raise ValueError(f"{context}: column '{column}' not found in plot_df.")

    raw = plot_df[column]
    numeric = pd.to_numeric(raw, errors="coerce")
    bad_mask = raw.notna() & numeric.isna()
    if bad_mask.any():
        sample = raw[bad_mask].iloc[0]
        raise ValueError(
            f"{context}: column '{column}' contains non-numeric value {sample!r}."
        )


def _validate_figure_spec(plot_df: pd.DataFrame, figure_spec: dict[str, Any]) -> None:
    spec = _required_dict(figure_spec, context="figure_spec")

    subfield_column = spec.get("subfield_column")
    if not isinstance(subfield_column, str) or not subfield_column.strip():
        raise ValueError("figure_spec.subfield_column must be a non-empty string.")
    if subfield_column not in plot_df.columns:
        raise ValueError(f"figure_spec.subfield_column '{subfield_column}' not found in plot_df.")

    legend_cfg_raw = spec.get("legend")
    if legend_cfg_raw is not None:
        legend_cfg = _required_dict(legend_cfg_raw, context="figure_spec.legend")
        legend_mode = str(legend_cfg.get("mode", "flat")).lower().strip()
        if legend_mode not in {"flat", "panel_stacks"}:
            raise ValueError("figure_spec.legend.mode must be 'flat' or 'panel_stacks'.")

    panels = _required_list(spec.get("panels"), context="figure_spec.panels")
    if not (2 <= len(panels) <= 4):
        raise ValueError("figure_spec.panels must contain between 2 and 4 panels in v1.")

    seen_panel_ids: set[str] = set()

    for panel_idx, panel in enumerate(panels):
        panel_ctx = f"figure_spec.panels[{panel_idx}]"
        panel_dict = _required_dict(panel, context=panel_ctx)

        panel_id = panel_dict.get("id")
        if not isinstance(panel_id, str) or not panel_id.strip():
            raise ValueError(f"{panel_ctx}.id must be a non-empty string.")
        if panel_id in seen_panel_ids:
            raise ValueError(f"Duplicate panel id '{panel_id}' in figure_spec.panels.")
        seen_panel_ids.add(panel_id)

        width_ratio = panel_dict.get("width_ratio", 1.0)
        if _resolve_float(width_ratio, context=f"{panel_ctx}.width_ratio") <= 0:
            raise ValueError(f"{panel_ctx}.width_ratio must be > 0.")

        axes_cfg = _required_dict(panel_dict.get("axes"), context=f"{panel_ctx}.axes")
        if "primary" not in axes_cfg:
            raise ValueError(f"{panel_ctx}.axes must include 'primary'.")

        for axis_name, axis_cfg in axes_cfg.items():
            axis_ctx = f"{panel_ctx}.axes['{axis_name}']"
            _required_dict(axis_cfg, context=axis_ctx)
            if axis_name not in {"primary", "secondary"}:
                raise ValueError(f"{axis_ctx}: axis name must be 'primary' or 'secondary'.")

            tick_mode = axis_cfg.get("tick_mode", "step")
            if tick_mode not in {"step", "count_auto"}:
                raise ValueError(f"{axis_ctx}.tick_mode must be 'step' or 'count_auto'.")
            if tick_mode == "step":
                tick_step = axis_cfg.get("tick_step")
                if tick_step is None:
                    raise ValueError(f"{axis_ctx}.tick_step is required when tick_mode='step'.")
                if _resolve_float(tick_step, context=f"{axis_ctx}.tick_step") <= 0:
                    raise ValueError(f"{axis_ctx}.tick_step must be > 0.")

            position = str(axis_cfg.get("position", "bottom")).lower()
            if position not in {"bottom", "top"}:
                raise ValueError(f"{axis_ctx}.position must be 'bottom' or 'top'.")

        traces = _required_list(panel_dict.get("traces"), context=f"{panel_ctx}.traces")
        if not traces:
            raise ValueError(f"{panel_ctx}.traces must not be empty.")

        secondary_axis_used = False
        for trace_idx, trace in enumerate(traces):
            trace_ctx = f"{panel_ctx}.traces[{trace_idx}]"
            trace_dict = _required_dict(trace, context=trace_ctx)

            trace_type = trace_dict.get("type")
            if trace_type != "barh":
                raise ValueError(f"{trace_ctx}.type must be 'barh' in v1.")

            column = trace_dict.get("column")
            if not isinstance(column, str) or not column.strip():
                raise ValueError(f"{trace_ctx}.column must be a non-empty string.")
            _validate_numeric_column(plot_df, column, context=trace_ctx)

            axis_name = str(trace_dict.get("axis", "primary"))
            if axis_name not in axes_cfg:
                raise ValueError(
                    f"{trace_ctx}.axis='{axis_name}' is not defined in {panel_ctx}.axes."
                )
            if axis_name == "secondary":
                secondary_axis_used = True

            value_label_cfg = trace_dict.get("value_label")
            if value_label_cfg is not None:
                value_label_dict = _required_dict(value_label_cfg, context=f"{trace_ctx}.value_label")
                if bool(value_label_dict.get("enabled", False)):
                    template = value_label_dict.get("template", "{value}")
                    if not isinstance(template, str):
                        raise ValueError(f"{trace_ctx}.value_label.template must be a string.")
                    template_fields = _template_fields(template)
                    include_row_context = bool(value_label_dict.get("include_row_context", True))
                    unknown_fields = {
                        field
                        for field in template_fields
                        if field not in _SPECIAL_TEMPLATE_FIELDS
                        and (field not in plot_df.columns or not include_row_context)
                    }
                    if unknown_fields:
                        unknown = ", ".join(sorted(unknown_fields))
                        raise ValueError(
                            f"{trace_ctx}.value_label.template uses unknown fields: {unknown}."
                        )

        if "secondary" in axes_cfg and not secondary_axis_used:
            raise ValueError(
                f"{panel_ctx}.axes defines 'secondary' but no traces are assigned to axis='secondary'."
            )

        reference_lines = panel_dict.get("reference_lines", [])
        if reference_lines is None:
            reference_lines = []
        reference_lines_list = _required_list(reference_lines, context=f"{panel_ctx}.reference_lines")

        for line_idx, line in enumerate(reference_lines_list):
            line_ctx = f"{panel_ctx}.reference_lines[{line_idx}]"
            line_dict = _required_dict(line, context=line_ctx)

            axis_name = str(line_dict.get("axis", "primary"))
            if axis_name not in axes_cfg:
                raise ValueError(f"{line_ctx}.axis='{axis_name}' is not defined in {panel_ctx}.axes.")

            if "x" not in line_dict:
                raise ValueError(f"{line_ctx}.x is required.")
            _resolve_float(line_dict.get("x"), context=f"{line_ctx}.x")

            label_template = line_dict.get("label_template")
            if label_template is not None and not isinstance(label_template, str):
                raise ValueError(f"{line_ctx}.label_template must be a string when provided.")

            label_position = line_dict.get("label_position")
            if label_position is not None:
                pos = str(label_position).lower().strip()
                if pos not in {"top", "bottom"}:
                    raise ValueError(f"{line_ctx}.label_position must be 'top' or 'bottom'.")


def _resolve_style(style_preset: str, style_overrides: dict[str, Any] | None) -> dict[str, Any]:
    if style_preset not in _STYLE_PRESETS:
        available = ", ".join(sorted(_STYLE_PRESETS.keys()))
        raise ValueError(f"Unknown style_preset '{style_preset}'. Available: {available}.")

    style = deepcopy(_STYLE_PRESETS[style_preset])
    if style_overrides is not None:
        if not isinstance(style_overrides, dict):
            raise ValueError("style_overrides must be a dict when provided.")
        style = _deep_merge(style, style_overrides)
    return style


def _prepare_axis(
    *,
    ax,
    axis_cfg: dict[str, Any],
    panel_id: str,
    axis_name: str,
    max_value: float,
    layout: dict[str, Any],
    colors: dict[str, Any],
) -> dict[str, float]:
    tick_mode = str(axis_cfg.get("tick_mode", "step"))

    if tick_mode == "count_auto":
        tick_step = _count_tick_step(
            max_value=max_value,
            is_full_count=bool(axis_cfg.get("count_is_full", False)),
        )
    else:
        tick_step = _resolve_float(axis_cfg.get("tick_step"), context=f"panel '{panel_id}' axis '{axis_name}' tick_step")

    xpad_factor = _resolve_float(
        axis_cfg.get("xpad_factor", _panel_option_value(layout.get("xpad_factor"), panel_id, 1.02)),
        context=f"panel '{panel_id}' axis '{axis_name}' xpad_factor",
    )
    gutter_ratio = _resolve_float(
        axis_cfg.get("gutter_ratio", _panel_option_value(layout.get("gutter_ratio"), panel_id, 0.10)),
        context=f"panel '{panel_id}' axis '{axis_name}' gutter_ratio",
    )
    extra_right_ratio = _resolve_float(
        axis_cfg.get("extra_right_ratio", _panel_option_value(layout.get("x_extra_right_ratio"), panel_id, 0.0)),
        context=f"panel '{panel_id}' axis '{axis_name}' extra_right_ratio",
    )

    min_plot_limit = axis_cfg.get("min_plot_limit", tick_step)
    min_plot_limit = _resolve_float(
        min_plot_limit,
        context=f"panel '{panel_id}' axis '{axis_name}' min_plot_limit",
    )

    padded_base = max(max_value, min_plot_limit)
    round_plot_limit_to_tick = bool(axis_cfg.get("round_plot_limit_to_tick", True))
    padded_plot_limit = max(tick_step, padded_base * xpad_factor)
    if round_plot_limit_to_tick:
        plot_limit = max(tick_step, _round_up(padded_plot_limit, tick_step))
    else:
        plot_limit = padded_plot_limit
    xlim_max = plot_limit * (1.0 + gutter_ratio + extra_right_ratio)

    ax.set_xlim(0, xlim_max)
    tick_limit = _round_up(xlim_max, tick_step)

    if tick_mode == "count_auto":
        tick_steps = int(round(tick_limit / tick_step))
        tick_values = [round(i * tick_step, 10) for i in range(tick_steps + 1)]
        ax.set_xticks(tick_values)

        is_full_count = bool(axis_cfg.get("count_is_full", False))
        ax.xaxis.set_major_formatter(
            mticker.FuncFormatter(
                lambda x, _pos: (
                    ""
                    if x > plot_limit + 1e-9
                    else (f"{int(x):,}" if is_full_count else f"{x:,.0f}")
                )
            )
        )
    else:
        tick_decimals = int(axis_cfg.get("tick_decimals", 0))
        tick_as_percent = bool(axis_cfg.get("tick_as_percent", False))

        tick_steps = int(round(tick_limit / tick_step))
        tick_values = [round(i * tick_step, 10) for i in range(tick_steps + 1)]
        ax.set_xticks(tick_values)

        ax.xaxis.set_major_formatter(
            mticker.FuncFormatter(
                lambda x, _pos: (
                    ""
                    if x > plot_limit + 1e-9
                    else (
                        f"{x:.{tick_decimals}%}"
                        if tick_as_percent
                        else f"{x:.{tick_decimals}f}"
                    )
                )
            )
        )

    label = str(axis_cfg.get("label", ""))
    if axis_name == "secondary":
        default_show_label = layout.get(
            "show_secondary_axis_labels",
            layout.get("show_axis_labels", True),
        )
    else:
        default_show_label = layout.get(
            "show_primary_axis_labels",
            layout.get("show_axis_labels", True),
        )
    show_label = bool(axis_cfg.get("show_label", default_show_label))
    axis_label_pad_default = layout.get("axis_label_pad", 8)
    axis_label_pad_by_panel = layout.get("axis_label_pad_by_panel", axis_label_pad_default)
    axis_label_pad = _resolve_float(
        axis_cfg.get("label_pad", _panel_option_value(axis_label_pad_by_panel, panel_id, axis_label_pad_default)),
        context=f"panel '{panel_id}' axis '{axis_name}' label_pad",
    )

    label_fontsize = _resolve_float(
        axis_cfg.get("label_fontsize", layout.get("axis_label_fontsize", 12)),
        context=f"panel '{panel_id}' axis '{axis_name}' label_fontsize",
    )

    if label and show_label:
        ax.set_xlabel(label, fontsize=label_fontsize, labelpad=axis_label_pad)
    elif not show_label:
        ax.set_xlabel("")

    position = str(axis_cfg.get("position", "bottom" if axis_name == "primary" else "top")).lower()
    if position == "top":
        ax.xaxis.set_ticks_position("top")
        ax.xaxis.set_label_position("top")
    else:
        ax.xaxis.set_ticks_position("bottom")
        ax.xaxis.set_label_position("bottom")

    tick_rotation = _resolve_float(
        axis_cfg.get("tick_rotation", _panel_option_value(layout.get("x_tick_rotation"), panel_id, 0.0)),
        context=f"panel '{panel_id}' axis '{axis_name}' tick_rotation",
    )
    tick_ha = str(axis_cfg.get("tick_ha", _panel_option_value(layout.get("x_tick_ha"), panel_id, "center")))
    tick_rotation_mode = str(axis_cfg.get("tick_rotation_mode", layout.get("x_tick_rotation_mode", "default")))
    tick_pad = _resolve_float(
        axis_cfg.get("tick_pad", _panel_option_value(layout.get("x_tick_pad"), panel_id, 2.0)),
        context=f"panel '{panel_id}' axis '{axis_name}' tick_pad",
    )

    plt.setp(
        ax.get_xticklabels(),
        rotation=tick_rotation,
        ha=tick_ha,
        rotation_mode=tick_rotation_mode,
    )
    ax.tick_params(axis="x", pad=tick_pad)

    show_grid = bool(axis_cfg.get("show_grid", axis_name == "primary"))
    _style_axis(
        ax,
        grid_color=str(colors.get("grid", "#d7d7d7")),
        axis_color=str(colors.get("axis", "#b0b0b0")),
        label_color=str(colors.get("tick_label", "#4a4a4a")),
        show_grid=show_grid,
    )

    return {
        "plot_limit": float(plot_limit),
        "xlim_max": float(xlim_max),
    }


def _apply_xtick_label_density(
    *,
    fig: plt.Figure,
    ax,
    panel_id: str,
    axis_name: str,
    axis_cfg: dict[str, Any],
    layout: dict[str, Any],
    colors: dict[str, Any],
) -> None:
    base_step_raw = axis_cfg.get(
        "tick_label_every_n",
        _panel_option_value(layout.get("x_tick_label_every_n"), panel_id, None),
    )
    base_step = _coerce_positive_int_or_none(
        base_step_raw,
        context=f"panel '{panel_id}' axis '{axis_name}' tick_label_every_n",
    )
    step = 1 if base_step is None else base_step

    auto_reduce = bool(
        axis_cfg.get(
            "auto_reduce_tick_labels",
            _panel_option_value(layout.get("auto_reduce_x_tick_labels"), panel_id, False),
        )
    )
    keep_first_last = bool(
        axis_cfg.get(
            "keep_first_last_tick_labels",
            layout.get("keep_first_last_tick_labels", True),
        )
    )
    min_gap_px = _resolve_float(
        axis_cfg.get(
            "tick_label_min_gap_px",
            _panel_option_value(layout.get("x_tick_label_min_gap_px"), panel_id, 6.0),
        ),
        context=f"panel '{panel_id}' axis '{axis_name}' tick_label_min_gap_px",
    )

    labels = list(ax.get_xticklabels())
    n_labels = len(labels)
    if n_labels <= 2:
        return

    def _apply_step(step_value: int) -> None:
        for idx, tick_label in enumerate(labels):
            keep = (idx % step_value) == 0
            if keep_first_last and idx in {0, n_labels - 1}:
                keep = True
            tick_label.set_visible(keep)

    _apply_step(max(1, step))
    if not auto_reduce:
        return

    try:
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
    except Exception:
        return

    current_step = max(1, step)
    while current_step <= n_labels:
        _apply_step(current_step)
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()

        visible_labels = [
            tick_label
            for tick_label in labels
            if tick_label.get_visible() and tick_label.get_text()
        ]
        if len(visible_labels) <= 1:
            break

        bboxes = [tick_label.get_window_extent(renderer=renderer) for tick_label in visible_labels]
        has_overlap = any(
            left.x1 + min_gap_px > right.x0
            for left, right in zip(bboxes, bboxes[1:])
        )
        if not has_overlap:
            break

        current_step += 1

    emphasize_ticks = bool(
        axis_cfg.get(
            "emphasize_labeled_ticks",
            _panel_option_value(layout.get("emphasize_labeled_x_ticks"), panel_id, False),
        )
    )
    if not emphasize_ticks:
        return

    tick_mark_direction = str(
        axis_cfg.get(
            "tick_mark_direction",
            _panel_option_value(layout.get("x_tick_mark_direction"), panel_id, "out"),
        )
    ).lower()
    if tick_mark_direction not in {"in", "out", "inout"}:
        tick_mark_direction = "out"

    tick_mark_color = _resolve_color(
        axis_cfg.get(
            "tick_mark_color",
            _panel_option_value(layout.get("x_tick_mark_color"), panel_id, "tick_mark"),
        ),
        colors,
        default=colors.get("tick_mark", colors.get("axis", "#7a7a7a")),
    )
    tick_mark_width = _resolve_float(
        axis_cfg.get(
            "tick_mark_width",
            _panel_option_value(layout.get("x_tick_mark_width"), panel_id, 0.85),
        ),
        context=f"panel '{panel_id}' axis '{axis_name}' tick_mark_width",
    )
    tick_mark_length = _resolve_float(
        axis_cfg.get(
            "tick_mark_length",
            _panel_option_value(layout.get("x_tick_mark_length"), panel_id, 4.0),
        ),
        context=f"panel '{panel_id}' axis '{axis_name}' tick_mark_length",
    )
    hide_unlabeled = bool(
        axis_cfg.get(
            "tick_mark_hide_unlabeled",
            _panel_option_value(layout.get("x_tick_mark_hide_unlabeled"), panel_id, True),
        )
    )
    unlabeled_alpha = _resolve_float(
        axis_cfg.get(
            "tick_mark_unlabeled_alpha",
            _panel_option_value(layout.get("x_tick_mark_unlabeled_alpha"), panel_id, 0.35),
        ),
        context=f"panel '{panel_id}' axis '{axis_name}' tick_mark_unlabeled_alpha",
    )
    unlabeled_length_ratio = _resolve_float(
        axis_cfg.get(
            "tick_mark_unlabeled_length_ratio",
            _panel_option_value(layout.get("x_tick_mark_unlabeled_length_ratio"), panel_id, 0.25),
        ),
        context=f"panel '{panel_id}' axis '{axis_name}' tick_mark_unlabeled_length_ratio",
    )

    ax.tick_params(
        axis="x",
        direction=tick_mark_direction,
        color=tick_mark_color,
    )

    axis_position = str(axis_cfg.get("position", "bottom" if axis_name == "primary" else "top")).lower()
    if axis_position not in {"top", "bottom"}:
        axis_position = "bottom"

    major_ticks = list(ax.xaxis.get_major_ticks())
    for idx, tick in enumerate(major_ticks):
        label_visible = False
        if idx < n_labels:
            label_obj = labels[idx]
            label_visible = bool(label_obj.get_visible() and label_obj.get_text())

        active_line = tick.tick2line if axis_position == "top" else tick.tick1line
        if hide_unlabeled and not label_visible:
            active_line.set_visible(False)
            continue

        active_line.set_visible(True)
        active_line.set_color(tick_mark_color)
        active_line.set_alpha(1.0 if label_visible else unlabeled_alpha)
        active_line.set_markeredgewidth(tick_mark_width)
        if label_visible:
            active_line.set_markersize(tick_mark_length)
        else:
            active_line.set_markersize(max(0.0, tick_mark_length * unlabeled_length_ratio))

    emphasize_gridlines = bool(
        axis_cfg.get(
            "emphasize_labeled_gridlines",
            _panel_option_value(layout.get("emphasize_labeled_gridlines"), panel_id, False),
        )
    )
    if not emphasize_gridlines:
        return

    labeled_grid_color = _resolve_color(
        axis_cfg.get(
            "grid_labeled_color",
            _panel_option_value(layout.get("x_grid_labeled_color"), panel_id, "grid_labeled"),
        ),
        colors,
        default=colors.get("grid_labeled", colors.get("tick_mark", colors.get("grid", "#d7d7d7"))),
    )
    unlabeled_grid_color = _resolve_color(
        axis_cfg.get(
            "grid_unlabeled_color",
            _panel_option_value(layout.get("x_grid_unlabeled_color"), panel_id, "grid"),
        ),
        colors,
        default=colors.get("grid", "#d7d7d7"),
    )
    labeled_grid_linewidth = _resolve_float(
        axis_cfg.get(
            "grid_labeled_linewidth",
            _panel_option_value(layout.get("x_grid_labeled_linewidth"), panel_id, 0.80),
        ),
        context=f"panel '{panel_id}' axis '{axis_name}' grid_labeled_linewidth",
    )
    unlabeled_grid_linewidth = _resolve_float(
        axis_cfg.get(
            "grid_unlabeled_linewidth",
            _panel_option_value(layout.get("x_grid_unlabeled_linewidth"), panel_id, 0.65),
        ),
        context=f"panel '{panel_id}' axis '{axis_name}' grid_unlabeled_linewidth",
    )
    labeled_grid_alpha = _resolve_float(
        axis_cfg.get(
            "grid_labeled_alpha",
            _panel_option_value(layout.get("x_grid_labeled_alpha"), panel_id, 1.0),
        ),
        context=f"panel '{panel_id}' axis '{axis_name}' grid_labeled_alpha",
    )
    unlabeled_grid_alpha = _resolve_float(
        axis_cfg.get(
            "grid_unlabeled_alpha",
            _panel_option_value(layout.get("x_grid_unlabeled_alpha"), panel_id, 1.0),
        ),
        context=f"panel '{panel_id}' axis '{axis_name}' grid_unlabeled_alpha",
    )

    grid_lines = list(ax.get_xgridlines())
    n_grid = len(grid_lines)
    if n_grid == 0:
        return

    for idx, grid_line in enumerate(grid_lines):
        label_visible = False
        if idx < n_labels:
            label_obj = labels[idx]
            label_visible = bool(label_obj.get_visible() and label_obj.get_text())
        if label_visible:
            grid_line.set_color(labeled_grid_color)
            grid_line.set_alpha(labeled_grid_alpha)
            grid_line.set_linewidth(labeled_grid_linewidth)
        else:
            grid_line.set_color(unlabeled_grid_color)
            grid_line.set_alpha(unlabeled_grid_alpha)
            grid_line.set_linewidth(unlabeled_grid_linewidth)


def _draw_row_block_separators(
    *,
    fig: plt.Figure,
    panel_axes_primary: list[Any],
    subfield_ax: Any,
    y: np.ndarray,
    layout: dict[str, Any],
    colors: dict[str, Any],
) -> None:
    every = _coerce_positive_int_or_none(
        layout.get("row_block_separator_every"),
        context="layout.row_block_separator_every",
    )
    if every is None:
        return

    n_rows = len(y)
    if n_rows <= every:
        return

    color = _resolve_color(
        layout.get("row_block_separator_color", "grid"),
        colors,
        default=colors.get("grid", "#d7d7d7"),
    )
    linewidth = _resolve_float(
        layout.get("row_block_separator_linewidth", 0.75),
        context="layout.row_block_separator_linewidth",
    )
    alpha = _resolve_float(
        layout.get("row_block_separator_alpha", 0.95),
        context="layout.row_block_separator_alpha",
    )
    linestyle = str(layout.get("row_block_separator_linestyle", "-"))
    zorder = _resolve_float(
        layout.get("row_block_separator_zorder", 2.2),
        context="layout.row_block_separator_zorder",
    )
    include_subfield_labels = bool(layout.get("row_block_separator_include_subfield_labels", True))
    left_pad = _resolve_float(
        layout.get("row_block_separator_left_pad", 0.0),
        context="layout.row_block_separator_left_pad",
    )
    right_pad = _resolve_float(
        layout.get("row_block_separator_right_pad", 0.0),
        context="layout.row_block_separator_right_pad",
    )

    try:
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()
    except Exception:
        renderer = None

    x_start = panel_axes_primary[0].get_position().x0
    if include_subfield_labels and renderer is not None:
        labels = [
            tick_label
            for tick_label in subfield_ax.get_yticklabels()
            if tick_label.get_visible() and tick_label.get_text()
        ]
        if labels:
            label_min_x = min(
                tick_label.get_window_extent(renderer=renderer).transformed(fig.transFigure.inverted()).x0
                for tick_label in labels
            )
            x_start = min(x_start, label_min_x)

    x_end = panel_axes_primary[-1].get_position().x1
    x_start = max(0.0, x_start - left_pad)
    x_end = min(1.0, x_end + right_pad)
    if x_end <= x_start:
        return

    for idx in range(every, n_rows, every):
        if idx >= n_rows:
            break
        y_sep = float((y[idx - 1] + y[idx]) / 2.0)
        _, y_disp = subfield_ax.transData.transform((0.0, y_sep))
        y_fig = fig.transFigure.inverted().transform((0.0, y_disp))[1]

        fig.add_artist(
            mlines.Line2D(
                [x_start, x_end],
                [y_fig, y_fig],
                transform=fig.transFigure,
                color=color,
                linewidth=linewidth,
                alpha=alpha,
                linestyle=linestyle,
                zorder=zorder,
            )
        )


def build_panel_figure(
    plot_df: pd.DataFrame,
    figure_spec: dict[str, Any],
    *,
    style_preset: str = "subfield_profile_v1",
    style_overrides: dict[str, Any] | None = None,
) -> tuple[plt.Figure, pd.DataFrame]:
    """
    Generic modular panel renderer (v1).

    Parameters
    ----------
    plot_df:
        Dataframe containing all columns referenced by figure_spec traces/labels.
    figure_spec:
        Role-free panel specification with 2-4 horizontal panels and optional dual x-axis.
    style_preset:
        Name of built-in style preset.
    style_overrides:
        Dict merged over selected preset.

    Returns
    -------
    fig, layout_debug_df
        Matplotlib figure and text-placement debug dataframe.
    """
    style = _resolve_style(style_preset=style_preset, style_overrides=style_overrides)
    _validate_figure_spec(plot_df=plot_df, figure_spec=figure_spec)

    spec = deepcopy(figure_spec)
    colors = style.get("colors", {})
    layout = style.get("layout", {})
    messages = style.get("messages", {})

    subfield_column = spec["subfield_column"]
    panels = spec["panels"]

    n_rows = len(plot_df)
    fig_height = max(
        float(layout.get("min_fig_height", 6.0)),
        float(layout.get("height_base", 1.5)) + float(layout.get("height_per_row", 0.25)) * n_rows,
    )

    width_ratios = [
        _resolve_float(panel.get("width_ratio", layout.get("default_width_ratio", 1.0)), context=f"panel '{panel.get('id')}' width_ratio")
        for panel in panels
    ]

    fig, axes = plt.subplots(
        nrows=1,
        ncols=len(panels),
        sharey=True,
        figsize=(float(layout.get("fig_width", 12.0)), fig_height),
        gridspec_kw={"width_ratios": width_ratios},
    )

    if len(panels) == 1:
        panel_axes_primary = [axes]
    else:
        panel_axes_primary = list(axes)

    if plot_df.empty:
        fig.text(
            0.5,
            0.5,
            str(spec.get("messages", {}).get("empty", messages.get("empty", "No data available."))),
            ha="center",
            va="center",
        )
        fig.subplots_adjust(**layout.get("subplots_adjust", {}))
        return fig, pd.DataFrame(columns=["panel", "subfield_label", "text_x", "axis_xlim_max"])

    row_step = float(layout.get("row_step", 1.0))
    y = np.arange(n_rows, dtype=float) * row_step

    y_inner_pad_default = float(layout.get("y_inner_pad", 0.10))
    y_inner_pad_top = float(layout.get("y_inner_pad_top", y_inner_pad_default))
    y_inner_pad_bottom = float(layout.get("y_inner_pad_bottom", y_inner_pad_default))

    max_trace_height = float(layout.get("bar_height_default", 0.6))
    for panel in panels:
        for trace in panel.get("traces", []):
            if "height" in trace:
                max_trace_height = max(max_trace_height, _resolve_float(trace["height"], context=f"panel '{panel['id']}' trace height"))

    max_bar_half_height = max_trace_height / 2.0
    y_min = float(y[0]) - (max_bar_half_height + y_inner_pad_top)
    y_max = float(y[-1]) + (max_bar_half_height + y_inner_pad_bottom)

    subfield_labels = plot_df[subfield_column].astype(str)
    wrap_width = _coerce_positive_int_or_none(
        layout.get("subfield_wrap_width"),
        context="layout.subfield_wrap_width",
    )
    wrap_break_long_words = bool(layout.get("subfield_wrap_break_long_words", False))
    wrap_max_lines = int(layout.get("subfield_wrap_max_lines", 2))
    if wrap_max_lines < 1:
        wrap_max_lines = 1

    subfield_labels_rendered = subfield_labels.apply(
        lambda value: _wrap_label(
            str(value),
            width=wrap_width,
            break_long_words=wrap_break_long_words,
            max_lines=wrap_max_lines,
        )
    )

    subfield_label_linespacing = _resolve_float(
        layout.get("subfield_label_linespacing", 1.0),
        context="layout.subfield_label_linespacing",
    )
    subfield_label_color = _resolve_color("subfield_label", colors, default="#202020")

    panel_contexts: list[dict[str, Any]] = []
    for idx, (primary_ax, panel) in enumerate(zip(panel_axes_primary, panels)):
        panel_id = str(panel["id"])
        axes_cfg = panel["axes"]

        panel_axes_map: dict[str, Any] = {"primary": primary_ax}
        if "secondary" in axes_cfg:
            secondary_ax = primary_ax.twiny()
            secondary_ax.set_ylim(y_max, y_min)
            secondary_ax.patch.set_alpha(0.0)
            secondary_ax.set_yticks([])
            secondary_ax.tick_params(axis="y", left=False, right=False, labelleft=False, labelright=False)
            panel_axes_map["secondary"] = secondary_ax

        primary_ax.set_ylim(y_max, y_min)
        primary_ax.set_yticks(y.tolist())
        if idx == 0:
            primary_ax.set_yticklabels(
                subfield_labels_rendered,
                fontsize=float(layout.get("subfield_fontsize", 10)),
                color=subfield_label_color,
            )
            primary_ax.tick_params(axis="y", which="both", left=False, right=False, labelleft=True, length=0)
            for tick_label in primary_ax.get_yticklabels():
                tick_label.set_linespacing(subfield_label_linespacing)
        else:
            primary_ax.tick_params(axis="y", which="both", left=False, right=False, labelleft=False, length=0)

        panel_contexts.append(
            {
                "panel_id": panel_id,
                "panel": panel,
                "axes": panel_axes_map,
            }
        )

    deferred_text_specs: list[dict[str, Any]] = []
    pending_tick_anchored_subtitles: list[dict[str, Any]] = []

    def _add_text(
        *,
        ax,
        x: float,
        y_coord: float,
        text: str,
        coords: str,
        draw_last: bool,
        **kwargs: Any,
    ) -> None:
        if not draw_last:
            if coords == "data":
                transform = ax.transData
            elif coords == "xaxis":
                transform = ax.get_xaxis_transform()
            else:
                transform = ax.transAxes
            ax.text(x, y_coord, text, transform=transform, **kwargs)
            return

        deferred_text_specs.append(
            {
                "ax": ax,
                "x": x,
                "y": y_coord,
                "text": text,
                "coords": coords,
                "kwargs": kwargs,
            }
        )

    axis_max_values: dict[tuple[str, str], list[float]] = {}
    pending_value_labels: list[dict[str, Any]] = []
    layout_debug_rows: list[dict[str, Any]] = []
    legend_entries: list[dict[str, Any]] = []
    legend_entries_by_panel: dict[str, list[dict[str, Any]]] = {}
    seen_legend_labels: set[str] = set()
    seen_legend_labels_by_panel: dict[str, set[str]] = {}
    legend_seq = 0

    for panel_ctx in panel_contexts:
        panel_id = panel_ctx["panel_id"]
        panel = panel_ctx["panel"]
        panel_axes_map = panel_ctx["axes"]

        for trace_idx, trace in enumerate(panel["traces"]):
            trace_id = str(trace.get("id", f"trace_{trace_idx}"))
            axis_name = str(trace.get("axis", "primary"))
            ax = panel_axes_map[axis_name]

            series = pd.to_numeric(plot_df[trace["column"]], errors="coerce")
            finite = series.replace([np.inf, -np.inf], np.nan).dropna()
            max_value = float(finite.max()) if not finite.empty else 0.0
            axis_max_values.setdefault((panel_id, axis_name), []).append(max_value)

            color_value = _resolve_color(trace.get("color"), colors, default=colors.get("text_main", "#202020"))
            edgecolor_value = _resolve_color(trace.get("edgecolor"), colors, default=color_value)

            alpha_value_raw = trace.get("alpha", 1.0)
            alpha_value = _resolve_color(alpha_value_raw, colors, default=1.0)
            alpha_value = _resolve_float(alpha_value, context=f"panel '{panel_id}' trace '{trace_id}' alpha")

            height_value = trace.get("height", layout.get("bar_height_default", 0.6))
            height_value = _resolve_float(height_value, context=f"panel '{panel_id}' trace '{trace_id}' height")

            zorder_value = _resolve_float(
                trace.get("zorder", 2.0),
                context=f"panel '{panel_id}' trace '{trace_id}' zorder",
            )

            ax.barh(
                y,
                series,
                color=color_value,
                edgecolor=edgecolor_value,
                alpha=alpha_value,
                height=height_value,
                zorder=zorder_value,
            )

            legend_label = trace.get("legend_label")
            if isinstance(legend_label, str) and legend_label:
                axis_cfg_for_trace = panel["axes"].get(axis_name, {})
                axis_pos_default = "bottom" if axis_name == "primary" else "top"
                axis_position = str(axis_cfg_for_trace.get("position", axis_pos_default)).lower()
                if axis_position not in {"top", "bottom"}:
                    axis_position = axis_pos_default

                if legend_label not in seen_legend_labels:
                    seen_legend_labels.add(legend_label)
                    legend_entries.append(
                        {
                            "label": legend_label,
                            "facecolor": color_value,
                            "edgecolor": edgecolor_value,
                            "alpha": alpha_value,
                        }
                    )

                panel_seen = seen_legend_labels_by_panel.setdefault(panel_id, set())
                if legend_label not in panel_seen:
                    panel_seen.add(legend_label)
                    legend_entries_by_panel.setdefault(panel_id, []).append(
                        {
                            "label": legend_label,
                            "facecolor": color_value,
                            "edgecolor": edgecolor_value,
                            "alpha": alpha_value,
                            "axis_position": axis_position,
                            "seq": legend_seq,
                        }
                    )
                    legend_seq += 1

            value_label_cfg = trace.get("value_label")
            if isinstance(value_label_cfg, dict) and bool(value_label_cfg.get("enabled", False)):
                pending_value_labels.append(
                    {
                        "panel_id": panel_id,
                        "axis_name": axis_name,
                        "trace_id": trace_id,
                        "ax": ax,
                        "series": series,
                        "config": value_label_cfg,
                    }
                )

        subtitle_cfg = panel.get("subtitle")
        if subtitle_cfg:
            subtitle_text: str
            subtitle_color: Any
            subtitle_fontsize: float
            subtitle_y: float
            subtitle_x: float
            subtitle_fontsize_default = _panel_option_value(
                layout.get("panel_subtitle_fontsize"),
                panel_id,
                9.0,
            )
            subtitle_y_default = _panel_option_value(
                layout.get("panel_subtitle_y"),
                panel_id,
                0.985,
            )
            subtitle_va_default = _panel_option_value(
                layout.get("panel_subtitle_va"),
                panel_id,
                "top",
            )
            subtitle_draw_last_default = _panel_option_value(
                layout.get("panel_subtitle_draw_last"),
                panel_id,
                False,
            )
            subtitle_anchor_default = _panel_option_value(
                layout.get("panel_subtitle_anchor"),
                panel_id,
                "axes",
            )
            subtitle_anchor_axis_default = _panel_option_value(
                layout.get("panel_subtitle_anchor_axis"),
                panel_id,
                None,
            )
            subtitle_gap_px_default = _panel_option_value(
                layout.get("panel_subtitle_gap_px"),
                panel_id,
                4.0,
            )
            subtitle_x_default = _panel_option_value(
                layout.get("panel_subtitle_x"),
                panel_id,
                0.01,
            )

            if isinstance(subtitle_cfg, str):
                subtitle_text = subtitle_cfg
                subtitle_color = _resolve_color("subtitle_default", colors, default=colors.get("text_main", "#202020"))
                subtitle_fontsize = _resolve_float(subtitle_fontsize_default, context=f"panel '{panel_id}' subtitle fontsize")
                subtitle_y = _resolve_float(subtitle_y_default, context=f"panel '{panel_id}' subtitle y")
                subtitle_x = _resolve_float(subtitle_x_default, context=f"panel '{panel_id}' subtitle x")
                subtitle_va = str(subtitle_va_default)
                subtitle_draw_last = bool(subtitle_draw_last_default)
                subtitle_anchor = str(subtitle_anchor_default).lower().strip()
                subtitle_anchor_axis = subtitle_anchor_axis_default
                subtitle_gap_px = _resolve_float(subtitle_gap_px_default, context=f"panel '{panel_id}' subtitle gap_px")
            elif isinstance(subtitle_cfg, dict):
                subtitle_text = str(subtitle_cfg.get("text", ""))
                subtitle_color = _resolve_color(
                    subtitle_cfg.get("color", subtitle_cfg.get("color_key", "subtitle_default")),
                    colors,
                    default=colors.get("text_main", "#202020"),
                )
                subtitle_fontsize = _resolve_float(
                    subtitle_cfg.get("fontsize", subtitle_fontsize_default),
                    context=f"panel '{panel_id}' subtitle fontsize",
                )
                subtitle_y = _resolve_float(
                    subtitle_cfg.get("y", subtitle_y_default),
                    context=f"panel '{panel_id}' subtitle y",
                )
                subtitle_x = _resolve_float(
                    subtitle_cfg.get("x", subtitle_x_default),
                    context=f"panel '{panel_id}' subtitle x",
                )
                subtitle_va = str(subtitle_cfg.get("va", subtitle_va_default))
                subtitle_draw_last = bool(
                    subtitle_cfg.get("draw_last", subtitle_draw_last_default)
                )
                subtitle_anchor = str(subtitle_cfg.get("anchor", subtitle_anchor_default)).lower().strip()
                subtitle_anchor_axis = subtitle_cfg.get("anchor_axis", subtitle_anchor_axis_default)
                subtitle_gap_px = _resolve_float(
                    subtitle_cfg.get("gap_px", subtitle_gap_px_default),
                    context=f"panel '{panel_id}' subtitle gap_px",
                )
            else:
                raise ValueError(f"panel '{panel_id}' subtitle must be string or dict.")

            if subtitle_text:
                if subtitle_anchor in {"axes", "axis"}:
                    _add_text(
                        ax=panel_axes_map["primary"],
                        x=subtitle_x,
                        y_coord=subtitle_y,
                        text=subtitle_text,
                        coords="axes",
                        draw_last=subtitle_draw_last,
                        ha="left",
                        va=subtitle_va,
                        fontsize=subtitle_fontsize,
                        color=subtitle_color,
                    )
                elif subtitle_anchor in {"top_ticks", "top_ticklabels"}:
                    pending_tick_anchored_subtitles.append(
                        {
                            "panel_id": panel_id,
                            "panel_axes_map": panel_axes_map,
                            "primary_ax": panel_axes_map["primary"],
                            "text": subtitle_text,
                            "x_axes": subtitle_x,
                            "ha": "left",
                            "va": subtitle_va,
                            "fontsize": subtitle_fontsize,
                            "color": subtitle_color,
                            "anchor_axis": subtitle_anchor_axis,
                            "gap_px": subtitle_gap_px,
                        }
                    )
                else:
                    raise ValueError(
                        f"panel '{panel_id}' subtitle anchor must be 'axes' or 'top_ticks', got {subtitle_anchor!r}."
                    )

        secondary_label_cfg = panel.get("secondary_label")
        if secondary_label_cfg:
            sec_text: str
            sec_color: Any
            sec_fontsize: float
            sec_y: float

            if isinstance(secondary_label_cfg, str):
                sec_text = secondary_label_cfg
                sec_color = _resolve_color("secondary_label", colors, default=colors.get("text_main", "#202020"))
                sec_fontsize = _resolve_float(layout.get("secondary_label_fontsize", layout.get("axis_label_fontsize", 12)), context=f"panel '{panel_id}' secondary label fontsize")
                sec_y = _resolve_float(layout.get("secondary_label_y", -0.08), context=f"panel '{panel_id}' secondary label y")
                sec_draw_last = bool(layout.get("secondary_label_draw_last", False))
            elif isinstance(secondary_label_cfg, dict):
                sec_text = str(secondary_label_cfg.get("text", ""))
                sec_color = _resolve_color(
                    secondary_label_cfg.get("color", secondary_label_cfg.get("color_key", "secondary_label")),
                    colors,
                    default=colors.get("text_main", "#202020"),
                )
                sec_fontsize = _resolve_float(
                    secondary_label_cfg.get("fontsize", layout.get("secondary_label_fontsize", layout.get("axis_label_fontsize", 12))),
                    context=f"panel '{panel_id}' secondary label fontsize",
                )
                sec_y = _resolve_float(
                    secondary_label_cfg.get("y", layout.get("secondary_label_y", -0.08)),
                    context=f"panel '{panel_id}' secondary label y",
                )
                sec_draw_last = bool(
                    secondary_label_cfg.get("draw_last", layout.get("secondary_label_draw_last", False))
                )
            else:
                raise ValueError(f"panel '{panel_id}' secondary_label must be string or dict.")

            if sec_text:
                _add_text(
                    ax=panel_axes_map["primary"],
                    x=0.5,
                    y_coord=sec_y,
                    text=sec_text,
                    coords="axes",
                    draw_last=sec_draw_last,
                    ha="center",
                    va="top",
                    fontsize=sec_fontsize,
                    color=sec_color,
                )

    axis_meta: dict[tuple[str, str], dict[str, float]] = {}

    for panel_ctx in panel_contexts:
        panel_id = panel_ctx["panel_id"]
        panel = panel_ctx["panel"]
        panel_axes_map = panel_ctx["axes"]

        ref_lines = panel.get("reference_lines", [])
        ref_line_by_axis: dict[str, list[float]] = {"primary": [], "secondary": []}
        for ref_line in ref_lines:
            axis_name = str(ref_line.get("axis", "primary"))
            ref_line_by_axis.setdefault(axis_name, []).append(_resolve_float(ref_line.get("x"), context=f"panel '{panel_id}' reference line x"))

        for axis_name, axis_cfg in panel["axes"].items():
            axis_key = (panel_id, axis_name)
            max_trace_value = max(axis_max_values.get(axis_key, [0.0]))
            ref_values = ref_line_by_axis.get(axis_name, [])
            max_ref_value = max(ref_values) if ref_values else 0.0
            max_value = max(max_trace_value, max_ref_value)

            axis_ax = panel_axes_map[axis_name]
            axis_meta[axis_key] = _prepare_axis(
                ax=axis_ax,
                axis_cfg=axis_cfg,
                panel_id=panel_id,
                axis_name=axis_name,
                max_value=max_value,
                layout=layout,
                colors=colors,
            )

    for panel_ctx in panel_contexts:
        panel_id = panel_ctx["panel_id"]
        panel = panel_ctx["panel"]
        panel_axes_map = panel_ctx["axes"]

        for ref_idx, ref_line in enumerate(panel.get("reference_lines", [])):
            axis_name = str(ref_line.get("axis", "primary"))
            axis_ax = panel_axes_map[axis_name]

            line_x = _resolve_float(ref_line.get("x"), context=f"panel '{panel_id}' reference_lines[{ref_idx}].x")
            line_color = _resolve_color(ref_line.get("color", "ratio_reference"), colors, default=colors.get("ratio_reference", "#666666"))
            line_width = _resolve_float(ref_line.get("linewidth", 1.0), context=f"panel '{panel_id}' reference_lines[{ref_idx}].linewidth")
            line_style = str(ref_line.get("linestyle", "--"))

            axis_ax.axvline(line_x, linestyle=line_style, color=line_color, linewidth=line_width)

            label_template = ref_line.get("label_template")
            if label_template:
                try:
                    label_text = str(label_template).format(x=line_x)
                except KeyError as exc:
                    raise ValueError(
                        f"panel '{panel_id}' reference line label_template has invalid field: {exc}."
                    ) from exc

                label_position = str(ref_line.get("label_position", "bottom")).lower().strip()
                if label_position not in {"top", "bottom"}:
                    raise ValueError(
                        f"panel '{panel_id}' reference_lines[{ref_idx}].label_position "
                        "must be 'top' or 'bottom'."
                    )

                label_pad_axes = _resolve_float(
                    ref_line.get("label_pad_axes", 0.02),
                    context=f"panel '{panel_id}' reference line label_pad_axes",
                )
                label_clamp_margin = _resolve_float(
                    ref_line.get("label_clamp_margin_axes", 0.01),
                    context=f"panel '{panel_id}' reference line label_clamp_margin_axes",
                )

                if "label_y" in ref_line:
                    label_y = _resolve_float(
                        ref_line.get("label_y"),
                        context=f"panel '{panel_id}' reference line label_y",
                    )
                else:
                    label_y = 1.0 - label_pad_axes if label_position == "top" else label_pad_axes

                label_y = max(label_clamp_margin, min(1.0 - label_clamp_margin, label_y))
                label_rotation = _resolve_float(ref_line.get("label_rotation", 90.0), context=f"panel '{panel_id}' reference line label_rotation")
                label_fontsize = _resolve_float(
                    ref_line.get("label_fontsize", layout.get("reference_label_fontsize", 10.0)),
                    context=f"panel '{panel_id}' reference line label_fontsize",
                )
                label_color = _resolve_color(
                    ref_line.get("label_color", "ratio_reference_text"),
                    colors,
                    default=colors.get("ratio_reference", "#666666"),
                )
                label_lock_within_axes = bool(ref_line.get("lock_within_axes", True))
                label_draw_last = bool(ref_line.get("draw_last", False))
                if label_lock_within_axes:
                    label_draw_last = False
                label_clip_on = bool(ref_line.get("clip_on", label_lock_within_axes))
                label_default_va = "top" if label_position == "top" else "bottom"
                label_default_ha = "right"

                _add_text(
                    ax=axis_ax,
                    x=line_x,
                    y_coord=label_y,
                    text=label_text,
                    coords="xaxis",
                    draw_last=label_draw_last,
                    rotation=label_rotation,
                    va=str(ref_line.get("label_va", label_default_va)),
                    ha=str(ref_line.get("label_ha", label_default_ha)),
                    fontsize=label_fontsize,
                    color=label_color,
                    clip_on=label_clip_on,
                    zorder=_resolve_float(
                        ref_line.get("zorder", layout.get("value_text_zorder", 8.0)),
                        context=f"panel '{panel_id}' reference line label zorder",
                    ),
                )

    for pending in pending_value_labels:
        panel_id = pending["panel_id"]
        axis_name = pending["axis_name"]
        trace_id = pending["trace_id"]
        ax = pending["ax"]
        values = pending["series"]
        value_label_cfg = pending["config"]

        axis_info = axis_meta[(panel_id, axis_name)]
        plot_limit = axis_info["plot_limit"]
        xlim_max = axis_info["xlim_max"]

        pad_ratio = _resolve_float(
            value_label_cfg.get("pad_ratio", _panel_option_value(layout.get("label_pad_ratio"), panel_id, 0.018)),
            context=f"panel '{panel_id}' trace '{trace_id}' value_label.pad_ratio",
        )
        right_margin_ratio = _resolve_float(
            value_label_cfg.get(
                "right_margin_ratio",
                _panel_option_value(layout.get("label_right_margin_ratio"), panel_id, 0.02),
            ),
            context=f"panel '{panel_id}' trace '{trace_id}' value_label.right_margin_ratio",
        )

        clip_on_default = _panel_option_value(layout.get("text_clip_on"), panel_id, True)
        clip_on = bool(value_label_cfg.get("clip_on", clip_on_default))

        draw_last = bool(value_label_cfg.get("draw_last", layout.get("draw_text_last", False)))

        label_color = _resolve_color(
            value_label_cfg.get("color", "value_label"),
            colors,
            default=colors.get("text_main", "#202020"),
        )

        label_fontsize = _resolve_float(
            value_label_cfg.get("fontsize", layout.get("value_label_fontsize", 10.0)),
            context=f"panel '{panel_id}' trace '{trace_id}' value_label.fontsize",
        )

        label_zorder = _resolve_float(
            value_label_cfg.get("zorder", layout.get("value_text_zorder", 8.0)),
            context=f"panel '{panel_id}' trace '{trace_id}' value_label.zorder",
        )

        template = str(value_label_cfg.get("template", "{value}"))
        include_row_context = bool(value_label_cfg.get("include_row_context", True))

        for row_idx, (y_val, value_raw) in enumerate(zip(y, values)):
            if pd.isna(value_raw):
                continue

            value = float(value_raw)
            text_x = min(value + (plot_limit * pad_ratio), xlim_max - (xlim_max * right_margin_ratio))

            context: dict[str, Any] = {}
            if include_row_context:
                context.update(plot_df.iloc[row_idx].to_dict())
            context.update(
                {
                    "value": value,
                    "value_pct": value * 100.0,
                    "x": value,
                }
            )
            context = {key: _label_context_value(item) for key, item in context.items()}

            try:
                label_text = template.format_map(context)
            except KeyError as exc:
                raise ValueError(
                    f"panel '{panel_id}' trace '{trace_id}' value_label.template uses missing field {exc}."
                ) from exc

            _add_text(
                ax=ax,
                x=float(text_x),
                y_coord=float(y_val),
                text=label_text,
                coords="data",
                draw_last=draw_last,
                va=str(value_label_cfg.get("va", "center")),
                ha=str(value_label_cfg.get("ha", "left")),
                fontsize=label_fontsize,
                color=label_color,
                clip_on=clip_on,
                zorder=label_zorder,
            )

            layout_debug_rows.append(
                {
                    "panel": panel_id,
                    "subfield_label": str(subfield_labels.iloc[row_idx]),
                    "text_x": float(text_x),
                    "axis_xlim_max": float(xlim_max),
                }
            )

    for idx, panel_ctx in enumerate(panel_contexts):
        panel_axes_map = panel_ctx["axes"]
        panel_id = panel_ctx["panel_id"]
        primary_ax = panel_axes_map["primary"]

        if idx == 0:
            primary_ax.tick_params(axis="y", labelcolor=subfield_label_color)
        else:
            primary_ax.tick_params(axis="y", labelleft=False)

        if "secondary" in panel_axes_map:
            panel_axes_map["secondary"].tick_params(
                axis="y",
                which="both",
                left=False,
                right=False,
                labelleft=False,
                labelright=False,
            )

    fig.subplots_adjust(**layout.get("subplots_adjust", {}))
    _autofit_subfield_left_margin(fig, subfield_ax=panel_axes_primary[0], layout=layout)

    for panel_ctx in panel_contexts:
        panel_id = panel_ctx["panel_id"]
        panel = panel_ctx["panel"]
        panel_axes_map = panel_ctx["axes"]

        for axis_name, axis_cfg in panel["axes"].items():
            _apply_xtick_label_density(
                fig=fig,
                ax=panel_axes_map[axis_name],
                panel_id=panel_id,
                axis_name=axis_name,
                axis_cfg=axis_cfg,
                layout=layout,
                colors=colors,
            )

    _draw_row_block_separators(
        fig=fig,
        panel_axes_primary=panel_axes_primary,
        subfield_ax=panel_axes_primary[0],
        y=y,
        layout=layout,
        colors=colors,
    )

    if pending_tick_anchored_subtitles:
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()

        for subtitle_item in pending_tick_anchored_subtitles:
            panel_axes_map = subtitle_item["panel_axes_map"]
            primary_ax = subtitle_item["primary_ax"]

            anchor_axis = subtitle_item.get("anchor_axis")
            if anchor_axis is None:
                anchor_axis_name = "secondary" if "secondary" in panel_axes_map else "primary"
            else:
                anchor_axis_name = str(anchor_axis).lower().strip()
            if anchor_axis_name not in panel_axes_map:
                anchor_axis_name = "secondary" if "secondary" in panel_axes_map else "primary"

            anchor_ax = panel_axes_map[anchor_axis_name]
            tick_labels = [
                tick_label
                for tick_label in anchor_ax.get_xticklabels()
                if tick_label.get_visible() and tick_label.get_text()
            ]

            if tick_labels:
                top_tick_label_y_disp = max(
                    tick_label.get_window_extent(renderer=renderer).y1
                    for tick_label in tick_labels
                )
            else:
                top_tick_label_y_disp = anchor_ax.transAxes.transform((0.0, 1.0))[1]

            y_disp = float(top_tick_label_y_disp) + float(subtitle_item["gap_px"])
            x_disp = primary_ax.transAxes.transform((float(subtitle_item["x_axes"]), 0.0))[0]
            x_fig, y_fig = fig.transFigure.inverted().transform((x_disp, y_disp))

            fig.text(
                x_fig,
                y_fig,
                str(subtitle_item["text"]),
                transform=fig.transFigure,
                ha=str(subtitle_item["ha"]),
                va=str(subtitle_item["va"]),
                fontsize=float(subtitle_item["fontsize"]),
                color=subtitle_item["color"],
                zorder=float(layout.get("deferred_text_zorder", 30.0)),
            )

    subfield_header = str(spec.get("subfield_header", "")).strip()
    if subfield_header and bool(layout.get("show_subfield_header", False)):
        subfield_header_x = float(layout.get("subfield_header_x", 0.15))
        subfield_header_y = float(layout.get("subfield_header_y", 0.93))
        subfield_header_ha = str(layout.get("subfield_header_ha", "center"))
        subfield_header_va = str(layout.get("subfield_header_va", "bottom"))
        subfield_header_fontsize = float(layout.get("subfield_header_fontsize", 12.0))
        subfield_header_coords = str(layout.get("subfield_header_coords", "figure")).lower().strip()

        if subfield_header_coords in {"axes", "axis"}:
            panel_axes_primary[0].text(
                subfield_header_x,
                subfield_header_y,
                subfield_header,
                transform=panel_axes_primary[0].transAxes,
                ha=subfield_header_ha,
                va=subfield_header_va,
                fontsize=subfield_header_fontsize,
                color=_resolve_color("text_main", colors, default="#202020"),
            )
        elif subfield_header_coords in {"figure", "fig"}:
            fig.text(
                subfield_header_x,
                subfield_header_y,
                subfield_header,
                ha=subfield_header_ha,
                va=subfield_header_va,
                fontsize=subfield_header_fontsize,
                color=_resolve_color("text_main", colors, default="#202020"),
            )
        else:
            raise ValueError(
                f"layout.subfield_header_coords must be 'figure' or 'axes', got {subfield_header_coords!r}."
            )

    legend_cfg = spec.get("legend", {})
    show_legend = bool(legend_cfg.get("show", layout.get("show_legend", False)))
    legend_mode = str(legend_cfg.get("mode", layout.get("legend_mode", "flat"))).lower().strip()
    if legend_mode not in {"flat", "panel_stacks"}:
        raise ValueError("legend mode must be 'flat' or 'panel_stacks'.")

    if show_legend and legend_entries:
        legend_patch_linewidth = float(
            legend_cfg.get("patch_linewidth", layout.get("legend_patch_linewidth", 0.9))
        )

        def _legend_patch(style_item: dict[str, Any]) -> mpatches.Patch:
            return mpatches.Patch(
                facecolor=style_item.get("facecolor"),
                edgecolor=style_item.get("edgecolor", style_item.get("facecolor")),
                linewidth=legend_patch_linewidth,
                alpha=style_item.get("alpha", 1.0),
                label=style_item["label"],
            )

        legend_frameon = bool(legend_cfg.get("frameon", False))
        legend_fontsize = float(legend_cfg.get("fontsize", layout.get("legend_fontsize", 9.0)))
        legend_handlelength = float(legend_cfg.get("handlelength", 0.95))
        legend_handleheight = float(legend_cfg.get("handleheight", 0.85))

        if legend_mode == "panel_stacks":
            panel_anchor_y = float(
                legend_cfg.get(
                    "panel_anchor_y",
                    layout.get("legend_panel_anchor_y", layout.get("legend_anchor", [0.02, 0.012])[1]),
                )
            )
            panel_anchor_x_offset = float(
                legend_cfg.get(
                    "panel_anchor_x_offset",
                    layout.get("legend_panel_anchor_x_offset", 0.0),
                )
            )
            panel_loc = str(legend_cfg.get("panel_loc", layout.get("legend_panel_loc", "lower left")))
            panel_ncol = int(legend_cfg.get("panel_ncol", 1))

            for panel_ctx, panel_ax in zip(panel_contexts, panel_axes_primary):
                panel_id = panel_ctx["panel_id"]
                panel_entries = legend_entries_by_panel.get(panel_id, [])
                if not panel_entries:
                    continue

                panel_entries_sorted = sorted(
                    panel_entries,
                    key=lambda item: (
                        0 if item.get("axis_position") == "top" else 1,
                        int(item.get("seq", 0)),
                    ),
                )
                panel_handles = [_legend_patch(item) for item in panel_entries_sorted]
                panel_x0 = panel_ax.get_position().x0 + panel_anchor_x_offset

                fig.legend(
                    handles=panel_handles,
                    loc=panel_loc,
                    bbox_to_anchor=(panel_x0, panel_anchor_y),
                    frameon=legend_frameon,
                    fontsize=legend_fontsize,
                    ncol=panel_ncol,
                    handlelength=legend_handlelength,
                    handleheight=legend_handleheight,
                )
        else:
            legend_handles = [_legend_patch(item) for item in legend_entries]
            fig.legend(
                handles=legend_handles,
                loc=str(legend_cfg.get("loc", "lower left")),
                bbox_to_anchor=tuple(legend_cfg.get("anchor", layout.get("legend_anchor", [0.02, 0.012]))),
                frameon=legend_frameon,
                fontsize=legend_fontsize,
                ncol=int(legend_cfg.get("ncol", 1)),
                handlelength=legend_handlelength,
                handleheight=legend_handleheight,
            )

    if deferred_text_specs:
        deferred_zorder = _resolve_float(
            layout.get("deferred_text_zorder", 30.0),
            context="layout.deferred_text_zorder",
        )
        for spec_item in deferred_text_specs:
            ax = spec_item["ax"]
            x = float(spec_item["x"])
            y_val = float(spec_item["y"])

            if spec_item["coords"] == "data":
                x_disp, y_disp = ax.transData.transform((x, y_val))
            elif spec_item["coords"] == "xaxis":
                x_disp, y_disp = ax.get_xaxis_transform().transform((x, y_val))
            else:
                x_disp, y_disp = ax.transAxes.transform((x, y_val))

            x_fig, y_fig = fig.transFigure.inverted().transform((x_disp, y_disp))

            kwargs = dict(spec_item["kwargs"])
            kwargs.pop("clip_on", None)
            kwargs.setdefault("zorder", deferred_zorder)

            fig.text(
                x_fig,
                y_fig,
                spec_item["text"],
                transform=fig.transFigure,
                **kwargs,
            )

    layout_debug_df = pd.DataFrame(
        layout_debug_rows,
        columns=["panel", "subfield_label", "text_x", "axis_xlim_max"],
    )
    return fig, layout_debug_df


def _legacy_cfg_to_figure_spec(cfg: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    cols = _required_dict(cfg.get("columns"), context="legacy cfg.columns")
    labels = _required_dict(cfg.get("labels"), context="legacy cfg.labels")
    colors = _required_dict(cfg.get("colors"), context="legacy cfg.colors")
    layout = _required_dict(cfg.get("layout"), context="legacy cfg.layout")
    fmt = _required_dict(cfg.get("format"), context="legacy cfg.format")

    count_mode = str(cfg.get("count_mode", "frac")).lower().strip()
    if count_mode not in {"full", "frac"}:
        raise ValueError(f"Unsupported legacy count_mode '{count_mode}'. Use 'full' or 'frac'.")

    width_ratios = list(layout.get("width_ratios", [1.2, 1.2, 1.0]))
    if len(width_ratios) != 3:
        raise ValueError("legacy layout.width_ratios must contain exactly 3 items.")

    share_value_decimals = int(fmt.get("share_value_decimals", 0))
    share_value_template = (
        f"{{value:.{share_value_decimals}%}}"
        if bool(fmt.get("share_value_as_percent", False))
        else f"{{value:.{share_value_decimals}f}}"
    )
    delta_decimals = int(fmt.get("delta_pp_decimals", 0))
    share_label_template = f"{share_value_template} ({{delta_oa_pp:+.{delta_decimals}f}}pp)"

    ratio_value_decimals = int(fmt.get("ratio_value_decimals", 2))
    ratio_label_template = f"{{value:.{ratio_value_decimals}f}}"

    figure_spec = {
        "subfield_column": cols["subfield_label"],
        "subfield_header": labels.get("subfield_header", ""),
        "legend": {
            "show": bool(layout.get("show_legend", False)),
            "anchor": layout.get("legend_anchor", [0.02, 0.012]),
            "fontsize": layout.get("legend_fontsize", 9.0),
            "mode": layout.get("legend_mode", "flat"),
            "panel_anchor_y": layout.get("legend_panel_anchor_y", 0.012),
            "panel_anchor_x_offset": layout.get("legend_panel_anchor_x_offset", 0.0),
            "panel_loc": layout.get("legend_panel_loc", "lower left"),
        },
        "panels": [
            {
                "id": "volume",
                "width_ratio": width_ratios[0],
                "axes": {
                    "primary": {
                        "label": labels.get("x_volume_primary", ""),
                        "tick_mode": "count_auto",
                        "count_is_full": bool(count_mode == "full"),
                        "xpad_factor": _panel_option_value(layout.get("xpad_factor"), "volume", 1.02),
                        "gutter_ratio": _panel_option_value(layout.get("gutter_ratio"), "volume", 0.10),
                        "extra_right_ratio": _panel_option_value(layout.get("x_extra_right_ratio"), "volume", 0.0),
                        "position": "bottom",
                        "show_grid": True,
                    }
                },
                "subtitle": {
                    "text": labels.get("subtitle_volume", ""),
                    "color": "subtitle_volume",
                },
                "secondary_label": {
                    "text": labels.get("x_volume_secondary", ""),
                    "y": layout.get("secondary_xlabel_y", -0.08),
                    "fontsize": layout.get("axis_label_fontsize", 12),
                    "color": "secondary_volume",
                },
                "traces": [
                    {
                        "id": "volume_full",
                        "type": "barh",
                        "axis": "primary",
                        "column": cols["volume_full"],
                        "color": "volume_full",
                        "edgecolor": "volume_full_edge",
                        "alpha": colors.get("volume_full_alpha", 0.95),
                        "height": _required_dict(layout.get("bar_heights", {}), context="legacy layout.bar_heights").get("volume_full", 0.72),
                        "legend_label": labels.get("legend_volume_full", ""),
                    },
                    {
                        "id": "volume_frac",
                        "type": "barh",
                        "axis": "primary",
                        "column": cols["volume_frac"],
                        "color": "volume_frac",
                        "edgecolor": "volume_frac_edge",
                        "alpha": colors.get("volume_frac_alpha", 0.78),
                        "height": _required_dict(layout.get("bar_heights", {}), context="legacy layout.bar_heights").get("volume_frac", 0.44),
                        "legend_label": labels.get("legend_volume_frac", ""),
                    },
                ],
            },
            {
                "id": "share",
                "width_ratio": width_ratios[1],
                "axes": {
                    "primary": {
                        "label": labels.get("x_share_primary", ""),
                        "tick_mode": "step",
                        "tick_step": fmt.get("share_tick_step", 0.1),
                        "tick_decimals": fmt.get("share_tick_decimals", 0),
                        "tick_as_percent": bool(fmt.get("share_tick_as_percent", False)),
                        "xpad_factor": _panel_option_value(layout.get("xpad_factor"), "share", 1.02),
                        "gutter_ratio": _panel_option_value(layout.get("gutter_ratio"), "share", 0.10),
                        "extra_right_ratio": _panel_option_value(layout.get("x_extra_right_ratio"), "share", 0.0),
                        "position": "bottom",
                        "show_grid": True,
                    }
                },
                "subtitle": {
                    "text": labels.get("subtitle_share", ""),
                    "color": "subtitle_share",
                },
                "secondary_label": {
                    "text": labels.get("x_share_secondary", ""),
                    "y": layout.get("secondary_xlabel_y", -0.08),
                    "fontsize": layout.get("field_label_fontsize", layout.get("axis_label_fontsize", 12)),
                    "color": "secondary_share",
                },
                "traces": [
                    {
                        "id": "share_field",
                        "type": "barh",
                        "axis": "primary",
                        "column": cols["share_field"],
                        "color": "share_field",
                        "edgecolor": "share_field_edge",
                        "alpha": colors.get("share_field_alpha", 0.92),
                        "height": _required_dict(layout.get("bar_heights", {}), context="legacy layout.bar_heights").get("share_field", 0.66),
                        "legend_label": labels.get("legend_share_field", ""),
                    },
                    {
                        "id": "share_inst",
                        "type": "barh",
                        "axis": "primary",
                        "column": cols["share_inst"],
                        "color": "share_inst",
                        "edgecolor": "share_inst_edge",
                        "alpha": colors.get("share_inst_alpha", 0.72),
                        "height": _required_dict(layout.get("bar_heights", {}), context="legacy layout.bar_heights").get("share_inst", 0.44),
                        "legend_label": labels.get("legend_share_inst", ""),
                        "value_label": {
                            "enabled": True,
                            "template": share_label_template,
                            "pad_ratio": _panel_option_value(layout.get("label_pad_ratio"), "share", 0.018),
                            "right_margin_ratio": _panel_option_value(layout.get("label_right_margin_ratio"), "share", 0.02),
                            "clip_on": _panel_option_value(layout.get("text_clip_on"), "share", True),
                            "draw_last": bool(layout.get("draw_text_last", False)),
                            "fontsize": layout.get("value_label_fontsize", 10),
                            "color": "value_label",
                        },
                    },
                ],
            },
            {
                "id": "ratio",
                "width_ratio": width_ratios[2],
                "axes": {
                    "primary": {
                        "label": labels.get("x_ratio", ""),
                        "tick_mode": "step",
                        "tick_step": fmt.get("ratio_tick_step", 0.5),
                        "tick_decimals": fmt.get("ratio_tick_decimals", 2),
                        "tick_as_percent": False,
                        "xpad_factor": _panel_option_value(layout.get("xpad_factor"), "ratio", 1.02),
                        "gutter_ratio": _panel_option_value(layout.get("gutter_ratio"), "ratio", 0.10),
                        "extra_right_ratio": _panel_option_value(layout.get("x_extra_right_ratio"), "ratio", 0.0),
                        "min_plot_limit": layout.get("ratio_min_plot_limit", 1.05),
                        "position": "bottom",
                        "show_grid": True,
                    }
                },
                "traces": [
                    {
                        "id": "ratio",
                        "type": "barh",
                        "axis": "primary",
                        "column": cols["ratio"],
                        "color": "ratio",
                        "edgecolor": "ratio_edge",
                        "alpha": colors.get("ratio_alpha", 0.90),
                        "height": _required_dict(layout.get("bar_heights", {}), context="legacy layout.bar_heights").get("ratio", 0.66),
                        "legend_label": labels.get("legend_ratio", ""),
                        "value_label": {
                            "enabled": True,
                            "template": ratio_label_template,
                            "pad_ratio": _panel_option_value(layout.get("label_pad_ratio"), "ratio", 0.018),
                            "right_margin_ratio": _panel_option_value(layout.get("label_right_margin_ratio"), "ratio", 0.02),
                            "clip_on": _panel_option_value(layout.get("text_clip_on"), "ratio", True),
                            "draw_last": bool(layout.get("draw_text_last", False)),
                            "fontsize": layout.get("value_label_fontsize", 10),
                            "color": "value_label",
                        },
                    },
                ],
                "reference_lines": [
                    {
                        "axis": "primary",
                        "x": layout.get("ratio_reference", 1.0),
                        "linestyle": "--",
                        "linewidth": layout.get("ratio_reference_linewidth", 1.0),
                        "color": "ratio_reference",
                        "label_template": "{x:.2f}",
                        "label_position": layout.get("ratio_reference_text_position", "bottom"),
                        "label_pad_axes": layout.get("ratio_reference_text_pad_axes", 0.02),
                        "label_clamp_margin_axes": layout.get("ratio_reference_text_clamp_margin_axes", 0.01),
                        "label_rotation": layout.get("ratio_reference_text_rotation", 90),
                        "label_fontsize": layout.get(
                            "ratio_reference_text_fontsize",
                            layout.get("reference_label_fontsize", 10),
                        ),
                        "label_color": "ratio_reference_text",
                        "draw_last": bool(layout.get("ratio_reference_text_draw_last", False)),
                        "lock_within_axes": bool(layout.get("ratio_reference_text_lock_within_axes", True)),
                    }
                ],
            },
        ],
    }

    style_overrides = {
        "colors": deepcopy(colors),
        "layout": deepcopy(layout),
        "messages": deepcopy(cfg.get("messages", {})),
    }
    return figure_spec, style_overrides


def build_subfield_profile_figure(
    plot_df: pd.DataFrame,
    cfg: dict[str, Any],
) -> tuple[plt.Figure, pd.DataFrame]:
    """
    Backward-compatible wrapper for the legacy 3-panel subfield profile config.

    Legacy `cfg` is translated into the generic panel spec and rendered by
    `build_panel_figure`.
    """
    figure_spec, style_overrides = _legacy_cfg_to_figure_spec(cfg)
    return build_panel_figure(
        plot_df,
        figure_spec,
        style_preset="subfield_profile_v1",
        style_overrides=style_overrides,
    )
