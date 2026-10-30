from pathlib import Path

import pandas as pd

from assets.collab_table_style import (
    CHANGE_PP_NEGATIVE_COLOR,
    CHANGE_PP_POSITIVE_COLOR,
    ROW_BACKGROUND_COLOR_EVEN,
    ROW_BACKGROUND_COLOR_ODD,
    SPARKLINE_HIGHEST_POINT_COLOR,
    SPARKLINE_LOWEST_POINT_COLOR,
)
from core.asset import (
    ETH_INTERNAL_EXCLUSIONS_PATH,
    INSTITUTION_DISPLAY_ORDER,
)
from assets.openalex_annotation_common import (
    RANKING_MACRO_EXCLUSION_COL,
    add_ranking_macro_exclusion_flags,
)
from utility import get_indicator_catalog_dict, get_unit_params_dict, shorten_institution_name

DOMAIN_REPORT = "ethdomain"
DOMAIN_MEMBERS = [inst for inst in INSTITUTION_DISPLAY_ORDER if inst != DOMAIN_REPORT]
ALL_INSTITUTIONS = list(INSTITUTION_DISPLAY_ORDER)

def parse_display_digits(value, default: int) -> int:
    try:
        if pd.isna(value):
            return default
    except TypeError:
        pass

    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _indicator_digits(catalog: dict, indicator: str, default: int) -> int:
    return parse_display_digits((catalog.get(indicator, {}) or {}).get("display_digits"), default)


IND_SHARE = "PP_COLLAB_PARTNER_SHARE_FRAC"
IND_CHANGE = "DPP_COLLAB_PARTNER_SHARE_CHANGE_FRAC"
CSV_STABLE_ROUND_DIGITS = 6
MIN_PARTNER_FRAC_COUNT = 10.0

SHOW_SPARKLINE_TOP_PARTNERS = True
SHOW_CHANGE_TOP_PARTNERS = True
SHOW_ROW_BACKGROUND_STRIPES_TOP_PARTNERS = True
SPARKLINE_COLOR_BY_TREND_TOP_PARTNERS = False
SHOW_SPARKLINE_MARK_EXTREMA_POINTS_TOP_PARTNERS = True
SHOW_SPARKLINE_MARK_HIGHEST_POINT_TOP_PARTNERS = True
SHOW_SPARKLINE_MARK_LOWEST_POINT_TOP_PARTNERS = True

TREND_COLUMN_POSITION_TOP_PARTNERS = "after_pfrac"
CHANGE_COLUMN_POSITION_TOP_PARTNERS = "after_intensity"

SPARKLINE_WIDTH_MM = 18.0
SPARKLINE_HEIGHT_MM = 4.0
SPARKLINE_LINE_WIDTH_PT = 0.45
SPARKLINE_NEUTRAL_LINE_COLOR = "#215caf"
SPARKLINE_NEUTRAL_FILL_COLOR = "black, fill opacity=0"
SPARKLINE_UP_LINE_COLOR = "green!55!black"
SPARKLINE_UP_FILL_COLOR = "green!25"
SPARKLINE_DOWN_LINE_COLOR = "red!70!black"
SPARKLINE_DOWN_FILL_COLOR = "red!25"
SPARKLINE_VERTICAL_SHIFT_EX = -0.9
SPARKLINE_HIGHEST_POINT_RADIUS_PT = 1.1
SPARKLINE_LOWEST_POINT_RADIUS_PT = 1.1

COLOR_CHANGE_PP_BY_SIGN = True
SHOW_CHANGE_PP_BAR_TOP_PARTNERS = True
CHANGE_PP_BAR_CELL_WIDTH_MM = 22.0
CHANGE_PP_BAR_LABEL_WIDTH_MM = 9.8
CHANGE_PP_BAR_GAP_MM = 0.8
CHANGE_PP_BAR_HEIGHT_MM = 1.9
CHANGE_PP_BAR_TRACK_MARGIN_MM = 0.30
CHANGE_PP_BAR_FILL_OPACITY = 0.80
CHANGE_PP_BAR_AXIS_COLOR = "black!45"
CHANGE_PP_BAR_ZERO_COLOR = "black!20"
CHANGE_PP_LABEL_SMALL = False
CHANGE_PP_LABEL_SMALL_COMMAND = r"\tiny"
CHANGE_PP_TIKZ_RAISEBOX_EX = -0.9

TABLE_COLUMN_SPEC_TOP_PARTNERS = {
    "rank": "r",
    "name": "l",
    "cc": "c",
    "pfrac": "r",
    "intensity": "r",
    "trend": "c",
    "change": "C{2.35cm}",
    "mncs": "R{1.45cm}",
    "pp": "R{1.45cm}",
}


def _ensuremath_wrap(s: str) -> str:
    if not s:
        return s
    if r"\ensuremath{" in s:
        return s
    return rf"\ensuremath{{{s}}}"


def _tex_escape(text: str) -> str:
    return (
        str(text)
        .replace("\\", r"\textbackslash{}")
        .replace("{", r"\{")
        .replace("}", r"\}")
        .replace("_", r"\_")
        .replace("%", r"\%")
        .replace("&", r"\&")
        .replace("#", r"\#")
    )


def _normalize_hex_color(color: str) -> str | None:
    raw = str(color).strip()
    if raw.startswith("#"):
        raw = raw[1:]

    if len(raw) == 3 and all(ch in "0123456789abcdefABCDEF" for ch in raw):
        raw = "".join(ch * 2 for ch in raw)

    if len(raw) == 6 and all(ch in "0123456789abcdefABCDEF" for ch in raw):
        return raw.upper()
    return None


def _hex_to_rgb_components(hex_color: str) -> tuple[int, int, int]:
    return int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)


def _build_rowcolor_command(color: str) -> str:
    raw = str(color).strip()
    if not raw:
        return ""

    hex_color = _normalize_hex_color(raw)
    if hex_color is not None:
        return rf"\rowcolor[HTML]{{{hex_color}}} "
    return rf"\rowcolor{{{raw}}} "


def _build_tikz_fill_color_option(color: str) -> str:
    raw = str(color).strip()
    if not raw:
        return "fill=none"

    hex_color = _normalize_hex_color(raw)
    if hex_color is None:
        return raw

    red, green, blue = _hex_to_rgb_components(hex_color)
    return f"fill={{rgb,255:red,{red};green,{green};blue,{blue}}}"


def _build_tikz_draw_color_option(color: str) -> str:
    raw = str(color).strip()
    if not raw:
        return "draw=none"

    hex_color = _normalize_hex_color(raw)
    if hex_color is None:
        return raw

    red, green, blue = _hex_to_rgb_components(hex_color)
    return f"draw={{rgb,255:red,{red};green,{green};blue,{blue}}}"


def _build_textcolor_command(text: str, color: str) -> str:
    raw = str(color).strip()
    if not raw:
        return text

    hex_color = _normalize_hex_color(raw)
    if hex_color is not None:
        return rf"\textcolor[HTML]{{{hex_color}}}{{{text}}}"
    return rf"\textcolor{{{raw}}}{{{text}}}"


def _fmt_frac(value, digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return r"\textit{n/a}"
    return f"{float(value):,.{digits}f}".replace(",", "{,}")


def _fmt_float(value, digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return r"\textit{n/a}"
    return f"{float(value):.{digits}f}"


def _fmt_pct(value, digits: int = 1) -> str:
    if value is None or pd.isna(value):
        return r"\textit{n/a}"
    pct = f"{100.0 * float(value):.{digits}f}".rstrip("0").rstrip(".")
    return f"{pct}\\%"


def _fmt_change_pp(value, digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return r"\textit{n/a}"

    numeric_value = float(value)
    formatted = f"{numeric_value:+.{digits}f}pp"
    if not COLOR_CHANGE_PP_BY_SIGN:
        return formatted
    if numeric_value > 0:
        return _build_textcolor_command(formatted, CHANGE_PP_POSITIVE_COLOR)
    if numeric_value < 0:
        return _build_textcolor_command(formatted, CHANGE_PP_NEGATIVE_COLOR)
    return formatted


def _format_change_pp_label(label: str) -> str:
    if not CHANGE_PP_LABEL_SMALL:
        return label
    return rf"{{{CHANGE_PP_LABEL_SMALL_COMMAND} {label}}}"


def _build_change_pp_cell(value, digits: int = 2, max_abs: float = 0.0) -> str:
    if value is None or pd.isna(value):
        return r"\textit{n/a}"

    numeric_value = float(value)
    text_part = _format_change_pp_label(_fmt_change_pp(numeric_value, digits=digits))

    if not SHOW_CHANGE_PP_BAR_TOP_PARTNERS or max_abs <= 0:
        return text_part

    bar_area_width = max(0.0, CHANGE_PP_BAR_CELL_WIDTH_MM - CHANGE_PP_BAR_LABEL_WIDTH_MM - CHANGE_PP_BAR_GAP_MM)
    if bar_area_width <= 0:
        return text_part

    track_half = max(0.0, bar_area_width / 2.0 - CHANGE_PP_BAR_TRACK_MARGIN_MM)
    if track_half <= 0:
        return text_part

    normalized = min(abs(numeric_value) / max_abs, 1.0)
    bar_length = normalized * track_half

    bar_color = CHANGE_PP_BAR_ZERO_COLOR
    if numeric_value > 0:
        bar_color = CHANGE_PP_POSITIVE_COLOR
    elif numeric_value < 0:
        bar_color = CHANGE_PP_NEGATIVE_COLOR

    fill_option = _build_tikz_fill_color_option(bar_color)
    axis_draw_option = _build_tikz_draw_color_option(CHANGE_PP_BAR_AXIS_COLOR)

    center_x = bar_area_width / 2.0
    label_x = bar_area_width + CHANGE_PP_BAR_GAP_MM + CHANGE_PP_BAR_LABEL_WIDTH_MM / 2.0
    half_h = CHANGE_PP_BAR_HEIGHT_MM / 2.0
    mid_y = half_h + 0.30
    cell_height = max(CHANGE_PP_BAR_HEIGHT_MM + 0.60, 2.0 * mid_y)
    y0 = mid_y - half_h
    y1 = mid_y + half_h

    bar_command = ""
    if bar_length > 1e-12:
        if numeric_value >= 0:
            x0 = center_x
            x1 = center_x + bar_length
        else:
            x0 = center_x - bar_length
            x1 = center_x

        bar_command = (
            rf"\fill[{fill_option}, fill opacity={CHANGE_PP_BAR_FILL_OPACITY}] "
            rf"({x0:.3f},{y0:.3f}) rectangle ({x1:.3f},{y1:.3f});"
        )

    tikz = (
        rf"\begin{{tikzpicture}}[x=1mm,y=1mm,baseline=-0.55ex]"
        rf"\path[use as bounding box] (0,0) rectangle ({CHANGE_PP_BAR_CELL_WIDTH_MM:.3f},{cell_height:.3f});"
        rf"\draw[{axis_draw_option}, line width=0.22pt] ({center_x:.3f},0.12) -- ({center_x:.3f},{cell_height - 0.12:.3f});"
        + bar_command
        + rf"\node[anchor=center] at ({label_x:.3f},{mid_y:.3f}) {{{text_part}}};"
        + r"\end{tikzpicture}"
    )
    return rf"\raisebox{{{CHANGE_PP_TIKZ_RAISEBOX_EX}ex}}{{{tikz}}}"


def _sparkline_colors(values: list[float], *, color_by_trend: bool) -> tuple[str, str]:
    if not color_by_trend or not values:
        return SPARKLINE_NEUTRAL_LINE_COLOR, SPARKLINE_NEUTRAL_FILL_COLOR

    diff = values[-1] - values[0]
    if abs(diff) < 1e-12:
        return SPARKLINE_NEUTRAL_LINE_COLOR, SPARKLINE_NEUTRAL_FILL_COLOR
    if diff > 0:
        return SPARKLINE_UP_LINE_COLOR, SPARKLINE_UP_FILL_COLOR
    return SPARKLINE_DOWN_LINE_COLOR, SPARKLINE_DOWN_FILL_COLOR


def _normalize_sparkline_values(values: list[float]) -> list[float]:
    if not values:
        return []

    max_value = max(values)
    if max_value <= 0:
        return [0.0 for _ in values]
    return [max(v, 0.0) / max_value for v in values]


def _build_sparkline_cell(
    row: pd.Series,
    years: list[int],
    *,
    color_by_trend: bool,
    show_extrema_points: bool,
) -> str:
    values: list[float] = []
    for year in years:
        value = row.get(f"frac_y_{year}")
        values.append(float(value) if pd.notna(value) else 0.0)

    if len(values) < 2:
        return r"\textit{n/a}"

    normalized = _normalize_sparkline_values(values)
    if len(normalized) < 2:
        return r"\textit{n/a}"

    line_color, fill_color = _sparkline_colors(values, color_by_trend=color_by_trend)
    fill_color_option = _build_tikz_fill_color_option(fill_color)
    line_color_option = _build_tikz_draw_color_option(line_color)
    step = 1.0 / (len(normalized) - 1)
    coords = [f"({idx * step:.4f},{value:.4f})" for idx, value in enumerate(normalized)]
    coords_path = " -- ".join(coords)

    marker_commands = ""
    if show_extrema_points:
        max_idx = values.index(max(values))
        min_idx = values.index(min(values))

        if SHOW_SPARKLINE_MARK_HIGHEST_POINT_TOP_PARTNERS:
            x_max = max_idx * step
            y_max = normalized[max_idx]
            highest_fill_option = _build_tikz_fill_color_option(SPARKLINE_HIGHEST_POINT_COLOR)
            highest_draw_option = _build_tikz_draw_color_option(SPARKLINE_HIGHEST_POINT_COLOR)
            marker_commands += (
                rf"\filldraw[{highest_fill_option},{highest_draw_option}] "
                rf"({x_max:.4f},{y_max:.4f}) circle[radius={SPARKLINE_HIGHEST_POINT_RADIUS_PT}pt];"
            )

        if SHOW_SPARKLINE_MARK_LOWEST_POINT_TOP_PARTNERS and (
            min_idx != max_idx or not SHOW_SPARKLINE_MARK_HIGHEST_POINT_TOP_PARTNERS
        ):
            x_min = min_idx * step
            y_min = normalized[min_idx]
            lowest_fill_option = _build_tikz_fill_color_option(SPARKLINE_LOWEST_POINT_COLOR)
            lowest_draw_option = _build_tikz_draw_color_option(SPARKLINE_LOWEST_POINT_COLOR)
            marker_commands += (
                rf"\filldraw[{lowest_fill_option},{lowest_draw_option}] "
                rf"({x_min:.4f},{y_min:.4f}) circle[radius={SPARKLINE_LOWEST_POINT_RADIUS_PT}pt];"
            )

    tikz = (
        rf"\begin{{tikzpicture}}[x={SPARKLINE_WIDTH_MM}mm,y={SPARKLINE_HEIGHT_MM}mm,baseline=(current bounding box.south)]"
        rf"\fill[{fill_color_option}] (0,0) -- {coords_path} -- (1,0) -- cycle;"
        rf"\draw[{line_color_option}, line width={SPARKLINE_LINE_WIDTH_PT}pt] {coords_path};"
        f"{marker_commands}"
        r"\end{tikzpicture}"
    )
    return rf"\raisebox{{{SPARKLINE_VERTICAL_SHIFT_EX}ex}}{{{tikz}}}"


def _resolve_token_position(position: str) -> str | None:
    pos = str(position).strip().lower()
    mapping = {
        "after_name": "name",
        "after_cc": "cc",
        "after_pfrac": "pfrac",
        "after_intensity": "intensity",
        "after_trend": "trend",
        "after_change": "change",
        "after_mncs": "mncs",
        "after_pp": "pp",
        "after_pptop10": "pp",
        "end": None,
    }
    return mapping.get(pos, None)


def _insert_optional_token(tokens: list[str], token: str, position: str, *, fallback_token: str = "intensity") -> None:
    anchor = _resolve_token_position(position)
    if anchor is None:
        tokens.append(token)
        return

    if anchor in tokens:
        idx = tokens.index(anchor) + 1
    elif fallback_token in tokens:
        idx = tokens.index(fallback_token) + 1
    else:
        idx = len(tokens)
    tokens.insert(idx, token)


def _build_grouped_header_lines(
    headers: list[str],
    display_tokens: list[str],
    *,
    first_group_label: str,
    decomposition_count: int = 0,
    decomposition_before_impact: bool = False,
    decomposition_group_label: str = "ETH Domain Members",
) -> list[str]:
    group_ids = []
    for token in display_tokens:
        if token in {"rank", "name", "cc"}:
            group_ids.append("first")
        elif token in {"pfrac", "trend"}:
            group_ids.append("volume")
        elif token in {"intensity", "change"}:
            group_ids.append("composition")
        elif token in {"mncs", "pp"}:
            group_ids.append("impact")
        else:
            group_ids.append("other")

    if decomposition_count > 0:
        if decomposition_before_impact:
            first_impact_idx = next((idx for idx, group in enumerate(group_ids) if group == "impact"), len(group_ids))
            group_ids = (
                group_ids[:first_impact_idx]
                + ["decomposition"] * decomposition_count
                + group_ids[first_impact_idx:]
            )
        else:
            group_ids.extend(["decomposition"] * decomposition_count)

    if len(group_ids) != len(headers) or not group_ids:
        return [r"  " + " & ".join(headers) + r" \\"]

    group_labels = {
        "first": first_group_label,
        "volume": "Output",
        "composition": "Relative Weight",
        "impact": "Impact",
        "decomposition": decomposition_group_label,
        "other": "",
    }

    runs: list[tuple[str, int, int]] = []
    run_start = 1
    current_group = group_ids[0]
    for col_idx, group in enumerate(group_ids[1:], start=2):
        if group != current_group:
            runs.append((current_group, run_start, col_idx - 1))
            run_start = col_idx
            current_group = group
    runs.append((current_group, run_start, len(group_ids)))

    top_header_cells = [
        rf"\multicolumn{{{col_end - col_start + 1}}}{{c}}{{\textbf{{{group_labels[group]}}}}}"
        for group, col_start, col_end in runs
    ]
    cmidrule_line = " ".join(
        rf"\cmidrule(lr){{{col_start}-{col_end}}}" for _, col_start, col_end in runs
    )

    return [
        r"  " + " & ".join(top_header_cells) + r" \\",
        r"  " + cmidrule_line,
        r"  " + " & ".join(headers) + r" \\",
    ]


def build_top_partners_table_tex(
    df: pd.DataFrame,
    years: list[int],
    *,
    recent_window: int,
    decomposition_members: list[str] | None = None,
    decomposition_group_label: str = "ETH Domain Members",
    marked_institution_ids: set[str] | None = None,
    marked_institution_marker: str = r"\textsuperscript{*}",
    marked_institution_note: str | None = None,
    marked_institution_notes_by_id: dict[str, str] | None = None,
    marked_institution_note_mode: str = "below_table",
    marked_institution_note_font: str = r"\footnotesize",
    marked_institution_note_rule: bool = False,
    marked_institution_note_width: str = r"0.94\linewidth",
    marked_institution_note_line_spread: str = "0.92",
) -> str:
    indicator_catalog = get_indicator_catalog_dict()
    decomposition_members = [str(m).strip().lower() for m in (decomposition_members or []) if str(m).strip()]
    show_decomposition = len(decomposition_members) > 0
    marked_institution_ids = {str(v).strip() for v in (marked_institution_ids or set())}
    marked_institution_notes_by_id = {
        str(k).strip(): str(v) for k, v in (marked_institution_notes_by_id or {}).items()
    }
    marked_institution_note_mode = str(marked_institution_note_mode).strip().lower()

    frac_symbol = (indicator_catalog.get("P_FRAC", {}) or {}).get("symbol_tex", "").strip()
    mncs_symbol = (indicator_catalog.get("COLLAB_IMPACT_MNCS_FRAC", {}) or {}).get("symbol_tex", "").strip()
    pp_symbol = (indicator_catalog.get("COLLAB_IMPACT_PP_TOPTEN_FRAC", {}) or {}).get("symbol_tex", "").strip()

    frac_label = _ensuremath_wrap(frac_symbol) if frac_symbol else r"\ensuremath{\mathrm{P}[\mathrm{Frac}]}"
    mncs_label = _ensuremath_wrap(mncs_symbol) if mncs_symbol else "MNCS"
    pp_label = _ensuremath_wrap(pp_symbol) if pp_symbol else "PPtop10"

    share_digits = parse_display_digits((indicator_catalog.get(IND_SHARE, {}) or {}).get("display_digits"), 1)
    change_digits = parse_display_digits((indicator_catalog.get(IND_CHANGE, {}) or {}).get("display_digits"), 2)
    mncs_digits = parse_display_digits(
        (indicator_catalog.get("COLLAB_IMPACT_MNCS_FRAC", {}) or {}).get("display_digits"),
        2,
    )
    pp_digits = max(
        1,
        parse_display_digits(
            (indicator_catalog.get("COLLAB_IMPACT_PP_TOPTEN_FRAC", {}) or {}).get("display_digits"),
            1,
        ),
    )

    change_header = rf"Change ({recent_window}y)"
    token_to_header = {
        "rank": r"Rank",
        "name": r"Institution",
        "cc": r"CC",
        "pfrac": frac_label,
        "intensity": r"Share",
        "trend": r"Trend",
        "change": change_header,
        "mncs": mncs_label,
        "pp": pp_label,
    }

    display_tokens = ["rank", "name", "cc", "pfrac", "intensity", "mncs", "pp"]
    if SHOW_SPARKLINE_TOP_PARTNERS:
        _insert_optional_token(
            display_tokens,
            "trend",
            TREND_COLUMN_POSITION_TOP_PARTNERS,
            fallback_token="intensity",
        )
    if SHOW_CHANGE_TOP_PARTNERS:
        _insert_optional_token(
            display_tokens,
            "change",
            CHANGE_COLUMN_POSITION_TOP_PARTNERS,
            fallback_token="intensity",
        )

    impact_tokens = [token for token in display_tokens if token in {"mncs", "pp"}]
    pre_impact_tokens = [token for token in display_tokens if token not in {"mncs", "pp"}]

    if show_decomposition:
        unit_params = get_unit_params_dict()
        member_headers = []
        for member in decomposition_members:
            short_name = str((unit_params.get(member, {}) or {}).get("InstShort", "")).strip()
            member_headers.append(_tex_escape(short_name if short_name else member.upper()))

        col_align = [TABLE_COLUMN_SPEC_TOP_PARTNERS.get(token, "r") for token in pre_impact_tokens]
        headers = [token_to_header[token] for token in pre_impact_tokens]

        col_align.extend(["r"] * len(decomposition_members))
        headers.extend([r"{" + header + "}" for header in member_headers])

        col_align.extend([TABLE_COLUMN_SPEC_TOP_PARTNERS.get(token, "r") for token in impact_tokens])
        headers.extend([token_to_header[token] for token in impact_tokens])
    else:
        col_align = [TABLE_COLUMN_SPEC_TOP_PARTNERS.get(token, "r") for token in display_tokens]
        headers = [token_to_header[token] for token in display_tokens]

    table_column_count = len(col_align)
    col_spec = "@{}" + "".join(col_align) + "@{}"
    grouped_header_lines = _build_grouped_header_lines(
        headers,
        display_tokens,
        first_group_label="Partner",
        decomposition_count=len(decomposition_members) if show_decomposition else 0,
        decomposition_before_impact=show_decomposition,
        decomposition_group_label=decomposition_group_label,
    )

    change_scale_max = 0.0
    if SHOW_CHANGE_TOP_PARTNERS and SHOW_CHANGE_PP_BAR_TOP_PARTNERS and "dpp_share_change_domain" in df.columns:
        change_series = pd.to_numeric(df["dpp_share_change_domain"], errors="coerce")
        if not change_series.empty:
            change_scale_max = float(change_series.abs().max())
            if pd.isna(change_scale_max):
                change_scale_max = 0.0

    lines = [
        r"\resizebox{\linewidth}{!}{%",
        r"\begin{tabular}{" + col_spec + r"}",
        r"  \toprule",
        *grouped_header_lines,
        r"  \midrule",
    ]

    marked_notes_in_table: list[str] = []

    for row_idx, (_, row) in enumerate(df.iterrows(), start=1):
        institution_id = str(row.get("institution_id", "")).strip()
        raw_name = row.get("institution_name", "")
        short_name = shorten_institution_name(raw_name)
        institution_name = _tex_escape(short_name)
        row_is_marked = institution_id in marked_institution_ids
        row_marked_note = marked_institution_notes_by_id.get(institution_id, marked_institution_note)
        if row_is_marked:
            institution_name += marked_institution_marker
        country_code = _tex_escape(row.get("country_code", "")) if pd.notna(row.get("country_code")) else r"\textit{n/a}"

        token_to_cell = {
            "rank": str(row_idx),
            "name": institution_name,
            "cc": country_code,
            "pfrac": _fmt_frac(row.get("frac_count"), digits=0),
            "intensity": _fmt_pct(row.get("pp_share_domain"), digits=share_digits),
            "mncs": _fmt_float(row.get("mncs"), digits=mncs_digits),
            "pp": _fmt_pct(row.get("pp_top10"), digits=pp_digits),
        }

        if SHOW_CHANGE_TOP_PARTNERS:
            token_to_cell["change"] = _build_change_pp_cell(
                row.get("dpp_share_change_domain"),
                digits=change_digits,
                max_abs=change_scale_max,
            )
        if SHOW_SPARKLINE_TOP_PARTNERS:
            token_to_cell["trend"] = _build_sparkline_cell(
                row,
                years,
                color_by_trend=SPARKLINE_COLOR_BY_TREND_TOP_PARTNERS,
                show_extrema_points=SHOW_SPARKLINE_MARK_EXTREMA_POINTS_TOP_PARTNERS,
            )

        if show_decomposition:
            cells = [token_to_cell[token] for token in pre_impact_tokens]
            cells.extend(_fmt_frac(row.get(f"frac_{member}"), digits=0) for member in decomposition_members)
            cells.extend(token_to_cell[token] for token in impact_tokens)
        else:
            cells = [token_to_cell[token] for token in display_tokens]

        row_prefix = "  "
        if SHOW_ROW_BACKGROUND_STRIPES_TOP_PARTNERS:
            row_color = ROW_BACKGROUND_COLOR_ODD if row_idx % 2 == 1 else ROW_BACKGROUND_COLOR_EVEN
            row_prefix += _build_rowcolor_command(row_color)

        note_row = ""
        if row_is_marked and row_marked_note:
            if row_marked_note not in marked_notes_in_table:
                marked_notes_in_table.append(row_marked_note)

        if row_is_marked and row_marked_note and marked_institution_note_mode in {"before_row", "after_row"}:
            note_row = (
                rf"  \multicolumn{{{table_column_count}}}{{@{{}}p{{{marked_institution_note_width}}}@{{}}}}"
                rf"{{{marked_institution_note_font}\raggedright {row_marked_note}\par}} \\"
            )

        if row_is_marked and note_row and marked_institution_note_mode == "before_row":
            lines.append(r"  \addlinespace[0.35ex]")
            lines.append(note_row)

        lines.append(row_prefix + " & ".join(cells) + r" \\")

        if row_is_marked and note_row and marked_institution_note_mode == "after_row":
            lines.append(r"  \addlinespace[0.15ex]")
            lines.append(note_row)
            lines.append(r"  \addlinespace[0.35ex]")

    lines.extend(
        [
            r"\end{tabular}%",
            r"}",
        ]
    )
    if marked_institution_note_mode == "below_table" and marked_notes_in_table:
        if marked_institution_note_rule:
            lines.extend(
                [
                    r"\vspace{0.45ex}",
                    r"\noindent\rule{\linewidth}{0.25pt}",
                ]
            )
        lines.extend(
            [
                r"\vspace{0.25ex}",
                r"{"
                + marked_institution_note_font
                + rf"\linespread{{{marked_institution_note_line_spread}}}\selectfont"
                + r"\raggedright "
                + r"\\ ".join(marked_notes_in_table)
                + r"\par}",
            ]
        )
    return "\n".join(lines) + "\n"


def load_child_ids() -> set[int]:
    if not ETH_INTERNAL_EXCLUSIONS_PATH.is_file():
        return set()

    try:
        df = pd.read_csv(
            ETH_INTERNAL_EXCLUSIONS_PATH,
            usecols=["institution_id", "relationship", "parent_institution"],
            dtype={"institution_id": "string", "relationship": "string", "parent_institution": "string"},
        )
    except (ValueError, pd.errors.EmptyDataError):
        return set()

    df["institution_id"] = pd.to_numeric(df["institution_id"], errors="coerce")
    df = df[df["institution_id"].notna() & (df["institution_id"] > 0)].copy()
    df["institution_id"] = df["institution_id"].astype(int)

    df["relationship"] = df["relationship"].fillna("").astype(str).str.lower()
    df = df[df["relationship"] == "child"].copy()
    return set(df["institution_id"].tolist())


def load_ethdomain_extra_ids() -> set[int]:
    """Load ETH Domain-related ids not guaranteed to appear in report membership sets.

    Currently this captures ETH Board records from the exclusion registry
    (parent_institution=eth_board), so they can be excluded with ETH-unit toggles.
    """
    if not ETH_INTERNAL_EXCLUSIONS_PATH.is_file():
        return set()

    try:
        df = pd.read_csv(
            ETH_INTERNAL_EXCLUSIONS_PATH,
            usecols=["institution_id", "parent_institution"],
            dtype={"institution_id": "string", "parent_institution": "string"},
        )
    except (ValueError, pd.errors.EmptyDataError):
        return set()

    df["institution_id"] = pd.to_numeric(df["institution_id"], errors="coerce")
    df = df[df["institution_id"].notna() & (df["institution_id"] > 0)].copy()
    df["institution_id"] = df["institution_id"].astype(int)

    parent = df["parent_institution"].fillna("").astype(str).str.lower()
    is_eth_board = parent.str.split(";").apply(
        lambda tokens: "eth_board" in {token.strip() for token in tokens}
    )
    return set(df.loc[is_eth_board, "institution_id"].tolist())


def fetch_report_institution_sets(con) -> tuple[set[int], set[int], dict[str, set[int]]]:
    report_list_sql = ", ".join([f"'{r}'" for r in [*DOMAIN_MEMBERS, DOMAIN_REPORT]])
    query = f"""
        SELECT DISTINCT report_name, institution_id
        FROM reports.report_institutions_ids
        WHERE report_name IN ({report_list_sql})
          AND institution_id IS NOT NULL
    """
    df = con.execute(query).df()
    if df.empty:
        return set(), set(), {m: set() for m in DOMAIN_MEMBERS}

    df["report_name"] = df["report_name"].astype("string")
    df["institution_id"] = pd.to_numeric(df["institution_id"], errors="coerce")
    df = df[df["institution_id"].notna()].copy()
    df["institution_id"] = df["institution_id"].astype(int)

    core_ids = set(df.loc[df["report_name"].isin(DOMAIN_MEMBERS), "institution_id"].tolist())
    ethdomain_ids = set(df.loc[df["report_name"].eq(DOMAIN_REPORT), "institution_id"].tolist())

    per_member: dict[str, set[int]] = {}
    for member in DOMAIN_MEMBERS:
        per_member[member] = set(df.loc[df["report_name"].eq(member), "institution_id"].tolist())

    return core_ids, ethdomain_ids, per_member


def add_partner_flags(
    df: pd.DataFrame,
    *,
    core_ids: set[int],
    child_ids: set[int],
    ethdomain_ids: set[int],
    ethdomain_extra_ids: set[int] | None = None,
) -> pd.DataFrame:
    out = df.copy()
    ids = pd.to_numeric(out.get("institution_id"), errors="coerce")
    ethdomain_all_ids = set(ethdomain_ids)
    if ethdomain_extra_ids:
        ethdomain_all_ids.update(ethdomain_extra_ids)
    out["FLAG_IS_CORE_UNIT"] = ids.isin(core_ids).astype(int)
    out["FLAG_IS_CHILD_OF_CORE_UNIT"] = ids.isin(child_ids).astype(int)
    out["FLAG_IS_ETHDOMAIN_INST"] = ids.isin(ethdomain_all_ids).astype(int)
    return out


def add_year_columns_from_raw(
    partner_df: pd.DataFrame,
    yearly_df: pd.DataFrame,
    years: list[int],
    *,
    metric_kind: str = "P_FRAC",
) -> pd.DataFrame:
    out = partner_df.copy()
    if yearly_df.empty:
        for y in years:
            out[f"frac_y_{y}"] = 0.0
        return out

    working = yearly_df.copy()
    working["metric_kind"] = working["metric_kind"].astype("string")
    working = working[working["metric_kind"].eq(metric_kind)].copy()
    if working.empty:
        for y in years:
            out[f"frac_y_{y}"] = 0.0
        return out

    year_cols = [str(y) for y in years if str(y) in working.columns]
    keep_cols = ["institution_id", *year_cols]
    working = working[keep_cols].copy()

    rename_map = {str(y): f"frac_y_{y}" for y in years if str(y) in working.columns}
    working = working.rename(columns=rename_map)

    out["institution_id"] = out["institution_id"].astype("string")
    working["institution_id"] = working["institution_id"].astype("string")
    out = out.merge(working, on="institution_id", how="left")

    for y in years:
        col = f"frac_y_{y}"
        if col not in out.columns:
            out[col] = 0.0
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0.0)

    return out


def _resolve_total_from_column(df: pd.DataFrame, column: str, fallback: pd.Series) -> float:
    if column in df.columns:
        values = pd.to_numeric(df[column], errors="coerce").dropna()
        if not values.empty:
            return float(values.iloc[0])
    return float(pd.to_numeric(fallback, errors="coerce").fillna(0.0).sum())


def add_share_and_change_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    for col in ["frac_count", "frac_recent", "frac_baseline"]:
        if col not in out.columns:
            out[col] = 0.0
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0.0)

    # Partner share should be normalized by focal-institution collaboration totals
    # when present (legacy-consistent). Fallback to row sums if totals are absent.
    total_full = _resolve_total_from_column(out, "p_collab_frac", out["frac_count"])
    total_recent = _resolve_total_from_column(out, "p_collab_frac_recent", out["frac_recent"])
    total_baseline = _resolve_total_from_column(out, "p_collab_frac_baseline", out["frac_baseline"])

    out["pp_share_domain"] = out["frac_count"] / total_full if total_full > 0 else 0.0
    out["share_recent_domain"] = out["frac_recent"] / total_recent if total_recent > 0 else 0.0
    out["share_baseline_domain"] = out["frac_baseline"] / total_baseline if total_baseline > 0 else 0.0

    if total_baseline > 0:
        out["dpp_share_change_domain"] = (
            out["share_recent_domain"] - out["share_baseline_domain"]
        ) * 100.0
    else:
        out["dpp_share_change_domain"] = pd.NA

    return out


def filter_min_partner_frac_count(
    df: pd.DataFrame,
    *,
    min_frac_count: float = MIN_PARTNER_FRAC_COUNT,
) -> pd.DataFrame:
    out = df.copy()
    if "frac_count" not in out.columns:
        return out

    frac_count = pd.to_numeric(out["frac_count"], errors="coerce").fillna(0.0)
    return out[frac_count >= min_frac_count].copy().reset_index(drop=True)


def finalize_collab_ratio(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    if "p_collab_frac" not in out.columns:
        out["p_collab_frac"] = pd.to_numeric(out.get("frac_count"), errors="coerce").fillna(0.0).sum()
    if "p_frac" not in out.columns:
        out["p_frac"] = out["p_collab_frac"]

    out["p_collab_frac"] = pd.to_numeric(out["p_collab_frac"], errors="coerce").fillna(0.0)
    out["p_frac"] = pd.to_numeric(out["p_frac"], errors="coerce").fillna(0.0)

    out["pp_collab_frac"] = pd.NA
    valid = out["p_frac"] > 0
    out.loc[valid, "pp_collab_frac"] = out.loc[valid, "p_collab_frac"] / out.loc[valid, "p_frac"]

    return out


def sorted_with_row_order(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in ["frac_count", "full_count"]:
        if col not in out.columns:
            out[col] = 0.0
    out["frac_count"] = pd.to_numeric(out["frac_count"], errors="coerce").fillna(0.0)
    out["full_count"] = pd.to_numeric(out["full_count"], errors="coerce").fillna(0.0)

    out = out.sort_values(
        ["frac_count", "full_count", "institution_name"],
        ascending=[False, False, True],
    ).reset_index(drop=True)
    out["row_order"] = out.index + 1
    return out


def capped_view(
    df: pd.DataFrame,
    *,
    top_n: int | None,
    exclude_children_from_top_n: bool,
    exclude_eth_units_from_top_n: bool,
) -> pd.DataFrame:
    out = sorted_with_row_order(df)

    if exclude_children_from_top_n and "FLAG_IS_CHILD_OF_CORE_UNIT" in out.columns:
        child_mask = pd.to_numeric(out["FLAG_IS_CHILD_OF_CORE_UNIT"], errors="coerce").fillna(0).astype(int)
        out = out[child_mask.eq(0)].copy().reset_index(drop=True)

    if exclude_eth_units_from_top_n:
        if "FLAG_IS_CORE_UNIT" in out.columns:
            core_mask = pd.to_numeric(out["FLAG_IS_CORE_UNIT"], errors="coerce").fillna(0).astype(int)
            out = out[core_mask.eq(0)].copy().reset_index(drop=True)
        if "FLAG_IS_ETHDOMAIN_INST" in out.columns:
            domain_mask = pd.to_numeric(out["FLAG_IS_ETHDOMAIN_INST"], errors="coerce").fillna(0).astype(int)
            out = out[domain_mask.eq(0)].copy().reset_index(drop=True)

    if top_n is not None:
        out = out.head(top_n).copy().reset_index(drop=True)

    out["row_order"] = out.index + 1
    return out


def to_indicator_export(df: pd.DataFrame, years: list[int]) -> pd.DataFrame:
    out = df.copy()
    indicator_catalog = get_indicator_catalog_dict()

    share_digits = _indicator_digits(indicator_catalog, "PP_COLLAB_PARTNER_SHARE_FRAC", 1)
    share_recent_digits = _indicator_digits(
        indicator_catalog, "PP_COLLAB_PARTNER_SHARE_RECENT_FRAC", share_digits
    )
    share_baseline_digits = _indicator_digits(
        indicator_catalog, "PP_COLLAB_PARTNER_SHARE_BASELINE_FRAC", share_digits
    )
    change_digits = _indicator_digits(indicator_catalog, "DPP_COLLAB_PARTNER_SHARE_CHANGE_FRAC", 2)
    mncs_digits = _indicator_digits(indicator_catalog, "COLLAB_IMPACT_MNCS_FRAC", 2)
    pp_digits = max(1, _indicator_digits(indicator_catalog, "COLLAB_IMPACT_PP_TOPTEN_FRAC", 1))
    pp_collab_digits = max(1, _indicator_digits(indicator_catalog, "PP_COLLAB_FRAC", 1))

    if "full_count" in out.columns:
        out["full_count"] = pd.to_numeric(out["full_count"], errors="coerce").round(0).astype("Int64")
        out["P_FULL"] = out["full_count"]

    numeric_cols = [
        "frac_count",
        "frac_recent",
        "frac_baseline",
        "mncs",
        "pp_top10",
        "pp_share_domain",
        "share_recent_domain",
        "share_baseline_domain",
        "dpp_share_change_domain",
        "p_collab_frac",
        "p_frac",
        "pp_collab_frac",
        *[f"frac_y_{y}" for y in years],
    ]

    for col in numeric_cols:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")

    for col in ["frac_count", "frac_recent", "frac_baseline", "p_collab_frac", "p_frac"]:
        if col in out.columns:
            out[col] = out[col].round(2)

    for col in [f"frac_y_{y}" for y in years]:
        if col in out.columns:
            out[col] = out[col].round(2)

    if "pp_share_domain" in out.columns:
        out["PP_COLLAB_PARTNER_SHARE_FRAC"] = out["pp_share_domain"].round(share_digits + 2)
    if "share_recent_domain" in out.columns:
        out["PP_COLLAB_PARTNER_SHARE_RECENT_FRAC"] = out["share_recent_domain"].round(
            share_recent_digits + 2
        )
    if "share_baseline_domain" in out.columns:
        out["PP_COLLAB_PARTNER_SHARE_BASELINE_FRAC"] = out[
            "share_baseline_domain"
        ].round(share_baseline_digits + 2)
    if "dpp_share_change_domain" in out.columns:
        out["DPP_COLLAB_PARTNER_SHARE_CHANGE_FRAC"] = out["dpp_share_change_domain"].round(change_digits)
    if "mncs" in out.columns:
        out["COLLAB_IMPACT_MNCS_FRAC"] = out["mncs"].round(mncs_digits)
    if "pp_top10" in out.columns:
        out["COLLAB_IMPACT_PP_TOPTEN_FRAC"] = out["pp_top10"].round(pp_digits + 2)
    if "p_collab_frac" in out.columns:
        out["P_COLLAB_FRAC"] = out["p_collab_frac"].round(2)
    if "p_frac" in out.columns:
        out["P_FRAC"] = out["p_frac"].round(2)
    if "pp_collab_frac" in out.columns:
        out["PP_COLLAB_FRAC"] = pd.to_numeric(out["pp_collab_frac"], errors="coerce").round(pp_collab_digits + 2)

    if "row_order" in out.columns:
        out["row_order"] = pd.to_numeric(out["row_order"], errors="coerce").round(0).astype("Int64")

    out = add_ranking_macro_exclusion_flags(out)

    flag_cols = [
        "FLAG_IS_CORE_UNIT",
        "FLAG_IS_CHILD_OF_CORE_UNIT",
        "FLAG_IS_ETHDOMAIN_INST",
        RANKING_MACRO_EXCLUSION_COL,
    ]
    for col in flag_cols:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0).round(0).astype("Int64")

    return out


def filter_yearly_raw_for_partners(yearly_df: pd.DataFrame, partner_ids: pd.Series) -> pd.DataFrame:
    if yearly_df.empty:
        return yearly_df.copy()

    keep = set(partner_ids.astype("string").tolist())
    out = yearly_df.copy()
    out["institution_id"] = out["institution_id"].astype("string")
    return out[out["institution_id"].isin(keep)].copy().reset_index(drop=True)


def reverse_indicator_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Allow rendering from indicator-exported files if needed."""
    out = df.copy()
    if "COLLAB_IMPACT_MNCS_FRAC" in out.columns and "mncs" not in out.columns:
        out["mncs"] = out["COLLAB_IMPACT_MNCS_FRAC"]
    if "COLLAB_IMPACT_PP_TOPTEN_FRAC" in out.columns and "pp_top10" not in out.columns:
        out["pp_top10"] = out["COLLAB_IMPACT_PP_TOPTEN_FRAC"]
    if "PP_COLLAB_PARTNER_SHARE_FRAC" in out.columns and "pp_share_domain" not in out.columns:
        out["pp_share_domain"] = out["PP_COLLAB_PARTNER_SHARE_FRAC"]
    if (
        "PP_COLLAB_PARTNER_SHARE_RECENT_FRAC" in out.columns
        and "share_recent_domain" not in out.columns
    ):
        out["share_recent_domain"] = out["PP_COLLAB_PARTNER_SHARE_RECENT_FRAC"]
    if (
        "PP_COLLAB_PARTNER_SHARE_BASELINE_FRAC" in out.columns
        and "share_baseline_domain" not in out.columns
    ):
        out["share_baseline_domain"] = out["PP_COLLAB_PARTNER_SHARE_BASELINE_FRAC"]
    if "DPP_COLLAB_PARTNER_SHARE_CHANGE_FRAC" in out.columns and "dpp_share_change_domain" not in out.columns:
        out["dpp_share_change_domain"] = out["DPP_COLLAB_PARTNER_SHARE_CHANGE_FRAC"]
    return out


def round_float_columns_for_stable_csv(
    df: pd.DataFrame,
    digits: int = CSV_STABLE_ROUND_DIGITS,
) -> pd.DataFrame:
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_float_dtype(out[col]):
            out[col] = pd.to_numeric(out[col], errors="coerce").round(digits)
    return out
