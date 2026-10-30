import pandas as pd

from core.asset import Asset
from utility import get_indicator_catalog_dict


MA_YEAR_COL = "MA_year"
INCLUDE_FULL_PERIOD_COLUMN = True
OVERALL_COLUMN_LABEL = "Overall"
LEFT_COL_HEADER = "Indicator"

INDICATORS = [
    "A_AFF_AUTHORS",
    "A_FEMALE_INST",
    "A_MALE_INST",
    "PA_F_INST",
    "A_ALL_AUTHORS",
    "A_FEMALE_PUBS",
    "A_MALE_PUBS",
    "PA_F_PUBS",
    "RPA_F",
]

TABLE_SECTIONS = [
    (
        "Affiliated authors on own publication set",
        ["A_AFF_AUTHORS", "A_FEMALE_INST", "A_MALE_INST", "PA_F_INST"],
    ),
    (
        "All contributing authors on the same publication set",
        ["A_ALL_AUTHORS", "A_FEMALE_PUBS", "A_MALE_PUBS", "PA_F_PUBS"],
    ),
    (
        "Relative female representation",
        ["RPA_F"],
    ),
]

COUNT_METRICS = {
    "A_AFF_AUTHORS",
    "A_FEMALE_INST",
    "A_MALE_INST",
    "A_ALL_AUTHORS",
    "A_FEMALE_PUBS",
    "A_MALE_PUBS",
}
PERCENT_METRICS = {"PA_F_INST", "PA_F_PUBS"}
RATIO_METRICS = {"RPA_F"}


def q_gender_metrics(inst: str, y0: int, y1: int, ma_window: int) -> str:
    n_windows = y1 - y0 - ma_window + 2

    return f"""
        WITH window_defs AS (
            SELECT
                {y0} + t.window_idx AS start_year,
                {y0} + t.window_idx + {ma_window} - 1 AS end_year,
                CAST({y0} + t.window_idx AS VARCHAR)
                    || '-' ||
                CAST({y0} + t.window_idx + {ma_window} - 1 AS VARCHAR) AS MA_year,
                FALSE AS is_full_period
            FROM range(GREATEST({n_windows}, 0)) AS t(window_idx)

            UNION ALL

            SELECT
                {y0} AS start_year,
                {y1} AS end_year,
                '{y0}-{y1}' AS MA_year,
                TRUE AS is_full_period
        ),
        report_works AS (
            SELECT DISTINCT
                rm.work_id,
                w.publication_year AS year
            FROM reports.report_membership rm
            JOIN core.work w
              ON w.work_id = rm.work_id
            JOIN core.work_to_status s
              ON s.work_id = rm.work_id
            WHERE rm.report_name = '{inst}'
              AND w.publication_year BETWEEN {y0} AND {y1}
              AND s.is_included = TRUE
        ),
        wag_year_author AS (
            SELECT
                rw.year,
                wag.author_id,
                BOOL_OR(COALESCE(wag.assigned_to_institution, FALSE)) AS assigned_to_institution,
                MAX(
                    CASE
                        WHEN LOWER(COALESCE(wag.gender_effective, '')) = 'female'
                        THEN 1 ELSE 0
                    END
                ) AS has_female,
                MAX(
                    CASE
                        WHEN LOWER(COALESCE(wag.gender_effective, '')) = 'male'
                        THEN 1 ELSE 0
                    END
                ) AS has_male
            FROM report_works rw
            JOIN reports.work_author_gender wag
              ON wag.work_id = rw.work_id
             AND wag.report_name = '{inst}'
            WHERE wag.author_id IS NOT NULL
            GROUP BY rw.year, wag.author_id
        ),
        author_year AS (
            SELECT
                year,
                author_id,
                assigned_to_institution,
                CASE
                    WHEN has_female = 1 AND has_male = 1 THEN 'unknown'
                    WHEN has_female = 1 THEN 'female'
                    WHEN has_male = 1 THEN 'male'
                    ELSE 'unknown'
                END AS gender
            FROM wag_year_author
        ),
        window_author AS (
            SELECT
                wd.MA_year,
                wd.start_year,
                wd.end_year,
                wd.is_full_period,
                ay.author_id,
                BOOL_OR(ay.assigned_to_institution) AS assigned_to_institution,
                MAX(CASE WHEN ay.gender = 'female' THEN 1 ELSE 0 END) AS has_female,
                MAX(CASE WHEN ay.gender = 'male' THEN 1 ELSE 0 END) AS has_male
            FROM window_defs wd
            LEFT JOIN author_year ay
              ON ay.year BETWEEN wd.start_year AND wd.end_year
            GROUP BY
                wd.MA_year,
                wd.start_year,
                wd.end_year,
                wd.is_full_period,
                ay.author_id
        ),
        window_author_gender AS (
            SELECT
                MA_year,
                start_year,
                end_year,
                is_full_period,
                author_id,
                assigned_to_institution,
                CASE
                    WHEN has_female = 1 AND has_male = 1 THEN 'unknown'
                    WHEN has_female = 1 THEN 'female'
                    WHEN has_male = 1 THEN 'male'
                    ELSE 'unknown'
                END AS gender
            FROM window_author
            WHERE author_id IS NOT NULL
        ),
        window_counts AS (
            SELECT
                MA_year,
                start_year,
                end_year,
                is_full_period,
                COUNT(*) AS A_ALL_AUTHORS,
                COUNT(*) FILTER (WHERE assigned_to_institution) AS A_AFF_AUTHORS,
                COUNT(*) FILTER (WHERE gender = 'female') AS A_FEMALE_PUBS_RAW,
                COUNT(*) FILTER (WHERE gender = 'male') AS A_MALE_PUBS_RAW,
                COUNT(*) FILTER (WHERE assigned_to_institution AND gender = 'female') AS A_FEMALE_INST_RAW,
                COUNT(*) FILTER (WHERE assigned_to_institution AND gender = 'male') AS A_MALE_INST_RAW
            FROM window_author_gender
            GROUP BY MA_year, start_year, end_year, is_full_period
        ),
        window_metrics AS (
            SELECT
                wd.MA_year,
                wd.start_year,
                wd.end_year,
                wd.is_full_period,
                COALESCE(wc.A_AFF_AUTHORS, 0) AS A_AFF_AUTHORS,
                COALESCE(wc.A_ALL_AUTHORS, 0) AS A_ALL_AUTHORS,
                COALESCE(wc.A_FEMALE_INST_RAW, 0) AS A_FEMALE_INST_RAW,
                COALESCE(wc.A_MALE_INST_RAW, 0) AS A_MALE_INST_RAW,
                COALESCE(wc.A_FEMALE_PUBS_RAW, 0) AS A_FEMALE_PUBS_RAW,
                COALESCE(wc.A_MALE_PUBS_RAW, 0) AS A_MALE_PUBS_RAW
            FROM window_defs wd
            LEFT JOIN window_counts wc
              ON wc.MA_year = wd.MA_year
             AND wc.start_year = wd.start_year
             AND wc.end_year = wd.end_year
             AND wc.is_full_period = wd.is_full_period
        )
        SELECT
            MA_year,
            start_year,
            end_year,
            is_full_period,
            A_AFF_AUTHORS,
            CASE
                WHEN A_FEMALE_INST_RAW + A_MALE_INST_RAW > 0
                THEN A_FEMALE_INST_RAW ELSE NULL
            END AS A_FEMALE_INST,
            CASE
                WHEN A_FEMALE_INST_RAW + A_MALE_INST_RAW > 0
                THEN A_MALE_INST_RAW ELSE NULL
            END AS A_MALE_INST,
            CASE
                WHEN A_FEMALE_INST_RAW + A_MALE_INST_RAW > 0
                THEN ROUND(
                    CAST(A_FEMALE_INST_RAW AS DOUBLE)
                    / CAST(A_FEMALE_INST_RAW + A_MALE_INST_RAW AS DOUBLE),
                    6
                )
                ELSE NULL
            END AS PA_F_INST,
            A_ALL_AUTHORS,
            CASE
                WHEN A_FEMALE_PUBS_RAW + A_MALE_PUBS_RAW > 0
                THEN A_FEMALE_PUBS_RAW ELSE NULL
            END AS A_FEMALE_PUBS,
            CASE
                WHEN A_FEMALE_PUBS_RAW + A_MALE_PUBS_RAW > 0
                THEN A_MALE_PUBS_RAW ELSE NULL
            END AS A_MALE_PUBS,
            CASE
                WHEN A_FEMALE_PUBS_RAW + A_MALE_PUBS_RAW > 0
                THEN ROUND(
                    CAST(A_FEMALE_PUBS_RAW AS DOUBLE)
                    / CAST(A_FEMALE_PUBS_RAW + A_MALE_PUBS_RAW AS DOUBLE),
                    6
                )
                ELSE NULL
            END AS PA_F_PUBS,
            CASE
                WHEN A_FEMALE_INST_RAW + A_MALE_INST_RAW > 0
                 AND A_FEMALE_PUBS_RAW + A_MALE_PUBS_RAW > 0
                 AND A_FEMALE_PUBS_RAW > 0
                THEN ROUND(
                    (
                        CAST(A_FEMALE_INST_RAW AS DOUBLE)
                        / CAST(A_FEMALE_INST_RAW + A_MALE_INST_RAW AS DOUBLE)
                    )
                    /
                    (
                        CAST(A_FEMALE_PUBS_RAW AS DOUBLE)
                        / CAST(A_FEMALE_PUBS_RAW + A_MALE_PUBS_RAW AS DOUBLE)
                    ),
                    6
                )
                ELSE NULL
            END AS RPA_F
        FROM window_metrics
        ORDER BY is_full_period, start_year;
    """


def tex_escape_text(text: str) -> str:
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


def fmt_count(value) -> str:
    if value is None or pd.isna(value):
        return r"\textit{n/a}"
    return f"{int(round(float(value))):,}"


def fmt_pct(value, digits: int = 0) -> str:
    if value is None or pd.isna(value):
        return r"\textit{n/a}"
    return f"{100.0 * float(value):.{digits}f}\\%"


def fmt_float(value, digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return r"\textit{n/a}"
    return f"{float(value):.{digits}f}"


def sort_year_label(label: str) -> int:
    try:
        return int(str(label).split("-")[0])
    except Exception:
        return -(10**9)


def build_metric_labels(indicator_catalog: dict) -> dict[str, str]:
    labels: dict[str, str] = {}
    for indicator in INDICATORS:
        symbol_tex = str((indicator_catalog.get(indicator, {}) or {}).get("symbol_tex", "")).strip()
        if symbol_tex:
            labels[indicator] = f"${symbol_tex}$"
        else:
            labels[indicator] = tex_escape_text(indicator)
    return labels


def build_table_tex(
    ma_df: pd.DataFrame,
    full_df: pd.DataFrame,
    metric_labels: dict[str, str],
    *,
    full_period_label: str,
    header_rotation_deg: float,
) -> str:
    year_cols = sorted(ma_df[MA_YEAR_COL].dropna().unique(), key=sort_year_label)
    value_map = ma_df.set_index(MA_YEAR_COL).to_dict(orient="index") if not ma_df.empty else {}
    full_row = full_df.iloc[0].to_dict() if not full_df.empty else {}

    col_headers = year_cols + ([full_period_label] if INCLUDE_FULL_PERIOD_COLUMN else [])

    if INCLUDE_FULL_PERIOD_COLUMN and year_cols:
        col_spec = "@{}l" + ("r" * len(year_cols)) + "|r@{}"
    elif INCLUDE_FULL_PERIOD_COLUMN:
        col_spec = "@{}lr@{}"
    else:
        col_spec = "@{}l" + ("r" * len(year_cols)) + "@{}"

    rotation = int(header_rotation_deg) if float(header_rotation_deg).is_integer() else float(header_rotation_deg)

    def render_value(indicator: str, value) -> str:
        if indicator in COUNT_METRICS:
            return fmt_count(value)
        if indicator in PERCENT_METRICS:
            return fmt_pct(value, 1)
        if indicator in RATIO_METRICS:
            return fmt_float(value, 2)
        return fmt_count(value)

    lines: list[str] = []
    lines.append(r"\begin{adjustbox}{max width=\linewidth}%")
    lines.append(rf"\begin{{tabular}}{{{col_spec}}}")
    lines.append(r"  \toprule")

    header_cells = [
        rf"\rotatebox[origin=c]{{{rotation}}}{{{tex_escape_text(h)}}}"
        for h in col_headers
    ]
    lines.append(rf"  {LEFT_COL_HEADER} & " + " & ".join(header_cells) + r" \\")
    lines.append(r"  \midrule")

    n_cols = len(col_headers) + 1
    first_section = True
    for section_title, section_indicators in TABLE_SECTIONS:
        if not first_section:
            lines.append(r"  \midrule")
        first_section = False
        lines.append(rf"  \multicolumn{{{n_cols}}}{{c}}{{{section_title}}} \\")
        lines.append(r"  \midrule")

        for indicator in section_indicators:
            label = metric_labels.get(indicator, tex_escape_text(indicator))
            values = [render_value(indicator, value_map.get(year, {}).get(indicator)) for year in year_cols]
            if INCLUDE_FULL_PERIOD_COLUMN:
                values.append(render_value(indicator, full_row.get(indicator)))
            lines.append(f"  {label} & " + " & ".join(values) + r" \\")

    lines.append(r"  \bottomrule")
    lines.append(r"\end{tabular}%")
    lines.append(r"\end{adjustbox}")
    lines.append("")
    return "\n".join(lines)


asset = Asset(script_file=__file__)
indicator_catalog = get_indicator_catalog_dict()
metric_labels = build_metric_labels(indicator_catalog)
header_rotation_deg = float(getattr(asset, "table_header_rotation_deg", 60))
ma_window = max(1, int(asset.year_range_moving))

raw_required_cols = {MA_YEAR_COL, "start_year", "end_year", "is_full_period", *INDICATORS}

for inst, con in asset.iterate_institutions():
    sql = q_gender_metrics(inst, asset.year_first, asset.year_last, ma_window)
    raw_df = asset.extract(
        con=con,
        inst=inst,
        query=sql,
        out_name="raw_data.csv",
    )

    if not raw_required_cols.issubset(set(raw_df.columns)):
        raw_df = asset.extract(
            con=con,
            inst=inst,
            query=sql,
            out_name="raw_data.csv",
            force=True,
        )

    missing_cols = raw_required_cols - set(raw_df.columns)
    if missing_cols:
        raise ValueError(f"Missing columns in raw_data.csv for {inst}: {sorted(missing_cols)}")

    raw_df = raw_df.copy()
    raw_df[MA_YEAR_COL] = raw_df[MA_YEAR_COL].astype("string")
    raw_df["is_full_period"] = (
        raw_df["is_full_period"]
        .astype("string")
        .str.strip()
        .str.lower()
        .isin({"1", "true", "t", "yes", "y"})
    )
    raw_df["start_year"] = pd.to_numeric(raw_df["start_year"], errors="coerce")

    for col in INDICATORS:
        raw_df[col] = pd.to_numeric(raw_df[col], errors="coerce")

    ma_df = (
        raw_df[~raw_df["is_full_period"]]
        .sort_values("start_year")
        [[MA_YEAR_COL] + INDICATORS]
        .reset_index(drop=True)
    )

    full_df = (
        raw_df[raw_df["is_full_period"]]
        .sort_values("start_year")
        [[MA_YEAR_COL] + INDICATORS]
        .reset_index(drop=True)
    )
    if full_df.empty:
        full_df = pd.DataFrame(
            [{MA_YEAR_COL: f"{asset.year_first}-{asset.year_last}", **{indicator: None for indicator in INDICATORS}}],
            columns=[MA_YEAR_COL] + INDICATORS,
        )

    # Keep moving-window rows and add the full-period row to data.csv so
    # \IndTable{asset=X-X-genderOverallTrend,id=<period>,...} can access it.
    data_df = pd.concat([ma_df, full_df], ignore_index=True)

    out = asset.inst_dir(inst)
    data_df.to_csv(out / "data.csv", index=False)

    table_data_df = ma_df.melt(
        id_vars=[MA_YEAR_COL],
        value_vars=INDICATORS,
        var_name="indicator",
        value_name="value",
    )

    if INCLUDE_FULL_PERIOD_COLUMN:
        full_row = full_df.iloc[0].to_dict()
        full_period_label = f"{asset.year_first}-{asset.year_last}"
        full_rows = [
            {
                MA_YEAR_COL: full_period_label,
                "indicator": indicator,
                "value": full_row.get(indicator),
            }
            for indicator in INDICATORS
        ]
        table_data_df = pd.concat([table_data_df, pd.DataFrame(full_rows)], ignore_index=True)

    table_data_df.to_csv(out / "table_data.csv", index=False)

    table_tex = build_table_tex(
        ma_df,
        full_df,
        metric_labels,
        full_period_label=OVERALL_COLUMN_LABEL,
        header_rotation_deg=header_rotation_deg,
    )
    (out / "table.tex").write_text(table_tex, encoding="utf-8")
