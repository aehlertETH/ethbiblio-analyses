import pandas as pd

from core.asset import Asset
from core.interdisciplinarity import compute_rs_vectorized
from utility import get_indicator_catalog_dict


MA_YEAR_COL = "MA_year"
INCLUDE_FULL_PERIOD_COLUMN = True
INCLUDE_SECTION_HEADINGS = True
OVERALL_COLUMN_LABEL = "Overall"
CLOSED_OA_STATUSES = {"closed", "bronze"}
INDUSTRY_TYPES = {"company"}
DOMAIN_UNIT_REPORTS = ["ethz", "epfl", "psi", "empa", "eawag", "wsl"]

# Keep the full metric set in the exports; filter only at table-render time.
VISIBLE_TABLE_ROWS = {
    "P_FULL",
    "P_FRAC",
    "OA_PP_FULL",
    "PP_COLLAB",
    "PP_INT_COLLAB",
    "PP_INDUSTRY_COLLAB",
    "PP_TOPTEN_FRAC",
    "C_MNCS_FRAC",
    "A_AFF_AUTHORS",
    "PA_F_INST",
    "RPA_F",
}

# Section order aligned with the overall performance table.
TABLE_SECTIONS = [
    ("Output", ["P_FULL", "P_FRAC"]),
    ("Open Access", ["OA_P_FULL", "OA_PP_FULL"]),
    ("Collaborations and Partners", ["PP_COLLAB", "PP_INT_COLLAB", "PP_INDUSTRY_COLLAB", "INTERDISC"]),
    ("Citation Impact", ["P_TOPTEN_FRAC", "PP_TOPTEN_FRAC", "C_MNCS_FRAC"]),
    ("Author and Gender Distribution", ["A_AFF_AUTHORS", "PA_F_INST", "RPA_F"]),
]
TABLE_METRIC_ORDER = [metric for _title, metrics in TABLE_SECTIONS for metric in metrics]
METRIC_ORDER = TABLE_METRIC_ORDER.copy()

COUNT_METRICS = {"P_FULL", "P_FRAC", "OA_P_FULL", "P_TOPTEN_FRAC", "A_AFF_AUTHORS"}
PERCENT_METRICS = {"OA_PP_FULL", "PP_COLLAB", "PP_INT_COLLAB", "PP_INDUSTRY_COLLAB", "PP_TOPTEN_FRAC", "PA_F_INST"}
FLOAT_METRICS = {"INTERDISC", "C_MNCS_FRAC", "RPA_F"}

# Prefer indicator catalog symbols where available.
INDICATOR_ID_BY_METRIC = {
    "P_FULL": "P_FULL",
    "P_FRAC": "P_FRAC",
    "INTERDISC": "INTERDISC",
    "OA_P_FULL": "OA_P_FULL",
    "OA_PP_FULL": "OA_PP_FULL",
    "PP_COLLAB": "PP_COLLAB",
    "PP_INT_COLLAB": "PP_INT_COLLAB",
    "PP_INDUSTRY_COLLAB": "PP_INDUSTRY_COLLAB",
    "P_TOPTEN_FRAC": "P_TOPTEN_FRAC",
    "PP_TOPTEN_FRAC": "PP_TOPTEN_FRAC",
    "C_MNCS_FRAC": "C_MNCS_FRAC",
    "A_AFF_AUTHORS": "A_AFF_AUTHORS",
    "PA_F_INST": "PA_F_INST",
    "RPA_F": "RPA_F",
}

# Non-catalog rows for this table (kept as TeX math snippets).
CUSTOM_SYMBOL_TEX = {
    "INTERDISC": r"\mathrm{InterDisc}",
}

# Keep heavy raw inputs in memory only by default (do not persist large CSV files).
PERSIST_RAW_INPUTS = False
RAW_INPUT_FILENAMES = ("raw_works.csv", "raw_gender.csv")

def q_work_trend_raw(inst: str, y0: int, y1: int) -> str:
    unit_report_list_sql = ", ".join(f"'{unit}'" for unit in DOMAIN_UNIT_REPORTS)

    return f"""
        WITH own_inst AS (
            SELECT institution_id
            FROM reports.report_institutions_ids
            WHERE report_name = '{inst}'
        ),
        base_works AS (
            SELECT DISTINCT
                rm.work_id
            FROM reports.report_membership rm
            JOIN core.work w
                ON w.work_id = rm.work_id
            WHERE rm.report_name = '{inst}'
              AND w.publication_year BETWEEN {y0} AND {y1}
        ),
        unit_membership AS (
            SELECT
                bw.work_id,
                COUNT(DISTINCT rm.report_name) AS n_eth_domain_units
            FROM base_works bw
            LEFT JOIN reports.report_membership rm
                ON rm.work_id = bw.work_id
               AND rm.report_name IN ({unit_report_list_sql})
            GROUP BY bw.work_id
        ),
        report_works AS (
            SELECT DISTINCT
                rm.work_id,
                w.publication_year AS year,
                LOWER(COALESCE(w.open_access_oa_status, '')) AS oa_status,
                COALESCE(tt.field_name, '') AS field_name,
                m.norm_vs_mean,
                m.n_institutions_on_work AS mncs_n_institutions_on_work,
                m.cohort_is_reliable AS mncs_cohort_is_reliable,
                CASE WHEN wm.is_top10 = 1 THEN 1 ELSE 0 END AS is_top10,
                wm.n_institutions_on_work AS pptop10_n_institutions_on_work,
                wm.cohort_is_reliable AS pptop10_cohort_is_reliable,
                COALESCE(wm.n_institutions_on_work, m.n_institutions_on_work) AS n_institutions_on_work
            FROM reports.report_membership rm
            JOIN core.work w
                ON w.work_id = rm.work_id
            LEFT JOIN marts.work_citation_metrics m
                ON m.work_id = rm.work_id
            LEFT JOIN marts.work_metrics wm
                ON wm.work_id = rm.work_id
            LEFT JOIN core.topics_tree tt
                ON tt.subfield = w.subfield
            WHERE rm.report_name = '{inst}'
              AND w.publication_year BETWEEN {y0} AND {y1}
        ),
        work_collab AS (
            SELECT
                rw.work_id,
                MAX(
                    CASE
                        WHEN wii.institution_id NOT IN (SELECT institution_id FROM own_inst)
                        THEN 1 ELSE 0
                    END
                ) AS has_collab,
                MAX(
                    CASE
                        WHEN wii.institution_id NOT IN (SELECT institution_id FROM own_inst)
                         AND COALESCE(dc.country_code, '') <> 'CH'
                        THEN 1 ELSE 0
                    END
                ) AS has_int_collab,
                MAX(
                    CASE
                        WHEN wii.institution_id NOT IN (SELECT institution_id FROM own_inst)
                         AND LOWER(COALESCE(di.type, '')) = 'company'
                        THEN 1 ELSE 0
                    END
                ) AS has_industry
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
            rw.oa_status,
            rw.field_name,
            rw.norm_vs_mean,
            rw.mncs_n_institutions_on_work,
            rw.mncs_cohort_is_reliable,
            rw.is_top10,
            rw.pptop10_n_institutions_on_work,
            rw.pptop10_cohort_is_reliable,
            rw.n_institutions_on_work,
            CASE
                WHEN COALESCE(um.n_eth_domain_units, 0) >= 2
                     OR COALESCE(wc.has_collab, 0) = 1
                THEN 1 ELSE 0
            END AS has_collab,
            COALESCE(wc.has_int_collab, 0) AS has_int_collab,
            COALESCE(wc.has_industry, 0) AS has_industry
        FROM report_works rw
        LEFT JOIN unit_membership um
            ON um.work_id = rw.work_id
        LEFT JOIN work_collab wc
            ON wc.work_id = rw.work_id
        ORDER BY rw.year, rw.work_id;
    """


def q_gender_raw(inst: str, y0: int, y1: int) -> str:
    return f"""
        SELECT DISTINCT
            w.publication_year AS year,
            wag.work_id,
            wag.author_id,
            LOWER(COALESCE(wag.gender_effective, '')) AS gender,
            wag.assigned_to_institution
        FROM reports.work_author_gender wag
        JOIN core.work w
            ON w.work_id = wag.work_id
        WHERE wag.report_name = '{inst}'
          AND w.publication_year BETWEEN {y0} AND {y1}
          AND wag.author_id IS NOT NULL
        ORDER BY w.publication_year, wag.work_id, wag.author_id;
    """


def q_interdisc_raw(inst: str, y0: int, y1: int) -> str:
    return f"""
        WITH subfield_tree AS (
            SELECT DISTINCT
                subfield,
                field,
                domain
            FROM core.topics_tree
        ),
        inst_works AS (
            SELECT DISTINCT
                w.work_id,
                w.publication_year AS year,
                wm.n_institutions_on_work
            FROM reports.report_membership rm
            JOIN core.work w
                ON w.work_id = rm.work_id
            JOIN marts.work_metrics wm
                ON wm.work_id = rm.work_id
            WHERE rm.report_name = '{inst}'
              AND w.publication_year BETWEEN {y0} AND {y1}
              AND wm.n_institutions_on_work > 0
              AND wm.has_references = 1
        ),
        ref_counts AS (
            SELECT
                iw.work_id,
                st.subfield AS cited_subfield,
                st.field AS cited_field,
                st.domain AS cited_domain,
                COUNT(*) AS n_refs_in_subfield
            FROM inst_works iw
            JOIN core.refs r
                ON r.citing_id = iw.work_id
            JOIN core.work cw2
                ON cw2.work_id = r.cited_id
            JOIN subfield_tree st
                ON st.subfield = cw2.subfield
            GROUP BY iw.work_id, st.subfield, st.field, st.domain
        )
        SELECT
            iw.work_id,
            iw.year,
            iw.n_institutions_on_work,
            rc.cited_field,
            rc.cited_domain,
            rc.n_refs_in_subfield,
            SUM(rc.n_refs_in_subfield) OVER (PARTITION BY iw.work_id) AS total_refs
        FROM inst_works iw
        JOIN ref_counts rc
            ON rc.work_id = iw.work_id
        ORDER BY iw.year, iw.work_id;
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


def weighted_mean(values: pd.Series, weights: pd.Series) -> float | None:
    if values.empty or weights.empty:
        return None
    valid = values.notna() & weights.notna() & (weights > 0)
    if not valid.any():
        return None
    num = (values[valid] * weights[valid]).sum()
    den = weights[valid].sum()
    if den == 0 or pd.isna(den):
        return None
    return float(num / den)


def calc_interdisc_mean(interdisc_refs: pd.DataFrame) -> float | None:
    if interdisc_refs.empty:
        return None

    rs_series = compute_rs_vectorized(interdisc_refs)
    if rs_series.empty:
        return None

    rs_df = (
        interdisc_refs.drop_duplicates(subset=["work_id"])[["work_id", "n_institutions_on_work"]]
        .set_index("work_id")
        .join(rs_series, how="inner")
    )
    weights = 1.0 / rs_df["n_institutions_on_work"]
    return weighted_mean(rs_df["rs_w"], weights)


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


def parse_display_digits(entry: dict, default: int = 0) -> int:
    if not entry:
        return default
    raw = str(entry.get("display_digits", "")).strip()
    if raw == "":
        return default
    try:
        parsed = int(float(raw))
    except ValueError:
        return default
    return parsed if parsed >= 0 else default


def get_pp_topten_display_digits(indicator_catalog_dict: dict, default: int = 1) -> int:
    entry = (indicator_catalog_dict or {}).get("PP_TOPTEN_FRAC", {})
    return parse_display_digits(entry, default=default)


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

        custom_symbol = CUSTOM_SYMBOL_TEX.get(metric)
        if custom_symbol:
            labels[metric] = f"${custom_symbol}$"
        else:
            labels[metric] = tex_escape_text(metric)

    return labels


def _calc_gender_metrics(gender_sub: pd.DataFrame) -> tuple[float | None, float | None, float | None, int | None, int | None]:
    if gender_sub.empty:
        return None, None, None, None, None

    all_authors = int(gender_sub.drop_duplicates(subset=["author_id"])["author_id"].nunique())
    aff_authors = int(gender_sub[to_bool(gender_sub["assigned_to_institution"])].drop_duplicates(subset=["author_id"])["author_id"].nunique())

    g = gender_sub.copy()
    g["gender"] = g["gender"].astype("string").str.strip().str.lower()
    g = g[g["gender"].isin({"female", "male"})]
    if g.empty:
        return None, None, None, aff_authors, all_authors

    all_auth = g.drop_duplicates(subset=["author_id"])
    inst_auth = g[to_bool(g["assigned_to_institution"])].drop_duplicates(subset=["author_id"])

    all_counts = all_auth["gender"].value_counts()
    inst_counts = inst_auth["gender"].value_counts()

    all_total = int(all_counts.get("female", 0)) + int(all_counts.get("male", 0))
    inst_total = int(inst_counts.get("female", 0)) + int(inst_counts.get("male", 0))

    pa_f_pubs = (int(all_counts.get("female", 0)) / all_total) if all_total > 0 else None
    pa_f_inst = (int(inst_counts.get("female", 0)) / inst_total) if inst_total > 0 else None

    if pa_f_inst is None or pa_f_pubs in (None, 0):
        rpa_f = None
    else:
        rpa_f = float(pa_f_inst / pa_f_pubs)

    return pa_f_inst, pa_f_pubs, rpa_f, aff_authors, all_authors


def _prepare_inputs(
    works_df: pd.DataFrame,
    gender_df: pd.DataFrame,
    interdisc_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    works = works_df.copy()
    works["year"] = pd.to_numeric(works["year"], errors="coerce")
    works = works.dropna(subset=["year", "work_id"]).copy()
    works["year"] = works["year"].astype(int)

    if works.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    works = works.sort_values(["year", "work_id"]).drop_duplicates(subset=["work_id"], keep="first")

    for col in ["mncs_n_institutions_on_work", "pptop10_n_institutions_on_work", "n_institutions_on_work", "norm_vs_mean"]:
        works[col] = pd.to_numeric(works[col], errors="coerce")

    works["is_top10"] = to_bool(works["is_top10"])
    works["mncs_cohort_is_reliable"] = to_bool(works["mncs_cohort_is_reliable"])
    works["pptop10_cohort_is_reliable"] = to_bool(works["pptop10_cohort_is_reliable"])
    works["has_collab"] = to_bool(works["has_collab"])
    works["has_int_collab"] = to_bool(works["has_int_collab"])
    works["has_industry"] = to_bool(works["has_industry"])
    works["oa_status"] = works["oa_status"].astype("string").str.strip().str.lower()
    works["field_name"] = works["field_name"].astype("string").str.strip().fillna("")

    gender = gender_df.copy()
    if not gender.empty:
        gender["year"] = pd.to_numeric(gender["year"], errors="coerce")
        gender = gender.dropna(subset=["year", "author_id"]).copy()
        gender["year"] = gender["year"].astype(int)

    interdisc = interdisc_df.copy()
    if not interdisc.empty:
        interdisc["year"] = pd.to_numeric(interdisc["year"], errors="coerce")
        interdisc["n_institutions_on_work"] = pd.to_numeric(interdisc["n_institutions_on_work"], errors="coerce")
        interdisc["n_refs_in_subfield"] = pd.to_numeric(interdisc["n_refs_in_subfield"], errors="coerce")
        interdisc["total_refs"] = pd.to_numeric(interdisc["total_refs"], errors="coerce")
        interdisc = interdisc.dropna(
            subset=[
                "year",
                "work_id",
                "n_institutions_on_work",
                "cited_field",
                "cited_domain",
                "n_refs_in_subfield",
                "total_refs",
            ]
        ).copy()
        interdisc["year"] = interdisc["year"].astype(int)
        interdisc = interdisc[interdisc["n_institutions_on_work"] > 0].copy()

    return works, gender, interdisc


def _compute_window_metrics(
    works: pd.DataFrame,
    gender: pd.DataFrame,
    interdisc_refs: pd.DataFrame,
    *,
    y0: int,
    y1: int,
) -> dict[str, float | int | None]:
    sub = works[(works["year"] >= y0) & (works["year"] <= y1)].copy()

    p_full = int(sub["work_id"].nunique())

    valid_n = sub["n_institutions_on_work"].notna() & (sub["n_institutions_on_work"] > 0)
    p_frac = float((1.0 / sub.loc[valid_n, "n_institutions_on_work"]).sum()) if valid_n.any() else None

    is_open = ~sub["oa_status"].isin(CLOSED_OA_STATUSES)
    p_oa = int(is_open.sum())
    pp_oa = (p_oa / p_full) if p_full > 0 else None

    pp_collab = float(sub["has_collab"].mean()) if not sub.empty else None
    pp_int_collab = float(sub["has_int_collab"].mean()) if not sub.empty else None
    pp_industry = float(sub["has_industry"].mean()) if not sub.empty else None

    sub_pp = sub[
        sub["pptop10_cohort_is_reliable"]
        & sub["pptop10_n_institutions_on_work"].notna()
        & (sub["pptop10_n_institutions_on_work"] > 0)
    ].copy()
    pp_weights = (1.0 / sub_pp["pptop10_n_institutions_on_work"]) if not sub_pp.empty else pd.Series(dtype=float)
    p_topten = float((sub_pp["is_top10"].astype(float) * pp_weights).sum()) if not sub_pp.empty else 0.0
    pp_topten = weighted_mean(sub_pp["is_top10"].astype(float), pp_weights)

    sub_mncs = sub[
        sub["mncs_cohort_is_reliable"]
        & sub["mncs_n_institutions_on_work"].notna()
        & (sub["mncs_n_institutions_on_work"] > 0)
        & sub["norm_vs_mean"].notna()
    ].copy()
    mncs_weights = (1.0 / sub_mncs["mncs_n_institutions_on_work"]) if not sub_mncs.empty else pd.Series(dtype=float)
    mncs = weighted_mean(sub_mncs["norm_vs_mean"], mncs_weights)

    interdisc_sub = (
        interdisc_refs[(interdisc_refs["year"] >= y0) & (interdisc_refs["year"] <= y1)].copy()
        if not interdisc_refs.empty
        else pd.DataFrame()
    )
    interdisc = calc_interdisc_mean(interdisc_sub)

    gender_sub = gender[(gender["year"] >= y0) & (gender["year"] <= y1)].copy() if not gender.empty else pd.DataFrame()
    pa_f_inst, _pa_f_pubs, rpa_f, a_aff_authors, _a_all_authors = _calc_gender_metrics(gender_sub)

    return {
        "P_FULL": p_full,
        "P_FRAC": round(p_frac, 6) if p_frac is not None else None,
        "INTERDISC": round(interdisc, 6) if interdisc is not None else None,
        "OA_P_FULL": p_oa,
        "OA_PP_FULL": round(pp_oa, 6) if pp_oa is not None else None,
        "PP_COLLAB": round(pp_collab, 6) if pp_collab is not None else None,
        "PP_INT_COLLAB": round(pp_int_collab, 6) if pp_int_collab is not None else None,
        "PP_INDUSTRY_COLLAB": round(pp_industry, 6) if pp_industry is not None else None,
        "P_TOPTEN_FRAC": round(p_topten, 6) if p_topten is not None else None,
        "PP_TOPTEN_FRAC": round(pp_topten, 6) if pp_topten is not None else None,
        "C_MNCS_FRAC": round(mncs, 6) if mncs is not None else None,
        "A_AFF_AUTHORS": int(a_aff_authors) if a_aff_authors is not None else None,
        "PA_F_INST": round(pa_f_inst, 6) if pa_f_inst is not None else None,
        "RPA_F": round(rpa_f, 6) if rpa_f is not None else None,
    }


def build_ma_df(
    works_df: pd.DataFrame,
    gender_df: pd.DataFrame,
    interdisc_df: pd.DataFrame,
    ma_window: int,
) -> pd.DataFrame:
    cols = [MA_YEAR_COL] + METRIC_ORDER
    works, gender, interdisc = _prepare_inputs(works_df, gender_df, interdisc_df)
    if works.empty:
        return pd.DataFrame(columns=cols)

    years = sorted(works["year"].unique())
    if not years:
        return pd.DataFrame(columns=cols)

    max_year = max(years)
    start_years = [y for y in years if y + (ma_window - 1) <= max_year]

    rows: list[dict[str, float | int | str | None]] = []
    for y0 in start_years:
        y1 = y0 + (ma_window - 1)
        row = {MA_YEAR_COL: f"{y0}-{y1}"}
        row.update(_compute_window_metrics(works, gender, interdisc, y0=y0, y1=y1))
        rows.append(row)

    return pd.DataFrame(rows, columns=cols)


def build_full_period_df(
    works_df: pd.DataFrame,
    gender_df: pd.DataFrame,
    interdisc_df: pd.DataFrame,
    *,
    y0: int,
    y1: int,
) -> pd.DataFrame:
    cols = [MA_YEAR_COL] + METRIC_ORDER
    label = f"{y0}-{y1}"

    works, gender, interdisc = _prepare_inputs(works_df, gender_df, interdisc_df)
    if works.empty:
        row = {MA_YEAR_COL: label, **{metric: None for metric in METRIC_ORDER}}
        return pd.DataFrame([row], columns=cols)

    row = {MA_YEAR_COL: label}
    row.update(_compute_window_metrics(works, gender, interdisc, y0=y0, y1=y1))
    return pd.DataFrame([row], columns=cols)


def build_table_tex(
    ma_df: pd.DataFrame,
    metric_labels: dict[str, str],
    *,
    full_period_df: pd.DataFrame,
    full_period_label: str,
    pp_topten_pct_digits: int,
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
    value_map = ma_df.set_index(MA_YEAR_COL).to_dict(orient="index") if not ma_df.empty else {}
    full_period_row = full_period_df.iloc[0].to_dict() if not full_period_df.empty else {}

    col_headers = year_cols + ([full_period_label] if include_full_period_column else [])

    if include_full_period_column and year_cols:
        col_spec = "@{}l" + ("r" * len(year_cols)) + "|r@{}"
    elif include_full_period_column:
        col_spec = "@{}lr@{}"
    else:
        col_spec = "@{}l" + ("r" * len(year_cols)) + "@{}"

    rotation = int(header_rotation_deg) if float(header_rotation_deg).is_integer() else float(header_rotation_deg)

    lines = []
    lines.append(r"\resizebox{\linewidth}{!}{%")
    lines.append(rf"\begin{{tabular}}{{{col_spec}}}")
    lines.append(r"  \toprule")

    header_cells = [rf"\rotatebox[origin=c]{{{rotation}}}{{{tex_escape_text(h)}}}" for h in col_headers]
    lines.append(r"  Indicator & " + " & ".join(header_cells) + r" \\")
    lines.append(r"  \midrule")

    def render_value(metric: str, value) -> str:
        if metric in COUNT_METRICS:
            return fmt_count(value)
        if metric in PERCENT_METRICS:
            if metric == "PP_TOPTEN_FRAC":
                return fmt_pct(value, pp_topten_pct_digits)
            return fmt_pct(value, 0)
        if metric in FLOAT_METRICS:
            return fmt_float(value, 2)
        return fmt_float(value, 2)

    def append_metric_row(metric: str) -> None:
        label = metric_labels.get(metric, tex_escape_text(metric))
        rendered_vals = [render_value(metric, value_map.get(year, {}).get(metric)) for year in year_cols]
        if include_full_period_column:
            rendered_vals.append(render_value(metric, full_period_row.get(metric)))
        lines.append(f"  {label} & " + " & ".join(rendered_vals) + r" \\")

    if include_section_headings:
        n_cols = len(col_headers) + 1
        first_section = True
        for title, metrics in TABLE_SECTIONS:
            visible_metrics = [metric for metric in metrics if metric in VISIBLE_TABLE_ROWS]
            if not visible_metrics:
                continue
            if not first_section:
                lines.append(r"  \midrule")
            first_section = False
            lines.append(rf"  \multicolumn{{{n_cols}}}{{c}}{{{title}}} \\")
            lines.append(r"  \midrule")
            for metric in visible_metrics:
                append_metric_row(metric)
    else:
        for metric in TABLE_METRIC_ORDER:
            if metric not in VISIBLE_TABLE_ROWS:
                continue
            append_metric_row(metric)

    lines.append(r"  \bottomrule")
    lines.append(r"\end{tabular}%")
    lines.append(r"}")
    lines.append("")
    return "\n".join(lines)


asset = Asset(script_file=__file__)
indicator_catalog_dict = get_indicator_catalog_dict()
metric_labels = get_metric_labels(indicator_catalog_dict)
pp_topten_pct_digits = get_pp_topten_display_digits(indicator_catalog_dict, default=1)
header_rotation_deg = float(getattr(asset, "table_header_rotation_deg", 60))
ma_window = max(1, int(asset.year_range_moving))

for inst, con in asset.iterate_institutions():
    works_df = con.query(q_work_trend_raw(inst, asset.year_first, asset.year_last)).df()
    gender_df = con.query(q_gender_raw(inst, asset.year_first, asset.year_last)).df()
    interdisc_df = con.query(q_interdisc_raw(inst, asset.year_first, asset.year_last)).df()

    out = asset.inst_dir(inst)

    if PERSIST_RAW_INPUTS:
        works_df.to_csv(out / RAW_INPUT_FILENAMES[0], index=False)
        gender_df.to_csv(out / RAW_INPUT_FILENAMES[1], index=False)
    else:
        for raw_name in RAW_INPUT_FILENAMES:
            raw_path = out / raw_name
            if raw_path.exists():
                raw_path.unlink()

    ma_df = build_ma_df(works_df, gender_df, interdisc_df, ma_window)

    full_period_label = f"{asset.year_first}-{asset.year_last}"
    full_period_df = build_full_period_df(
        works_df,
        gender_df,
        interdisc_df,
        y0=asset.year_first,
        y1=asset.year_last,
    )

    ma_df.to_csv(out / "data.csv", index=False)

    table_data_df = (
        ma_df.melt(
            id_vars=[MA_YEAR_COL],
            value_vars=TABLE_METRIC_ORDER,
            var_name="indicator",
            value_name="value",
        )
    )

    if INCLUDE_FULL_PERIOD_COLUMN:
        full_period_row = full_period_df.iloc[0].to_dict() if not full_period_df.empty else {}
        full_period_rows = [
            {
                MA_YEAR_COL: full_period_label,
                "indicator": metric,
                "value": full_period_row.get(metric),
            }
            for metric in TABLE_METRIC_ORDER
        ]
        table_data_df = pd.concat([table_data_df, pd.DataFrame(full_period_rows)], ignore_index=True)
        year_cols = sorted(ma_df[MA_YEAR_COL].dropna().unique(), key=sort_year_label) if not ma_df.empty else []
        year_order = {year: idx for idx, year in enumerate(year_cols)}
        year_order[full_period_label] = len(year_cols)
        metric_order = {metric: idx for idx, metric in enumerate(TABLE_METRIC_ORDER)}
        table_data_df = (
            table_data_df.assign(
                _indicator_order=lambda d: d["indicator"].map(metric_order).fillna(10**9),
                _year_order=lambda d: d[MA_YEAR_COL].map(year_order).fillna(10**9),
            )
            .sort_values(["_indicator_order", "_year_order"])
            .drop(columns=["_indicator_order", "_year_order"])
            .reset_index(drop=True)
        )
    else:
        metric_order = {metric: idx for idx, metric in enumerate(TABLE_METRIC_ORDER)}
        table_data_df = (
            table_data_df.assign(
                _indicator_order=lambda d: d["indicator"].map(metric_order).fillna(10**9),
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
            full_period_df=full_period_df,
            full_period_label=OVERALL_COLUMN_LABEL,
            pp_topten_pct_digits=pp_topten_pct_digits,
            include_full_period_column=INCLUDE_FULL_PERIOD_COLUMN,
            include_section_headings=INCLUDE_SECTION_HEADINGS,
            header_rotation_deg=header_rotation_deg,
        ),
        encoding="utf-8",
    )
