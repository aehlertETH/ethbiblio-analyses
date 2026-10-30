import pandas as pd

from assets.collab_table_style import (
    CHANGE_PP_NEGATIVE_COLOR,
    CHANGE_PP_POSITIVE_COLOR,
    ROW_BACKGROUND_COLOR_EVEN,
    ROW_BACKGROUND_COLOR_ODD,
    SPARKLINE_HIGHEST_POINT_COLOR,
    SPARKLINE_LOWEST_POINT_COLOR,
)
from core.asset import Asset, INSTITUTION_DISPLAY_ORDER
from utility import (
    full_country_name,
    get_indicator_catalog_dict,
    get_unit_params_dict,
    shorten_country_name,
)

asset = Asset(script_file=__file__)

TOP_N = 30
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

IND_SHARE = "PP_COLLAB_COUNTRY_SHARE_FULL"
IND_SHARE_RECENT = "PP_COLLAB_COUNTRY_SHARE_RECENT_FULL"
IND_SHARE_BASELINE = "PP_COLLAB_COUNTRY_SHARE_BASELINE_FULL"
IND_CHANGE = "DPP_COLLAB_COUNTRY_SHARE_CHANGE_FULL"
IND_IMPACT_MNCS = "COLLAB_IMPACT_MNCS_FRAC"
IND_IMPACT_PP = "COLLAB_IMPACT_PP_TOPTEN_FRAC"

COUNT_COL = "collab_work_count"
SHARE_COL = "share"
CHANGE_COL = "share_change_pp"
MNCS_COL = "mncs"
PP_COL = "pp_top10"

SHOW_DECOMPOSED_COUNTS_ETHDOMAIN = True
SHOW_DECOMPOSED_COUNTS_UNITS = False

SHOW_INTENSITY_CHANGE_ETHDOMAIN = True
SHOW_INTENSITY_CHANGE_UNITS = True

SHOW_SPARKLINE_ETHDOMAIN = True
SHOW_SPARKLINE_UNITS = True

# Sparkline/change placement options: after_name, after_cc, after_pfrac,
# after_intensity, after_trend, after_change, after_mncs, after_pp, end
TREND_COLUMN_POSITION = "after_change"
CHANGE_COLUMN_POSITION = "after_intensity"

SPARKLINE_COLOR_BY_TREND_ETHDOMAIN = False
SPARKLINE_COLOR_BY_TREND_UNITS = False

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

SHOW_ROW_BACKGROUND_STRIPES_ETHDOMAIN = True
SHOW_ROW_BACKGROUND_STRIPES_UNITS = True

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
TABLE_COLUMN_SPEC_UNITS = {
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
TABLE_COLUMN_SPEC_ETHDOMAIN = {
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
DECOMPOSITION_COLUMN_SPEC = "r"


"""
How to use this asset script:

1) Extract country-level external collaboration links in one query.
2) Compute full-period intensity share + recent-vs-baseline change.
3) Keep output indicator-ready for LaTeX access via indicator-assets pipeline.
4) Render table per institution so ETH Domain and unit reports can differ.
"""

unit_params_dict = get_unit_params_dict()
indicator_catalog_dict = get_indicator_catalog_dict()


def count_year_col(year: int) -> str:
    return f"{COUNT_COL}_y_{year}"


def member_count_col(member: str) -> str:
    return f"{COUNT_COL}_{member}"


def get_display_digits() -> dict[str, int]:
    return {
        "share": parse_display_digits(
            (indicator_catalog_dict.get(IND_SHARE, {}) or {}).get("display_digits"),
            2,
        ),
        "change": parse_display_digits(
            (indicator_catalog_dict.get(IND_CHANGE, {}) or {}).get("display_digits"),
            2,
        ),
        "mncs": parse_display_digits(
            (indicator_catalog_dict.get(IND_IMPACT_MNCS, {}) or {}).get(
                "display_digits"
            ),
            2,
        ),
        "pp": max(
            1,
            parse_display_digits(
                (indicator_catalog_dict.get(IND_IMPACT_PP, {}) or {}).get(
                    "display_digits"
                ),
                1,
            ),
        ),
    }


def q_top_external_countries(
    y0: int,
    y1: int,
    years: list[int],
    recent_start: int,
    recent_end: int,
    baseline_start: int,
    baseline_end: int,
    members: list[str],
    domain_report: str,
) -> str:
    member_list_sql = ", ".join(f"'{m}'" for m in members)

    member_case_cols = []
    member_select_cols = []
    for m in members:
        member_case_cols.extend(
            [
                f"SUM(CASE WHEN mcl.domain_member = '{m}' THEN 1 ELSE 0 END) AS frac_{m}",
                (
                    f"SUM(CASE WHEN mcl.domain_member = '{m}' "
                    f"AND mcl.publication_year BETWEEN {recent_start} AND {recent_end} "
                    f"THEN 1 ELSE 0 END) AS frac_recent_{m}"
                ),
                (
                    f"SUM(CASE WHEN mcl.domain_member = '{m}' "
                    f"AND mcl.publication_year BETWEEN {baseline_start} AND {baseline_end} "
                    f"THEN 1 ELSE 0 END) AS frac_baseline_{m}"
                ),
                (
                    f"SUM(CASE WHEN mcl.domain_member = '{m}' AND wm.cohort_is_reliable = TRUE "
                    f"THEN mcl.own_weight_frac * wm.norm_vs_mean ELSE 0 END) "
                    f"/ NULLIF(SUM(CASE WHEN mcl.domain_member = '{m}' AND wm.cohort_is_reliable = TRUE "
                    f"THEN mcl.own_weight_frac ELSE 0 END), 0) AS mncs_{m}"
                ),
                (
                    f"SUM(CASE WHEN mcl.domain_member = '{m}' AND wm.cohort_is_reliable = TRUE "
                    f"THEN mcl.own_weight_frac * CAST(wm.is_top10 AS DOUBLE) ELSE 0 END) "
                    f"/ NULLIF(SUM(CASE WHEN mcl.domain_member = '{m}' AND wm.cohort_is_reliable = TRUE "
                    f"THEN mcl.own_weight_frac ELSE 0 END), 0) AS pp_top10_{m}"
                ),
            ]
        )

        for year in years:
            member_case_cols.append(
                (
                    f"SUM(CASE WHEN mcl.domain_member = '{m}' "
                    f"AND mcl.publication_year = {year} "
                    f"THEN 1 ELSE 0 END) AS frac_y_{year}_{m}"
                )
            )

        member_select_cols.extend(
            [
                f"ROUND(ma.frac_{m}, 6) AS frac_{m}",
                f"ROUND(ma.frac_recent_{m}, 6) AS frac_recent_{m}",
                f"ROUND(ma.frac_baseline_{m}, 6) AS frac_baseline_{m}",
                f"ROUND(ma.mncs_{m}, 6) AS mncs_{m}",
                f"ROUND(ma.pp_top10_{m}, 6) AS pp_top10_{m}",
                (
                    f"ROUND((SELECT p_output_full FROM member_output_totals "
                    f"WHERE domain_member = '{m}'), 6) AS p_output_full_{m}"
                ),
                (
                    f"ROUND((SELECT p_output_full_recent FROM member_output_totals "
                    f"WHERE domain_member = '{m}'), 6) AS p_output_full_recent_{m}"
                ),
                (
                    f"ROUND((SELECT p_output_full_baseline FROM member_output_totals "
                    f"WHERE domain_member = '{m}'), 6) AS p_output_full_baseline_{m}"
                ),
            ]
        )

        for year in years:
            member_select_cols.append(
                f"ROUND(ma.frac_y_{year}_{m}, 6) AS frac_y_{year}_{m}"
            )

    year_case_cols = [
        (
            f"SUM(CASE WHEN ocl.publication_year = {year} "
            f"THEN 1 ELSE 0 END) AS frac_y_{year}"
        )
        for year in years
    ]
    year_select_cols = [
        f"ROUND(oa.frac_y_{year}, 6) AS frac_y_{year}" for year in years
    ]
    year_select_cols_coalesce_sql = ",\n            ".join(
        [f"ROUND(COALESCE(oa.frac_y_{year}, 0), 6) AS frac_y_{year}" for year in years]
    )

    member_case_cols_sql = ",\n                ".join(member_case_cols)
    member_select_cols_sql = ",\n            ".join(member_select_cols)
    year_case_cols_sql = ",\n                ".join(year_case_cols)
    year_select_cols_sql = ",\n            ".join(year_select_cols)

    return f"""
        WITH domain_inst_ids AS (
            SELECT DISTINCT institution_id
            FROM reports.report_institutions_ids
            WHERE report_name = '{domain_report}'
        ),
        domain_works_dedup AS (
            SELECT DISTINCT
                rm.work_id,
                wm.publication_year,
                wm.n_institutions_on_work
            FROM reports.report_membership rm
            JOIN marts.work_metrics wm
              ON wm.work_id = rm.work_id
            WHERE rm.report_name = '{domain_report}'
              AND wm.publication_year BETWEEN {y0} AND {y1}
              AND wm.n_institutions_on_work > 0
        ),
        domain_work_weights AS (
            SELECT
                dw.work_id,
                COALESCE(SUM(wii.weight_frac), 0.0) AS own_weight_frac_raw
            FROM domain_works_dedup dw
            LEFT JOIN marts.work_institution_info wii
              ON wii.work_id = dw.work_id
             AND wii.institution_id IN (SELECT institution_id FROM domain_inst_ids)
            GROUP BY dw.work_id
        ),
        overall_partner_institutions AS (
            SELECT DISTINCT
                dw.work_id,
                dw.publication_year,
                wii.institution_id,
                CASE
                    WHEN dww.own_weight_frac_raw > 0 THEN dww.own_weight_frac_raw
                    ELSE 1.0 / dw.n_institutions_on_work
                END AS own_weight_frac
            FROM domain_works_dedup dw
            JOIN domain_work_weights dww
              ON dww.work_id = dw.work_id
            JOIN marts.work_institution_info wii
              ON wii.work_id = dw.work_id
            LEFT JOIN reports.report_institutions_ids rii
              ON rii.report_name = '{domain_report}'
             AND rii.institution_id = wii.institution_id
            WHERE rii.institution_id IS NULL
        ),
        member_works AS (
            SELECT DISTINCT
                rm.report_name AS domain_member,
                rm.work_id,
                wm.publication_year,
                wm.n_institutions_on_work
            FROM reports.report_membership rm
            JOIN marts.work_metrics wm
              ON wm.work_id = rm.work_id
            WHERE rm.report_name IN ({member_list_sql})
              AND wm.publication_year BETWEEN {y0} AND {y1}
              AND wm.n_institutions_on_work > 0
        ),
        member_inst_ids AS (
            SELECT DISTINCT
                report_name AS domain_member,
                institution_id
            FROM reports.report_institutions_ids
            WHERE report_name IN ({member_list_sql})
        ),
        member_work_weights AS (
            SELECT
                mw.domain_member,
                mw.work_id,
                COALESCE(SUM(wii.weight_frac), 0.0) AS own_weight_frac_raw
            FROM member_works mw
            JOIN member_inst_ids mii
              ON mii.domain_member = mw.domain_member
            LEFT JOIN marts.work_institution_info wii
              ON wii.work_id = mw.work_id
             AND wii.institution_id = mii.institution_id
            GROUP BY mw.domain_member, mw.work_id
        ),
        member_partner_institutions AS (
            SELECT DISTINCT
                mw.domain_member,
                mw.work_id,
                mw.publication_year,
                wii.institution_id,
                CASE
                    WHEN mww.own_weight_frac_raw > 0 THEN mww.own_weight_frac_raw
                    ELSE 1.0 / mw.n_institutions_on_work
                END AS own_weight_frac
            FROM member_works mw
            JOIN member_work_weights mww
              ON mww.domain_member = mw.domain_member
             AND mww.work_id = mw.work_id
            JOIN marts.work_institution_info wii
              ON wii.work_id = mw.work_id
            LEFT JOIN reports.report_institutions_ids rii
              ON rii.report_name = mw.domain_member
             AND rii.institution_id = wii.institution_id
            WHERE rii.institution_id IS NULL
        ),
        overall_country_links_dedup AS (
            SELECT DISTINCT
                dc.country_code,
                COALESCE(oac.display_name, dc.country_code) AS country_name,
                opi.work_id,
                opi.publication_year,
                opi.own_weight_frac
            FROM overall_partner_institutions opi
            JOIN core.dim_institution di
              ON di.institution_id = opi.institution_id
            JOIN core.dim_country dc
              ON dc.country_id = di.country_id
            LEFT JOIN augmented.openalex_countries oac
              ON oac.code = dc.country_code
            WHERE dc.country_code IS NOT NULL
        ),
        member_country_links AS (
            SELECT DISTINCT
                mpi.domain_member,
                dc.country_code,
                COALESCE(oac.display_name, dc.country_code) AS country_name,
                mpi.work_id,
                mpi.publication_year,
                mpi.own_weight_frac
            FROM member_partner_institutions mpi
            JOIN core.dim_institution di
              ON di.institution_id = mpi.institution_id
            JOIN core.dim_country dc
              ON dc.country_id = di.country_id
            LEFT JOIN augmented.openalex_countries oac
              ON oac.code = dc.country_code
            WHERE dc.country_code IS NOT NULL
        ),
        overall_output_totals AS (
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
            FROM domain_works_dedup
        ),
        member_output_totals AS (
            SELECT
                domain_member,
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
            FROM member_works
            GROUP BY domain_member
        ),
        overall_agg AS (
            SELECT
                ocl.country_code,
                ocl.country_name,
                COUNT(*) AS frac_count_dedup,
                SUM(
                    CASE
                        WHEN ocl.publication_year BETWEEN {recent_start} AND {recent_end}
                        THEN 1
                        ELSE 0
                    END
                ) AS frac_recent_dedup,
                SUM(
                    CASE
                        WHEN ocl.publication_year BETWEEN {baseline_start} AND {baseline_end}
                        THEN 1
                        ELSE 0
                    END
                ) AS frac_baseline_dedup,
                {year_case_cols_sql},
                SUM(
                    CASE
                        WHEN wm.cohort_is_reliable = TRUE
                        THEN ocl.own_weight_frac * wm.norm_vs_mean
                        ELSE 0
                    END
                ) / NULLIF(
                    SUM(
                        CASE
                            WHEN wm.cohort_is_reliable = TRUE
                            THEN ocl.own_weight_frac
                            ELSE 0
                        END
                    ),
                    0
                ) AS mncs,
                SUM(
                    CASE
                        WHEN wm.cohort_is_reliable = TRUE
                        THEN ocl.own_weight_frac * CAST(wm.is_top10 AS DOUBLE)
                        ELSE 0
                    END
                ) / NULLIF(
                    SUM(
                        CASE
                            WHEN wm.cohort_is_reliable = TRUE
                            THEN ocl.own_weight_frac
                            ELSE 0
                        END
                    ),
                    0
                ) AS pp_top10
            FROM overall_country_links_dedup ocl
            JOIN marts.work_metrics wm
              ON wm.work_id = ocl.work_id
            GROUP BY ocl.country_code, ocl.country_name
        ),
        member_agg AS (
            SELECT
                mcl.country_code,
                mcl.country_name,
                {member_case_cols_sql}
            FROM member_country_links mcl
            JOIN marts.work_metrics wm
              ON wm.work_id = mcl.work_id
            GROUP BY mcl.country_code, mcl.country_name
        )
        SELECT
            COALESCE(oa.country_code, ma.country_code) AS country_code,
            COALESCE(oa.country_name, ma.country_name) AS country_name,
            ROUND(COALESCE(oa.frac_count_dedup, 0), 6) AS frac_count,
            ROUND(COALESCE(oa.frac_recent_dedup, 0), 6) AS frac_recent,
            ROUND(COALESCE(oa.frac_baseline_dedup, 0), 6) AS frac_baseline,
            {year_select_cols_coalesce_sql},
            ROUND(oa.mncs, 6) AS mncs,
            ROUND(oa.pp_top10, 6) AS pp_top10,
            ROUND(oot.p_output_full, 6) AS p_output_full_domain,
            ROUND(oot.p_output_full_recent, 6) AS p_output_full_recent_domain,
            ROUND(oot.p_output_full_baseline, 6) AS p_output_full_baseline_domain,
            {member_select_cols_sql}
        FROM overall_agg oa
        FULL OUTER JOIN member_agg ma
          ON ma.country_code = oa.country_code
         AND ma.country_name = oa.country_name
        CROSS JOIN overall_output_totals oot
        ORDER BY COALESCE(oa.frac_count_dedup, 0) DESC, COALESCE(oa.country_name, ma.country_name) ASC;
    """


def ensuremath_wrap(s: str) -> str:
    if not s:
        return s
    if r"\ensuremath{" in s:
        return s
    return rf"\ensuremath{{{s}}}"


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


def _resolve_total_from_column(
    df: pd.DataFrame, column: str, fallback_series: pd.Series
) -> float:
    if column in df.columns:
        totals = pd.to_numeric(df[column], errors="coerce").dropna()
        positive_totals = totals[totals > 0]
        if not positive_totals.empty:
            return float(positive_totals.iloc[0])

    fallback_total = pd.to_numeric(fallback_series, errors="coerce").sum()
    return float(fallback_total) if pd.notna(fallback_total) else 0.0


def add_intensity_columns(
    df: pd.DataFrame, members: list[str], years: list[int]
) -> pd.DataFrame:
    out = df.copy()

    count_cols = [
        "frac_count",
        "frac_recent",
        "frac_baseline",
        "p_output_full_domain",
        "p_output_full_recent_domain",
        "p_output_full_baseline_domain",
        *[f"frac_y_{y}" for y in years],
    ]
    for m in members:
        count_cols.extend(
            [
                f"frac_{m}",
                f"frac_recent_{m}",
                f"frac_baseline_{m}",
                f"p_output_full_{m}",
                f"p_output_full_recent_{m}",
                f"p_output_full_baseline_{m}",
                *[f"frac_y_{y}_{m}" for y in years],
            ]
        )

    impact_cols = [
        "mncs",
        "pp_top10",
        *[f"mncs_{m}" for m in members],
        *[f"pp_top10_{m}" for m in members],
    ]

    existing_count_cols = [col for col in count_cols if col in out.columns]
    out[existing_count_cols] = (
        out[existing_count_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    )
    existing_impact_cols = [col for col in impact_cols if col in out.columns]
    out[existing_impact_cols] = out[existing_impact_cols].apply(
        pd.to_numeric, errors="coerce"
    )

    total_full = _resolve_total_from_column(
        out, "p_output_full_domain", out["frac_count"]
    )
    total_recent = _resolve_total_from_column(
        out, "p_output_full_recent_domain", out["frac_recent"]
    )
    total_baseline = _resolve_total_from_column(
        out, "p_output_full_baseline_domain", out["frac_baseline"]
    )

    derived_cols = {
        IND_SHARE: out["frac_count"] / total_full if total_full > 0 else 0.0,
        "share_recent_domain": (
            out["frac_recent"] / total_recent if total_recent > 0 else 0.0
        ),
        "share_baseline_domain": (
            out["frac_baseline"] / total_baseline if total_baseline > 0 else 0.0
        ),
    }
    if total_baseline > 0:
        derived_cols[IND_CHANGE] = (
            derived_cols["share_recent_domain"] - derived_cols["share_baseline_domain"]
        ) * 100.0
    else:
        derived_cols[IND_CHANGE] = pd.NA

    for m in members:
        full_col = f"frac_{m}"
        recent_col = f"frac_recent_{m}"
        baseline_col = f"frac_baseline_{m}"

        share_col = f"pp_share_{m}"
        recent_share_col = f"share_recent_{m}"
        baseline_share_col = f"share_baseline_{m}"
        change_col = f"dpp_share_change_{m}"

        total_m_full = _resolve_total_from_column(
            out, f"p_output_full_{m}", out[full_col]
        )
        total_m_recent = _resolve_total_from_column(
            out, f"p_output_full_recent_{m}", out[recent_col]
        )
        total_m_baseline = _resolve_total_from_column(
            out, f"p_output_full_baseline_{m}", out[baseline_col]
        )

        derived_cols[share_col] = (
            out[full_col] / total_m_full if total_m_full > 0 else 0.0
        )
        derived_cols[recent_share_col] = (
            out[recent_col] / total_m_recent if total_m_recent > 0 else 0.0
        )
        derived_cols[baseline_share_col] = (
            out[baseline_col] / total_m_baseline if total_m_baseline > 0 else 0.0
        )
        if total_m_baseline > 0:
            derived_cols[change_col] = (
                derived_cols[recent_share_col] - derived_cols[baseline_share_col]
            ) * 100.0
        else:
            derived_cols[change_col] = pd.NA

    derived_df = pd.DataFrame(derived_cols, index=out.index)
    return pd.concat([out, derived_df], axis=1)


def prepare_base_df(
    df: pd.DataFrame, members: list[str], years: list[int]
) -> pd.DataFrame:
    ordered_cols = [
        "country_code",
        "country_name",
        "frac_count",
        *[f"frac_y_{year}" for year in years],
        IND_SHARE,
        "share_recent_domain",
        "share_baseline_domain",
        IND_CHANGE,
        "mncs",
        "pp_top10",
        *[f"frac_{m}" for m in members],
        *[f"pp_share_{m}" for m in members],
        *[f"share_recent_{m}" for m in members],
        *[f"share_baseline_{m}" for m in members],
        *[f"dpp_share_change_{m}" for m in members],
        *[f"mncs_{m}" for m in members],
        *[f"pp_top10_{m}" for m in members],
        *[f"frac_y_{year}_{m}" for m in members for year in years],
    ]
    return df[ordered_cols].copy()


def finalize_view_df(df: pd.DataFrame) -> pd.DataFrame:
    out = df.sort_values([COUNT_COL, "country_name"], ascending=[False, True]).reset_index(
        drop=True
    )
    out = out.head(TOP_N).reset_index(drop=True)
    return out.assign(
        row_order=out.index + 1,
        recent_start=RECENT_START,
        recent_end=RECENT_END,
        baseline_start=BASELINE_START,
        baseline_end=BASELINE_END,
    )


def prepare_domain_view_df(
    df: pd.DataFrame, members: list[str], years: list[int]
) -> pd.DataFrame:
    cols = [
        "country_code",
        "country_name",
        "frac_count",
        *[f"frac_y_{year}" for year in years],
        IND_SHARE,
        "share_recent_domain",
        "share_baseline_domain",
        IND_CHANGE,
        "mncs",
        "pp_top10",
        *[f"frac_{m}" for m in members],
    ]
    out = df[cols].copy()
    out = out.rename(
        columns={
            "frac_count": COUNT_COL,
            IND_SHARE: SHARE_COL,
            "share_recent_domain": "share_recent",
            "share_baseline_domain": "share_baseline",
            IND_CHANGE: CHANGE_COL,
            "mncs": MNCS_COL,
            "pp_top10": PP_COL,
            **{f"frac_y_{year}": count_year_col(year) for year in years},
            **{f"frac_{m}": member_count_col(m) for m in members},
        }
    )
    return finalize_view_df(out)


def prepare_unit_view_df(df: pd.DataFrame, inst: str, years: list[int]) -> pd.DataFrame:
    cols = [
        "country_code",
        "country_name",
        f"frac_{inst}",
        f"pp_share_{inst}",
        f"share_recent_{inst}",
        f"share_baseline_{inst}",
        f"dpp_share_change_{inst}",
        f"mncs_{inst}",
        f"pp_top10_{inst}",
        *[f"frac_y_{year}_{inst}" for year in years],
    ]
    out = df[cols].copy()
    out = out.rename(
        columns={
            f"frac_{inst}": COUNT_COL,
            f"pp_share_{inst}": SHARE_COL,
            f"share_recent_{inst}": "share_recent",
            f"share_baseline_{inst}": "share_baseline",
            f"dpp_share_change_{inst}": CHANGE_COL,
            f"mncs_{inst}": MNCS_COL,
            f"pp_top10_{inst}": PP_COL,
            **{
                f"frac_y_{year}_{inst}": count_year_col(year)
                for year in years
            },
        }
    )
    return finalize_view_df(out)


def prepare_view_df(
    df: pd.DataFrame, inst: str, members: list[str], years: list[int]
) -> pd.DataFrame:
    if inst == DOMAIN_REPORT:
        return prepare_domain_view_df(df, members, years)
    return prepare_unit_view_df(df, inst, years)


def build_member_cell(frac: float) -> str:
    return f"{fmt_frac(frac, digits=0)}"


def table_options_for_inst(inst: str) -> dict[str, bool]:
    is_domain = inst == DOMAIN_REPORT
    return {
        "show_decomposition": SHOW_DECOMPOSED_COUNTS_ETHDOMAIN
        if is_domain
        else SHOW_DECOMPOSED_COUNTS_UNITS,
        "show_change": SHOW_INTENSITY_CHANGE_ETHDOMAIN
        if is_domain
        else SHOW_INTENSITY_CHANGE_UNITS,
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

    return [max(v, 0.0) / max_value for v in values]


def build_sparkline_cell(
    row: pd.Series,
    years: list[int],
    *,
    color_by_trend: bool,
    show_extrema_points: bool,
) -> str:
    values = []
    for year in years:
        value = row.get(count_year_col(year))
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


def _insert_optional_token(
    tokens: list[str], token: str, position: str, *, fallback_token: str = "intensity"
) -> None:
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


def build_grouped_header_lines(
    headers: list[str],
    display_tokens: list[str],
    *,
    first_group_label: str,
    decomposition_count: int,
    decomposition_before_impact: bool = False,
    decomposition_group_label: str = "ETH Domain Members",
) -> list[str]:
    group_ids = []
    for token in display_tokens:
        if token in {"rank", "name", "cc"}:
            group_ids.append("first")
        elif token in {"pfrac", "intensity", "trend", "change"}:
            group_ids.append("volume")
        elif token in {"mncs", "pp"}:
            group_ids.append("impact")
        else:
            group_ids.append("other")

    if decomposition_count > 0:
        if decomposition_before_impact:
            first_impact_idx = next(
                (idx for idx, group in enumerate(group_ids) if group == "impact"),
                len(group_ids),
            )
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


def build_table_tex(
    df: pd.DataFrame, members: list[str], inst: str, years: list[int]
) -> str:
    options = table_options_for_inst(inst)
    show_decomposition = options["show_decomposition"]
    show_change = options["show_change"]
    show_sparkline = options["show_sparkline"]
    sparkline_color_by_trend = options["sparkline_color_by_trend"]
    show_row_background_stripes = options["show_row_background_stripes"]
    sparkline_mark_extrema_points = options["sparkline_mark_extrema_points"]

    frac_symbol = (
        (indicator_catalog_dict.get("P_FULL", {}) or {}).get("symbol_tex", "").strip()
    )
    mncs_symbol = (
        (indicator_catalog_dict.get(IND_IMPACT_MNCS, {}) or {})
        .get("symbol_tex", "")
        .strip()
    )
    pp_symbol = (
        (indicator_catalog_dict.get(IND_IMPACT_PP, {}) or {})
        .get("symbol_tex", "")
        .strip()
    )

    frac_label = (
        ensuremath_wrap(frac_symbol)
        if frac_symbol
        else r"\ensuremath{\mathrm{P}[\mathrm{Frac}]}"
    )
    mncs_label = ensuremath_wrap(mncs_symbol) if mncs_symbol else "MNCS"
    pp_label = ensuremath_wrap(pp_symbol) if pp_symbol else "PPtop10"

    display_digits = get_display_digits()
    share_digits = display_digits["share"]
    change_digits = display_digits["change"]
    mncs_digits = display_digits["mncs"]
    pp_digits = display_digits["pp"]

    member_headers = [
        tex_escape(unit_params_dict.get(m, {}).get("InstShort", m.upper()))
        for m in members
    ]

    change_header = rf"Change ({RECENT_WINDOW}y)"
    token_to_header = {
        "rank": r"Rank",
        "name": r"Country",
        "cc": r"CC",
        "pfrac": frac_label,
        "intensity": r"Share",
        "trend": r"Trend",
        "change": change_header,
        "mncs": mncs_label,
        "pp": pp_label,
    }
    token_to_colspec = (
        TABLE_COLUMN_SPEC_ETHDOMAIN
        if inst == DOMAIN_REPORT
        else TABLE_COLUMN_SPEC_UNITS
    )

    display_tokens = ["rank", "name", "cc", "pfrac", "intensity", "mncs", "pp"]

    if show_sparkline:
        _insert_optional_token(
            display_tokens, "trend", TREND_COLUMN_POSITION, fallback_token="intensity"
        )
    if show_change:
        _insert_optional_token(
            display_tokens, "change", CHANGE_COLUMN_POSITION, fallback_token="intensity"
        )

    impact_tokens = [token for token in display_tokens if token in {"mncs", "pp"}]
    pre_impact_tokens = [
        token for token in display_tokens if token not in {"mncs", "pp"}
    ]

    if show_decomposition:
        ordered_tokens = pre_impact_tokens + impact_tokens

        col_align = [token_to_colspec.get(token, "r") for token in pre_impact_tokens]
        headers = [token_to_header[token] for token in pre_impact_tokens]

        col_align.extend([DECOMPOSITION_COLUMN_SPEC] * len(members))
        headers.extend([r"{" + h + "}" for h in member_headers])

        col_align.extend([token_to_colspec.get(token, "r") for token in impact_tokens])
        headers.extend([token_to_header[token] for token in impact_tokens])
    else:
        ordered_tokens = display_tokens
        col_align = [token_to_colspec.get(token, "r") for token in ordered_tokens]
        headers = [token_to_header[token] for token in ordered_tokens]

    col_spec = "@{}" + "".join(col_align) + "@{}"
    grouped_header_lines = build_grouped_header_lines(
        headers,
        display_tokens,
        first_group_label="Country",
        decomposition_count=len(members) if show_decomposition else 0,
        decomposition_before_impact=show_decomposition,
    )

    change_scale_max = 0.0
    if show_change and SHOW_CHANGE_PP_BAR:
        change_series = pd.to_numeric(df.get(CHANGE_COL), errors="coerce")
        if change_series is not None and not change_series.empty:
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

    for row_idx, (_, row) in enumerate(df.iterrows(), start=1):
        country_name = tex_escape(shorten_country_name(row.get("country_name", "")))
        country_code = (
            tex_escape(row.get("country_code", ""))
            if pd.notna(row.get("country_code"))
            else r"\textit{n/a}"
        )

        token_to_cell = {
            "rank": str(row_idx),
            "name": country_name,
            "cc": country_code,
            "pfrac": fmt_frac(row.get(COUNT_COL), digits=0),
            "intensity": fmt_pct(row.get(SHARE_COL), digits=share_digits),
            "mncs": fmt_float(row.get(MNCS_COL), digits=mncs_digits),
            "pp": fmt_pct(row.get(PP_COL), digits=pp_digits),
        }

        if show_change:
            token_to_cell["change"] = build_change_pp_cell(
                row.get(CHANGE_COL), digits=change_digits, max_abs=change_scale_max
            )

        if show_sparkline:
            token_to_cell["trend"] = build_sparkline_cell(
                row,
                years,
                color_by_trend=sparkline_color_by_trend,
                show_extrema_points=sparkline_mark_extrema_points,
            )

        if show_decomposition:
            cells = [token_to_cell[token] for token in pre_impact_tokens]
            cells.extend(build_member_cell(row.get(member_count_col(m))) for m in members)
            cells.extend(token_to_cell[token] for token in impact_tokens)
        else:
            cells = [token_to_cell[token] for token in ordered_tokens]

        row_prefix = "  "
        if show_row_background_stripes:
            row_color = (
                ROW_BACKGROUND_COLOR_ODD
                if row_idx % 2 == 1
                else ROW_BACKGROUND_COLOR_EVEN
            )
            row_prefix += build_rowcolor_command(row_color)

        lines.append(row_prefix + " & ".join(cells) + r" \\")

    lines.extend(
        [
            r"\end{tabular}%",
            r"}",
        ]
    )
    return "\n".join(lines) + "\n"


def _round_count_series(series: pd.Series) -> pd.Series:
    rounded = pd.to_numeric(series, errors="coerce").round(0)
    return rounded.astype("Int64")


def _round_export_series(series: pd.Series, digits: int) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").round(digits)


def _round_export_pct_series(series: pd.Series, digits: int) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").round(digits + 2)


def prepare_numeric_export(
    view_df: pd.DataFrame, inst: str, members: list[str]
) -> pd.DataFrame:
    display_digits = get_display_digits()

    export_df = view_df[
        [
            "row_order",
            "country_code",
            "country_name",
            "recent_start",
            "recent_end",
            "baseline_start",
            "baseline_end",
        ]
    ].copy()
    export_df["country_name_short"] = export_df["country_name"].map(
        lambda value: shorten_country_name(None if pd.isna(value) else value)
    )
    export_df["country_name_full"] = export_df["country_name"].map(
        lambda value: full_country_name(None if pd.isna(value) else value)
    )
    export_df[COUNT_COL] = _round_count_series(view_df[COUNT_COL])
    export_df[IND_SHARE] = _round_export_pct_series(
        view_df[SHARE_COL], display_digits["share"]
    )
    export_df[IND_SHARE_RECENT] = _round_export_pct_series(
        view_df["share_recent"], display_digits["share"]
    )
    export_df[IND_SHARE_BASELINE] = _round_export_pct_series(
        view_df["share_baseline"], display_digits["share"]
    )
    export_df[IND_CHANGE] = _round_export_series(
        view_df[CHANGE_COL], display_digits["change"]
    )
    export_df[IND_IMPACT_MNCS] = _round_export_series(
        view_df[MNCS_COL], display_digits["mncs"]
    )
    export_df[IND_IMPACT_PP] = _round_export_pct_series(
        view_df[PP_COL], display_digits["pp"]
    )

    if inst == DOMAIN_REPORT:
        for member in members:
            col = member_count_col(member)
            export_df[col] = _round_count_series(view_df[col])

    return export_df


def export_to_all_institutions(
    base_df: pd.DataFrame,
    members: list[str],
    years: list[int],
    institutions: list[str],
) -> None:
    for inst in institutions:
        out = asset.inst_dir(inst)
        view_df = prepare_view_df(base_df, inst, members, years)

        table_tex = build_table_tex(view_df, members, inst=inst, years=years)
        (out / "table.tex").write_text(table_tex, encoding="utf-8")
        prepare_numeric_export(view_df, inst, members).to_csv(
            out / "data.csv", index=False
        )


def main() -> None:
    con = asset.connect()
    try:
        raw_df = con.execute(
            q_top_external_countries(
                YEAR_FIRST,
                YEAR_LAST,
                YEARS,
                RECENT_START,
                RECENT_END,
                BASELINE_START,
                BASELINE_END,
                DOMAIN_MEMBERS,
                DOMAIN_REPORT,
            )
        ).df()
    finally:
        con.close()

    processed_df = add_intensity_columns(raw_df, DOMAIN_MEMBERS, YEARS)
    base_df = prepare_base_df(processed_df, DOMAIN_MEMBERS, YEARS)
    export_to_all_institutions(base_df, DOMAIN_MEMBERS, YEARS, ALL_INSTITUTIONS)

    print(
        f"exported top {TOP_N} partner countries to {len(ALL_INSTITUTIONS)} institution folders"
    )


if __name__ == "__main__":
    main()
