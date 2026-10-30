from utility import get_unit_params_dict, get_indicator_catalog_dict
from core.asset import Asset

import pandas as pd

asset = Asset(script_file=__file__)
ROUND_DIGITS = 10
YEAR_FIRST = int(asset.year_first)
YEAR_LAST = int(asset.year_last)
RECENT_WINDOW = 4
RECENT_END = YEAR_LAST
RECENT_START = max(YEAR_FIRST, RECENT_END - RECENT_WINDOW + 1)
BASELINE_START = YEAR_FIRST
BASELINE_END = RECENT_START - 1
RECENT_N_YEARS = max(1, RECENT_END - RECENT_START + 1)
BASELINE_N_YEARS = max(0, BASELINE_END - BASELINE_START + 1)

# Load naming conventions from data/...csv files
unit_params_dict = get_unit_params_dict()
indicator_catalog_dict = get_indicator_catalog_dict()


def ensuremath_wrap(symbol_tex: str) -> str:
    if not symbol_tex:
        return symbol_tex
    if r"\ensuremath{" in symbol_tex:
        return symbol_tex
    return rf"\ensuremath{{{symbol_tex}}}"


# inst is the institution name, con is the connection to the database (if needed)
for inst, con in asset.iterate_institutions():

    # Extract main data using asset.extract()
    def query_wrapper(inst: str) -> str:
        return f'''
WITH report_base AS (
    SELECT DISTINCT
        cw.work_id,
        cw.subfield,
        cw.publication_year,
        wm.n_institutions_on_work,
        wm.norm_vs_mean,
        wm.is_top10,
        wm.cohort_is_reliable
    FROM reports.report_membership r
    JOIN core.work cw
      ON cw.work_id = r.work_id
    JOIN marts.work_metrics wm
      ON wm.work_id = r.work_id
    WHERE r.report_name = '{inst}'
      AND cw.publication_year BETWEEN {YEAR_FIRST} AND {YEAR_LAST}
),

inst_agg AS (
    SELECT
        subfield,
        COUNT(*) AS p_full,
        SUM(CASE WHEN n_institutions_on_work > 0 THEN 1.0 / n_institutions_on_work ELSE 0 END) AS p_frac,
        SUM(
            CASE
                WHEN publication_year BETWEEN {BASELINE_START} AND {BASELINE_END}
                     AND n_institutions_on_work > 0
                THEN 1.0 / n_institutions_on_work
                ELSE 0
            END
        ) AS p_frac_baseline,
        SUM(
            CASE
                WHEN publication_year BETWEEN {RECENT_START} AND {RECENT_END}
                     AND n_institutions_on_work > 0
                THEN 1.0 / n_institutions_on_work
                ELSE 0
            END
        ) AS p_frac_recent
    FROM report_base
    GROUP BY subfield
    HAVING SUM(CASE WHEN n_institutions_on_work > 0 THEN 1.0 / n_institutions_on_work ELSE 0 END) > 50
),

inst_impact AS (
    SELECT
        subfield,
        SUM(
            CASE
                WHEN cohort_is_reliable = TRUE AND n_institutions_on_work > 0
                THEN norm_vs_mean * (1.0 / n_institutions_on_work)
                ELSE 0
            END
        ) / NULLIF(
            SUM(
                CASE
                    WHEN cohort_is_reliable = TRUE AND n_institutions_on_work > 0
                    THEN 1.0 / n_institutions_on_work
                    ELSE 0
                END
            ),
            0
        ) AS mncs_frac,
        SUM(
            CASE
                WHEN cohort_is_reliable = TRUE AND n_institutions_on_work > 0 AND is_top10
                THEN 1.0 / n_institutions_on_work
                ELSE 0
            END
        ) / NULLIF(
            SUM(
                CASE
                    WHEN cohort_is_reliable = TRUE AND n_institutions_on_work > 0
                    THEN 1.0 / n_institutions_on_work
                    ELSE 0
                END
            ),
            0
        ) AS pp_top10_frac
    FROM report_base
    GROUP BY subfield
),

inst_total AS (
    SELECT SUM(p_frac) AS p_local_total_frac
    FROM inst_agg
),

-- GLOBAL (FULL COUNT)
global_agg AS (
    SELECT
        w.subfield,
        COUNT(*) AS p_world_full,

        SUM(
            CASE
                WHEN w.publication_year BETWEEN {BASELINE_START} AND {BASELINE_END}
                THEN 1 ELSE 0
            END
        ) AS p_world_full_baseline,

        SUM(
            CASE
                WHEN w.publication_year BETWEEN {RECENT_START} AND {RECENT_END}
                THEN 1 ELSE 0
            END
        ) AS p_world_full_recent

    FROM core.work w
    WHERE w.publication_year BETWEEN {YEAR_FIRST} AND {YEAR_LAST}
    GROUP BY w.subfield
),

global_total AS (
    SELECT SUM(p_world_full) AS p_world_total_full
    FROM global_agg
)

SELECT
    ia.subfield,

    -- size metrics
    ia.p_full,
    ia.p_frac,

    -- TREND institution (fractional, recent vs baseline)
    CASE
        WHEN {BASELINE_N_YEARS} > 0 AND ia.p_frac_baseline > 0
            THEN (ia.p_frac_recent / {float(RECENT_N_YEARS)})
                 / (ia.p_frac_baseline / {float(BASELINE_N_YEARS)})
        ELSE NULL
    END AS trend_inst_recent_vs_baseline,

    -- TREND global (full count, recent vs baseline)
    CASE
        WHEN {BASELINE_N_YEARS} > 0 AND ga.p_world_full_baseline > 0
            THEN (ga.p_world_full_recent::DOUBLE / {float(RECENT_N_YEARS)})
                 / (ga.p_world_full_baseline::DOUBLE / {float(BASELINE_N_YEARS)})
        ELSE NULL
    END AS trend_world_recent_vs_baseline,

    -- impact metrics
    ii.mncs_frac,
    ii.pp_top10_frac,

    -- local vs global share (fractional vs full)
    ia.p_frac / it.p_local_total_frac AS share_local,
    ga.p_world_full::DOUBLE / gt.p_world_total_full AS share_world,

    -- SPECIALIZATION = local share / world share
    (ia.p_frac / it.p_local_total_frac)
        / NULLIF(
            ga.p_world_full::DOUBLE / gt.p_world_total_full,
            0
        ) AS specialization_ratio

FROM inst_agg ia
LEFT JOIN inst_impact ii ON ii.subfield = ia.subfield
CROSS JOIN inst_total it
LEFT JOIN global_agg ga ON ga.subfield = ia.subfield
CROSS JOIN global_total gt
WHERE specialization_ratio >= 1.5
ORDER BY specialization_ratio DESC, ia.subfield ASC;
        '''

    df = asset.extract(
        con=con,
        inst=inst,
        query=query_wrapper,
        force=True,
    )
    expected_cols = {
        "p_frac",
        "trend_inst_recent_vs_baseline",
        "trend_world_recent_vs_baseline",
        "mncs_frac",
        "pp_top10_frac",
        "share_local",
        "share_world",
        "specialization_ratio",
    }
    if not expected_cols.issubset(df.columns):
        df = asset.extract(
            con=con,
            inst=inst,
            query=query_wrapper,
            force=True,
        )
    df[
        [
            "p_frac",
            "trend_inst_recent_vs_baseline",
            "trend_world_recent_vs_baseline",
            "mncs_frac",
            "pp_top10_frac",
            "share_local",
            "share_world",
            "specialization_ratio",
        ]
    ] = df[
        [
            "p_frac",
            "trend_inst_recent_vs_baseline",
            "trend_world_recent_vs_baseline",
            "mncs_frac",
            "pp_top10_frac",
            "share_local",
            "share_world",
            "specialization_ratio",
        ]
    ].round(ROUND_DIGITS)
    df = df.sort_values(["specialization_ratio", "subfield"], ascending=[False, True]).reset_index(drop=True)
    df.to_csv(asset.inst_dir(inst) / "data.csv", index=False)

    # Extract tree data (second extract with different out_name)
    def tree_query_wrapper(inst: str) -> str:
        return '''
             SELECT subfield, ANY_VALUE(subfield_name) as subfield_name, ANY_VALUE(field_name) as field_name, ANY_VALUE(domain_name) as domain_name
             FROM core.topics_tree
             GROUP BY subfield
        '''

    tree_df = asset.extract(
        con=con,
        inst=inst,
        query=tree_query_wrapper,
        out_name="tree.csv",
        force=True,
    )

    # Join the tree data
    df = df.merge(tree_df, on='subfield', how='left')
    df["subfield_label"] = (
        df["subfield_name"].fillna(df["subfield"].astype(str))
        + df["field_name"].fillna("").map(lambda v: f" ({v})" if v else "")
    )
    df["row_order"] = pd.RangeIndex(start=1, stop=len(df) + 1, step=1)
    df.to_csv(asset.inst_dir(inst) / "data.csv", index=False)

    # ------------------------------
    # Data Preparation
    # ------------------------------
    df['subfield_display'] = df['subfield_name']
    df_pretty = df[
        [
            'subfield_display',
            'specialization_ratio',
            'p_full',
            #'trend_inst_recent_vs_baseline',
            'mncs_frac',
            'pp_top10_frac',
        ]
    ].copy()

    p_full_symbol_tex = (indicator_catalog_dict.get("P_FULL", {}) or {}).get("symbol_tex", "").strip()
    mncs_symbol_tex = (indicator_catalog_dict.get("C_MNCS_FRAC", {}) or {}).get("symbol_tex", "").strip()
    pp_top10_symbol_tex = (indicator_catalog_dict.get("PP_TOPTEN_FRAC", {}) or {}).get("symbol_tex", "").strip()

    p_full_label = ensuremath_wrap(p_full_symbol_tex) if p_full_symbol_tex else "P[full]"
    mncs_label = ensuremath_wrap(mncs_symbol_tex) if mncs_symbol_tex else "MNCS[frac]"
    pp_top10_label = ensuremath_wrap(pp_top10_symbol_tex) if pp_top10_symbol_tex else "PP[top10][frac]"
    trend_label = f"Trend ({RECENT_N_YEARS}y)"

    col_subfield = "Subfield"
    col_spec = "Spec."
    col_count = p_full_label
    col_trend = trend_label
    col_mncs = mncs_label
    col_pp = pp_top10_label

    #df_pretty.columns = [col_subfield, col_spec, col_count, col_trend, col_mncs, col_pp]
    df_pretty.columns = [col_subfield, col_spec, col_count, col_mncs, col_pp]
    df_pretty.index = pd.RangeIndex(start=1, stop=len(df_pretty) + 1, step=1)
    #df_pretty.index.name = "rank"

    # PPtop10 in %
    df_pretty[col_pp] *= 100

    # ------------------------------
    # Style and format table
    # ------------------------------
    styled = df_pretty.style.format({
        col_spec: "{:.1f}",
        col_count: "{:.0f}",
        #col_trend: "{:.1f}",
        col_mncs: "{:.2f}",
        col_pp: "{:.1f}\\%",
    })

    # Specialization ratio: 1.5..10 (no real midpoint needed here, just darker for higher)
    styled = styled.background_gradient(
        cmap="Blues",
        subset=[col_spec],
        vmin=1.5,
        vmax=10,
    )

    # Publications: automatic scaling
    styled = styled.background_gradient(
        cmap="Blues",
        subset=[col_count],
    )

    # Trends: midpoint = 1  → symmetric range 0.5..1.5
    # styled = styled.background_gradient(
    #     cmap="RdBu",
    #     subset=[col_trend],
    #     vmin=0.5,
    #     vmax=1.5,
    # )

    # MNCS: midpoint = 1 → symmetric range 0.5..1.5
    styled = styled.background_gradient(
        cmap="RdBu",
        subset=[col_mncs],
        vmin=0.5,
        vmax=1.5,
    )

    # PPtop10: midpoint = 10 → symmetric-ish 0..20
    styled = styled.background_gradient(
        cmap="RdBu",
        subset=[col_pp],
        vmin=0,
        vmax=20,
    )

    # ------------------------------
    # Export LaTeX table
    # ------------------------------
    latex = styled.to_latex(hrules=True, convert_css=True)

    latex_wrapped = (
        "\\begin{adjustbox}{max width=\\linewidth}%\n"
        + latex +
        "\\end{adjustbox}\n"
    )

    out = asset.inst_dir(inst)
    with open(out / "table.tex", "w") as f:
        f.write(latex_wrapped)
