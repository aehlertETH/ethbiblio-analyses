import pandas as pd

from core.asset import Asset, INSTITUTION_DISPLAY_ORDER


MA_YEAR_COL = "MA_year"
INCLUDE_FULL_PERIOD_COLUMN = True
OVERALL_COLUMN_LABEL = "Overall"
LEFT_COL_HEADER = "Indicator"

ALL_INSTITUTIONS = list(INSTITUTION_DISPLAY_ORDER)
DOMAIN_UNIT_REPORTS = ["ethz", "epfl", "psi", "empa", "eawag", "wsl"]

COUNT_METRICS = {"P_FULL"}
PERCENT_METRICS = {"PP_ANY_NAT_PARTNER", "PP_ANY_INT_PARTNER"}
DECIMAL_METRICS = {
    "AVG_N_PARTNER_INST_TOTAL_EXT",
    "AVG_N_PARTNER_INST_ETHDOMAIN",
    "AVG_N_PARTNER_INST_NAT_OUTSIDE_DOMAIN",
    "AVG_N_PARTNER_INST_NAT",
    "AVG_N_PARTNER_INST_INT",
    "MED_N_PARTNER_INST_TOTAL_EXT",
    "MED_N_PARTNER_INST_ETHDOMAIN",
    "MED_N_PARTNER_INST_NAT_OUTSIDE_DOMAIN",
    "MED_N_PARTNER_INST_NAT",
    "MED_N_PARTNER_INST_INT",
}

OUTPUT_ROWS = [
    {"metric": "P_FULL", "label": "Publications (full)"},
]

MEAN_ROWS = [
    {"metric": "AVG_N_PARTNER_INST_TOTAL_EXT", "label": "External partners (total)"},
    {"metric": "AVG_N_PARTNER_INST_ETHDOMAIN", "label": "ETH Domain partners"},
    {"metric": "AVG_N_PARTNER_INST_NAT_OUTSIDE_DOMAIN", "label": "National partners (outside ETH Domain)"},
    {"metric": "AVG_N_PARTNER_INST_NAT", "label": "National partners (incl. ETH Domain)"},
    {"metric": "AVG_N_PARTNER_INST_INT", "label": "International partners"},
]

MEDIAN_ROWS = [
    {"metric": "MED_N_PARTNER_INST_TOTAL_EXT", "label": "External partners (total)"},
    {"metric": "MED_N_PARTNER_INST_ETHDOMAIN", "label": "ETH Domain partners"},
    {"metric": "MED_N_PARTNER_INST_NAT_OUTSIDE_DOMAIN", "label": "National partners (outside ETH Domain)"},
    {"metric": "MED_N_PARTNER_INST_NAT", "label": "National partners (incl. ETH Domain)"},
    {"metric": "MED_N_PARTNER_INST_INT", "label": "International partners"},
]

BRIDGE_ROWS = [
    {"metric": "PP_ANY_NAT_PARTNER", "label": "Any national partner"},
    {"metric": "PP_ANY_INT_PARTNER", "label": "Any international partner"},
]

METRIC_ORDER = [row["metric"] for row in OUTPUT_ROWS + MEAN_ROWS + MEDIAN_ROWS + BRIDGE_ROWS]


def q_partner_intensity_raw(inst: str, y0: int, y1: int) -> str:
    unit_report_list_sql = ", ".join(f"'{unit}'" for unit in DOMAIN_UNIT_REPORTS)

    return f"""
        WITH own_inst AS (
            SELECT DISTINCT institution_id
            FROM reports.report_institutions_ids
            WHERE report_name = '{inst}'
        ),
        domain_inst AS (
            SELECT DISTINCT institution_id
            FROM reports.report_institutions_ids
            WHERE report_name = 'ethdomain'
        ),
        base AS (
            SELECT DISTINCT
                rm.work_id,
                w.publication_year AS year,
                wm.n_institutions_on_work
            FROM reports.report_membership rm
            JOIN core.work w
                ON w.work_id = rm.work_id
            JOIN core.work_to_status s
                ON s.work_id = rm.work_id
            LEFT JOIN marts.work_metrics wm
                ON wm.work_id = rm.work_id
            WHERE rm.report_name = '{inst}'
              AND w.publication_year BETWEEN {y0} AND {y1}
              AND s.is_included = TRUE
              AND wm.n_institutions_on_work > 0
        ),
        unit_membership AS (
            SELECT
                b.work_id,
                COUNT(DISTINCT rm.report_name) AS n_eth_domain_units
            FROM base b
            LEFT JOIN reports.report_membership rm
                ON rm.work_id = b.work_id
               AND rm.report_name IN ({unit_report_list_sql})
            GROUP BY b.work_id
        ),
        partner_rows AS (
            SELECT
                b.work_id,
                wii.institution_id AS partner_inst_id,
                CASE
                    WHEN wii.institution_id IN (SELECT institution_id FROM domain_inst)
                    THEN 1 ELSE 0
                END AS is_ethdomain_partner,
                COALESCE(dc.country_code, '') AS country_code
            FROM base b
            LEFT JOIN marts.work_institution_info wii
                ON wii.work_id = b.work_id
            LEFT JOIN core.dim_institution di
                ON di.institution_id = wii.institution_id
            LEFT JOIN core.dim_country dc
                ON dc.country_id = di.country_id
            WHERE wii.institution_id NOT IN (SELECT institution_id FROM own_inst)
        ),
        per_work_counts AS (
            SELECT
                b.work_id,
                COUNT(DISTINCT pr.partner_inst_id) AS n_partner_inst_total_ext,
                COUNT(
                    DISTINCT CASE
                        WHEN pr.is_ethdomain_partner = 1
                        THEN pr.partner_inst_id
                        ELSE NULL
                    END
                ) AS n_partner_inst_ethdomain,
                COUNT(
                    DISTINCT CASE
                        WHEN pr.is_ethdomain_partner = 0
                         AND pr.country_code = 'CH'
                        THEN pr.partner_inst_id
                        ELSE NULL
                    END
                ) AS n_partner_inst_nat_outside_domain,
                COUNT(
                    DISTINCT CASE
                        WHEN pr.country_code <> 'CH'
                        THEN pr.partner_inst_id
                        ELSE NULL
                    END
                ) AS n_partner_inst_int
            FROM base b
            LEFT JOIN partner_rows pr
                ON pr.work_id = b.work_id
            GROUP BY b.work_id
        )
        SELECT
            b.work_id,
            b.year,
            b.n_institutions_on_work,
            COALESCE(pwc.n_partner_inst_total_ext, 0) AS n_partner_inst_total_ext,
            COALESCE(pwc.n_partner_inst_ethdomain, 0) AS n_partner_inst_ethdomain,
            COALESCE(pwc.n_partner_inst_nat_outside_domain, 0) AS n_partner_inst_nat_outside_domain,
            COALESCE(pwc.n_partner_inst_ethdomain, 0)
                + COALESCE(pwc.n_partner_inst_nat_outside_domain, 0) AS n_partner_inst_nat,
            COALESCE(pwc.n_partner_inst_int, 0) AS n_partner_inst_int,
            CASE
                WHEN COALESCE(um.n_eth_domain_units, 0) >= 2
                  OR COALESCE(pwc.n_partner_inst_nat_outside_domain, 0) > 0
                THEN 1 ELSE 0
            END AS has_any_nat_partner,
            CASE
                WHEN COALESCE(pwc.n_partner_inst_int, 0) > 0
                THEN 1 ELSE 0
            END AS has_any_int_partner,
            COALESCE(um.n_eth_domain_units, 0) AS n_eth_domain_units
        FROM base b
        LEFT JOIN per_work_counts pwc
            ON pwc.work_id = b.work_id
        LEFT JOIN unit_membership um
            ON um.work_id = b.work_id
        ORDER BY b.year, b.work_id;
    """


def fmt_count(value) -> str:
    if value is None or pd.isna(value):
        return r"\textit{n/a}"
    return f"{int(round(float(value))):,}"


def fmt_pct(value, digits: int = 1) -> str:
    if value is None or pd.isna(value):
        return r"\textit{n/a}"
    return f"{100.0 * float(value):.{digits}f}\\%"


def fmt_decimal(value, digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return r"\textit{n/a}"
    return f"{float(value):.{digits}f}"


def sort_year_label(label: str) -> int:
    try:
        return int(str(label).split("-")[0])
    except Exception:
        return -(10**9)


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


def _prepare_inputs(raw_df: pd.DataFrame) -> pd.DataFrame:
    df = raw_df.copy()
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df = df.dropna(subset=["work_id", "year"]).copy()
    if df.empty:
        return pd.DataFrame()

    df["year"] = df["year"].astype(int)
    df = df.sort_values(["year", "work_id"]).drop_duplicates(
        subset=["work_id"], keep="first"
    )

    numeric_cols = [
        "n_partner_inst_total_ext",
        "n_partner_inst_ethdomain",
        "n_partner_inst_nat_outside_domain",
        "n_partner_inst_nat",
        "n_partner_inst_int",
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    df["has_any_nat_partner"] = pd.to_numeric(
        df["has_any_nat_partner"], errors="coerce"
    ).fillna(0).astype(int)
    df["has_any_int_partner"] = pd.to_numeric(
        df["has_any_int_partner"], errors="coerce"
    ).fillna(0).astype(int)

    return df


def _compute_window_metrics(df: pd.DataFrame, *, y0: int, y1: int) -> dict[str, float | int | None]:
    sub = df[(df["year"] >= y0) & (df["year"] <= y1)].copy()
    p_full = int(sub["work_id"].nunique())

    result: dict[str, float | int | None] = {"P_FULL": p_full}

    base_metric_names = [
        "N_PARTNER_INST_TOTAL_EXT",
        "N_PARTNER_INST_ETHDOMAIN",
        "N_PARTNER_INST_NAT_OUTSIDE_DOMAIN",
        "N_PARTNER_INST_NAT",
        "N_PARTNER_INST_INT",
    ]

    source_map = {
        "N_PARTNER_INST_TOTAL_EXT": "n_partner_inst_total_ext",
        "N_PARTNER_INST_ETHDOMAIN": "n_partner_inst_ethdomain",
        "N_PARTNER_INST_NAT_OUTSIDE_DOMAIN": "n_partner_inst_nat_outside_domain",
        "N_PARTNER_INST_NAT": "n_partner_inst_nat",
        "N_PARTNER_INST_INT": "n_partner_inst_int",
    }

    for metric in base_metric_names:
        col = source_map[metric]
        if sub.empty:
            result[f"AVG_{metric}"] = None
            result[f"MED_{metric}"] = None
        else:
            result[f"AVG_{metric}"] = round(float(sub[col].mean()), 6)
            result[f"MED_{metric}"] = round(float(sub[col].median()), 6)

    if sub.empty or p_full == 0:
        result["PP_ANY_NAT_PARTNER"] = None
        result["PP_ANY_INT_PARTNER"] = None
    else:
        result["PP_ANY_NAT_PARTNER"] = round(float(sub["has_any_nat_partner"].mean()), 6)
        result["PP_ANY_INT_PARTNER"] = round(float(sub["has_any_int_partner"].mean()), 6)

    return result


def build_ma_df(raw_df: pd.DataFrame, ma_window: int) -> pd.DataFrame:
    cols = [MA_YEAR_COL] + METRIC_ORDER
    df = _prepare_inputs(raw_df)
    if df.empty:
        return pd.DataFrame(columns=cols)

    years = sorted(df["year"].unique())
    max_year = max(years)
    start_years = [y for y in years if y + (ma_window - 1) <= max_year]

    rows: list[dict[str, float | int | str | None]] = []
    for y_start in start_years:
        y_end = y_start + (ma_window - 1)
        row = {MA_YEAR_COL: f"{y_start}-{y_end}"}
        row.update(_compute_window_metrics(df, y0=y_start, y1=y_end))
        rows.append(row)

    return pd.DataFrame(rows, columns=cols)


def build_full_period_df(raw_df: pd.DataFrame, *, y0: int, y1: int) -> pd.DataFrame:
    cols = [MA_YEAR_COL] + METRIC_ORDER
    label = f"{y0}-{y1}"

    df = _prepare_inputs(raw_df)
    if df.empty:
        row = {MA_YEAR_COL: label, **{metric: None for metric in METRIC_ORDER}}
        return pd.DataFrame([row], columns=cols)

    row = {MA_YEAR_COL: label}
    row.update(_compute_window_metrics(df, y0=y0, y1=y1))
    return pd.DataFrame([row], columns=cols)


def build_table_tex(
    ma_df: pd.DataFrame,
    full_period_df: pd.DataFrame,
    *,
    full_period_label: str,
    include_full_period_column: bool = True,
    header_rotation_deg: float = 60,
) -> str:
    year_cols = (
        sorted(ma_df[MA_YEAR_COL].dropna().unique(), key=sort_year_label)
        if not ma_df.empty
        else []
    )
    value_map = (
        ma_df.set_index(MA_YEAR_COL).to_dict(orient="index") if not ma_df.empty else {}
    )
    full_period_row = (
        full_period_df.iloc[0].to_dict() if not full_period_df.empty else {}
    )

    col_headers = year_cols + (
        [full_period_label] if include_full_period_column else []
    )

    if include_full_period_column and year_cols:
        col_spec = "@{}l" + ("r" * len(year_cols)) + "|r@{}"
    elif include_full_period_column:
        col_spec = "@{}lr@{}"
    else:
        col_spec = "@{}l" + ("r" * len(year_cols)) + "@{}"

    rotation = (
        int(header_rotation_deg)
        if float(header_rotation_deg).is_integer()
        else float(header_rotation_deg)
    )

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

    def render_value(metric: str, value) -> str:
        if metric in COUNT_METRICS:
            return fmt_count(value)
        if metric in PERCENT_METRICS:
            return fmt_pct(value, 1)
        if metric in DECIMAL_METRICS:
            return fmt_decimal(value, 2)
        return fmt_decimal(value, 2)

    def append_section(title: str, rows: list[dict[str, str]]) -> None:
        n_cols = len(col_headers) + 1
        lines.append(rf"  \multicolumn{{{n_cols}}}{{c}}{{{title}}} \\")
        lines.append(r"  \midrule")
        for row in rows:
            metric = row["metric"]
            rendered_vals = [
                render_value(metric, value_map.get(year, {}).get(metric))
                for year in year_cols
            ]
            if include_full_period_column:
                rendered_vals.append(render_value(metric, full_period_row.get(metric)))
            lines.append(f"  {row['label']} & " + " & ".join(rendered_vals) + r" \\")

    append_section("Output", OUTPUT_ROWS)
    lines.append(r"  \midrule")
    append_section("Partner institutions per publication (mean)", MEAN_ROWS)
    lines.append(r"  \midrule")
    append_section("Partner institutions per publication (median)", MEDIAN_ROWS)
    lines.append(r"  \midrule")
    append_section("Bridge shares (presence-based)", BRIDGE_ROWS)

    lines.append(r"  \bottomrule")
    lines.append(r"\end{tabular}%")
    lines.append(r"\end{adjustbox}")
    lines.append("")
    return "\n".join(lines)


asset = Asset(script_file=__file__, institutions=ALL_INSTITUTIONS)
header_rotation_deg = float(getattr(asset, "table_header_rotation_deg", 60))
ma_window = max(1, int(asset.year_range_moving))
full_period_label = f"{asset.year_first}-{asset.year_last}"

for inst, con in asset.iterate_institutions():
    raw_df = asset.extract(
        con=con,
        inst=inst,
        query=q_partner_intensity_raw(inst, asset.year_first, asset.year_last),
        out_name="data_raw.csv",
    )

    out = asset.inst_dir(inst)
    ma_df = build_ma_df(raw_df, ma_window)
    full_period_df = build_full_period_df(
        raw_df, y0=asset.year_first, y1=asset.year_last
    )

    command_df = ma_df.copy()
    if not full_period_df.empty:
        command_df = pd.concat([command_df, full_period_df], ignore_index=True)
    command_df.to_csv(out / "data.csv", index=False)

    table_data_df = ma_df.melt(
        id_vars=[MA_YEAR_COL],
        value_vars=METRIC_ORDER,
        var_name="indicator",
        value_name="value",
    )

    if INCLUDE_FULL_PERIOD_COLUMN:
        full_period_row = (
            full_period_df.iloc[0].to_dict() if not full_period_df.empty else {}
        )
        full_period_rows = [
            {
                MA_YEAR_COL: full_period_label,
                "indicator": metric,
                "value": full_period_row.get(metric),
            }
            for metric in METRIC_ORDER
        ]
        table_data_df = pd.concat(
            [table_data_df, pd.DataFrame(full_period_rows)], ignore_index=True
        )

    year_cols = (
        sorted(ma_df[MA_YEAR_COL].dropna().unique(), key=sort_year_label)
        if not ma_df.empty
        else []
    )
    year_order = {year: idx for idx, year in enumerate(year_cols)}
    year_order[full_period_label] = len(year_cols)
    metric_order = {metric: idx for idx, metric in enumerate(METRIC_ORDER)}
    table_data_df = (
        table_data_df.assign(
            _indicator_order=lambda d: d["indicator"].map(metric_order).fillna(10**9),
            _year_order=lambda d: d[MA_YEAR_COL].map(year_order).fillna(10**9),
        )
        .sort_values(["_indicator_order", "_year_order"])
        .drop(columns=["_indicator_order", "_year_order"])
        .reset_index(drop=True)
    )
    table_data_df.to_csv(out / "table_data.csv", index=False)

    (out / "table.tex").write_text(
        build_table_tex(
            ma_df,
            full_period_df,
            full_period_label=OVERALL_COLUMN_LABEL,
            include_full_period_column=INCLUDE_FULL_PERIOD_COLUMN,
            header_rotation_deg=header_rotation_deg,
        ),
        encoding="utf-8",
    )
