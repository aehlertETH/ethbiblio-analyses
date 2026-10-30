import pandas as pd

from assets.collab_table_style import (
    CHANGE_PP_NEGATIVE_COLOR,
    CHANGE_PP_POSITIVE_COLOR,
    SPARKLINE_HIGHEST_POINT_COLOR,
    SPARKLINE_LOWEST_POINT_COLOR,
)
from core.asset import Asset, INSTITUTION_DISPLAY_ORDER
from utility import get_indicator_catalog_dict

asset = Asset(script_file=__file__)

YEAR_FIRST = asset.year_first
YEAR_LAST = asset.year_last
YEARS = list(range(YEAR_FIRST, YEAR_LAST + 1))
RECENT_WINDOW = max(1, int(asset.year_range_moving))
RECENT_END = YEAR_LAST
RECENT_START = max(YEAR_FIRST, RECENT_END - RECENT_WINDOW + 1)
BASELINE_START = YEAR_FIRST
BASELINE_END = RECENT_START - 1

DOMAIN_REPORT = "ethdomain"
DOMAIN_MEMBERS = [inst for inst in INSTITUTION_DISPLAY_ORDER if inst != DOMAIN_REPORT]
ALL_INSTITUTIONS = list(INSTITUTION_DISPLAY_ORDER)

ALL_PUBLICATIONS_KEY = "all_publications"

DOMESTIC_PARTNER_SCOPE_KEY = "domestic_partner_scope"
EUROPEAN_PARTNER_SCOPE_KEY = "european_partner_scope"
BROADER_INTERNATIONAL_PARTNER_SCOPE_KEY = "broader_international_partner_scope"

SUMMARY_ROW_SPECS = [
    (1, ALL_PUBLICATIONS_KEY, "All publications", None),
    (
        2,
        "no_partner_institutions",
        "No institutional collaborations",
        ["no_partner_institutions"],
    ),
    (
        2.5,
        DOMESTIC_PARTNER_SCOPE_KEY,
        "Swiss collaborations",
        [
            "eth_domain_only",
            "other_swiss_only_no_eth_domain",
            "eth_domain_plus_other_swiss_only",
        ],
    ),
    (3, "eth_domain_only", "ETH Domain only", ["eth_domain_only"]),
    (
        4,
        "other_swiss_only_no_eth_domain",
        "Swiss (outside ETH Domain) only",
        ["other_swiss_only_no_eth_domain"],
    ),
    (
        5,
        "eth_domain_plus_other_swiss_only",
        "Swiss (ETH Domain and others)",
        ["eth_domain_plus_other_swiss_only"],
    ),
    (
        5.5,
        EUROPEAN_PARTNER_SCOPE_KEY,
        "European collaborations",
        [
            "europe_only_no_swiss",
            "swiss_plus_europe_only",
        ],
    ),
    (6, "europe_only_no_swiss", "European only", ["europe_only_no_swiss"]),
    (7, "swiss_plus_europe_only", "Swiss + European", ["swiss_plus_europe_only"]),
    (
        7.5,
        BROADER_INTERNATIONAL_PARTNER_SCOPE_KEY,
        "Global collaborations",
        [
            "non_europe_only_no_swiss_or_europe",
            "europe_plus_non_europe_no_swiss",
            "swiss_europe_non_europe",
        ],
    ),
    (
        8,
        "non_europe_only_no_swiss_or_europe",
        "Non-European only",
        ["non_europe_only_no_swiss_or_europe"],
    ),
    (
        9,
        "europe_plus_non_europe_no_swiss",
        "European + non-European",
        ["europe_plus_non_europe_no_swiss"],
    ),
    (
        10,
        "swiss_europe_non_europe",
        "Swiss + European + non-European",
        ["swiss_europe_non_europe"],
    ),
]

TABLE_DISPLAY_ROWS = [
    {"type": "all", "scope_key": ALL_PUBLICATIONS_KEY, "indent": 0},
    {
        "type": "leaf",
        "scope_key": "no_partner_institutions",
        "indent": 0,
        "label": "No institutional collaborations",
        "bold": True,
        "row_background": "group",
    },
    {"type": "group", "scope_key": DOMESTIC_PARTNER_SCOPE_KEY, "indent": 0},
    {"type": "leaf", "scope_key": "eth_domain_only", "indent": 1},
    {"type": "leaf", "scope_key": "other_swiss_only_no_eth_domain", "indent": 1},
    {"type": "leaf", "scope_key": "eth_domain_plus_other_swiss_only", "indent": 1},
    {"type": "group", "scope_key": EUROPEAN_PARTNER_SCOPE_KEY, "indent": 0},
    {"type": "leaf", "scope_key": "europe_only_no_swiss", "indent": 1},
    {"type": "leaf", "scope_key": "swiss_plus_europe_only", "indent": 1},
    {
        "type": "group",
        "scope_key": BROADER_INTERNATIONAL_PARTNER_SCOPE_KEY,
        "indent": 0,
    },
    {"type": "leaf", "scope_key": "non_europe_only_no_swiss_or_europe", "indent": 1},
    {"type": "leaf", "scope_key": "europe_plus_non_europe_no_swiss", "indent": 1},
    {"type": "leaf", "scope_key": "swiss_europe_non_europe", "indent": 1},
]

IND_CHANGE = "DPP_COLLAB_SCOPE_SHARE_CHANGE_FULL"
CHANGE_SHARE_COUNTING_MODE = "full"  # allowed: frac | full

SHOW_SPARKLINE_ETHDOMAIN = True
SHOW_SPARKLINE_UNITS = True
SHOW_CHANGE_ETHDOMAIN = True
SHOW_CHANGE_UNITS = True

SPARKLINE_COLOR_BY_TREND_ETHDOMAIN = False
SPARKLINE_COLOR_BY_TREND_UNITS = False

SHOW_ROW_BACKGROUND_STRIPES_ETHDOMAIN = True
SHOW_ROW_BACKGROUND_STRIPES_UNITS = True

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

SHOW_SPARKLINE_MARK_EXTREMA_POINTS_ETHDOMAIN = True
SHOW_SPARKLINE_MARK_EXTREMA_POINTS_UNITS = True
SHOW_SPARKLINE_MARK_HIGHEST_POINT = True
SHOW_SPARKLINE_MARK_LOWEST_POINT = True
SPARKLINE_HIGHEST_POINT_RADIUS_PT = 1.1
SPARKLINE_LOWEST_POINT_RADIUS_PT = 1.1

COLOR_CHANGE_PP_BY_SIGN = True
SHOW_CHANGE_PP_BAR = True
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

TABLE_COLUMN_SPEC = "@{}L{6.2cm}rrC{2.35cm}cR{1.45cm}R{1.45cm}@{}"
TABLE_NOTE_TEXT = (
    r"``European'' refers to partners in Europe outside Switzerland. "
    r"``Non-European'' refers to partners outside Europe and Switzerland. Thus, ``European + non-European'' excludes other Swiss partners, "
    r"whereas ``Swiss + European + non-European'' includes all three collaboration scopes."
)

TABLE_ROW_COLOR_ALL = "D3DEEF"
TABLE_ROW_COLOR_GROUP = "EAF0F8"
TABLE_CHILD_INDENT = r"\hspace*{1.2em}"

VOLUME_SHARE_DISPLAY_DIGITS = 1

if CHANGE_SHARE_COUNTING_MODE not in {"frac", "full"}:
    raise ValueError("CHANGE_SHARE_COUNTING_MODE must be one of: frac, full")

indicator_catalog_dict = get_indicator_catalog_dict()


def q_publication_scope_classification(
    inst: str,
    y0: int,
    y1: int,
    domain_members: list[str],
) -> str:
    domain_member_list_sql = ", ".join(f"'{member}'" for member in domain_members)

    return f"""
        WITH own_inst_ids AS (
            SELECT DISTINCT institution_id
            FROM reports.report_institutions_ids
            WHERE report_name = '{inst}'
        ),
        domain_inst_ids AS (
            SELECT DISTINCT institution_id
            FROM reports.report_institutions_ids
            WHERE report_name IN ({domain_member_list_sql})
        ),
        inst_works AS (
            SELECT DISTINCT
                rm.work_id,
                wm.publication_year,
                wm.number_authors_on_work,
                wm.n_institutions_on_work,
                wm.norm_vs_mean,
                wm.cohort_is_reliable,
                CAST(wm.is_top10 AS INT) AS is_top10
            FROM reports.report_membership rm
            JOIN marts.work_metrics wm
              ON wm.work_id = rm.work_id
            WHERE rm.report_name = '{inst}'
              AND wm.publication_year BETWEEN {y0} AND {y1}
              AND wm.n_institutions_on_work > 0
        ),
        unit_membership AS (
            SELECT
                iw.work_id,
                COUNT(DISTINCT rm.report_name) AS n_eth_domain_units
            FROM inst_works iw
            LEFT JOIN reports.report_membership rm
              ON rm.work_id = iw.work_id
             AND rm.report_name IN ({domain_member_list_sql})
            GROUP BY iw.work_id
        ),
        own_work_weights AS (
            SELECT
                iw.work_id,
                COALESCE(SUM(wii.weight_frac), 0.0) AS own_weight_frac_raw
            FROM inst_works iw
            LEFT JOIN marts.work_institution_info wii
              ON wii.work_id = iw.work_id
             AND wii.institution_id IN (SELECT institution_id FROM own_inst_ids)
            GROUP BY iw.work_id
        ),
        partner_rows AS (
            SELECT
                iw.work_id,
                wii.institution_id AS partner_institution_id,
                dc.country_code,
                oac.continent_name
            FROM inst_works iw
            JOIN marts.work_institution_info wii
              ON wii.work_id = iw.work_id
             AND wii.institution_id NOT IN (SELECT institution_id FROM domain_inst_ids)
            LEFT JOIN core.dim_institution di
              ON di.institution_id = wii.institution_id
            LEFT JOIN core.dim_country dc
              ON dc.country_id = di.country_id
            LEFT JOIN augmented.openalex_countries oac
              ON oac.code = dc.country_code
        ),
        work_scope AS (
            SELECT
                iw.work_id,
                iw.publication_year,
                iw.number_authors_on_work,
                iw.n_institutions_on_work,
                iw.norm_vs_mean,
                iw.cohort_is_reliable,
                iw.is_top10,
                COALESCE(um.n_eth_domain_units, 0) AS n_eth_domain_units,
                CASE
                    WHEN ow.own_weight_frac_raw > 0 THEN ow.own_weight_frac_raw
                    ELSE 1.0 / iw.n_institutions_on_work
                END AS p_frac_weight,
                COUNT(DISTINCT pr.partner_institution_id) AS partner_inst_count,
                COALESCE(
                    MAX(
                        CASE
                            WHEN pr.country_code = 'CH' THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS has_other_swiss_partner,
                COALESCE(
                    MAX(
                        CASE
                            WHEN pr.country_code <> 'CH' AND pr.continent_name = 'Europe' THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS has_europe_partner,
                COALESCE(
                    MAX(
                        CASE
                            WHEN pr.partner_institution_id IS NOT NULL
                                 AND (pr.country_code IS NULL OR pr.country_code <> 'CH')
                                 AND (pr.continent_name IS NULL OR pr.continent_name <> 'Europe')
                            THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS has_non_europe_partner
            FROM inst_works iw
            LEFT JOIN unit_membership um
              ON um.work_id = iw.work_id
            LEFT JOIN own_work_weights ow
              ON ow.work_id = iw.work_id
            LEFT JOIN partner_rows pr
              ON pr.work_id = iw.work_id
            GROUP BY
                iw.work_id,
                iw.publication_year,
                iw.number_authors_on_work,
                iw.n_institutions_on_work,
                iw.norm_vs_mean,
                iw.cohort_is_reliable,
                iw.is_top10,
                um.n_eth_domain_units,
                ow.own_weight_frac_raw
        )
        SELECT
            ws.work_id,
            ws.publication_year,
            ws.number_authors_on_work,
            ws.n_institutions_on_work,
            ws.norm_vs_mean,
            ws.cohort_is_reliable,
            ws.is_top10,
            ws.p_frac_weight,
            CASE
                WHEN ws.partner_inst_count = 0
                     AND ws.n_eth_domain_units <= 1
                    THEN 'no_partner_institutions'
                WHEN ws.partner_inst_count = 0
                     AND ws.n_eth_domain_units >= 2
                    THEN 'eth_domain_only'
                WHEN ws.n_eth_domain_units <= 1
                     AND ws.has_other_swiss_partner = 0
                     AND ws.has_europe_partner = 1
                     AND ws.has_non_europe_partner = 0
                    THEN 'europe_only_no_swiss'
                WHEN ws.n_eth_domain_units <= 1
                     AND ws.has_other_swiss_partner = 1
                     AND ws.has_europe_partner = 0
                     AND ws.has_non_europe_partner = 0
                    THEN 'other_swiss_only_no_eth_domain'
                WHEN ws.n_eth_domain_units >= 2
                     AND ws.has_other_swiss_partner = 1
                     AND ws.has_europe_partner = 0
                     AND ws.has_non_europe_partner = 0
                    THEN 'eth_domain_plus_other_swiss_only'
                WHEN (ws.n_eth_domain_units >= 2 OR ws.has_other_swiss_partner = 1)
                     AND ws.has_europe_partner = 1
                     AND ws.has_non_europe_partner = 0
                    THEN 'swiss_plus_europe_only'
                WHEN ws.n_eth_domain_units <= 1
                     AND ws.has_other_swiss_partner = 0
                     AND ws.has_europe_partner = 0
                     AND ws.has_non_europe_partner = 1
                    THEN 'non_europe_only_no_swiss_or_europe'
                WHEN ws.n_eth_domain_units <= 1
                     AND ws.has_other_swiss_partner = 0
                     AND ws.has_europe_partner = 1
                     AND ws.has_non_europe_partner = 1
                    THEN 'europe_plus_non_europe_no_swiss'
                ELSE 'swiss_europe_non_europe'
            END AS scope_key
        FROM work_scope ws;
    """


def ensuremath_wrap(symbol_tex: str) -> str:
    if not symbol_tex:
        return symbol_tex
    if r"\ensuremath{" in symbol_tex:
        return symbol_tex
    return rf"\ensuremath{{{symbol_tex}}}"


def tex_escape(text: str) -> str:
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


def to_bool(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)
    return (
        series.astype("string")
        .str.strip()
        .str.lower()
        .isin({"1", "true", "t", "yes", "y"})
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


def build_rowcolor_command(color: str) -> str:
    raw = str(color).strip()
    if not raw:
        return ""

    hex_color = _normalize_hex_color(raw)
    if hex_color is not None:
        return rf"\rowcolor[HTML]{{{hex_color}}} "

    return rf"\rowcolor{{{raw}}} "


def _hex_to_rgb_components(hex_color: str) -> tuple[int, int, int]:
    return int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)


def build_tikz_fill_color_option(color: str) -> str:
    raw = str(color).strip()
    if not raw:
        return "fill=none"

    hex_color = _normalize_hex_color(raw)
    if hex_color is None:
        return raw

    red, green, blue = _hex_to_rgb_components(hex_color)
    return f"fill={{rgb,255:red,{red};green,{green};blue,{blue}}}"


def build_tikz_draw_color_option(color: str) -> str:
    raw = str(color).strip()
    if not raw:
        return "draw=none"

    hex_color = _normalize_hex_color(raw)
    if hex_color is None:
        return raw

    red, green, blue = _hex_to_rgb_components(hex_color)
    return f"draw={{rgb,255:red,{red};green,{green};blue,{blue}}}"


def build_textcolor_command(text: str, color: str) -> str:
    raw = str(color).strip()
    if not raw:
        return text

    hex_color = _normalize_hex_color(raw)
    if hex_color is not None:
        return rf"\textcolor[HTML]{{{hex_color}}}{{{text}}}"

    return rf"\textcolor{{{raw}}}{{{text}}}"


def fmt_count(value) -> str:
    if value is None or pd.isna(value):
        return r"\textit{n/a}"
    return f"{int(round(float(value))):,}".replace(",", "{,}")


def fmt_frac(value, digits: int = 0) -> str:
    if value is None or pd.isna(value):
        return r"\textit{n/a}"
    return f"{float(value):,.{digits}f}".replace(",", "{,}")


def fmt_float(value, digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return r"\textit{n/a}"
    return f"{float(value):.{digits}f}"


def fmt_pct(value, digits: int = 1) -> str:
    if value is None or pd.isna(value):
        return r"\textit{n/a}"
    pct = f"{100.0 * float(value):.{digits}f}".rstrip("0").rstrip(".")
    return f"{pct}\\%"


def fmt_change_pp(value, digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return r"\textit{n/a}"
    numeric_value = float(value)
    formatted = f"{numeric_value:+.{digits}f}pp"
    if not COLOR_CHANGE_PP_BY_SIGN:
        return formatted
    if numeric_value > 0:
        return build_textcolor_command(formatted, CHANGE_PP_POSITIVE_COLOR)
    if numeric_value < 0:
        return build_textcolor_command(formatted, CHANGE_PP_NEGATIVE_COLOR)
    return formatted


def _format_change_pp_label(label: str) -> str:
    if not CHANGE_PP_LABEL_SMALL:
        return label
    return rf"{{{CHANGE_PP_LABEL_SMALL_COMMAND} {label}}}"


def build_change_pp_cell(value, digits: int = 2, max_abs: float = 0.0) -> str:
    if value is None or pd.isna(value):
        return r"\textit{n/a}"

    numeric_value = float(value)
    text_part = _format_change_pp_label(fmt_change_pp(numeric_value, digits=digits))

    if not SHOW_CHANGE_PP_BAR or max_abs <= 0:
        return text_part

    bar_area_width = max(
        0.0,
        CHANGE_PP_BAR_CELL_WIDTH_MM
        - CHANGE_PP_BAR_LABEL_WIDTH_MM
        - CHANGE_PP_BAR_GAP_MM,
    )
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

    fill_option = build_tikz_fill_color_option(bar_color)
    axis_draw_option = build_tikz_draw_color_option(CHANGE_PP_BAR_AXIS_COLOR)

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

    first = values[0]
    last = values[-1]
    diff = last - first

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

    return [max(value, 0.0) / max_value for value in values]


def build_sparkline_cell(
    row: pd.Series,
    years: list[int],
    *,
    color_by_trend: bool,
    show_extrema_points: bool,
) -> str:
    values = []
    for year in years:
        value = row.get(f"full_count_y_{year}")
        values.append(float(value) if pd.notna(value) else 0.0)

    if len(values) < 2:
        return r"\textit{n/a}"

    normalized = _normalize_sparkline_values(values)
    if len(normalized) < 2:
        return r"\textit{n/a}"

    line_color, fill_color = _sparkline_colors(values, color_by_trend=color_by_trend)
    fill_color_option = build_tikz_fill_color_option(fill_color)
    line_color_option = build_tikz_draw_color_option(line_color)
    step = 1.0 / (len(normalized) - 1)
    coords = [f"({idx * step:.4f},{value:.4f})" for idx, value in enumerate(normalized)]
    coords_path = " -- ".join(coords)

    marker_commands = ""
    if show_extrema_points:
        max_idx = values.index(max(values))
        min_idx = values.index(min(values))

        if SHOW_SPARKLINE_MARK_HIGHEST_POINT:
            x_max = max_idx * step
            y_max = normalized[max_idx]
            highest_fill_option = build_tikz_fill_color_option(
                SPARKLINE_HIGHEST_POINT_COLOR
            )
            highest_draw_option = build_tikz_draw_color_option(
                SPARKLINE_HIGHEST_POINT_COLOR
            )
            marker_commands += (
                rf"\filldraw[{highest_fill_option},{highest_draw_option}] "
                rf"({x_max:.4f},{y_max:.4f}) circle[radius={SPARKLINE_HIGHEST_POINT_RADIUS_PT}pt];"
            )

        if SHOW_SPARKLINE_MARK_LOWEST_POINT and (
            min_idx != max_idx or not SHOW_SPARKLINE_MARK_HIGHEST_POINT
        ):
            x_min = min_idx * step
            y_min = normalized[min_idx]
            lowest_fill_option = build_tikz_fill_color_option(
                SPARKLINE_LOWEST_POINT_COLOR
            )
            lowest_draw_option = build_tikz_draw_color_option(
                SPARKLINE_LOWEST_POINT_COLOR
            )
            marker_commands += (
                rf"\filldraw[{lowest_fill_option},{lowest_draw_option}] "
                rf"({x_min:.4f},{y_min:.4f}) circle[radius={SPARKLINE_LOWEST_POINT_RADIUS_PT}pt];"
            )

    tikz = (
        rf"\begin{{tikzpicture}}[x={SPARKLINE_WIDTH_MM}mm,y={SPARKLINE_HEIGHT_MM}mm,baseline=(current bounding box.south)]"
        rf"\fill[{fill_color_option}] (0,0) -- {coords_path} -- (1,0) -- cycle;"
        rf"\draw[{line_color_option}, line width={SPARKLINE_LINE_WIDTH_PT}pt] {coords_path};"
        f"{marker_commands}" + r"\end{tikzpicture}"
    )
    return rf"\raisebox{{{SPARKLINE_VERTICAL_SHIFT_EX}ex}}{{{tikz}}}"


def table_options_for_inst(inst: str) -> dict[str, bool]:
    is_domain = inst == DOMAIN_REPORT
    return {
        "show_change": SHOW_CHANGE_ETHDOMAIN if is_domain else SHOW_CHANGE_UNITS,
        "show_sparkline": SHOW_SPARKLINE_ETHDOMAIN
        if is_domain
        else SHOW_SPARKLINE_UNITS,
        "sparkline_color_by_trend": (
            SPARKLINE_COLOR_BY_TREND_ETHDOMAIN
            if is_domain
            else SPARKLINE_COLOR_BY_TREND_UNITS
        ),
        "show_row_background_stripes": (
            SHOW_ROW_BACKGROUND_STRIPES_ETHDOMAIN
            if is_domain
            else SHOW_ROW_BACKGROUND_STRIPES_UNITS
        ),
        "sparkline_mark_extrema_points": (
            SHOW_SPARKLINE_MARK_EXTREMA_POINTS_ETHDOMAIN
            if is_domain
            else SHOW_SPARKLINE_MARK_EXTREMA_POINTS_UNITS
        ),
    }


def compute_scope_summary(work_df: pd.DataFrame, years: list[int]) -> pd.DataFrame:
    out = work_df.copy()
    numeric_cols = [
        "publication_year",
        "number_authors_on_work",
        "n_institutions_on_work",
        "norm_vs_mean",
        "is_top10",
        "p_frac_weight",
    ]
    out[numeric_cols] = out[numeric_cols].apply(pd.to_numeric, errors="coerce")
    out["cohort_is_reliable"] = to_bool(out["cohort_is_reliable"])
    out["scope_key"] = out["scope_key"].astype(str)

    recent_mask = (out["publication_year"] >= RECENT_START) & (
        out["publication_year"] <= RECENT_END
    )
    baseline_mask = (out["publication_year"] >= BASELINE_START) & (
        out["publication_year"] <= BASELINE_END
    )

    if CHANGE_SHARE_COUNTING_MODE == "full":
        total_recent = float(recent_mask.sum())
        total_baseline = float(baseline_mask.sum())
    else:
        total_recent = float(out.loc[recent_mask, "p_frac_weight"].sum())
        total_baseline = float(out.loc[baseline_mask, "p_frac_weight"].sum())
    total_p_full_all = float(out["work_id"].nunique())

    rows = []
    for row_order, scope_key, scope_label, member_scope_keys in SUMMARY_ROW_SPECS:
        if member_scope_keys is None:
            sub = out
        else:
            sub = out[out["scope_key"].isin(member_scope_keys)]

        p_full = int(sub["work_id"].nunique())
        p_frac = float(sub["p_frac_weight"].sum())

        if CHANGE_SHARE_COUNTING_MODE == "full":
            cat_recent = float(
                (
                    (sub["publication_year"] >= RECENT_START)
                    & (sub["publication_year"] <= RECENT_END)
                ).sum()
            )
            cat_baseline = float(
                (
                    (sub["publication_year"] >= BASELINE_START)
                    & (sub["publication_year"] <= BASELINE_END)
                ).sum()
            )
        else:
            cat_recent = float(
                sub.loc[
                    (sub["publication_year"] >= RECENT_START)
                    & (sub["publication_year"] <= RECENT_END),
                    "p_frac_weight",
                ].sum()
            )
            cat_baseline = float(
                sub.loc[
                    (sub["publication_year"] >= BASELINE_START)
                    & (sub["publication_year"] <= BASELINE_END),
                    "p_frac_weight",
                ].sum()
            )

        share_recent = cat_recent / total_recent if total_recent > 0 else 0.0
        share_baseline = cat_baseline / total_baseline if total_baseline > 0 else 0.0
        dpp_share_change = (
            (share_recent - share_baseline) * 100.0 if total_baseline > 0 else pd.NA
        )

        med_authors = sub["number_authors_on_work"].median() if p_full > 0 else pd.NA
        med_institutions = (
            sub["n_institutions_on_work"].median() if p_full > 0 else pd.NA
        )

        sub_rel = sub[sub["cohort_is_reliable"]].copy()
        weight_sum = float(sub_rel["p_frac_weight"].sum())
        if weight_sum > 0:
            mncs_frac = float(
                (sub_rel["p_frac_weight"] * sub_rel["norm_vs_mean"]).sum() / weight_sum
            )
            pp_top10_frac = float(
                (sub_rel["p_frac_weight"] * sub_rel["is_top10"]).sum() / weight_sum
            )
        else:
            mncs_frac = pd.NA
            pp_top10_frac = pd.NA

        row_data = {
            "row_order": row_order,
            "scope_key": scope_key,
            "scope_label": scope_label,
            "p_full": p_full,
            "p_frac": p_frac,
            "volume_share_full": (p_full / total_p_full_all)
            if total_p_full_all > 0
            else pd.NA,
            "share_recent": share_recent,
            "share_baseline": share_baseline,
            "dpp_share_change": dpp_share_change,
            "med_authors": med_authors,
            "med_institutions": med_institutions,
            "mncs_frac": mncs_frac,
            "pp_top10_frac": pp_top10_frac,
            "recent_start": RECENT_START,
            "recent_end": RECENT_END,
            "baseline_start": BASELINE_START,
            "baseline_end": BASELINE_END,
            "change_share_counting_mode": CHANGE_SHARE_COUNTING_MODE,
        }

        for year in years:
            row_data[f"full_count_y_{year}"] = float(
                (sub["publication_year"] == year).sum()
            )

        rows.append(row_data)

    summary = pd.DataFrame(rows).sort_values("row_order").reset_index(drop=True)
    return summary


def build_table_tex(df: pd.DataFrame, inst: str, years: list[int]) -> str:
    options = table_options_for_inst(inst)
    show_change = options["show_change"]
    show_sparkline = options["show_sparkline"]
    sparkline_color_by_trend = options["sparkline_color_by_trend"]
    sparkline_mark_extrema_points = options["sparkline_mark_extrema_points"]

    pfull_symbol = (
        (indicator_catalog_dict.get("P_FULL", {}) or {}).get("symbol_tex", "").strip()
    )
    mncs_symbol = (
        (indicator_catalog_dict.get("COLLAB_IMPACT_MNCS_FRAC", {}) or {})
        .get("symbol_tex", "")
        .strip()
    )
    pp_symbol = (
        (indicator_catalog_dict.get("COLLAB_IMPACT_PP_TOPTEN_FRAC", {}) or {})
        .get("symbol_tex", "")
        .strip()
    )

    pfull_label = (
        ensuremath_wrap(pfull_symbol)
        if pfull_symbol
        else r"\ensuremath{\mathrm{P}_{\mathrm{full}}}"
    )
    mncs_label = ensuremath_wrap(mncs_symbol) if mncs_symbol else "MNCS"
    pp_label = ensuremath_wrap(pp_symbol) if pp_symbol else "PPtop10"

    change_digits = parse_display_digits(
        (indicator_catalog_dict.get(IND_CHANGE, {}) or {}).get("display_digits"), 2
    )
    mncs_digits = parse_display_digits(
        (indicator_catalog_dict.get("COLLAB_IMPACT_MNCS_FRAC", {}) or {}).get(
            "display_digits"
        ),
        2,
    )
    pp_digits = max(
        1,
        parse_display_digits(
            (indicator_catalog_dict.get("COLLAB_IMPACT_PP_TOPTEN_FRAC", {}) or {}).get(
                "display_digits"
            ),
            1,
        ),
    )

    change_header = rf"Change ({RECENT_WINDOW}y)"
    trend_header = "Trend"
    if not show_sparkline:
        trend_header = r""
    if not show_change:
        change_header = r""

    change_scale_max = 0.0
    if show_change and SHOW_CHANGE_PP_BAR:
        change_series = pd.to_numeric(df.get("dpp_share_change"), errors="coerce")
        if change_series is not None and not change_series.empty:
            change_scale_max = float(change_series.abs().max())
            if pd.isna(change_scale_max):
                change_scale_max = 0.0

    lines = [
        r"\resizebox{\linewidth}{!}{%",
        r"\begin{tabular}{" + TABLE_COLUMN_SPEC + r"}",
        r"  \toprule",
        r"  \multicolumn{1}{c}{\textbf{Collaboration Scope}} & \multicolumn{4}{c}{\textbf{Output}} & \multicolumn{2}{c}{\textbf{Impact}} \\",
        r"  \cmidrule(lr){1-1} \cmidrule(lr){2-5} \cmidrule(lr){6-7}",
        r"  Scope & "
        + pfull_label
        + r" & Share & "
        + change_header
        + r" & "
        + trend_header
        + r" & "
        + mncs_label
        + r" & "
        + pp_label
        + r" \\",
        r"  \midrule",
    ]

    rows_by_key = df.set_index("scope_key").to_dict("index")

    for display_row in TABLE_DISPLAY_ROWS:
        row = rows_by_key[display_row["scope_key"]]
        row_type = display_row["type"]
        if row_type == "group":
            lines.append(r"  \addlinespace[0.2em]")

        scope_label = tex_escape(display_row.get("label", row.get("scope_label", "")))
        if display_row.get("indent", 0) > 0:
            scope_label = TABLE_CHILD_INDENT + scope_label
        if row_type in {"all", "group"} or display_row.get("bold", False):
            scope_label = rf"\textbf{{{scope_label}}}"

        p_full_cell = fmt_count(row.get("p_full"))
        volume_share_cell = fmt_pct(
            row.get("volume_share_full"), digits=VOLUME_SHARE_DISPLAY_DIGITS
        )
        mncs_cell = fmt_float(row.get("mncs_frac"), digits=mncs_digits)
        pp_cell = fmt_pct(row.get("pp_top10_frac"), digits=pp_digits)

        trend_cell = (
            build_sparkline_cell(
                row,
                years,
                color_by_trend=sparkline_color_by_trend,
                show_extrema_points=sparkline_mark_extrema_points,
            )
            if show_sparkline
            else ""
        )
        change_cell = (
            build_change_pp_cell(
                row.get("dpp_share_change"),
                digits=change_digits,
                max_abs=change_scale_max,
            )
            if show_change
            else ""
        )

        cells = [
            scope_label,
            p_full_cell,
            volume_share_cell,
            change_cell,
            trend_cell,
            mncs_cell,
            pp_cell,
        ]

        row_prefix = "  "
        if row_type == "all":
            row_prefix += build_rowcolor_command(TABLE_ROW_COLOR_ALL)
        elif row_type == "group" or display_row.get("row_background") == "group":
            row_prefix += build_rowcolor_command(TABLE_ROW_COLOR_GROUP)

        lines.append(row_prefix + " & ".join(cells) + r" \\")

    lines.extend(
        [
            r"\bottomrule",
            r"\end{tabular}%",
            r"}",
            r"\vspace{0.4em}",
            r"\begin{minipage}{\linewidth}",
            r"  \tiny",
            rf"  \textit{{Note:}} {TABLE_NOTE_TEXT}",
            r"\end{minipage}",
        ]
    )
    return "\n".join(lines) + "\n"


def _prepare_numeric_export(df_in: pd.DataFrame) -> pd.DataFrame:
    out_df = df_in.copy()
    numeric_cols = [
        col
        for col in out_df.columns
        if col not in {"scope_key", "scope_label", "change_share_counting_mode"}
    ]
    out_df[numeric_cols] = out_df[numeric_cols].apply(pd.to_numeric, errors="coerce")

    full_year_cols = [col for col in out_df.columns if col.startswith("full_count_y_")]
    round_map = {
        "p_frac": 2,
        "volume_share_full": 4,
        "share_recent": 4,
        "share_baseline": 4,
        "dpp_share_change": 2,
        "med_authors": 2,
        "med_institutions": 2,
        "mncs_frac": 3,
        "pp_top10_frac": 3,
    }
    for col in full_year_cols:
        round_map[col] = 2

    for col, digits in round_map.items():
        if col in out_df.columns:
            out_df[col] = pd.to_numeric(out_df[col], errors="coerce").round(digits)

    if "row_order" in out_df.columns:
        out_df["row_order"] = (
            pd.to_numeric(out_df["row_order"], errors="coerce").round(0).astype("Int64")
        )

    out_df = out_df.rename(
        columns={
            "p_full": "P_FULL",
            "p_frac": "P_FRAC",
            "dpp_share_change": IND_CHANGE,
            "mncs_frac": "COLLAB_IMPACT_MNCS_FRAC",
            "pp_top10_frac": "COLLAB_IMPACT_PP_TOPTEN_FRAC",
        }
    )
    return out_df


def main() -> None:
    for inst, con in asset.iterate_institutions():
        work_df = con.execute(
            q_publication_scope_classification(
                inst,
                YEAR_FIRST,
                YEAR_LAST,
                DOMAIN_MEMBERS,
            )
        ).df()

        summary_df = compute_scope_summary(work_df, YEARS)
        export_df = _prepare_numeric_export(summary_df)

        out = asset.inst_dir(inst)
        export_df.to_csv(out / "data_raw.csv", index=False)
        export_df.to_csv(out / "data_prepost.csv", index=False)
        export_df.to_csv(out / "data.csv", index=False)

        table_tex = build_table_tex(summary_df, inst, YEARS)
        (out / "table.tex").write_text(table_tex, encoding="utf-8")

        print(inst, "-> scope decomposition table exported")


if __name__ == "__main__":
    main()
