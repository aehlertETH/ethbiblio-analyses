import pandas as pd

from core.asset import Asset
from utility import get_indicator_catalog_dict


MA_YEAR_COL = "MA_year"
INCLUDE_FULL_PERIOD_COLUMN = True
INCLUDE_SECTION_HEADINGS = True
OVERALL_COLUMN_LABEL = "Overall"
LEFT_COL_HEADER = "Indicator"
DOMAIN_UNIT_REPORTS = ["ethz", "epfl", "psi", "empa", "eawag", "wsl"]

OUTPUT_ROWS = [
    {"metric": "P_FULL", "label_mode": "indicator"},
    {"metric": "P_COLLAB_FULL", "label_mode": "indicator"},
    {"metric": "P_FRAC", "label_mode": "indicator"},
    {"metric": "P_COLLAB_FRAC", "label_mode": "indicator"},
]

SCOPE_ROWS = [
    {
        "metric": "PP_COLLAB",
        "label_mode": "text",
        "label_text": "All collaborations",
    },
    {
        "metric": "PP_COLLAB_ETHDOMAIN_FULL",
        "label_mode": "text",
        "label_text": "Within ETH Domain",
    },
    {
        "metric": "PP_COLLAB_NAT_OUTSIDE_DOMAIN_FULL",
        "label_mode": "text",
        "label_text": "National (outside ETH Domain)",
    },
    {
        "metric": "PP_COLLAB_NAT_FULL",
        "label_mode": "text",
        "label_text": "National (including within ETH Domain)",
    },
    {
        "metric": "PP_INT_COLLAB",
        "label_mode": "text",
        "label_text": "International",
    },
    {
        "metric": "PP_INDUSTRY_COLLAB",
        "label_mode": "text",
        "label_text": "Industry collaboration",
    },
]

METRIC_ORDER = [row["metric"] for row in OUTPUT_ROWS + SCOPE_ROWS]

COUNT_METRICS = {
    "P_FULL",
    "P_FRAC",
    "P_COLLAB_FULL",
    "P_COLLAB_FRAC",
}
PERCENT_METRICS = {
    "PP_COLLAB",
    "PP_COLLAB_ETHDOMAIN_FULL",
    "PP_COLLAB_NAT_OUTSIDE_DOMAIN_FULL",
    "PP_COLLAB_NAT_FULL",
    "PP_INT_COLLAB",
    "PP_INDUSTRY_COLLAB",
}

INDICATOR_ID_BY_METRIC = {
    "P_FULL": "P_FULL",
    "P_FRAC": "P_FRAC",
    "P_COLLAB_FULL": "P_COLLAB_FULL",
    "P_COLLAB_FRAC": "P_COLLAB_FRAC",
    "PP_COLLAB": "PP_COLLAB",
}


def q_collab_trend_raw(inst: str, y0: int, y1: int) -> str:
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
        external_partner_flags AS (
            SELECT
                b.work_id,
                COALESCE(
                    MAX(
                        CASE
                            WHEN wii.institution_id NOT IN (SELECT institution_id FROM own_inst)
                            THEN 1 ELSE 0
                        END
                    ),
                    0
                ) AS has_external_collab,
                COALESCE(
                    MAX(
                        CASE
                            WHEN wii.institution_id NOT IN (SELECT institution_id FROM own_inst)
                             AND COALESCE(dc.country_code, '') = 'CH'
                             AND wii.institution_id NOT IN (SELECT institution_id FROM domain_inst)
                            THEN 1 ELSE 0
                        END
                    ),
                    0
                ) AS has_nat_outside_domain_collab,
                COALESCE(
                    MAX(
                        CASE
                            WHEN wii.institution_id NOT IN (SELECT institution_id FROM own_inst)
                             AND COALESCE(dc.country_code, '') <> 'CH'
                            THEN 1 ELSE 0
                        END
                    ),
                    0
                ) AS has_int_collab,
                COALESCE(
                    MAX(
                        CASE
                            WHEN wii.institution_id NOT IN (SELECT institution_id FROM own_inst)
                             AND LOWER(COALESCE(di.type, '')) = 'company'
                            THEN 1 ELSE 0
                        END
                    ),
                    0
                ) AS has_industry_collab
            FROM base b
            LEFT JOIN marts.work_institution_info wii
                ON wii.work_id = b.work_id
            LEFT JOIN core.dim_institution di
                ON di.institution_id = wii.institution_id
            LEFT JOIN core.dim_country dc
                ON dc.country_id = di.country_id
            GROUP BY b.work_id
        )
        SELECT
            base.work_id,
            base.year,
            base.n_institutions_on_work,
            CASE
                WHEN COALESCE(um.n_eth_domain_units, 0) >= 2
                     OR COALESCE(epf.has_external_collab, 0) = 1
                THEN 1 ELSE 0
            END AS has_collab,
            CASE
                WHEN COALESCE(um.n_eth_domain_units, 0) >= 2
                     OR COALESCE(epf.has_nat_outside_domain_collab, 0) = 1
                THEN 1 ELSE 0
            END AS has_nat_collab,
            CASE
                WHEN COALESCE(um.n_eth_domain_units, 0) >= 2
                THEN 1 ELSE 0
            END AS has_ethdomain_collab,
            COALESCE(epf.has_nat_outside_domain_collab, 0) AS has_nat_outside_domain_collab,
            COALESCE(epf.has_int_collab, 0) AS has_int_collab,
            COALESCE(epf.has_industry_collab, 0) AS has_industry_collab
        FROM base
        LEFT JOIN unit_membership um
            ON um.work_id = base.work_id
        LEFT JOIN external_partner_flags epf
            ON epf.work_id = base.work_id
        ORDER BY base.year, base.work_id;
    """


def to_bool(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)
    return (
        series.astype("string")
        .str.strip()
        .str.lower()
        .isin({"1", "true", "t", "yes", "y"})
    )


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


def sort_year_label(label: str) -> int:
    try:
        return int(str(label).split("-")[0])
    except Exception:
        return -(10**9)


def get_metric_labels(indicator_catalog_dict: dict) -> dict[str, str]:
    labels: dict[str, str] = {}
    for metric in METRIC_ORDER:
        indicator_id = INDICATOR_ID_BY_METRIC.get(metric)
        if indicator_id:
            entry = (indicator_catalog_dict or {}).get(indicator_id, {})
            symbol = str(entry.get("symbol_tex", "")).strip()
            if symbol:
                labels[metric] = f"${symbol}$"
                continue

        labels[metric] = tex_escape_text(metric)

    return labels


def get_scope_header_title(indicator_catalog_dict: dict) -> str:
    entry = (indicator_catalog_dict or {}).get("PP_COLLAB", {})
    symbol = str(entry.get("symbol_tex", "")).strip()
    if not symbol:
        symbol = r"\mathrm{PP}\lbrack\mathrm{collab}\rbrack_{\mathrm{full}}"

    return (
        r"Share of collaborative output as \% of total output "
        + f"(${symbol}$) by collaboration scope"
    )


def build_table_sections(
    scope_header_title: str,
) -> list[tuple[str, list[dict[str, str]]]]:
    return [
        ("Output", OUTPUT_ROWS),
        (scope_header_title, SCOPE_ROWS),
    ]


def _prepare_inputs(raw_df: pd.DataFrame) -> pd.DataFrame:
    df = raw_df.copy()
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df = df.dropna(subset=["year", "work_id"]).copy()
    if df.empty:
        return pd.DataFrame()

    df["year"] = df["year"].astype(int)
    df = df.sort_values(["year", "work_id"]).drop_duplicates(
        subset=["work_id"], keep="first"
    )

    df["n_institutions_on_work"] = pd.to_numeric(
        df["n_institutions_on_work"], errors="coerce"
    )
    df["has_collab"] = to_bool(df["has_collab"])
    df["has_nat_collab"] = to_bool(df["has_nat_collab"])
    df["has_ethdomain_collab"] = to_bool(df["has_ethdomain_collab"])
    df["has_nat_outside_domain_collab"] = to_bool(df["has_nat_outside_domain_collab"])
    df["has_int_collab"] = to_bool(df["has_int_collab"])
    df["has_industry_collab"] = to_bool(df["has_industry_collab"])

    return df


def _sum_fractional_count(
    sub: pd.DataFrame, mask: pd.Series | None = None
) -> float | None:
    if sub.empty:
        return None

    valid_n = sub["n_institutions_on_work"].notna() & (
        sub["n_institutions_on_work"] > 0
    )
    if mask is not None:
        valid_n = valid_n & mask

    if not valid_n.any():
        return None
    return float((1.0 / sub.loc[valid_n, "n_institutions_on_work"]).sum())


def _compute_window_metrics(
    df: pd.DataFrame,
    *,
    y0: int,
    y1: int,
) -> dict[str, float | int | None]:
    sub = df[(df["year"] >= y0) & (df["year"] <= y1)].copy()
    p_full = int(sub["work_id"].nunique())

    p_frac = _sum_fractional_count(sub)
    p_collab = int(sub["has_collab"].sum()) if not sub.empty else 0
    p_collab_frac = _sum_fractional_count(sub, sub["has_collab"])

    p_collab_nat = int(sub["has_nat_collab"].sum()) if not sub.empty else 0
    p_collab_eth = int(sub["has_ethdomain_collab"].sum()) if not sub.empty else 0
    p_collab_nat_outside_domain = (
        int(sub["has_nat_outside_domain_collab"].sum()) if not sub.empty else 0
    )
    p_int_collab = int(sub["has_int_collab"].sum()) if not sub.empty else 0
    p_industry_collab = int(sub["has_industry_collab"].sum()) if not sub.empty else 0

    pp_collab = (p_collab / p_full) if p_full > 0 else None
    pp_collab_nat = (p_collab_nat / p_full) if p_full > 0 else None
    pp_collab_eth = (p_collab_eth / p_full) if p_full > 0 else None
    pp_collab_nat_outside_domain = (
        (p_collab_nat_outside_domain / p_full) if p_full > 0 else None
    )
    pp_int_collab = (p_int_collab / p_full) if p_full > 0 else None
    pp_industry_collab = (p_industry_collab / p_full) if p_full > 0 else None

    return {
        "P_FULL": p_full,
        "P_FRAC": round(p_frac, 6) if p_frac is not None else None,
        "P_COLLAB_FULL": p_collab,
        "P_COLLAB_FRAC": round(p_collab_frac, 6) if p_collab_frac is not None else None,
        "PP_COLLAB": round(pp_collab, 6) if pp_collab is not None else None,
        "PP_COLLAB_ETHDOMAIN_FULL": round(pp_collab_eth, 6)
        if pp_collab_eth is not None
        else None,
        "PP_COLLAB_NAT_OUTSIDE_DOMAIN_FULL": (
            round(pp_collab_nat_outside_domain, 6)
            if pp_collab_nat_outside_domain is not None
            else None
        ),
        "PP_COLLAB_NAT_FULL": round(pp_collab_nat, 6)
        if pp_collab_nat is not None
        else None,
        "PP_INT_COLLAB": round(pp_int_collab, 6) if pp_int_collab is not None else None,
        "PP_INDUSTRY_COLLAB": (
            round(pp_industry_collab, 6) if pp_industry_collab is not None else None
        ),
    }


def build_ma_df(raw_df: pd.DataFrame, ma_window: int) -> pd.DataFrame:
    cols = [MA_YEAR_COL] + METRIC_ORDER
    df = _prepare_inputs(raw_df)
    if df.empty:
        return pd.DataFrame(columns=cols)

    years = sorted(df["year"].unique())
    if not years:
        return pd.DataFrame(columns=cols)

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
    metric_labels: dict[str, str],
    *,
    table_sections: list[tuple[str, list[dict[str, str]]]],
    full_period_df: pd.DataFrame,
    full_period_label: str,
    include_full_period_column: bool = INCLUDE_FULL_PERIOD_COLUMN,
    include_section_headings: bool = INCLUDE_SECTION_HEADINGS,
    header_rotation_deg: float = 60,
) -> str:
    if ma_df.empty and not include_full_period_column:
        return "\\textit{No MA data available.}\n"

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

    lines = []
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
            return fmt_pct(value, 0)
        return fmt_count(value)

    def append_metric_row(row_def: dict[str, str]) -> None:
        metric = row_def["metric"]
        if row_def.get("label_mode") == "text":
            label = tex_escape_text(str(row_def.get("label_text", metric)))
        else:
            label = metric_labels.get(metric, tex_escape_text(metric))
        rendered_vals = [
            render_value(metric, value_map.get(year, {}).get(metric))
            for year in year_cols
        ]
        if include_full_period_column:
            rendered_vals.append(render_value(metric, full_period_row.get(metric)))
        lines.append(f"  {label} & " + " & ".join(rendered_vals) + r" \\")

    if include_section_headings:
        n_cols = len(col_headers) + 1
        first_section = True
        for title, rows in table_sections:
            if not first_section:
                lines.append(r"  \midrule")
            first_section = False
            lines.append(rf"  \multicolumn{{{n_cols}}}{{c}}{{{title}}} \\")
            lines.append(r"  \midrule")
            for row_def in rows:
                append_metric_row(row_def)
    else:
        for _title, rows in table_sections:
            for row_def in rows:
                append_metric_row(row_def)

    lines.append(r"  \bottomrule")
    lines.append(r"\end{tabular}%")
    lines.append(r"\end{adjustbox}")
    lines.append("")
    return "\n".join(lines)


asset = Asset(script_file=__file__)
indicator_catalog_dict = get_indicator_catalog_dict()
metric_labels = get_metric_labels(indicator_catalog_dict)
scope_header_title = get_scope_header_title(indicator_catalog_dict)
table_sections = build_table_sections(scope_header_title)
header_rotation_deg = float(getattr(asset, "table_header_rotation_deg", 60))
ma_window = max(1, int(asset.year_range_moving))
full_period_label = f"{asset.year_first}-{asset.year_last}"

for inst, con in asset.iterate_institutions():
    raw_df = con.query(q_collab_trend_raw(inst, asset.year_first, asset.year_last)).df()

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
                _indicator_order=lambda d: (
                    d["indicator"].map(metric_order).fillna(10**9)
                ),
                _year_order=lambda d: d[MA_YEAR_COL].map(year_order).fillna(10**9),
            )
            .sort_values(["_indicator_order", "_year_order"])
            .drop(columns=["_indicator_order", "_year_order"])
            .reset_index(drop=True)
        )
    else:
        metric_order = {metric: idx for idx, metric in enumerate(METRIC_ORDER)}
        table_data_df = (
            table_data_df.assign(
                _indicator_order=lambda d: (
                    d["indicator"].map(metric_order).fillna(10**9)
                ),
                _year_order=lambda d: d[MA_YEAR_COL].map(sort_year_label).fillna(10**9),
            )
            .sort_values(["_indicator_order", "_year_order"])
            .drop(columns=["_indicator_order", "_year_order"])
            .reset_index(drop=True)
        )

    table_data_df.to_csv(out / "table_data.csv", index=False)

    (out / "table.tex").write_text(
        build_table_tex(
            ma_df,
            metric_labels,
            table_sections=table_sections,
            full_period_df=full_period_df,
            full_period_label=OVERALL_COLUMN_LABEL,
            include_full_period_column=INCLUDE_FULL_PERIOD_COLUMN,
            include_section_headings=INCLUDE_SECTION_HEADINGS,
            header_rotation_deg=header_rotation_deg,
        ),
        encoding="utf-8",
    )
