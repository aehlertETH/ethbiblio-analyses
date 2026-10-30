from utility import get_unit_params_dict, get_indicator_catalog_dict
from core.asset import Asset
from core.interdisciplinarity import compute_rs_vectorized

import pandas as pd

asset = Asset(script_file=__file__)

YEAR_FIRST = asset.year_first
YEAR_LAST = asset.year_last
OA_MODE = "open_vs_closed"  # selected_statuses | open_vs_closed
OA_SELECTED_STATUSES = ("gold", "hybrid", "green")
OA_CLOSED_STATUSES = ("closed", "bronze")
INCLUDE_READERSHIP_SECTION = False
COLLAB_COUNTRY_TOP_N = 5

INCLUDE_SECTION_OUTPUT = True
INCLUDE_SECTION_COLLAB = True
INCLUDE_SECTION_CITEDNESS = True
INCLUDE_SECTION_GENDER = True
INCLUDE_SUBSECTION_COLLAB_TYPES = False
INCLUDE_SUBSECTION_COLLAB_COUNTRIES = False

COLLAB_TYPE_ORDER = (
    "education",
    "company",
    "government",
    "healthcare",
    "nonprofit",
    "facility",
    "archive",
    "other",
    "unknown",
)
DOCUMENT_GROUPS = ("journals", "proceedings", "overall")
GENDER_ORDER = ("female", "male", "unknown")
DOMAIN_UNIT_REPORTS = ["ethz", "epfl", "psi", "empa", "eawag", "wsl"]


"""
How to use this template:

1) Copy-Paste this folder and use the chapter as prefix (see report.pdf)
2) Connect and iterate over institutions
3) When querying the data, use asset.extract() which returns a dataframe (advantage: using this function will also export the CSV file to the asset directory)
4) Use unit_params_dict for unit-specific labels (InstName, InstShort, ...).
5) Use indicator_catalog_dict for indicator symbols/definitions (symbol_tex, definition_*).
6) For Plotly assets:
    - Everything which is assets specific should be done in this script here (e.g., x-label, position of labels, etc.)
    - Then, call apply_style(fig) to apply the default style (colors, fonts, etc.)
"""

# Load naming conventions from data/...csv files
unit_params_dict = get_unit_params_dict()
indicator_catalog_dict = get_indicator_catalog_dict()


def q_works(inst: str, y0: int, y1: int) -> str:
    unit_report_list_sql = ", ".join(f"'{unit}'" for unit in DOMAIN_UNIT_REPORTS)

    return f"""
        WITH own_inst AS (
            SELECT institution_id
            FROM reports.report_institutions_ids
            WHERE report_name = '{inst}'
        ),
        report_works AS (
            SELECT DISTINCT
                w.work_id,
                CASE
                    WHEN w.type_is_proceedings = TRUE THEN 'proceedings'
                    ELSE 'journals'
                END AS document_group,
                wm.n_institutions_on_work,
                wm.n_citations,
                wm.norm_vs_mean,
                wm.is_top10,
                wm.is_uncited,
                wm.cohort_is_reliable,
                LOWER(COALESCE(w.open_access_oa_status, '')) AS oa_status,
                COALESCE(tt.field_name, '') AS field_name
            FROM reports.report_membership rm
            JOIN core.work w
              ON w.work_id = rm.work_id
            JOIN core.work_to_status s
              ON s.work_id = rm.work_id
            JOIN marts.work_metrics wm
              ON wm.work_id = rm.work_id
            LEFT JOIN core.topics_tree tt
              ON tt.subfield = w.subfield
            WHERE rm.report_name = '{inst}'
              AND w.publication_year BETWEEN {y0} AND {y1}
              AND s.is_included = TRUE
        ),
        unit_membership AS (
            SELECT
                rw.work_id,
                COUNT(DISTINCT rm.report_name) AS n_eth_domain_units
            FROM report_works rw
            LEFT JOIN reports.report_membership rm
              ON rm.work_id = rw.work_id
             AND rm.report_name IN ({unit_report_list_sql})
            GROUP BY rw.work_id
        ),
        external_collab AS (
            SELECT
                rw.work_id,
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
            FROM report_works rw
            LEFT JOIN marts.work_institution_info wii
              ON wii.work_id = rw.work_id
            LEFT JOIN core.dim_institution di
              ON di.institution_id = wii.institution_id
            LEFT JOIN core.dim_country dc
              ON dc.country_id = di.country_id
            GROUP BY rw.work_id
        )
        SELECT
            rw.work_id,
            rw.document_group,
            rw.n_institutions_on_work,
            rw.n_citations,
            rw.norm_vs_mean,
            rw.is_top10,
            rw.is_uncited,
            rw.cohort_is_reliable,
            rw.oa_status,
            rw.field_name,
            CASE
                WHEN COALESCE(um.n_eth_domain_units, 0) >= 2
                     OR COALESCE(ec.has_external_collab, 0) = 1
                THEN 1 ELSE 0
            END AS has_collab,
            COALESCE(ec.has_int_collab, 0) AS has_int_collab,
            COALESCE(ec.has_industry_collab, 0) AS has_industry_collab
        FROM report_works rw
        LEFT JOIN unit_membership um
          ON um.work_id = rw.work_id
        LEFT JOIN external_collab ec
          ON ec.work_id = rw.work_id
        ORDER BY rw.work_id;
    """


def q_self_citations(inst: str, y0: int, y1: int) -> str:
    return f"""
        WITH inst_works AS (
            SELECT DISTINCT
                w.work_id
            FROM reports.report_membership rm
            JOIN core.work w
              ON w.work_id = rm.work_id
            JOIN core.work_to_status s
              ON s.work_id = rm.work_id
            WHERE rm.report_name = '{inst}'
              AND w.publication_year BETWEEN {y0} AND {y1}
              AND s.is_included = TRUE
        ),
        inst_authors AS (
            SELECT DISTINCT
                a.work_id AS cited_id,
                a.author_id
            FROM core.authors a
            JOIN inst_works iw
              ON iw.work_id = a.work_id
        ),
        citing_links AS (
            SELECT DISTINCT
                r.citing_id,
                r.cited_id
            FROM core.refs r
            WHERE r.cited_id IN (SELECT work_id FROM inst_works)
              AND r.citing_id <> r.cited_id
        ),
        citing_authors AS (
            SELECT DISTINCT
                a.work_id AS citing_id,
                a.author_id
            FROM core.authors a
            JOIN citing_links cl
              ON cl.citing_id = a.work_id
        ),
        self_links AS (
            SELECT DISTINCT
                cl.citing_id,
                cl.cited_id
            FROM citing_links cl
            JOIN inst_authors ia
              ON ia.cited_id = cl.cited_id
            JOIN citing_authors ca
              ON ca.citing_id = cl.citing_id
             AND ca.author_id = ia.author_id
        ),
        author_counts AS (
            SELECT
                iw.work_id,
                COUNT(DISTINCT a.author_id) AS n_authors
            FROM inst_works iw
            LEFT JOIN core.authors a
              ON a.work_id = iw.work_id
            GROUP BY iw.work_id
        ),
        citation_counts AS (
            SELECT
                iw.work_id,
                COUNT(DISTINCT cl.citing_id) AS p_all_cits,
                COUNT(DISTINCT sl.citing_id) AS p_self_cits
            FROM inst_works iw
            LEFT JOIN citing_links cl
              ON cl.cited_id = iw.work_id
            LEFT JOIN self_links sl
              ON sl.cited_id = iw.work_id
             AND sl.citing_id = cl.citing_id
            GROUP BY iw.work_id
        )
        SELECT
            iw.work_id,
            COALESCE(ac.n_authors, 0) AS n_authors,
            COALESCE(cc.p_self_cits, 0) AS P_SELF_CITS_FULL,
            COALESCE(cc.p_all_cits, 0) AS P_ALL_CITS_FULL,
            CASE
                WHEN COALESCE(cc.p_all_cits, 0) > 0
                THEN 1.0 * COALESCE(cc.p_self_cits, 0) / cc.p_all_cits
                ELSE NULL
            END AS PP_SELF_CITS_FULL
        FROM inst_works iw
        LEFT JOIN author_counts ac
          ON ac.work_id = iw.work_id
        LEFT JOIN citation_counts cc
          ON cc.work_id = iw.work_id
        ORDER BY iw.work_id;
    """


def q_interdisc_refs(inst: str, y0: int, y1: int) -> str:
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
                CASE
                    WHEN w.type_is_proceedings = TRUE THEN 'proceedings'
                    ELSE 'journals'
                END AS document_group,
                wm.n_institutions_on_work
            FROM reports.report_membership rm
            JOIN core.work w
              ON w.work_id = rm.work_id
            JOIN core.work_to_status s
              ON s.work_id = rm.work_id
            JOIN marts.work_metrics wm
              ON wm.work_id = rm.work_id
            WHERE rm.report_name = '{inst}'
              AND w.publication_year BETWEEN {y0} AND {y1}
              AND s.is_included = TRUE
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
            iw.document_group,
            iw.n_institutions_on_work,
            rc.cited_field,
            rc.cited_domain,
            rc.n_refs_in_subfield,
            SUM(rc.n_refs_in_subfield) OVER (PARTITION BY iw.work_id) AS total_refs
        FROM inst_works iw
        JOIN ref_counts rc
          ON rc.work_id = iw.work_id
        ORDER BY iw.document_group, iw.work_id;
    """


def q_coverage(inst: str, y0: int, y1: int) -> str:
    # INT_COV is reported as the share of unique matched works that are
    # included in scope, both restricted to the evaluation period. The CTE
    # mirrors the funnel base used by assets/X_X_coverage/script.py exactly:
    # we filter on s.publication_year (from core.work_to_status, the same
    # column the funnel uses), so n_unique here equals COV_WORKS_UNIQUE in
    # the funnel and n_in_analysis equals COV_WORKS_IN_SCOPE.
    return f"""
        WITH base AS (
            SELECT
                r.work_id,
                r.work_id_duplicated,
                s.publication_year,
                s.is_included
            FROM reports.report_membership r
            LEFT JOIN core.work_to_status s
              ON s.work_id = r.work_id
            WHERE r.report_name = '{inst}'
              AND (s.publication_year BETWEEN {y0} AND {y1}
                   OR s.publication_year IS NULL)
        ),
        unique_found AS (
            SELECT *
            FROM base
            WHERE work_id = work_id_duplicated
        )
        SELECT
            COUNT(*) AS n_unique,
            SUM(
                CASE
                    WHEN is_included = TRUE
                     AND publication_year BETWEEN {y0} AND {y1}
                    THEN 1 ELSE 0
                END
            ) AS n_in_analysis
        FROM unique_found;
    """


def q_gender(inst: str, y0: int, y1: int, affiliated_only: bool) -> str:
    aff_filter = "AND wag.assigned_to_institution = TRUE" if affiliated_only else ""
    return f"""
        WITH unique_authors AS (
            SELECT DISTINCT
                wag.author_id,
                CASE
                    WHEN LOWER(COALESCE(wag.gender_effective, '')) IN ('female', 'male')
                    THEN LOWER(wag.gender_effective)
                    ELSE 'unknown'
                END AS gender,
                CASE
                    WHEN w.type_is_proceedings = TRUE THEN 'proceedings'
                    ELSE 'journals'
                END AS document_group
            FROM reports.work_author_gender wag
            JOIN core.work w
              ON w.work_id = wag.work_id
            JOIN core.work_to_status s
              ON s.work_id = wag.work_id
            WHERE wag.report_name = '{inst}'
              {aff_filter}
              AND w.publication_year BETWEEN {y0} AND {y1}
              AND s.is_included = TRUE
        ),
        by_group AS (
            SELECT
                document_group,
                gender,
                COUNT(*) AS n_authors
            FROM unique_authors
            GROUP BY document_group, gender
        ),
        overall AS (
            SELECT
                'overall' AS document_group,
                gender,
                COUNT(*) AS n_authors
            FROM (
                SELECT DISTINCT author_id, gender
                FROM unique_authors
            ) u
            GROUP BY gender
        )
        SELECT
            document_group,
            gender,
            n_authors
        FROM by_group
        UNION ALL
        SELECT
            document_group,
            gender,
            n_authors
        FROM overall
        ORDER BY document_group, gender;
    """


def q_collab_partners(inst: str, y0: int, y1: int) -> str:
    return f"""
        WITH own_inst AS (
            SELECT institution_id
            FROM reports.report_institutions_ids
            WHERE report_name = '{inst}'
        ),
        report_works AS (
            SELECT DISTINCT
                w.work_id,
                CASE
                    WHEN w.type_is_proceedings = TRUE THEN 'proceedings'
                    ELSE 'journals'
                END AS document_group
            FROM reports.report_membership rm
            JOIN core.work w
              ON w.work_id = rm.work_id
            JOIN core.work_to_status s
              ON s.work_id = rm.work_id
            WHERE rm.report_name = '{inst}'
              AND w.publication_year BETWEEN {y0} AND {y1}
              AND s.is_included = TRUE
        )
        SELECT
            rw.work_id,
            rw.document_group,
            LOWER(COALESCE(di.type, 'unknown')) AS collab_type,
            UPPER(COALESCE(dc.country_code, 'UNK')) AS country_code
        FROM report_works rw
        JOIN marts.work_institution_info wii
          ON wii.work_id = rw.work_id
        LEFT JOIN core.dim_institution di
          ON di.institution_id = wii.institution_id
        LEFT JOIN core.dim_country dc
          ON dc.country_id = di.country_id
        WHERE wii.institution_id NOT IN (SELECT institution_id FROM own_inst)
        ORDER BY rw.work_id, collab_type, country_code;
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


def fmt_count(value) -> str:
    if value is None or pd.isna(value):
        return r"\textit{n/a}"
    return f"{int(round(float(value))):,}"


def fmt_float(value, digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return r"\textit{n/a}"
    return f"{float(value):.{digits}f}"


def fmt_pct(value, digits: int = 0) -> str:
    if value is None or pd.isna(value):
        return r"\textit{n/a}"
    return f"{100.0 * float(value):.{digits}f}\\%"


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



def indicator_catalog_entry(indicator_id: str) -> dict:
    return (indicator_catalog_dict or {}).get(indicator_id, {})


def apply_symbol_placeholders(symbol_tex: str, placeholder_map: dict[str, str] | None = None) -> str:
    out = str(symbol_tex)
    if placeholder_map:
        for key, value in placeholder_map.items():
            out = out.replace(rf"\mathrm{{{key}}}", rf"\mathrm{{{value}}}")
            out = out.replace(f"{{{key}}}", f"{{{value}}}")
    return out


def indicator_symbol_tex(
    indicator_id: str,
    fallback_tex: str,
    *,
    placeholder_map: dict[str, str] | None = None,
    suffix_text: str = "",
) -> str:
    entry = indicator_catalog_entry(indicator_id)
    symbol = apply_symbol_placeholders(str(entry.get("symbol_tex", "")).strip(), placeholder_map)
    base = f"${symbol}$" if symbol else fallback_tex
    if suffix_text:
        return f"{base}{tex_escape(suffix_text)}"
    return base


def indicator_display_digits(indicator_id: str, default: int = 0) -> int:
    entry = indicator_catalog_entry(indicator_id)
    raw = str(entry.get("display_digits", "")).strip()
    if raw == "":
        return default
    try:
        parsed = int(float(raw))
    except ValueError:
        return default
    return parsed if parsed >= 0 else default


def oa_status_dimension_value() -> str:
    if OA_MODE == "selected_statuses":
        statuses = [str(x).strip().lower() for x in OA_SELECTED_STATUSES if str(x).strip()]
        return "+".join(dict.fromkeys(statuses))
    if OA_MODE == "open_vs_closed":
        return "open"
    raise ValueError("OA_MODE must be 'selected_statuses' or 'open_vs_closed'")


def build_interdisc_by_group(interdisc_df: pd.DataFrame) -> dict[str, float | None]:
    result = {group: None for group in DOCUMENT_GROUPS}
    if interdisc_df.empty:
        return result

    df = interdisc_df.copy()
    df["n_institutions_on_work"] = pd.to_numeric(df["n_institutions_on_work"], errors="coerce")
    df["n_refs_in_subfield"] = pd.to_numeric(df["n_refs_in_subfield"], errors="coerce")
    df["total_refs"] = pd.to_numeric(df["total_refs"], errors="coerce")
    df = df.dropna(
        subset=[
            "work_id",
            "document_group",
            "n_institutions_on_work",
            "cited_field",
            "cited_domain",
            "n_refs_in_subfield",
            "total_refs",
        ]
    ).copy()
    df = df[df["n_institutions_on_work"] > 0].copy()
    if df.empty:
        return result

    rs_series = compute_rs_vectorized(df)
    if rs_series.empty:
        return result

    rs_df = (
        df.drop_duplicates(subset=["work_id"])[["work_id", "document_group", "n_institutions_on_work"]]
        .set_index("work_id")
        .join(rs_series, how="inner")
        .reset_index()
    )
    if rs_df.empty:
        return result

    for document_group in ("journals", "proceedings"):
        grp = rs_df.loc[rs_df["document_group"] == document_group].copy()
        if grp.empty:
            continue
        weights = 1.0 / grp["n_institutions_on_work"]
        result[document_group] = weighted_mean(grp["rs_w"], weights)

    overall_weights = 1.0 / rs_df["n_institutions_on_work"]
    result["overall"] = weighted_mean(rs_df["rs_w"], overall_weights)
    return result


def build_split_metrics(
    works_df: pd.DataFrame,
    int_cov: float | None,
    interdisc_df: pd.DataFrame,
) -> pd.DataFrame:
    if works_df.empty:
        return pd.DataFrame(columns=["document_group"])

    df = works_df.copy()
    df["n_institutions_on_work"] = pd.to_numeric(df["n_institutions_on_work"], errors="coerce")
    df["n_citations"] = pd.to_numeric(df["n_citations"], errors="coerce")
    df["norm_vs_mean"] = pd.to_numeric(df["norm_vs_mean"], errors="coerce")
    if "P_SELF_CITS_FULL" in df.columns:
        df["P_SELF_CITS_FULL"] = pd.to_numeric(df["P_SELF_CITS_FULL"], errors="coerce")
    if "P_ALL_CITS_FULL" in df.columns:
        df["P_ALL_CITS_FULL"] = pd.to_numeric(df["P_ALL_CITS_FULL"], errors="coerce")
    df["is_top10"] = to_bool(df["is_top10"])
    df["is_uncited"] = to_bool(df["is_uncited"])
    df["cohort_is_reliable"] = to_bool(df["cohort_is_reliable"])
    df["has_collab"] = to_bool(df["has_collab"])
    df["has_int_collab"] = to_bool(df["has_int_collab"])
    if "has_industry_collab" not in df.columns:
        df["has_industry_collab"] = False
    df["has_industry_collab"] = to_bool(df["has_industry_collab"])
    df["oa_status"] = df["oa_status"].astype("string").str.strip().str.lower()
    df = pd.concat([df, df.assign(document_group="overall")], ignore_index=True)
    interdisc_by_group = build_interdisc_by_group(interdisc_df)

    if OA_MODE == "selected_statuses":
        selected = {x.lower() for x in OA_SELECTED_STATUSES}
        df["is_oa_selected"] = df["oa_status"].isin(selected)
    elif OA_MODE == "open_vs_closed":
        closed = {x.lower() for x in OA_CLOSED_STATUSES}
        df["is_oa_selected"] = ~df["oa_status"].isin(closed)
    else:
        raise ValueError("OA_MODE must be 'selected_statuses' or 'open_vs_closed'")

    out_rows = []
    for document_group in DOCUMENT_GROUPS:
        dfg = df.loc[df["document_group"] == document_group].copy()
        if dfg.empty:
            out_rows.append({"document_group": document_group})
            continue

        weights = pd.Series(0.0, index=dfg.index)
        valid_weight = dfg["n_institutions_on_work"] > 0
        weights.loc[valid_weight] = 1.0 / dfg.loc[valid_weight, "n_institutions_on_work"]

        tcs_frac = None
        mcs_frac = None
        weight_sum = float(weights.sum())
        if weight_sum > 0:
            tcs_frac = float((dfg["n_citations"].fillna(0.0) * weights).sum())
            mcs_frac = float(tcs_frac / weight_sum)

        dfg_rel = dfg.loc[dfg["cohort_is_reliable"]].copy()
        rel_weights = pd.Series(0.0, index=dfg_rel.index)
        valid_rel_weight = dfg_rel["n_institutions_on_work"] > 0
        rel_weights.loc[valid_rel_weight] = 1.0 / dfg_rel.loc[valid_rel_weight, "n_institutions_on_work"]

        p_uncited_value = None
        if not dfg_rel.empty:
            p_uncited_value = int(dfg_rel["is_uncited"].sum())

        rel_mncs = dfg_rel.loc[valid_rel_weight & dfg_rel["norm_vs_mean"].notna()].copy()
        mncs_weights = pd.Series(
            rel_weights.loc[valid_rel_weight & dfg_rel["norm_vs_mean"].notna()],
            index=rel_mncs.index,
        )
        if mncs_weights.sum() > 0:
            mncs_value = float((rel_mncs["norm_vs_mean"] * mncs_weights).sum() / mncs_weights.sum())
        else:
            mncs_value = None

        rel_pp = dfg_rel.loc[valid_rel_weight].copy()
        pp_weights = pd.Series(rel_weights.loc[valid_rel_weight], index=rel_pp.index)
        if pp_weights.sum() > 0:
            p_topten_value = float((rel_pp["is_top10"].astype(float) * pp_weights).sum())
            pp_topten_value = float(p_topten_value / pp_weights.sum())
        else:
            p_topten_value = None
            pp_topten_value = None

        p_self_cits = None
        p_all_cits = None
        pp_self_cits = None
        if "P_SELF_CITS_FULL" in dfg.columns and "P_ALL_CITS_FULL" in dfg.columns:
            p_self_cits = float(dfg["P_SELF_CITS_FULL"].fillna(0.0).sum())
            p_all_cits = float(dfg["P_ALL_CITS_FULL"].fillna(0.0).sum())
            if p_all_cits > 0:
                pp_self_cits = float(p_self_cits / p_all_cits)

        row = {
            "document_group": document_group,
            "P_FULL": int(len(dfg)),
            "P_FRAC": round(float(weights.sum()), 2),
            "INT_COV": int_cov if document_group == "overall" else None,
            "INTERDISC": interdisc_by_group.get(document_group),
            "C_TCS_FULL": float(dfg["n_citations"].sum(skipna=True)),
            "C_TCS_FRAC": tcs_frac,
            "C_MCS_FULL": float(dfg["n_citations"].mean(skipna=True)),
            "C_MCS_FRAC": mcs_frac,
            "P_TOPTEN_FRAC": round(p_topten_value, 6) if p_topten_value is not None else None,
            "PP_TOPTEN_FRAC": pp_topten_value,
            "C_MNCS_FRAC": mncs_value,
            "P_UNCITED_FULL": p_uncited_value,
            "PP_UNCITED_FULL": float(dfg_rel["is_uncited"].mean()) if not dfg_rel.empty else None,
            "P_SELF_CITS_FULL": p_self_cits,
            "P_ALL_CITS_FULL": p_all_cits,
            "PP_SELF_CITS_FULL": pp_self_cits,
            "PP_COLLAB": float(dfg["has_collab"].mean()),
            "PP_INT_COLLAB": float(dfg["has_int_collab"].mean()),
            "PP_INDUSTRY_COLLAB": float(dfg["has_industry_collab"].mean()),
            "P_OA_SELECTED": int(dfg["is_oa_selected"].sum()),
            "PP_OA_SELECTED": float(dfg["is_oa_selected"].mean()),
        }

        if OA_MODE == "selected_statuses":
            row["OA_TYPE_P_Y_FULL"] = row["P_OA_SELECTED"]
            row["OA_TYPE_PP_Y_FULL"] = row["PP_OA_SELECTED"]
        else:
            row["OA_P_FULL"] = row["P_OA_SELECTED"]
            row["OA_PP_FULL"] = row["PP_OA_SELECTED"]

        out_rows.append(row)

    return pd.DataFrame(out_rows)


def build_gender_metrics(aff_df: pd.DataFrame, all_df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    def to_group_counts(df: pd.DataFrame) -> dict[str, dict[str, int]]:
        counts = {group: {} for group in DOCUMENT_GROUPS}
        if df.empty:
            return counts

        tmp = df.copy()
        tmp["document_group"] = tmp["document_group"].astype("string").str.strip().str.lower()
        tmp["gender"] = tmp["gender"].astype("string").str.strip().str.lower()
        tmp["n_authors"] = pd.to_numeric(tmp["n_authors"], errors="coerce").fillna(0).astype(int)
        tmp = tmp[tmp["document_group"].isin(DOCUMENT_GROUPS)].copy()
        tmp["gender"] = tmp["gender"].where(tmp["gender"].isin(GENDER_ORDER), "unknown")

        grouped = (
            tmp.groupby(["document_group", "gender"], as_index=False)["n_authors"]
            .sum()
            .reset_index(drop=True)
        )
        for _, row in grouped.iterrows():
            group = str(row["document_group"])
            gender = str(row["gender"])
            counts[group][gender] = int(row["n_authors"])

        return counts

    aff_counts_by_group = to_group_counts(aff_df)
    all_counts_by_group = to_group_counts(all_df)

    rows = []
    summary: dict[str, dict[str, float | int | None]] = {}
    for group in DOCUMENT_GROUPS:
        aff_counts = aff_counts_by_group.get(group, {})
        all_counts = all_counts_by_group.get(group, {})

        aff_female = int(aff_counts.get("female", 0))
        aff_male = int(aff_counts.get("male", 0))
        all_female = int(all_counts.get("female", 0))
        all_male = int(all_counts.get("male", 0))

        aff_binary_total = aff_female + aff_male
        all_binary_total = all_female + all_male

        pa_f_inst = (aff_female / aff_binary_total) if aff_binary_total > 0 else None
        pa_f_pubs = (all_female / all_binary_total) if all_binary_total > 0 else None
        rpa_f = (pa_f_inst / pa_f_pubs) if pa_f_inst is not None and pa_f_pubs not in (None, 0) else None

        aff_unknown = int(aff_counts.get("unknown", 0))
        all_unknown = int(all_counts.get("unknown", 0))
        aff_total_all = aff_female + aff_male + aff_unknown
        all_total_all = all_female + all_male + all_unknown

        summary[group] = {
            "A_AFF_AUTHORS": aff_total_all if aff_total_all > 0 else None,
            "A_ALL_AUTHORS": all_total_all if all_total_all > 0 else None,
            "A_F_INST": aff_female if aff_binary_total > 0 else None,
            "A_M_INST": aff_male if aff_binary_total > 0 else None,
            "A_FEMALE_INST": aff_female if aff_binary_total > 0 else None,
            "A_MALE_INST": aff_male if aff_binary_total > 0 else None,
            "A_FEMALE_PUBS": all_female if all_binary_total > 0 else None,
            "A_MALE_PUBS": all_male if all_binary_total > 0 else None,
            "PA_F_INST": pa_f_inst,
            "PA_F_PUBS": pa_f_pubs,
            "RPA_F": rpa_f,
            "A_UNKNOWN_INST": aff_unknown,
            "A_UNKNOWN_PUBS": all_unknown,
            "PA_UNKNOWN_INST_ALL": (aff_unknown / aff_total_all) if aff_total_all > 0 else None,
            "PA_UNKNOWN_PUBS_ALL": (all_unknown / all_total_all) if all_total_all > 0 else None,
        }

        for gender in GENDER_ORDER:
            aff_count = int(aff_counts.get(gender, 0))
            all_count = int(all_counts.get(gender, 0))

            if gender in {"female", "male"} and aff_binary_total > 0:
                aff_share = aff_count / aff_binary_total
            else:
                aff_share = None

            if gender in {"female", "male"} and all_binary_total > 0:
                all_share = all_count / all_binary_total
            else:
                all_share = None

            rows.append(
                {
                    "document_group": group,
                    "gender": gender,
                    "G_AFF_AUTHORS_COUNT": aff_count,
                    "PA_F_INST": aff_share,
                    "G_ALL_AUTHORS_COUNT": all_count,
                    "PA_F_PUBS": all_share,
                }
            )

    return pd.DataFrame(rows), summary


def build_collab_type_metrics(works_df: pd.DataFrame, partners_df: pd.DataFrame) -> pd.DataFrame:
    if works_df.empty:
        return pd.DataFrame(columns=["document_group", "collab_type", "n_work", "PP_COLLAB_TYPE"])

    works = works_df[["work_id", "document_group"]].drop_duplicates().copy()
    works_all = pd.concat([works, works.assign(document_group="overall")], ignore_index=True)
    totals = (
        works_all.groupby("document_group", as_index=False)["work_id"]
        .nunique()
        .rename(columns={"work_id": "n_total"})
    )

    if partners_df.empty:
        observed_types = []
        counts = pd.DataFrame(columns=["document_group", "collab_type", "n_work"])
    else:
        part = partners_df[["work_id", "document_group", "collab_type"]].copy()
        part["collab_type"] = (
            part["collab_type"]
            .astype("string")
            .str.strip()
            .str.lower()
            .replace("", "unknown")
            .fillna("unknown")
        )
        part = part.drop_duplicates()
        observed_types = sorted(set(part["collab_type"]))
        part_all = pd.concat([part, part.assign(document_group="overall")], ignore_index=True)
        counts = (
            part_all.groupby(["document_group", "collab_type"], as_index=False)["work_id"]
            .nunique()
            .rename(columns={"work_id": "n_work"})
        )

    ordered_types = list(COLLAB_TYPE_ORDER) + [t for t in observed_types if t not in COLLAB_TYPE_ORDER]
    grid = pd.MultiIndex.from_product(
        [["journals", "proceedings", "overall"], ordered_types],
        names=["document_group", "collab_type"],
    ).to_frame(index=False)

    out = grid.merge(counts, on=["document_group", "collab_type"], how="left")
    out = out.merge(totals, on="document_group", how="left")
    out["n_work"] = pd.to_numeric(out["n_work"], errors="coerce").fillna(0).astype(int)
    out["PP_COLLAB_TYPE"] = out["n_work"] / out["n_total"]
    return out[["document_group", "collab_type", "n_work", "PP_COLLAB_TYPE"]]


def build_collab_country_metrics(works_df: pd.DataFrame, partners_df: pd.DataFrame, top_n: int) -> pd.DataFrame:
    if works_df.empty or top_n <= 0:
        return pd.DataFrame(columns=["document_group", "country_code", "n_work", "n_overall_work", "PP_COLLAB_COUNTRY"])

    works = works_df[["work_id", "document_group"]].drop_duplicates().copy()
    works_all = pd.concat([works, works.assign(document_group="overall")], ignore_index=True)
    totals = (
        works_all.groupby("document_group", as_index=False)["work_id"]
        .nunique()
        .rename(columns={"work_id": "n_total"})
    )

    if partners_df.empty:
        return pd.DataFrame(columns=["document_group", "country_code", "n_work", "n_overall_work", "PP_COLLAB_COUNTRY"])

    part = partners_df[["work_id", "document_group", "country_code"]].copy()
    part["country_code"] = (
        part["country_code"]
        .astype("string")
        .str.strip()
        .str.upper()
        .replace("", "UNK")
        .fillna("UNK")
    )
    part = part.drop_duplicates()
    part_all = pd.concat([part, part.assign(document_group="overall")], ignore_index=True)

    counts = (
        part_all.groupby(["document_group", "country_code"], as_index=False)["work_id"]
        .nunique()
        .rename(columns={"work_id": "n_work"})
    )

    overall_rank = counts.loc[counts["document_group"] == "overall", ["country_code", "n_work"]].copy()
    overall_rank = overall_rank.sort_values(["n_work", "country_code"], ascending=[False, True]).head(top_n)

    if overall_rank.empty:
        return pd.DataFrame(columns=["document_group", "country_code", "n_work", "n_overall_work", "PP_COLLAB_COUNTRY"])

    top_codes = overall_rank["country_code"].tolist()
    grid = pd.MultiIndex.from_product(
        [["journals", "proceedings", "overall"], top_codes],
        names=["document_group", "country_code"],
    ).to_frame(index=False)

    out = grid.merge(counts, on=["document_group", "country_code"], how="left")
    out = out.merge(totals, on="document_group", how="left")
    out["n_work"] = pd.to_numeric(out["n_work"], errors="coerce").fillna(0).astype(int)
    out["PP_COLLAB_COUNTRY"] = out["n_work"] / out["n_total"]
    out = out.merge(
        overall_rank.rename(columns={"n_work": "n_overall_work"}),
        on="country_code",
        how="left",
    )
    return out[["document_group", "country_code", "n_work", "n_overall_work", "PP_COLLAB_COUNTRY"]]


def build_data_csv(split_df: pd.DataFrame, gender_df: pd.DataFrame, gender_summary: dict) -> pd.DataFrame:
    oa_cols = ["OA_TYPE_P_Y_FULL", "OA_TYPE_PP_Y_FULL"] if OA_MODE == "selected_statuses" else ["OA_P_FULL", "OA_PP_FULL"]

    split_base_cols = [c for c in split_df.columns if c not in {"document_group", *oa_cols}]
    split_part = split_df[["document_group", *split_base_cols]].copy()
    split_part["gender"] = ""
    split_part["oa_status"] = ""

    available_oa_cols = [c for c in oa_cols if c in split_df.columns]
    oa_part = pd.DataFrame(columns=["document_group", "gender", "oa_status", *available_oa_cols])
    if available_oa_cols:
        oa_part = split_df[["document_group", *available_oa_cols]].copy()
        oa_part["gender"] = ""
        oa_part["oa_status"] = oa_status_dimension_value()
        has_oa_value = pd.Series(False, index=oa_part.index)
        for col in available_oa_cols:
            has_oa_value = has_oa_value | pd.to_numeric(oa_part[col], errors="coerce").notna()
        oa_part = oa_part.loc[has_oa_value].copy()

    gender_cols = [
        "document_group",
        "gender",
        "G_AFF_AUTHORS_COUNT",
        "PA_F_INST",
        "G_ALL_AUTHORS_COUNT",
        "PA_F_PUBS",
    ]
    gender_cols = [c for c in gender_cols if c in gender_df.columns]
    gender_part = gender_df[gender_cols].copy()
    gender_part["oa_status"] = ""

    author_totals_rows = []
    for group in DOCUMENT_GROUPS:
        group_summary = gender_summary.get(group, {}) if isinstance(gender_summary, dict) else {}
        author_totals_rows.append(
            {
                "document_group": group,
                "gender": "",
                "oa_status": "",
                "A_AFF_AUTHORS": group_summary.get("A_AFF_AUTHORS"),
                "A_ALL_AUTHORS": group_summary.get("A_ALL_AUTHORS"),
                "A_FEMALE_INST": group_summary.get("A_FEMALE_INST"),
                "A_MALE_INST": group_summary.get("A_MALE_INST"),
                "A_FEMALE_PUBS": group_summary.get("A_FEMALE_PUBS"),
                "A_MALE_PUBS": group_summary.get("A_MALE_PUBS"),
                "PA_F_INST": group_summary.get("PA_F_INST"),
                "PA_F_PUBS": group_summary.get("PA_F_PUBS"),
                "RPA_F": group_summary.get("RPA_F"),
            }
        )
    author_totals_part = pd.DataFrame(author_totals_rows)

    out = pd.concat([split_part, oa_part, gender_part, author_totals_part], ignore_index=True, sort=False)
    dim_cols = ["document_group", "gender", "oa_status"]
    indicator_ids = set((indicator_catalog_dict or {}).keys())
    indicator_cols = [c for c in out.columns if c not in dim_cols and c in indicator_ids]
    return out[dim_cols + indicator_cols]


def round_float_outputs(df: pd.DataFrame, decimals: int = 8) -> pd.DataFrame:
    out = df.copy()
    float_cols = out.select_dtypes(include=["float16", "float32", "float64", "Float32", "Float64"]).columns
    if len(float_cols) > 0:
        out.loc[:, float_cols] = out.loc[:, float_cols].round(decimals)
    return out


def build_table_tex(
    split_df: pd.DataFrame,
    gender_summary: dict,
    collab_type_df: pd.DataFrame,
    collab_country_df: pd.DataFrame,
) -> str:
    split = split_df.copy()
    split["document_group"] = split["document_group"].astype("string").str.lower()
    split = split.drop_duplicates(subset=["document_group"], keep="last").set_index("document_group")

    def value(group: str, col: str):
        if group not in split.index or col not in split.columns:
            return None
        return split.at[group, col]

    def gvalue(group: str, col: str):
        if not isinstance(gender_summary, dict):
            return None
        group_values = gender_summary.get(group, {})
        if not isinstance(group_values, dict):
            return None
        return group_values.get(col)

    p_full_label = indicator_symbol_tex("P_FULL", tex_escape("P [full]"))
    p_frac_label = indicator_symbol_tex("P_FRAC", tex_escape("P [frac]"))
    int_cov_label = indicator_symbol_tex("INT_COV", tex_escape("Int Cov"))
    tcs_label = indicator_symbol_tex("C_TCS_FULL", tex_escape("TCS [full]"))
    mcs_label = indicator_symbol_tex("C_MCS_FULL", tex_escape("MCS [full]"))
    p_top10_label = indicator_symbol_tex("P_TOPTEN_FRAC", tex_escape("P [top 10%]"))
    pp_top10_label = indicator_symbol_tex("PP_TOPTEN_FRAC", tex_escape("PP [top 10%]"))
    mncs_label = indicator_symbol_tex("C_MNCS_FRAC", tex_escape("MNCS [frac]"))
    p_uncited_label = indicator_symbol_tex("P_UNCITED_FULL", tex_escape("P [uncited]"))
    pp_uncited_label = indicator_symbol_tex("PP_UNCITED_FULL", tex_escape("PP [uncited]"))
    p_self_cits_label = indicator_symbol_tex("P_SELF_CITS_FULL", tex_escape("P [self cits]"))
    pp_self_cits_label = indicator_symbol_tex("PP_SELF_CITS_FULL", tex_escape("PP [self cits]"))

    pp_industry_label = indicator_symbol_tex("PP_INDUSTRY_COLLAB", tex_escape("PP [industry collab]"))
    pp_collab_label = indicator_symbol_tex("PP_COLLAB", tex_escape("PP [collab]"))
    pp_int_collab_label = indicator_symbol_tex("PP_INT_COLLAB", tex_escape("PP [int collab]"))
    interdisc_label = indicator_symbol_tex("INTERDISC", r"$\mathrm{InterDisc}$")

    oa_count_label = indicator_symbol_tex("OA_P_FULL", tex_escape("P [OA open]"))
    oa_share_label = indicator_symbol_tex("OA_PP_FULL", tex_escape("PP [OA open]"))

    a_f_inst_label = indicator_symbol_tex(
        "A_FEMALE_INST",
        tex_escape("A[F inst]"),
        placeholder_map={"gender": "female"},
    )
    a_m_inst_label = indicator_symbol_tex(
        "A_MALE_INST",
        tex_escape("A[M inst]"),
        placeholder_map={"gender": "male"},
    )
    pa_f_inst_label = indicator_symbol_tex(
        "PA_F_INST",
        tex_escape("PA[F inst]"),
        placeholder_map={"gender": "female"},
    )
    pa_f_pubs_label = indicator_symbol_tex(
        "PA_F_PUBS",
        tex_escape("PA[F pubs]"),
        placeholder_map={"gender": "female"},
    )
    a_aff_authors_label = indicator_symbol_tex("A_AFF_AUTHORS", r"$\mathrm{A}_{\mathrm{aff}}$")
    rpa_f_label = indicator_symbol_tex("RPA_F", r"$\mathrm{RPA}[\mathrm{female}]$")
    int_cov_digits = indicator_display_digits("INT_COV", default=2)

    unknown_aff_note = f"{fmt_count(gvalue('overall', 'A_UNKNOWN_INST'))} ({fmt_pct(gvalue('overall', 'PA_UNKNOWN_INST_ALL'), 1)})"
    unknown_all_note = f"{fmt_count(gvalue('overall', 'A_UNKNOWN_PUBS'))} ({fmt_pct(gvalue('overall', 'PA_UNKNOWN_PUBS_ALL'), 1)})"

    lines = [
        r"{",
        r"  \sbox0{%",
        r"  \begin{tabular}{@{}lrrr@{}}",
        r"    \toprule",
        r"    Indicator & Journals & Proceedings & Overall \\",
        r"    \midrule",
    ]

    state = {"first": True}

    def start_section(title: str) -> None:
        if not state["first"]:
            lines.append(r"    \midrule")
        state["first"] = False
        lines.append(rf"    \multicolumn{{4}}{{c}}{{{title}}} \\")
        lines.append(r"    \midrule")

    start_section("Output")
    lines.append(
        rf"    {p_full_label} & {fmt_count(value('journals', 'P_FULL'))} & {fmt_count(value('proceedings', 'P_FULL'))} & {fmt_count(value('overall', 'P_FULL'))} \\",
    )
    lines.append(
        rf"    {p_frac_label} & {fmt_count(value('journals', 'P_FRAC'))} & {fmt_count(value('proceedings', 'P_FRAC'))} & {fmt_count(value('overall', 'P_FRAC'))} \\",
    )
    lines.append(
        rf"    {int_cov_label} &  &  & {fmt_pct(value('overall', 'INT_COV'), int_cov_digits)} \\",
    )

    start_section("Open Access")
    lines.append(
        rf"    {oa_count_label} & {fmt_count(value('journals', 'OA_P_FULL'))} & {fmt_count(value('proceedings', 'OA_P_FULL'))} & {fmt_count(value('overall', 'OA_P_FULL'))} \\",
    )
    lines.append(
        rf"    {oa_share_label} & {fmt_pct(value('journals', 'OA_PP_FULL'))} & {fmt_pct(value('proceedings', 'OA_PP_FULL'))} & {fmt_pct(value('overall', 'OA_PP_FULL'))} \\",
    )

    start_section("Collaborations and Partners")

    lines.append(
        rf"    {pp_collab_label} & {fmt_pct(value('journals', 'PP_COLLAB'))} & {fmt_pct(value('proceedings', 'PP_COLLAB'))} & {fmt_pct(value('overall', 'PP_COLLAB'))} \\",
    )
    lines.append(
        rf"    {pp_int_collab_label} & {fmt_pct(value('journals', 'PP_INT_COLLAB'))} & {fmt_pct(value('proceedings', 'PP_INT_COLLAB'))} & {fmt_pct(value('overall', 'PP_INT_COLLAB'))} \\",
    )
    lines.append(
        rf"    {pp_industry_label} & {fmt_pct(value('journals', 'PP_INDUSTRY_COLLAB'))} & {fmt_pct(value('proceedings', 'PP_INDUSTRY_COLLAB'))} & {fmt_pct(value('overall', 'PP_INDUSTRY_COLLAB'))} \\",
    )
    lines.append(
        rf"    {interdisc_label} & {fmt_float(value('journals', 'INTERDISC'), 2)} & {fmt_float(value('proceedings', 'INTERDISC'), 2)} & {fmt_float(value('overall', 'INTERDISC'), 2)} \\",
    )

    start_section("Citation Impact")

    lines.append(
        rf"    {tcs_label} & {fmt_count(value('journals', 'C_TCS_FULL'))} & {fmt_count(value('proceedings', 'C_TCS_FULL'))} & {fmt_count(value('overall', 'C_TCS_FULL'))} \\",
    )
    lines.append(
        rf"    {mcs_label} & {fmt_float(value('journals', 'C_MCS_FULL'), 2)} & {fmt_float(value('proceedings', 'C_MCS_FULL'), 2)} & {fmt_float(value('overall', 'C_MCS_FULL'), 2)} \\",
    )
    lines.append(
        rf"    {p_self_cits_label} & {fmt_count(value('journals', 'P_SELF_CITS_FULL'))} & {fmt_count(value('proceedings', 'P_SELF_CITS_FULL'))} & {fmt_count(value('overall', 'P_SELF_CITS_FULL'))} \\",
    )
    lines.append(
        rf"    {pp_self_cits_label} & {fmt_pct(value('journals', 'PP_SELF_CITS_FULL'))} & {fmt_pct(value('proceedings', 'PP_SELF_CITS_FULL'))} & {fmt_pct(value('overall', 'PP_SELF_CITS_FULL'))} \\",
    )
    lines.append(
        rf"    {p_uncited_label} & {fmt_count(value('journals', 'P_UNCITED_FULL'))} & {fmt_count(value('proceedings', 'P_UNCITED_FULL'))} & {fmt_count(value('overall', 'P_UNCITED_FULL'))} \\",
    )
    lines.append(
        rf"    {pp_uncited_label} & {fmt_pct(value('journals', 'PP_UNCITED_FULL'))} & {fmt_pct(value('proceedings', 'PP_UNCITED_FULL'))} & {fmt_pct(value('overall', 'PP_UNCITED_FULL'))} \\",
    )
    lines.append(
        rf"    {p_top10_label} & {fmt_count(value('journals', 'P_TOPTEN_FRAC'))} & {fmt_count(value('proceedings', 'P_TOPTEN_FRAC'))} & {fmt_count(value('overall', 'P_TOPTEN_FRAC'))} \\",
    )
    lines.append(
        rf"    {pp_top10_label} & {fmt_pct(value('journals', 'PP_TOPTEN_FRAC'), 1)} & {fmt_pct(value('proceedings', 'PP_TOPTEN_FRAC'), 1)} & {fmt_pct(value('overall', 'PP_TOPTEN_FRAC'), 1)} \\",
    )
    lines.append(
        rf"    {mncs_label} & {fmt_float(value('journals', 'C_MNCS_FRAC'), 2)} & {fmt_float(value('proceedings', 'C_MNCS_FRAC'), 2)} & {fmt_float(value('overall', 'C_MNCS_FRAC'), 2)} \\",
    )

    start_section("Author and Gender Distribution")
    lines.append(
        rf"    {a_aff_authors_label} & {fmt_count(gvalue('journals', 'A_AFF_AUTHORS'))} & {fmt_count(gvalue('proceedings', 'A_AFF_AUTHORS'))} & {fmt_count(gvalue('overall', 'A_AFF_AUTHORS'))} \\",
    )
    lines.append(
        rf"    {a_f_inst_label} & {fmt_count(gvalue('journals', 'A_F_INST'))} & {fmt_count(gvalue('proceedings', 'A_F_INST'))} & {fmt_count(gvalue('overall', 'A_F_INST'))} \\",
    )
    lines.append(
        rf"    {a_m_inst_label} & {fmt_count(gvalue('journals', 'A_M_INST'))} & {fmt_count(gvalue('proceedings', 'A_M_INST'))} & {fmt_count(gvalue('overall', 'A_M_INST'))} \\",
    )
    lines.append(
        rf"    {pa_f_inst_label} & {fmt_pct(gvalue('journals', 'PA_F_INST'), 0)} & {fmt_pct(gvalue('proceedings', 'PA_F_INST'), 0)} & {fmt_pct(gvalue('overall', 'PA_F_INST'), 0)} \\",
    )
    lines.append(
        rf"    {pa_f_pubs_label} & {fmt_pct(gvalue('journals', 'PA_F_PUBS'), 0)} & {fmt_pct(gvalue('proceedings', 'PA_F_PUBS'), 0)} & {fmt_pct(gvalue('overall', 'PA_F_PUBS'), 0)} \\",
    )
    lines.append(
        rf"    {rpa_f_label} & {fmt_float(gvalue('journals', 'RPA_F'), 2)} & {fmt_float(gvalue('proceedings', 'RPA_F'), 2)} & {fmt_float(gvalue('overall', 'RPA_F'), 2)} \\",
    )

    lines.extend(
        [
            r"    \bottomrule",
            r"  \end{tabular}%",
            r"  }",
            r"  \usebox0",
            r"  \vspace{0.4em}",
            r"    \footnotesize",
            r"  \begin{minipage}{\wd0}",
            f"    \\textit{{Note:}} Authors with unknown gender represent {unknown_aff_note} among \\InstShort{{}}-affiliated authors and {unknown_all_note} among all authors contributing contributing to \\InstShort{{}} publications.",
            r"  \end{minipage}",
            r"}",
            "",
        ]
    )
    return "\n".join(lines)


# inst is the institution name, con is the connection to the database (if needed)
for inst, con in asset.iterate_institutions():
    works_df = asset.extract(
        con=con,
        inst=inst,
        query=q_works(inst, asset.year_first, asset.year_last),
        out_name="works.csv",
    )

    self_cits_df = asset.extract(
        con=con,
        inst=inst,
        query=q_self_citations(inst, asset.year_first, asset.year_last),
        out_name="works_self_citations.csv",
    )

    interdisc_refs_df = asset.extract(
        con=con,
        inst=inst,
        query=q_interdisc_refs(inst, asset.year_first, asset.year_last),
        out_name="works_interdisciplinarity.csv",
    )

    if not self_cits_df.empty:
        works_df = works_df.merge(self_cits_df, on="work_id", how="left")

    coverage_df = asset.extract(
        con=con,
        inst=inst,
        query=q_coverage(inst, asset.year_first, asset.year_last),
        out_name="coverage.csv",
    )

    gender_aff_df = asset.extract(
        con=con,
        inst=inst,
        query=q_gender(inst, asset.year_first, asset.year_last, affiliated_only=True),
        out_name="gender_affiliated.csv",
    )

    gender_all_df = asset.extract(
        con=con,
        inst=inst,
        query=q_gender(inst, asset.year_first, asset.year_last, affiliated_only=False),
        out_name="gender_all.csv",
    )
    collab_partners_df = asset.extract(
        con=con,
        inst=inst,
        query=q_collab_partners(inst, asset.year_first, asset.year_last),
        out_name="collab_partners.csv",
    )

    n_unique = pd.to_numeric(coverage_df.loc[0, "n_unique"], errors="coerce")
    n_in_analysis = pd.to_numeric(coverage_df.loc[0, "n_in_analysis"], errors="coerce")
    if pd.notna(n_unique) and n_unique > 0 and pd.notna(n_in_analysis):
        int_cov = float(n_in_analysis) / float(n_unique)
    else:
        int_cov = None

    split_df = build_split_metrics(works_df, int_cov, interdisc_refs_df)
    gender_df, gender_summary = build_gender_metrics(gender_aff_df, gender_all_df)
    collab_type_df = build_collab_type_metrics(works_df, collab_partners_df)
    collab_country_df = build_collab_country_metrics(works_df, collab_partners_df, COLLAB_COUNTRY_TOP_N)
    data_df = build_data_csv(split_df, gender_df, gender_summary)

    out = asset.inst_dir(inst)
    export_data_df = round_float_outputs(data_df, decimals=8)
    export_data_df.to_csv(out / "data.csv", index=False)

    pd.concat(
        [
            split_df.assign(metric_scope="summary_split"),
            gender_df.assign(metric_scope="summary_gender"),
            collab_type_df.assign(metric_scope="summary_collab_type"),
            collab_country_df.assign(metric_scope="summary_collab_country"),
        ],
        ignore_index=True,
        sort=False,
    ).to_csv(out / "table_data.csv", index=False)

    (out / "table.tex").write_text(
        build_table_tex(split_df, gender_summary, collab_type_df, collab_country_df),
        encoding="utf-8",
    )
