import pandas as pd

from core.asset import Asset
from utility import get_indicator_catalog_dict


OA_TYPES = ["gold", "green", "hybrid", "closed"]
INDICATORS = [
    ("p_full", "P_FULL"),
    ("oa_pp_full", "OA_PP_FULL"),
    ("pp_topten_frac", "PP_TOPTEN_FRAC"),
    ("c_mncs_frac", "C_MNCS_FRAC"),
    ("pp_int_collab", "PP_INT_COLLAB"),
]


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
        ORDER BY rw.year, rw.work_id;
    """


def to_bool(series: pd.Series) -> pd.Series:
    return (
        series.astype("string")
        .str.strip()
        .str.lower()
        .isin({"1", "true", "t", "yes", "y"})
        .fillna(False)
    )


def compute_metrics(group_df: pd.DataFrame) -> dict[str, float | int | None]:
    p_full = int(group_df["work_id"].nunique())

    top10_df = group_df[
        group_df["pptop10_cohort_is_reliable"]
        & group_df["pptop10_n_institutions_on_work"].notna()
        & (group_df["pptop10_n_institutions_on_work"] > 0)
    ].copy()

    if top10_df.empty:
        p_topten_frac = 0.0
        pp_topten_frac = None
    else:
        top10_w = 1.0 / top10_df["pptop10_n_institutions_on_work"]
        p_topten_frac = float((top10_df["is_top10"].astype(float) * top10_w).sum())
        top10_w_sum = float(top10_w.sum())
        pp_topten_frac = (p_topten_frac / top10_w_sum) if top10_w_sum > 0 else None

    mncs_df = group_df[
        group_df["mncs_cohort_is_reliable"]
        & group_df["mncs_n_institutions_on_work"].notna()
        & (group_df["mncs_n_institutions_on_work"] > 0)
        & group_df["norm_vs_mean"].notna()
    ].copy()

    if mncs_df.empty:
        c_mncs_frac = None
    else:
        mncs_w = 1.0 / mncs_df["mncs_n_institutions_on_work"]
        mncs_w_sum = float(mncs_w.sum())
        if mncs_w_sum > 0:
            c_mncs_frac = float((mncs_df["norm_vs_mean"] * mncs_w).sum() / mncs_w_sum)
        else:
            c_mncs_frac = None

    pp_int_collab = float(group_df["has_int_collab"].mean()) if not group_df.empty else None

    return {
        "p_full": p_full,
        "p_topten_frac": round(p_topten_frac, 6),
        "pp_topten_frac": round(pp_topten_frac, 6) if pp_topten_frac is not None else None,
        "c_mncs_frac": round(c_mncs_frac, 6) if c_mncs_frac is not None else None,
        "pp_int_collab": round(pp_int_collab, 6) if pp_int_collab is not None else None,
    }


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

pp_topten_digits = parse_digits(indicator_catalog.get("PP_TOPTEN_FRAC", {}).get("display_digits", ""), 1)
oa_pp_full_digits = parse_digits(indicator_catalog.get("OA_PP_FULL", {}).get("display_digits", ""), 1)

indicator_labels: dict[str, str] = {}
for metric_key, indicator_id in INDICATORS:
    symbol_tex = str(indicator_catalog.get(indicator_id, {}).get("symbol_tex", "")).strip()
    indicator_labels[metric_key] = f"${symbol_tex}$" if symbol_tex else indicator_id
indicator_labels["oa_pp_full"] = r"Share of total"

for inst, con in asset.iterate_institutions():
    raw_df = asset.extract(
        con=con,
        inst=inst,
        query=query_function(inst, asset.year_first, asset.year_last),
        out_name="raw_data.csv",
        #force=True,
    )

    df = raw_df.copy()
    if not df.empty:
        df["year"] = pd.to_numeric(df["year"], errors="coerce")
        df = df.dropna(subset=["year", "work_id"]).copy()
        df["year"] = df["year"].astype(int)
        df = df.sort_values(["year", "work_id"]).drop_duplicates(subset=["work_id"], keep="first")

        oa_map = {
            "gold": "gold",
            "diamond": "gold",
            "hybrid": "hybrid",
            "green": "green",
            "closed": "closed",
            "bronze": "closed",
        }
        df["oa_type"] = df["oa_status_raw"].astype("string").str.strip().str.lower().map(oa_map)
        df = df[df["oa_type"].notna()].copy()

        if not df.empty:
            df["is_top10"] = to_bool(df["is_top10"])
            df["has_int_collab"] = to_bool(df["has_int_collab"])
            df["pptop10_cohort_is_reliable"] = to_bool(df["pptop10_cohort_is_reliable"])
            df["mncs_cohort_is_reliable"] = to_bool(df["mncs_cohort_is_reliable"])
            df["pptop10_n_institutions_on_work"] = pd.to_numeric(df["pptop10_n_institutions_on_work"], errors="coerce")
            df["mncs_n_institutions_on_work"] = pd.to_numeric(df["mncs_n_institutions_on_work"], errors="coerce")
            df["norm_vs_mean"] = pd.to_numeric(df["norm_vs_mean"], errors="coerce")

    metrics_by_type: dict[str, dict[str, float | int | None]] = {}
    default_metrics = {
        "p_full": 0,
        "oa_pp_full": None,
        "pp_int_collab": None,
        "pp_topten_frac": None,
        "c_mncs_frac": None,
    }

    if df.empty:
        for oa_type in OA_TYPES:
            metrics_by_type[oa_type] = default_metrics.copy()
        metrics_by_type["open"] = default_metrics.copy()
        metrics_by_type["total"] = default_metrics.copy()
    else:
        for oa_type in OA_TYPES:
            metrics_by_type[oa_type] = compute_metrics(df[df["oa_type"] == oa_type].copy())
        metrics_by_type["open"] = compute_metrics(df[df["oa_type"].isin(["gold", "green", "hybrid"])].copy())
        metrics_by_type["total"] = compute_metrics(df.copy())

    total_p_full = float(metrics_by_type["total"]["p_full"] or 0)
    for key in ["total", "closed", "open", "gold", "green", "hybrid"]:
        p_full_value = float(metrics_by_type[key]["p_full"] or 0)
        if total_p_full > 0:
            metrics_by_type[key]["oa_pp_full"] = round(p_full_value / total_p_full, 6)
        else:
            metrics_by_type[key]["oa_pp_full"] = None

    rows = []
    for row_order, (metric_key, _) in enumerate(INDICATORS, start=1):
        rows.append(
            {
                "row_order": row_order,
                "indicator": metric_key,
                "TOTAL": metrics_by_type["total"][metric_key],
                "CLOSED_ACCESS": metrics_by_type["closed"][metric_key],
                "OPEN_ACCESS": metrics_by_type["open"][metric_key],
                "OA_GOLD": metrics_by_type["gold"][metric_key],
                "OA_GREEN": metrics_by_type["green"][metric_key],
                "OA_HYBRID": metrics_by_type["hybrid"][metric_key],
            }
        )

    data_df = pd.DataFrame(
        rows,
        columns=[
            "row_order",
            "indicator",
            "TOTAL",
            "CLOSED_ACCESS",
            "OPEN_ACCESS",
            "OA_GOLD",
            "OA_GREEN",
            "OA_HYBRID",
        ],
    )

    lines: list[str] = []
    lines.append(r"\begin{adjustbox}{max width=\linewidth}")
    lines.append(r"\begin{tabular}{@{}lr|rr|rrr@{}}")
    lines.append(r"  \toprule")
    lines.append(
        "  "
        + r"\multicolumn{1}{c}{}"
        + " & "
        + r"\multicolumn{1}{c}{\textbf{Total}}"
        + " & "
        + r"\multicolumn{2}{c}{\textbf{Access status}}"
        + " & "
        + r"\multicolumn{3}{c}{\textbf{Open-access category}} \\"
    )
    lines.append(r"  \cmidrule(lr){2-2}\cmidrule(lr){3-4}\cmidrule(lr){5-7}")
    lines.append(
        "  "
        + r"\textbf{Indicator}"
        + " & "
        + r"\textbf{Total}"
        + " & "
        + r"\shortstack[c]{\textbf{Closed access}\\\textbf{incl.\ bronze}}"
        + " & "
        + r"\textbf{Open access}"
        + " & "
        + r"\shortstack[c]{\textbf{Gold}\\\textbf{incl.\ diamond}}"
        + " & "
        + r"\textbf{Green}"
        + " & "
        + r"\textbf{Hybrid} \\"
    )
    lines.append(r"  \midrule")

    for metric_key, _ in INDICATORS:
        row = data_df[data_df["indicator"] == metric_key].iloc[0]
        values = [
            row["TOTAL"],
            row["CLOSED_ACCESS"],
            row["OPEN_ACCESS"],
            row["OA_GOLD"],
            row["OA_GREEN"],
            row["OA_HYBRID"],
        ]

        if metric_key == "p_full":
            formatted_values = [format_count(v) for v in values]
        elif metric_key == "oa_pp_full":
            formatted_values = [format_pct(v, oa_pp_full_digits) for v in values]
        elif metric_key == "pp_topten_frac":
            formatted_values = [format_pct(v, pp_topten_digits) for v in values]
        elif metric_key == "c_mncs_frac":
            formatted_values = [format_float(v, 2) for v in values]
        elif metric_key == "pp_int_collab":
            formatted_values = [format_pct(v, 1) for v in values]
        else:
            formatted_values = [format_pct(v, 0) for v in values]

        lines.append(
            "  "
            + indicator_labels[metric_key]
            + " & "
            + " & ".join(formatted_values)
            + r" \\"
        )

    lines.append(r"  \bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{adjustbox}")
    lines.append("")

    out = asset.inst_dir(inst)
    data_df.to_csv(out / "data.csv", index=False)
    (out / "table.tex").write_text("\n".join(lines), encoding="utf-8")
