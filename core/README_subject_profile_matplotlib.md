# Subject Profile Matplotlib Renderer

Canonical documentation for `core/subject_profile_matplotlib.py`.

This module provides two APIs:

1. `build_panel_figure(plot_df, figure_spec, style_preset="subject_profile_v1", style_overrides=None)`
2. `build_subject_profile_figure(plot_df, cfg)` (legacy compatibility wrapper)

---

## 1) Generic API (`build_panel_figure`)

### Purpose
Render a role-free, modular horizontal panel figure with:

- 1 row, **2-4 panels**
- shared y categories
- per-panel width ratio
- per-panel x-axis config
- optional dual x-axis (`primary` + `secondary`)
- bar traces (`barh`) in v1
- optional value labels per trace
- optional vertical reference lines with labels
- optional deferred text layer (`draw_text_last`)

### Function signature

```python
fig, layout_debug_df = build_panel_figure(
    plot_df,
    figure_spec,
    style_preset="subject_profile_v1",
    style_overrides=None,
)
```

### Inputs

- `plot_df`: pandas DataFrame with all referenced columns.
- `figure_spec`: panel grammar (see below).
- `style_preset`: `"subject_profile_v1"`.
- `style_overrides`: dict merged over preset.

### Output

- `fig`: Matplotlib figure
- `layout_debug_df`: DataFrame with columns:
  - `panel`
  - `subject_label`
  - `text_x`
  - `axis_xlim_max`

---

## 2) Figure Spec Grammar (v1)

### Top-level keys

- `subject_column` (str, required): y-label source column.
- `panels` (list, required): 2-4 panel specs.
- `subject_header` (str, optional): figure-level subject header text.
- `legend` (dict, optional): figure-level legend options (`mode="flat"` or `mode="panel_stacks"`).
- `messages` (dict, optional): message overrides (`empty`).

### Panel spec

Required keys:

- `id` (str, unique)
- `width_ratio` (float > 0)
- `axes` (dict): must include `primary`; optional `secondary`
- `traces` (list): at least one trace

Optional keys:

- `subtitle` (str or dict)
- `secondary_label` (str or dict)
- `reference_lines` (list)

### Axis spec (`axes.primary` / `axes.secondary`)

Required in each axis object:

- `tick_mode`: `"step"` or `"count_auto"`

When `tick_mode="step"`, required:

- `tick_step` (> 0)

Optional keys:

- `label`
- `show_label` (bool, default from `layout.show_primary_axis_labels` / `layout.show_secondary_axis_labels`, fallback `layout.show_axis_labels`)
- `tick_decimals`
- `tick_as_percent`
- `count_is_full` (for `count_auto`)
- `xpad_factor`
- `gutter_ratio`
- `extra_right_ratio`
- `min_plot_limit`
- `label_pad`
- `label_fontsize`
- `position`: `"bottom"` or `"top"`
- `show_grid`
- `tick_rotation`
- `tick_ha`
- `tick_rotation_mode`
- `tick_pad`
- `auto_reduce_tick_labels` (bool): auto-hide some tick labels to avoid overlap
- `tick_label_every_n` (int): show every n-th tick label
- `tick_label_min_gap_px` (float): minimum pixel gap between visible tick labels in auto mode
- `keep_first_last_tick_labels` (bool): keep endpoints visible while thinning
- `emphasize_labeled_ticks` (bool): draw darker/longer tick marks where labels are shown
- `tick_mark_color` (literal or color-key)
- `tick_mark_width` (float)
- `tick_mark_length` (float)
- `tick_mark_direction` (`"in" | "out" | "inout"`)
- `tick_mark_hide_unlabeled` (bool)
- `tick_mark_unlabeled_alpha` (float)
- `tick_mark_unlabeled_length_ratio` (float)
- `emphasize_labeled_gridlines` (bool): darken grid lines that correspond to visible tick labels
- `grid_labeled_color` (literal or color-key)
- `grid_labeled_linewidth` (float)
- `grid_labeled_alpha` (float)
- `grid_unlabeled_color` (literal or color-key)
- `grid_unlabeled_linewidth` (float)
- `grid_unlabeled_alpha` (float)

Note: `panel.secondary_label` is separate from axis titles. Hiding axis labels does not automatically hide legend entries.
Note: grid lines extend across the full panel x-range (including right label gutter); tick labels remain suppressed beyond the main plotted limit.

### Trace spec (v1)

Required:

- `type`: must be `"barh"`
- `column`: numeric column in `plot_df`

Optional:

- `id`
- `axis`: `"primary"` or `"secondary"` (default `primary`)
- `color` (literal or color-key)
- `edgecolor` (literal or color-key)
- `alpha`
- `height`
- `zorder`
- `legend_label`
- `value_label` (dict)

### Value label spec (`trace.value_label`)

Important keys:

- `enabled` (bool)
- `template` (default `"{value}"`)
- `pad_ratio`
- `right_margin_ratio`
- `clip_on`
- `draw_last`
- `fontsize`
- `color` (literal or color-key)
- `zorder`
- `include_row_context` (default `True`)

Template fields:

- Always available: `value`, `value_pct`, `x`
- If `include_row_context=True`: all row columns from `plot_df`

### Reference line spec (`panel.reference_lines[]`)

Required:

- `x`

Optional:

- `axis` (`primary` default)
- `linestyle`
- `linewidth`
- `color`
- `label_template` (e.g. `"{x:.2f}"`)
- `label_y`
- `label_position` (`"bottom"` or `"top"`): convenient anchor for inside-axis placement
- `label_pad_axes` (axes coords; default `0.02`)
- `label_clamp_margin_axes` (axes coords; default `0.01`)
- `label_rotation`
- `label_fontsize`
- `label_color`
- `label_ha`
- `label_va`
- `draw_last`
- `lock_within_axes` (bool): keep label clipped and inside axis by forcing non-deferred draw
- `clip_on`
- `zorder`

---

## 3) Style Preset and Overrides

`style_preset="subject_profile_v1"` contains defaults for:

- colors
- layout
- messages

`style_overrides` can override any nested key.

### Common layout keys

- figure sizing: `fig_width`, `min_fig_height`, `height_base`, `height_per_row`
- y spacing: `row_step`, `y_inner_pad`, `y_inner_pad_top`, `y_inner_pad_bottom`
- subject labels: `subject_fontsize`, `subject_label_linespacing`, `subject_wrap_width`, `subject_wrap_max_lines`, `subject_wrap_break_long_words`
- subject fit: `subject_autofit_left`, `subject_autofit_pad`, `subject_autofit_left_min`, `subject_autofit_left_max`
- x sizing defaults: `xpad_factor`, `gutter_ratio`, `x_extra_right_ratio`
- value label defaults: `label_pad_ratio`, `label_right_margin_ratio`, `text_clip_on`
- text layering: `draw_text_last`, `deferred_text_zorder`, `value_text_zorder`
- x ticks: `x_tick_rotation`, `x_tick_ha`, `x_tick_rotation_mode`, `x_tick_pad`, `auto_reduce_x_tick_labels`, `x_tick_label_min_gap_px`, `x_tick_label_every_n`, `keep_first_last_tick_labels`, `emphasize_labeled_x_ticks`, `x_tick_mark_color`, `x_tick_mark_width`, `x_tick_mark_length`, `x_tick_mark_direction`, `x_tick_mark_hide_unlabeled`, `x_tick_mark_unlabeled_alpha`, `x_tick_mark_unlabeled_length_ratio`, `emphasize_labeled_gridlines`, `x_grid_labeled_color`, `x_grid_labeled_linewidth`, `x_grid_labeled_alpha`, `x_grid_unlabeled_color`, `x_grid_unlabeled_linewidth`, `x_grid_unlabeled_alpha`
- axis labels: `show_axis_labels`, `show_primary_axis_labels`, `show_secondary_axis_labels`, `axis_label_fontsize`, `axis_label_pad`, `axis_label_pad_by_panel`
- subtitles/secondary labels: `panel_subtitle_y`, `panel_subtitle_va`, `panel_subtitle_fontsize`, `panel_subtitle_draw_last`, `secondary_label_y`, `secondary_label_fontsize`, `secondary_label_draw_last`
- row separators: `row_block_separator_every`, `row_block_separator_color`, `row_block_separator_linewidth`, `row_block_separator_alpha`, `row_block_separator_linestyle`, `row_block_separator_zorder`, `row_block_separator_include_subject_labels`, `row_block_separator_left_pad`, `row_block_separator_right_pad`
- header/legend: `show_subject_header`, `subject_header_x`, `subject_header_y`, `show_legend`, `legend_anchor`, `legend_fontsize`, `legend_mode`, `legend_panel_anchor_y`, `legend_panel_anchor_x_offset`, `legend_panel_loc`, `legend_patch_linewidth`
- frame: `subplots_adjust`

### Common color keys

- base: `axis`, `grid`, `grid_labeled`, `tick_label`, `tick_mark`, `subject_label`, `text_main`, `value_label`
- subtitle/secondary: `subtitle_default`, `secondary_label`
- reference: `ratio_reference`, `ratio_reference_text`
- plus any domain-specific keys used by traces (e.g. `volume_full`, `share_inst`, `ratio`)

---

## 4) Label Fit and Legend Modes

### Subject labels that overflow left boundary

Use wrapping and left-margin autofit together:

- `layout.subject_wrap_width`: character width before wrapping (set `None`/`0` to disable)
- `layout.subject_wrap_max_lines`: max wrapped lines (overflow gets ellipsis)
- `layout.subject_wrap_break_long_words`: break long words when needed
- `layout.subject_autofit_left`: when `True`, renderer expands `subplots_adjust.left` only if labels would spill out
- `layout.subject_autofit_pad`: target left padding in figure coordinates
- `layout.subject_autofit_left_max`: safety cap for maximum left margin expansion

### Legend layouts

`figure_spec.legend.mode` supports:

- `"flat"`: single combined legend (existing behavior)
- `"panel_stacks"`: one stacked legend per panel, arranged left-to-right by panel position

In `panel_stacks`, entries are ordered by axis position so traces on a top axis are listed above traces on a bottom axis.
Legend patches inherit both trace face color and edge color so outline encodings stay visible.

For `"panel_stacks"` use:

- `legend.panel_anchor_y`
- `legend.panel_anchor_x_offset`
- `legend.panel_loc`

The same keys can be set via layout defaults:

- `layout.legend_mode`
- `layout.legend_panel_anchor_y`
- `layout.legend_panel_anchor_x_offset`
- `layout.legend_panel_loc`

---

## 5) Strict Validation (Fail-fast)

Before rendering, the engine validates:

- missing columns
- duplicate panel ids
- invalid trace axis references
- non-coercible numeric columns for trace data
- invalid axis config (`tick_mode`, missing `tick_step`, invalid position)
- secondary axis declared but unused
- invalid template fields in value labels

Validation errors raise `ValueError` with panel/trace/axis context.

---

## 6) Legacy Wrapper (`build_subject_profile_figure`)

`build_subject_profile_figure(plot_df, cfg)` remains available.

It translates legacy 3-panel config (`columns`, `labels`, `colors`, `format`, `layout`) into the generic `figure_spec` and calls `build_panel_figure`.

Compatibility goals:

- preserve classic volume/share/ratio rendering behavior
- preserve layout controls and color overrides
- preserve `layout_debug_df` columns

---

## 7) Minimal Example

```python
figure_spec = {
    "subject_column": "subject_label",
    "panels": [
        {
            "id": "p1",
            "width_ratio": 1.0,
            "axes": {
                "primary": {
                    "label": "P",
                    "tick_mode": "count_auto",
                    "count_is_full": True,
                }
            },
            "traces": [
                {
                    "id": "full",
                    "type": "barh",
                    "column": "P_FULL",
                    "color": "#d9dee8",
                    "edgecolor": "#d9dee8",
                    "alpha": 1.0,
                    "height": 0.70,
                },
                {
                    "id": "frac",
                    "type": "barh",
                    "column": "P_FRAC",
                    "color": "#215CAF",
                    "edgecolor": "#215CAF",
                    "alpha": 0.8,
                    "height": 0.45,
                },
            ],
        },
        {
            "id": "p2",
            "width_ratio": 1.0,
            "axes": {
                "primary": {
                    "label": "PP[OA]",
                    "tick_mode": "step",
                    "tick_step": 0.10,
                    "tick_decimals": 0,
                    "tick_as_percent": True,
                }
            },
            "traces": [
                {
                    "id": "share",
                    "type": "barh",
                    "column": "OA_PP_INST",
                    "color": "#215CAF",
                    "edgecolor": "#215CAF",
                    "alpha": 0.8,
                    "height": 0.45,
                    "value_label": {
                        "enabled": True,
                        "template": "{value:.0%}",
                    },
                }
            ],
        },
    ],
}
```

---

## 8) Advanced Dual-axis Example

```python
panel_dual = {
    "id": "impact_dual",
    "width_ratio": 1.0,
    "axes": {
        "primary": {
            "label": "MNCS",
            "tick_mode": "step",
            "tick_step": 0.20,
            "tick_decimals": 2,
            "position": "bottom",
        },
        "secondary": {
            "label": "PP[Top10]",
            "tick_mode": "step",
            "tick_step": 0.05,
            "tick_decimals": 0,
            "tick_as_percent": True,
            "position": "top",
        },
    },
    "traces": [
        {"id": "mncs", "type": "barh", "axis": "primary", "column": "MNCS", "color": "#4f81bd", "edgecolor": "#4f81bd", "alpha": 0.85, "height": 0.56},
        {"id": "pptop10", "type": "barh", "axis": "secondary", "column": "PP_TOP10", "color": "#9bbb59", "edgecolor": "#9bbb59", "alpha": 0.45, "height": 0.36},
    ],
}
```

---

## 8) Migration Notes

For new assets, prefer `build_panel_figure` directly with compact panel specs and asset-side precomputed derived columns.

For existing assets, keep the wrapper until they are explicitly migrated.
