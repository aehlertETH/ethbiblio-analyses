import pandas as pd

from core.asset import Asset
from utility import get_indicator_catalog_dict


REPORTS = [
    ("ethdomain", "ETH Domain", 1),
    ("ethz", "ETH Zurich", 2),
    ("epfl", "EPFL", 3),
    ("psi", "PSI", 4),
    ("wsl", "WSL", 5),
    ("empa", "Empa", 6),
    ("eawag", "Eawag", 7),
]
STATUS_ORDER = ["open", "closed"]
INDICATOR_ORDER = [
    "P_FULL",
    "OA_PP_FULL",
    "PP_TOPTEN_FRAC",
    "C_MNCS_FRAC",
    "PP_INT_COLLAB",
]
COUNT_METRICS = {"P_FULL"}
SHARE_METRICS = {"OA_PP_FULL", "PP_TOPTEN_FRAC", "PP_INT_COLLAB"}


def query_function(y0: int, y1: int) -> str:
    report_values = ",\n                ".join(
        f"('{report_name}', '{report_label}', {report_order})"
        for report_name, report_label, report_order in REPORTS
    )

    return f"""
        WITH target_reports(report_name, report_label, report_order) AS (
            VALUES
                {report_values}
        ),
        own_inst AS (
            SELECT
                tr.report_name,
                rii.institution_id
            FROM target_reports tr
            INNER JOIN reports.report_institutions_ids rii
                ON rii.report_name = tr.report_name
        ),
        report_works AS (
            SELECT DISTINCT
                tr.report_name,
                tr.report_label,
                tr.report_order,
                rm.work_id,
                w.publication_year AS year,
                CASE
                    WHEN w.open_access_oa_status_is_closed = TRUE
                      OR w.open_access_oa_status_is_bronze = TRUE
                    THEN 'closed'
                    ELSE 'open'
                END AS oa_status,
                m.norm_vs_mean,
                m.n_institutions_on_work AS mncs_n_institutions_on_work,
                m.cohort_is_reliable AS mncs_cohort_is_reliable,
                CASE WHEN wm.is_top10 = 1 THEN 1 ELSE 0 END AS is_top10,
                wm.n_institutions_on_work AS pptop10_n_institutions_on_work,
                wm.cohort_is_reliable AS pptop10_cohort_is_reliable
            FROM target_reports tr
            INNER JOIN reports.report_membership rm
                ON rm.report_name = tr.report_name
            INNER JOIN core.work w
                ON w.work_id = rm.work_id
            LEFT JOIN marts.work_citation_metrics m
                ON m.work_id = rm.work_id
            LEFT JOIN marts.work_metrics wm
                ON wm.work_id = rm.work_id
            WHERE w.publication_year BETWEEN {y0} AND {y1}
        ),
        work_collab AS (
            SELECT
                rw.report_name,
                rw.work_id,
                MAX(
                    CASE
                        WHEN wii.institution_id NOT IN (
                            SELECT oi.institution_id
                            FROM own_inst oi
                            WHERE oi.report_name = rw.report_name
                        )
                         AND COALESCE(dc.country_code, '') <> 'CH'
                        THEN 1 ELSE 0
                    END
                ) AS has_int_collab
            FROM report_works rw
            INNER JOIN marts.work_institution_info wii
                ON wii.work_id = rw.work_id
            LEFT JOIN core.dim_institution di
                ON di.institution_id = wii.institution_id
            LEFT JOIN core.dim_country dc
                ON dc.country_id = di.country_id
            GROUP BY rw.report_name, rw.work_id
        )
        SELECT
            rw.report_name,
            rw.report_label,
            rw.report_order,
            rw.work_id,
            rw.year,
            rw.oa_status,
            rw.norm_vs_mean,
            rw.mncs_n_institutions_on_work,
            rw.mncs_cohort_is_reliable,
            rw.is_top10,
            rw.pptop10_n_institutions_on_work,
            rw.pptop10_cohort_is_reliable,
            COALESCE(wc.has_int_collab, 0) AS has_int_collab
        FROM report_works rw
        LEFT JOIN work_collab wc
            ON wc.report_name = rw.report_name
           AND wc.work_id = rw.work_id
        ORDER BY rw.report_order, rw.year, rw.oa_status, rw.work_id;
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


asset = Asset(script_file=__file__, institutions=["ethdomain"])
indicator_catalog = get_indicator_catalog_dict()

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
        query=query_function(asset.year_first, asset.year_last),
        out_name="raw_data.csv",
    )

    df = raw_df.copy()
    if not df.empty:
        df["year"] = pd.to_numeric(df["year"], errors="coerce")
        df["report_order"] = pd.to_numeric(df["report_order"], errors="coerce")
        df = df.dropna(subset=["report_name", "report_order", "year", "work_id"]).copy()
        df["year"] = df["year"].astype(int)
        df["report_order"] = df["report_order"].astype(int)
        df = (
            df.sort_values(["report_order", "year", "oa_status", "work_id"])
            .drop_duplicates(subset=["report_name", "work_id"], keep="first")
            .reset_index(drop=True)
        )

        df["oa_status"] = (
            df["oa_status"].astype("string").str.strip().str.lower().replace({"": "open"}).fillna("open")
        )
        df["oa_status"] = df["oa_status"].where(df["oa_status"].isin(STATUS_ORDER), "open")

        df["is_top10"] = to_bool(df["is_top10"])
        df["has_int_collab"] = to_bool(df["has_int_collab"])
        df["mncs_cohort_is_reliable"] = to_bool(df["mncs_cohort_is_reliable"])
        df["pptop10_cohort_is_reliable"] = to_bool(df["pptop10_cohort_is_reliable"])

        df["norm_vs_mean"] = pd.to_numeric(df["norm_vs_mean"], errors="coerce")
        df["mncs_n_institutions_on_work"] = pd.to_numeric(df["mncs_n_institutions_on_work"], errors="coerce")
        df["pptop10_n_institutions_on_work"] = pd.to_numeric(df["pptop10_n_institutions_on_work"], errors="coerce")

    rows = []
    for report_name, report_label, report_order in REPORTS:
        report_df = df[df["report_name"] == report_name].copy() if not df.empty else pd.DataFrame()
        total_p_full = int(report_df["work_id"].nunique()) if not report_df.empty else 0

        for status in STATUS_ORDER:
            sub = report_df[report_df["oa_status"] == status].copy() if not report_df.empty else pd.DataFrame()

            p_full = int(sub["work_id"].nunique()) if not sub.empty else 0
            oa_pp_full = round(p_full / total_p_full, 6) if total_p_full > 0 else None

            if sub.empty:
                pp_topten_frac = None
                c_mncs_frac = None
                pp_int_collab = None
            else:
                top_sub = sub[
                    sub["pptop10_cohort_is_reliable"]
                    & sub["pptop10_n_institutions_on_work"].notna()
                    & (sub["pptop10_n_institutions_on_work"] > 0)
                ].copy()
                if top_sub.empty:
                    pp_topten_frac = None
                else:
                    top_w = 1.0 / top_sub["pptop10_n_institutions_on_work"]
                    top_w_sum = float(top_w.sum())
                    if top_w_sum > 0:
                        pp_topten_frac = float((top_sub["is_top10"].astype(float) * top_w).sum() / top_w_sum)
                    else:
                        pp_topten_frac = None

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

                pp_int_collab = float(sub["has_int_collab"].mean())

            report_key = "overall" if report_name == "ethdomain" else report_name
            rows.append(
                {
                    "report_name": report_name,
                    "report_key": report_key,
                    "report_label": report_label,
                    "report_order": report_order,
                    "oa_status": status,
                    "P_FULL": p_full,
                    "OA_PP_FULL": oa_pp_full,
                    "PP_TOPTEN_FRAC": round(pp_topten_frac, 6) if pp_topten_frac is not None else None,
                    "C_MNCS_FRAC": round(c_mncs_frac, 6) if c_mncs_frac is not None else None,
                    "PP_INT_COLLAB": round(pp_int_collab, 6) if pp_int_collab is not None else None,
                    "id": f"{status}-{report_key}",
                }
            )

    data_df = pd.DataFrame(
        rows,
        columns=[
            "report_name",
            "report_key",
            "report_label",
            "report_order",
            "oa_status",
            "P_FULL",
            "OA_PP_FULL",
            "PP_TOPTEN_FRAC",
            "C_MNCS_FRAC",
            "PP_INT_COLLAB",
            "id",
        ],
    )
    data_df["OA_PP_FULL_OPEN_INST"] = data_df["OA_PP_FULL"].where(
        (data_df["oa_status"] == "open") & (data_df["report_name"] != "ethdomain")
    )

    table_rows = []
    for status in STATUS_ORDER:
        for indicator in INDICATOR_ORDER:
            for report_name, report_label, report_order in REPORTS:
                hit = data_df[
                    (data_df["oa_status"] == status)
                    & (data_df["report_name"] == report_name)
                ]
                value = hit.iloc[0][indicator] if not hit.empty else None
                table_rows.append(
                    {
                        "oa_status": status,
                        "indicator": indicator,
                        "report_name": report_name,
                        "report_label": report_label,
                        "report_order": report_order,
                        "value": value,
                    }
                )
    table_data_df = pd.DataFrame(
        table_rows,
        columns=["oa_status", "indicator", "report_name", "report_label", "report_order", "value"],
    )

    lines: list[str] = []
    lines.append(r"\begin{adjustbox}{max width=\linewidth}")
    lines.append(r"\begin{tabular}{@{}llr|rrrrrr@{}}")
    lines.append(r"  \toprule")
    lines.append(
        r"  \multicolumn{3}{c}{} & \multicolumn{6}{c}{\textbf{ETH Domain Members}} \\"
    )
    lines.append(r"  \cmidrule(lr){4-9}")
    lines.append(
        "  Status & Indicator & "
        + r"\shortstack[c]{ETH\\Domain} & \shortstack[c]{ETH\\Zurich} & EPFL & PSI & WSL & Empa & Eawag \\"
    )
    lines.append(r"  \midrule")

    for status_i, status in enumerate(STATUS_ORDER):
        status_label = status.capitalize()
        for indicator_i, indicator in enumerate(INDICATOR_ORDER):
            left = status_label if indicator_i == 0 else ""
            label = metric_labels.get(indicator, indicator)

            values_for_row = []
            for report_name, _, _ in REPORTS:
                hit = data_df[
                    (data_df["oa_status"] == status)
                    & (data_df["report_name"] == report_name)
                ]
                value = hit.iloc[0][indicator] if not hit.empty else None

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

        if status_i < len(STATUS_ORDER) - 1:
            lines.append(r"  \midrule")

    lines.append(r"  \bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{adjustbox}")
    lines.append("")

    out = asset.inst_dir(inst)
    data_df.to_csv(out / "data.csv", index=False)
    table_data_df.to_csv(out / "table_data.csv", index=False)
    (out / "table.tex").write_text("\n".join(lines), encoding="utf-8")
