import pandas as pd

from assets.collab_table_style import CHANGE_PP_NEGATIVE_COLOR, CHANGE_PP_POSITIVE_COLOR, ROW_BACKGROUND_COLOR_EVEN, ROW_BACKGROUND_COLOR_ODD, SPARKLINE_HIGHEST_POINT_COLOR, SPARKLINE_LOWEST_POINT_COLOR
from utility import shorten_country_name, shorten_institution_name

SPARKLINE_WIDTH_MM = 18.0
SPARKLINE_HEIGHT_MM = 4.0
SPARKLINE_LINE_WIDTH_PT = 0.45
SPARKLINE_LINE_COLOR = "#215caf"
SPARKLINE_FILL_COLOR = "black, fill opacity=0"
SPARKLINE_VERTICAL_SHIFT_EX = -0.9
SPARKLINE_POINT_RADIUS_PT = 1.1
CHANGE_PP_BAR_CELL_WIDTH_MM = 22.0
CHANGE_PP_BAR_LABEL_WIDTH_MM = 9.8
CHANGE_PP_BAR_GAP_MM = 0.8
CHANGE_PP_BAR_HEIGHT_MM = 1.9
CHANGE_PP_BAR_TRACK_MARGIN_MM = 0.30
CHANGE_PP_BAR_FILL_OPACITY = 0.80
CHANGE_PP_BAR_AXIS_COLOR = "black!45"
CHANGE_PP_BAR_ZERO_COLOR = "black!20"
CHANGE_PP_TIKZ_RAISEBOX_EX = -0.9
DEFAULT_FRAC_LABEL = r"\ensuremath{\mathrm{P}_{\mathrm{frac}}}"
TABLE_COLUMN_SPEC_WITH_CC = {"name": "l", "cc": "c", "pfrac": "r", "intensity": "r", "change": "C{2.35cm}", "trend": "c"}
TABLE_COLUMN_SPEC_NO_CC = {"name": "l", "pfrac": "r", "intensity": "r", "change": "C{2.35cm}", "trend": "c"}


def tex_escape(text: str) -> str:
    return str(text).replace("\\", r"\textbackslash{}").replace("{", r"\{").replace("}", r"\}").replace("_", r"\_").replace("%", r"\%").replace("&", r"\&").replace("#", r"\#")


def _normalize_hex_color(color: str) -> str | None:
    raw = str(color).strip().lstrip("#")
    if len(raw) == 3 and all(ch in "0123456789abcdefABCDEF" for ch in raw):
        raw = "".join(ch * 2 for ch in raw)
    return raw.upper() if len(raw) == 6 and all(ch in "0123456789abcdefABCDEF" for ch in raw) else None


def _hex_to_rgb_components(hex_color: str) -> tuple[int, int, int]:
    return int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)


def build_rowcolor_command(color: str) -> str:
    hex_color = _normalize_hex_color(color)
    return rf"\rowcolor[HTML]{{{hex_color}}} " if hex_color else rf"\rowcolor{{{color}}} "


def _tikz_color(prefix: str, color: str) -> str:
    hex_color = _normalize_hex_color(color)
    if not hex_color:
        return f"{prefix}=none" if not str(color).strip() else color
    red, green, blue = _hex_to_rgb_components(hex_color)
    return f"{prefix}={{rgb,255:red,{red};green,{green};blue,{blue}}}"


def build_textcolor_command(text: str, color: str) -> str:
    hex_color = _normalize_hex_color(color)
    return rf"\textcolor[HTML]{{{hex_color}}}{{{text}}}" if hex_color else rf"\textcolor{{{color}}}{{{text}}}"


def fmt_frac(value, digits: int = 0) -> str:
    return r"\textit{n/a}" if value is None or pd.isna(value) else f"{float(value):,.{digits}f}".replace(",", "{,}")


def fmt_pct(value, digits: int = 1) -> str:
    if value is None or pd.isna(value):
        return r"\textit{n/a}"
    pct = f"{100.0 * float(value):.{digits}f}".rstrip("0").rstrip(".")
    return f"{pct}\\%"


def build_change_pp_cell(value, digits: int = 2, max_abs: float = 0.0) -> str:
    if value is None or pd.isna(value):
        return r"\textit{n/a}"
    numeric_value = float(value)
    label = f"{numeric_value:+.{digits}f}pp"
    if numeric_value > 0:
        label = build_textcolor_command(label, CHANGE_PP_POSITIVE_COLOR)
    elif numeric_value < 0:
        label = build_textcolor_command(label, CHANGE_PP_NEGATIVE_COLOR)
    if max_abs <= 0:
        return label
    bar_area_width = max(0.0, CHANGE_PP_BAR_CELL_WIDTH_MM - CHANGE_PP_BAR_LABEL_WIDTH_MM - CHANGE_PP_BAR_GAP_MM)
    track_half = max(0.0, bar_area_width / 2.0 - CHANGE_PP_BAR_TRACK_MARGIN_MM)
    if track_half <= 0:
        return label
    bar_color = CHANGE_PP_BAR_ZERO_COLOR
    if numeric_value > 0:
        bar_color = CHANGE_PP_POSITIVE_COLOR
    elif numeric_value < 0:
        bar_color = CHANGE_PP_NEGATIVE_COLOR
    bar_length = min(abs(numeric_value) / max_abs, 1.0) * track_half
    center_x = bar_area_width / 2.0
    label_x = bar_area_width + CHANGE_PP_BAR_GAP_MM + CHANGE_PP_BAR_LABEL_WIDTH_MM / 2.0
    half_h = CHANGE_PP_BAR_HEIGHT_MM / 2.0
    mid_y = half_h + 0.30
    cell_height = max(CHANGE_PP_BAR_HEIGHT_MM + 0.60, 2.0 * mid_y)
    y0 = mid_y - half_h
    y1 = mid_y + half_h
    bar = ""
    if bar_length > 1e-12:
        x0, x1 = (center_x, center_x + bar_length) if numeric_value >= 0 else (center_x - bar_length, center_x)
        bar = rf"\fill[{_tikz_color('fill', bar_color)}, fill opacity={CHANGE_PP_BAR_FILL_OPACITY}] ({x0:.3f},{y0:.3f}) rectangle ({x1:.3f},{y1:.3f});"
    tikz = rf"\begin{{tikzpicture}}[x=1mm,y=1mm,baseline=-0.55ex]\path[use as bounding box] (0,0) rectangle ({CHANGE_PP_BAR_CELL_WIDTH_MM:.3f},{cell_height:.3f});\draw[{_tikz_color('draw', CHANGE_PP_BAR_AXIS_COLOR)}, line width=0.22pt] ({center_x:.3f},0.12) -- ({center_x:.3f},{cell_height - 0.12:.3f});" + bar + rf"\node[anchor=center] at ({label_x:.3f},{mid_y:.3f}) {{{label}}};\end{{tikzpicture}}"
    return rf"\raisebox{{{CHANGE_PP_TIKZ_RAISEBOX_EX}ex}}{{{tikz}}}"


def build_sparkline_cell(row: pd.Series, years: list[int]) -> str:
    values = []
    for year in years:
        value = pd.to_numeric(pd.Series([row.get(f"frac_y_{year}", 0.0)]), errors="coerce").fillna(0.0).iloc[0]
        values.append(float(value))
    if len(values) < 2:
        return r"\textit{n/a}"
    max_value = max(values)
    normalized = [0.0 for _ in values] if max_value <= 0 else [max(v, 0.0) / max_value for v in values]
    step = 1.0 / (len(normalized) - 1)
    coords = " -- ".join(f"({idx * step:.4f},{value:.4f})" for idx, value in enumerate(normalized))
    max_idx, min_idx = values.index(max(values)), values.index(min(values))
    max_x, max_y = max_idx * step, normalized[max_idx]
    min_x, min_y = min_idx * step, normalized[min_idx]
    tikz = rf"\begin{{tikzpicture}}[x={SPARKLINE_WIDTH_MM}mm,y={SPARKLINE_HEIGHT_MM}mm,baseline=(current bounding box.south)]\fill[{_tikz_color('fill', SPARKLINE_FILL_COLOR)}] (0,0) -- {coords} -- (1,0) -- cycle;\draw[{_tikz_color('draw', SPARKLINE_LINE_COLOR)}, line width={SPARKLINE_LINE_WIDTH_PT}pt] {coords};\filldraw[{_tikz_color('fill', SPARKLINE_HIGHEST_POINT_COLOR)},{_tikz_color('draw', SPARKLINE_HIGHEST_POINT_COLOR)}] ({max_x:.4f},{max_y:.4f}) circle[radius={SPARKLINE_POINT_RADIUS_PT}pt];\filldraw[{_tikz_color('fill', SPARKLINE_LOWEST_POINT_COLOR)},{_tikz_color('draw', SPARKLINE_LOWEST_POINT_COLOR)}] ({min_x:.4f},{min_y:.4f}) circle[radius={SPARKLINE_POINT_RADIUS_PT}pt];\end{{tikzpicture}}"
    return rf"\raisebox{{{SPARKLINE_VERTICAL_SHIFT_EX}ex}}{{{tikz}}}"


def build_grouped_header_lines(headers: list[str], display_tokens: list[str], *, first_group_label: str) -> list[str]:
    group_ids = ["first" if token in {"name", "cc"} else "volume" for token in display_tokens]
    runs: list[tuple[str, int, int]] = []
    run_start, current_group = 1, group_ids[0]
    for col_idx, group in enumerate(group_ids[1:], start=2):
        if group != current_group:
            runs.append((current_group, run_start, col_idx - 1))
            run_start, current_group = col_idx, group
    runs.append((current_group, run_start, len(group_ids)))
    labels = {"first": first_group_label, "volume": "Volume"}
    top = " & ".join(rf"\multicolumn{{{end - start + 1}}}{{c}}{{\textbf{{{labels[group]}}}}}" for group, start, end in runs)
    rules = " ".join(rf"\cmidrule(lr){{{start}-{end}}}" for _, start, end in runs)
    return [r"  " + top + r" \\", r"  " + rules, r"  " + " & ".join(headers) + r" \\"]


def add_share_change_columns(df: pd.DataFrame, *, frac_col: str, recent_col: str, baseline_col: str, years: list[int], share_col: str = "intensity_share", recent_share_col: str = "share_recent", baseline_share_col: str = "share_baseline", change_col: str = "intensity_change_pp") -> pd.DataFrame:
    out = df.copy()
    numeric_cols = [frac_col, recent_col, baseline_col, *[f"frac_y_{year}" for year in years if f"frac_y_{year}" in out.columns]]
    out[numeric_cols] = out[numeric_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    total_full, total_recent, total_baseline = float(out[frac_col].sum()), float(out[recent_col].sum()), float(out[baseline_col].sum())
    out[share_col] = out[frac_col] / total_full if total_full > 0 else 0.0
    out[recent_share_col] = out[recent_col] / total_recent if total_recent > 0 else 0.0
    out[baseline_share_col] = out[baseline_col] / total_baseline if total_baseline > 0 else 0.0
    out[change_col] = (out[recent_share_col] - out[baseline_share_col]) * 100.0 if total_baseline > 0 else pd.NA
    return out


def build_citing_table_tex(df: pd.DataFrame, *, years: list[int], recent_window: int, first_group_label: str, entity_header: str, entity_kind: str, frac_col: str, share_col: str = "intensity_share", change_col: str = "intensity_change_pp", show_cc: bool = True, code_col: str = "country_code", name_col: str = "institution_name", frac_label: str = DEFAULT_FRAC_LABEL, share_digits: int = 2, change_digits: int = 2) -> str:
    display_tokens = ["name"] + (["cc"] if show_cc else []) + ["pfrac", "intensity", "change", "trend"]
    headers = {"name": entity_header, "cc": r"CC", "pfrac": frac_label, "intensity": r"Intensity", "change": rf"Change ({recent_window}y)", "trend": r"Trend"}
    colspec = "@{}" + "".join((TABLE_COLUMN_SPEC_WITH_CC if show_cc else TABLE_COLUMN_SPEC_NO_CC)[token] for token in display_tokens) + "@{}"
    change_series = pd.to_numeric(df.get(change_col), errors="coerce")
    change_scale_max = 0.0
    if change_series is not None and not change_series.empty:
        change_scale_max = float(change_series.abs().max())
        if pd.isna(change_scale_max):
            change_scale_max = 0.0
    lines = [r"\resizebox{\linewidth}{!}{%", r"\begin{tabular}{" + colspec + r"}", r"  \toprule", *build_grouped_header_lines([headers[token] for token in display_tokens], display_tokens, first_group_label=first_group_label), r"  \midrule"]
    for row_idx, (_, row) in enumerate(df.iterrows(), start=1):
        raw_name = row.get(name_col, "")
        if pd.isna(raw_name):
            raw_name = ""
        name = shorten_country_name(raw_name) if entity_kind == "country" else shorten_institution_name(raw_name)
        cells = {"name": tex_escape(name), "pfrac": fmt_frac(row.get(frac_col), digits=0), "intensity": fmt_pct(row.get(share_col), digits=share_digits), "change": build_change_pp_cell(row.get(change_col), digits=change_digits, max_abs=change_scale_max), "trend": build_sparkline_cell(row, years)}
        if show_cc:
            raw_code = row.get(code_col, "")
            cells["cc"] = tex_escape(raw_code) if pd.notna(raw_code) and str(raw_code).strip() else r"\textit{n/a}"
        prefix = "  " + build_rowcolor_command(ROW_BACKGROUND_COLOR_ODD if row_idx % 2 == 1 else ROW_BACKGROUND_COLOR_EVEN)
        lines.append(prefix + " & ".join(cells[token] for token in display_tokens) + r" \\")
    lines.extend([r"\end{tabular}%", r"}"])
    return "\n".join(lines) + "\n"
