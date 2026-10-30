import pandas as pd

from core.asset import Asset
from utility import get_indicator_catalog_dict


MA_YEAR_COL = "MA_year"
OVERALL_LABEL = "Overall"
INCLUDE_FULL_PERIOD_COLUMN = True

TYPE_ORDER = ["closed", "open", "gold", "green", "hybrid"]
OPEN_SUBTYPES = ["gold", "green", "hybrid"]
TYPE_LABELS = {
    "closed": r"\shortstack[l]{Closed access\\incl. bronze}",
    "open": "Open access",
    "gold": r"\shortstack[l]{Gold\\incl. diamond}",
    "green": "Green",
    "hybrid": "Hybrid",
}
TYPE_MAP = {
    "gold": "gold",
    "diamond": "gold",
    "hybrid": "hybrid",
    "green": "green",
    "closed": "closed",
    "bronze": "closed",
}

INDICATOR_ORDER = [
    "P_FULL",
    "OA_PP_FULL",
    "PP_TOPTEN_FRAC",
    "C_MNCS_FRAC",
    "PP_INT_COLLAB",
]
COUNT_METRICS = {"P_FULL"}
SHARE_METRICS = {"OA_PP_FULL", "PP_TOPTEN_FRAC", "PP_INT_COLLAB"}


def query_function(inst: str, y0: int, y1: int) -> str:
    return f"""
        WITH own_inst AS (
            SELECT institution_id
            FROM reports.report_institutions_ids
            WHERE report_name = '{inst}'
        ),
        report_works AS (
            SELECT DISTINCT
                rm.work_id,
                w.publication_year AS year,
                LOWER(TRIM(COALESCE(w.open_access_oa_status, ''))) AS oa_status_raw,
                CASE WHEN wm.is_top10 = 1 THEN 1 ELSE 0 END AS is_top10,
                wm.cohort_is_reliable AS pptop10_cohort_is_reliable,
                wm.n_institutions_on_work AS pptop10_n_institutions_on_work,
                m.norm_vs_mean,
                m.cohort_is_reliable AS mncs_cohort_is_reliable,
                m.n_institutions_on_work AS mncs_n_institutions_on_work
            FROM reports.report_membership rm
            INNER JOIN core.work w
                ON w.work_id = rm.work_id
            LEFT JOIN marts.work_metrics wm
                ON wm.work_id = rm.work_id
            LEFT JOIN marts.work_citation_metrics m
                ON m.work_id = rm.work_id
            WHERE rm.report_name = '{inst}'
              AND w.publication_year BETWEEN {y0} AND {y1}
        ),
        work_collab AS (
            SELECT
                rw.work_id,
                MAX(
                    CASE
                        WHEN wii.institution_id NOT IN (SELECT institution_id FROM own_inst)
                         AND COALESCE(dc.country_code, '') <> 'CH'
                        THEN 1 ELSE 0
                    END
                ) AS has_int_collab
            FROM report_works rw
            JOIN marts.work_institution_info wii
                ON wii.work_id = rw.work_id
            LEFT JOIN core.dim_institution di
                ON di.institution_id = wii.institution_id
            LEFT JOIN core.dim_country dc
                ON dc.country_id = di.country_id
            GROUP BY rw.work_id
        )
        SELECT
            rw.work_id,
            rw.year,
            rw.oa_status_raw,
            rw.is_top10,
            rw.pptop10_cohort_is_reliable,
            rw.pptop10_n_institutions_on_work,
            rw.norm_vs_mean,
            rw.mncs_cohort_is_reliable,
            rw.mncs_n_institutions_on_work,
            COALESCE(wc.has_int_collab, 0) AS has_int_collab
        FROM report_works rw
        LEFT JOIN work_collab wc
            ON wc.work_id = rw.work_id
        ORDER BY rw.year, rw.oa_status_raw, rw.work_id;
    """


def to_bool(series: pd.Series) -> pd.Series:
    return (
        series.astype("string")
        .str.strip()
        .str.lower()
        .isin({"1", "true", "t", "yes", "y"})
        .fillna(False)
    )


def parse_digits(raw_value, default: int) -> int:
    raw = str(raw_value).strip()
    if raw == "" or raw.lower() == "nan":
        return default
    try:
        parsed = int(float(raw))
    except ValueError:
        return default
    return parsed if parsed >= 0 else default


def format_count(value) -> str:
    if value is None or pd.isna(value):
        return r"\textit{n/a}"
    return f"{int(round(float(value))):,}"


def format_pct(value, digits: int) -> str:
    if value is None or pd.isna(value):
        return r"\textit{n/a}"
    return f"{100.0 * float(value):.{digits}f}\\%"


def format_float(value, digits: int) -> str:
    if value is None or pd.isna(value):
        return r"\textit{n/a}"
    return f"{float(value):.{digits}f}"


asset = Asset(script_file=__file__)
indicator_catalog = get_indicator_catalog_dict()

rotation_raw = float(getattr(asset, "table_header_rotation_deg", 60))
header_rotation = int(rotation_raw) if float(rotation_raw).is_integer() else rotation_raw
ma_window = max(1, int(asset.year_range_moving))
pp_topten_digits = parse_digits(indicator_catalog.get("PP_TOPTEN_FRAC", {}).get("display_digits", ""), 1)

metric_labels: dict[str, str] = {}
for metric in INDICATOR_ORDER:
    symbol_tex = str(indicator_catalog.get(metric, {}).get("symbol_tex", "")).strip()
    if symbol_tex.lower() in {"", "nan", "none"}:
        symbol_tex = ""
    metric_labels[metric] = f"${symbol_tex}$" if symbol_tex else metric
metric_labels["OA_PP_FULL"] = "Share of total"

for inst, con in asset.iterate_institutions():
    raw_df = asset.extract(
        con=con,
        inst=inst,
        query=query_function(inst, asset.year_first, asset.year_last),
        out_name="raw_data.csv",
    )

    df = raw_df.copy()
    if not df.empty:
        df["year"] = pd.to_numeric(df["year"], errors="coerce")
        df = df.dropna(subset=["year", "work_id"]).copy()
        df["year"] = df["year"].astype(int)
        df = df.sort_values(["year", "oa_status_raw", "work_id"]).drop_duplicates(subset=["work_id"], keep="first")

        df["oa_type"] = df["oa_status_raw"].astype("string").str.strip().str.lower().map(TYPE_MAP)
        df = df[df["oa_type"].notna()].copy()

        if not df.empty:
            df["is_top10"] = to_bool(df["is_top10"])
            df["has_int_collab"] = to_bool(df["has_int_collab"])
            df["pptop10_cohort_is_reliable"] = to_bool(df["pptop10_cohort_is_reliable"])
            df["mncs_cohort_is_reliable"] = to_bool(df["mncs_cohort_is_reliable"])
            df["pptop10_n_institutions_on_work"] = pd.to_numeric(df["pptop10_n_institutions_on_work"], errors="coerce")
            df["mncs_n_institutions_on_work"] = pd.to_numeric(df["mncs_n_institutions_on_work"], errors="coerce")
            df["norm_vs_mean"] = pd.to_numeric(df["norm_vs_mean"], errors="coerce")

    rows = []
    if df.empty:
        year_labels: list[str] = []
        periods = [(OVERALL_LABEL, df)]
    else:
        years = sorted(df["year"].unique())
        start_years = [y for y in years if y + (ma_window - 1) <= max(years)]
        year_labels = [f"{y}-{y + (ma_window - 1)}" for y in start_years]
        periods = [
            (f"{y}-{y + (ma_window - 1)}", df[(df["year"] >= y) & (df["year"] <= y + (ma_window - 1))].copy())
            for y in start_years
        ]
        if INCLUDE_FULL_PERIOD_COLUMN:
            periods.append((OVERALL_LABEL, df[(df["year"] >= asset.year_first) & (df["year"] <= asset.year_last)].copy()))

    for period_label, period_df in periods:
        total_p_full = int(period_df["work_id"].nunique()) if not period_df.empty else 0

        for oa_status in TYPE_ORDER:
            if oa_status == "open":
                sub = period_df[period_df["oa_type"].isin(OPEN_SUBTYPES)].copy()
            else:
                sub = period_df[period_df["oa_type"] == oa_status].copy()

            p_full = int(sub["work_id"].nunique()) if not sub.empty else 0

            top_sub = sub[
                sub["pptop10_cohort_is_reliable"]
                & sub["pptop10_n_institutions_on_work"].notna()
                & (sub["pptop10_n_institutions_on_work"] > 0)
            ].copy()
            if top_sub.empty:
                p_topten_frac = 0.0
                pp_topten_frac = None
            else:
                top_w = 1.0 / top_sub["pptop10_n_institutions_on_work"]
                p_topten_frac = float((top_sub["is_top10"].astype(float) * top_w).sum())
                top_w_sum = float(top_w.sum())
                pp_topten_frac = (p_topten_frac / top_w_sum) if top_w_sum > 0 else None

            mncs_sub = sub[
                sub["mncs_cohort_is_reliable"]
                & sub["mncs_n_institutions_on_work"].notna()
                & (sub["mncs_n_institutions_on_work"] > 0)
                & sub["norm_vs_mean"].notna()
            ].copy()
            if mncs_sub.empty:
                c_mncs_frac = None
            else:
                mncs_w = 1.0 / mncs_sub["mncs_n_institutions_on_work"]
                mncs_w_sum = float(mncs_w.sum())
                if mncs_w_sum > 0:
                    c_mncs_frac = float((mncs_sub["norm_vs_mean"] * mncs_w).sum() / mncs_w_sum)
                else:
                    c_mncs_frac = None

            pp_int_collab = float(sub["has_int_collab"].mean()) if not sub.empty else None

            rows.append(
                {
                    "oa_status": oa_status,
                    MA_YEAR_COL: period_label,
                    "P_FULL": p_full,
                    "OA_PP_FULL": round(p_full / total_p_full, 6) if total_p_full > 0 else None,
                    "PP_TOPTEN_FRAC": round(pp_topten_frac, 6) if pp_topten_frac is not None else None,
                    "C_MNCS_FRAC": round(c_mncs_frac, 6) if c_mncs_frac is not None else None,
                    "PP_INT_COLLAB": round(pp_int_collab, 6) if pp_int_collab is not None else None,
                }
            )

    data_df = pd.DataFrame(rows, columns=["oa_status", MA_YEAR_COL] + INDICATOR_ORDER)
    year_order = {label: idx for idx, label in enumerate(year_labels)}
    year_order[OVERALL_LABEL] = len(year_labels)

    if not data_df.empty:
        data_df = (
            data_df.assign(
                oa_status_order=lambda d: d["oa_status"].map({status: i for i, status in enumerate(TYPE_ORDER)}),
                year_order=lambda d: d[MA_YEAR_COL].map(year_order).fillna(10**9),
            )
            .sort_values(["oa_status_order", "year_order"])
            .drop(columns=["oa_status_order", "year_order"])
            .reset_index(drop=True)
        )
        data_df["id"] = data_df["oa_status"].astype(str) + "-" + data_df[MA_YEAR_COL].astype(str)
        ma_only = data_df[MA_YEAR_COL] != OVERALL_LABEL
        for oa_status in TYPE_ORDER:
            status_mask = ma_only & (data_df["oa_status"] == oa_status)
            status_suffix = oa_status.upper()
            for metric in INDICATOR_ORDER:
                data_df[f"{metric}_{status_suffix}_MA"] = data_df[metric].where(status_mask)

    ma_df = data_df[data_df[MA_YEAR_COL] != OVERALL_LABEL].copy()
    full_df = data_df[data_df[MA_YEAR_COL] == OVERALL_LABEL].copy()

    table_rows = []
    for oa_status in TYPE_ORDER:
        for indicator in INDICATOR_ORDER:
            for year_label in year_labels:
                value = None
                if not ma_df.empty:
                    hit = ma_df[
                        (ma_df["oa_status"] == oa_status)
                        & (ma_df[MA_YEAR_COL] == year_label)
                    ]
                    if not hit.empty:
                        value = hit.iloc[0][indicator]
                table_rows.append(
                    {
                        "oa_status": oa_status,
                        MA_YEAR_COL: year_label,
                        "indicator": indicator,
                        "value": value,
                    }
                )

            if INCLUDE_FULL_PERIOD_COLUMN:
                value = None
                if not full_df.empty:
                    hit = full_df[full_df["oa_status"] == oa_status]
                    if not hit.empty:
                        value = hit.iloc[0][indicator]
                table_rows.append(
                    {
                        "oa_status": oa_status,
                        MA_YEAR_COL: OVERALL_LABEL,
                        "indicator": indicator,
                        "value": value,
                    }
                )

    table_data_df = pd.DataFrame(table_rows, columns=["oa_status", MA_YEAR_COL, "indicator", "value"])

    lines: list[str] = []
    n_year = len(year_labels)
    if INCLUDE_FULL_PERIOD_COLUMN and n_year > 0:
        colspec = "@{}ll" + ("r" * n_year) + "|r@{}"
    elif INCLUDE_FULL_PERIOD_COLUMN:
        colspec = "@{}llr@{}"
    else:
        colspec = "@{}ll" + ("r" * n_year) + "@{}"

    lines.append(r"\begin{adjustbox}{max width=\linewidth}%")
    lines.append(rf"\begin{{tabular}}{{{colspec}}}")
    lines.append(r"  \toprule")

    header_labels = year_labels + ([OVERALL_LABEL] if INCLUDE_FULL_PERIOD_COLUMN else [])
    header_cells = [rf"\rotatebox[origin=c]{{{header_rotation}}}{{{h}}}" for h in header_labels]
    lines.append("  Access type & Indicator & " + " & ".join(header_cells) + r" \\")
    lines.append(r"  \midrule")

    for status_i, oa_status in enumerate(TYPE_ORDER):
        for indicator_i, indicator in enumerate(INDICATOR_ORDER):
            left = TYPE_LABELS[oa_status] if indicator_i == 0 else ""
            label = metric_labels.get(indicator, indicator)

            values_for_row = []
            for year_label in year_labels:
                value = None
                if not ma_df.empty:
                    hit = ma_df[(ma_df["oa_status"] == oa_status) & (ma_df[MA_YEAR_COL] == year_label)]
                    if not hit.empty:
                        value = hit.iloc[0][indicator]

                if indicator in COUNT_METRICS:
                    values_for_row.append(format_count(value))
                elif indicator in SHARE_METRICS:
                    if indicator == "PP_TOPTEN_FRAC":
                        values_for_row.append(format_pct(value, pp_topten_digits))
                    else:
                        values_for_row.append(format_pct(value, 0))
                else:
                    values_for_row.append(format_float(value, 2))

            if INCLUDE_FULL_PERIOD_COLUMN:
                value = None
                if not full_df.empty:
                    hit = full_df[full_df["oa_status"] == oa_status]
                    if not hit.empty:
                        value = hit.iloc[0][indicator]

                if indicator in COUNT_METRICS:
                    values_for_row.append(format_count(value))
                elif indicator in SHARE_METRICS:
                    if indicator == "PP_TOPTEN_FRAC":
                        values_for_row.append(format_pct(value, pp_topten_digits))
                    else:
                        values_for_row.append(format_pct(value, 0))
                else:
                    values_for_row.append(format_float(value, 2))

            lines.append(f"  {left} & {label} & " + " & ".join(values_for_row) + r" \\")

        if status_i < len(TYPE_ORDER) - 1:
            lines.append(r"  \midrule")

    lines.append(r"  \bottomrule")
    lines.append(r"\end{tabular}%")
    lines.append(r"\end{adjustbox}")
    lines.append("")

    out = asset.inst_dir(inst)
    data_df.to_csv(out / "data.csv", index=False)
    table_data_df.to_csv(out / "table_data.csv", index=False)
    (out / "table.tex").write_text("\n".join(lines), encoding="utf-8")
