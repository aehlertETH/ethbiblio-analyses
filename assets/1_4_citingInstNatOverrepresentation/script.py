import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from assets.collab_table_style import ROW_BACKGROUND_COLOR_EVEN, ROW_BACKGROUND_COLOR_ODD
from assets.openalex_annotation_common import (
    ANNOTATION_PLACEHOLDER_MARKER,
    add_ranking_macro_exclusion_flags,
    add_table_note_below,
    annotation_for_institution_id,
    annotation_notes_for_df,
    apply_marked_table_row_styles,
)
from assets.table_asset_common import (
    build_basic_table_tex,
    finalize_ranked_table_df,
    tex_escape,
)
from core.asset import Asset, postprocess_excluded_institutions
from utility import full_institution_name, get_indicator_catalog_dict


COLUMN_COUNT = "C_CITING_INST_NAT_FULL"
COLUMN_SHARE = "PC_CITING_INST_NAT_FULL"
COLUMN_WORLD_SHARE = "PC_CITING_INST_WORLD"
COLUMN_RPC = "RPC_CITING_INST"
TOP_N = 20
EPS_SHARE = 1e-12
DISPLAY_EXCLUDED_ROW_TEXT_CELL_INDEXES = {0, 1, 2, 3, 4, 5}

TABLE_COLUMNS = [
    "row_order",
    "institution_name",
    COLUMN_COUNT,
    COLUMN_SHARE,
    COLUMN_WORLD_SHARE,
    COLUMN_RPC,
]

indicator_catalog_dict = get_indicator_catalog_dict()
OBSERVED_SYMBOL_TEX = str(
    indicator_catalog_dict.get(COLUMN_SHARE, {}).get("symbol_tex") or ""
).strip()
WORLD_SYMBOL_TEX = str(
    indicator_catalog_dict.get(COLUMN_WORLD_SHARE, {}).get("symbol_tex") or ""
).strip()
RPC_SYMBOL_TEX = str(
    indicator_catalog_dict.get(COLUMN_RPC, {}).get("symbol_tex") or ""
).strip()
OBSERVED_SYMBOL = (
    rf"\ensuremath{{{OBSERVED_SYMBOL_TEX}}}" if OBSERVED_SYMBOL_TEX else "Observed share"
)
WORLD_SYMBOL = (
    rf"\ensuremath{{{WORLD_SYMBOL_TEX}}}" if WORLD_SYMBOL_TEX else "World share"
)
RPC_SYMBOL = rf"\ensuremath{{{RPC_SYMBOL_TEX}}}" if RPC_SYMBOL_TEX else "RPC"

TABLE_NOTE_TEXT = (
    f"{OBSERVED_SYMBOL} is the share of incoming citation links to "
    r"\InstShort{} publications in which the Swiss citing institution is "
    f"represented. {WORLD_SYMBOL} is the share of global outgoing citation "
    "links to publications from the evaluation period in which the same "
    f"institution is represented. {RPC_SYMBOL} is {OBSERVED_SYMBOL} divided "
    f"by {WORLD_SYMBOL}; values above 1 indicate above-benchmark citation "
    "uptake. Shares use the same denominator as the overall "
    "citing-institution table and are non-exclusive because a citing "
    "publication can involve multiple institutions."
)


def query_function(inst: str, y0: int, y1: int) -> str:
    return f"""
        WITH target_pubs AS (
            SELECT DISTINCT rm.work_id
            FROM reports.report_membership AS rm
            JOIN core.work AS w
                ON w.work_id = rm.work_id
            WHERE rm.report_name = '{inst}'
                AND w.publication_year BETWEEN {y0} AND {y1}
        ),

        benchmark_pubs AS (
            SELECT DISTINCT w.work_id
            FROM core.work AS w
            WHERE w.publication_year BETWEEN {y0} AND {y1}
        ),

        target_citing_edges AS (
            SELECT
                r.citing_id AS citing_work_id,
                COUNT(DISTINCT r.cited_id) AS n_edges
            FROM core.refs AS r
            JOIN target_pubs AS tp
                ON tp.work_id = r.cited_id
            GROUP BY r.citing_id
        ),

        benchmark_citing_edges AS (
            SELECT
                r.citing_id AS citing_work_id,
                COUNT(DISTINCT r.cited_id) AS n_edges
            FROM core.refs AS r
            JOIN benchmark_pubs AS bp
                ON bp.work_id = r.cited_id
            GROUP BY r.citing_id
        ),

        target_institution AS (
            SELECT
                wii.institution_id,
                SUM(tce.n_edges) AS target_links_full
            FROM target_citing_edges AS tce
            JOIN marts.work_institution_info AS wii
                ON wii.work_id = tce.citing_work_id
            JOIN core.dim_institution AS di
                ON di.institution_id = wii.institution_id
            LEFT JOIN core.dim_country AS dc
                ON dc.country_id = di.country_id
            WHERE dc.country_code IS NOT NULL
            GROUP BY wii.institution_id
        ),

        benchmark_institution AS (
            SELECT
                wii.institution_id,
                SUM(bce.n_edges) AS benchmark_links_full
            FROM benchmark_citing_edges AS bce
            JOIN marts.work_institution_info AS wii
                ON wii.work_id = bce.citing_work_id
            JOIN core.dim_institution AS di
                ON di.institution_id = wii.institution_id
            LEFT JOIN core.dim_country AS dc
                ON dc.country_id = di.country_id
            WHERE dc.country_code IS NOT NULL
            GROUP BY wii.institution_id
        ),

        totals AS (
            SELECT
                (SELECT SUM(n_edges) FROM target_citing_edges) AS total_target_links,
                (SELECT SUM(n_edges) FROM benchmark_citing_edges) AS total_benchmark_links
        )

        SELECT
            di.institution_id,
            di.name AS institution_name,
            dc.country_code,
            COALESCE(ti.target_links_full, 0) AS {COLUMN_COUNT},
            COALESCE(bi.benchmark_links_full, 0) AS benchmark_links_full,
            totals.total_target_links,
            totals.total_benchmark_links
        FROM target_institution AS ti
        FULL OUTER JOIN benchmark_institution AS bi
            ON ti.institution_id = bi.institution_id
        JOIN core.dim_institution AS di
            ON di.institution_id = COALESCE(ti.institution_id, bi.institution_id)
        LEFT JOIN core.dim_country AS dc
            ON dc.country_id = di.country_id
        CROSS JOIN totals
        ORDER BY {COLUMN_COUNT} DESC,
            di.name ASC,
            di.institution_id ASC;
    """


asset = Asset(script_file=__file__)


for inst, con in asset.iterate_institutions():
    raw_df = asset.extract(
        con=con,
        inst=inst,
        query=query_function(inst, asset.year_first, asset.year_last),
        out_name="data_raw.csv",
    )

    df_base = raw_df.copy()
    for column in [
        COLUMN_COUNT,
        "benchmark_links_full",
        "total_target_links",
        "total_benchmark_links",
    ]:
        df_base[column] = pd.to_numeric(df_base[column], errors="coerce").fillna(0.0)

    df_base["institution_name_full"] = df_base["institution_name"].map(full_institution_name)

    raw_export_df = add_ranking_macro_exclusion_flags(df_base)
    raw_export_df = raw_export_df.drop(columns=["institution_id"], errors="ignore").copy()
    raw_export_df[COLUMN_SHARE] = 0.0
    raw_export_df[COLUMN_WORLD_SHARE] = 0.0
    target_denom = (
        float(raw_export_df["total_target_links"].iloc[0])
        if not raw_export_df.empty
        else 0.0
    )
    benchmark_denom = (
        float(raw_export_df["total_benchmark_links"].iloc[0])
        if not raw_export_df.empty
        else 0.0
    )
    if target_denom > 0:
        raw_export_df[COLUMN_SHARE] = raw_export_df[COLUMN_COUNT] / target_denom
    if benchmark_denom > 0:
        raw_export_df[COLUMN_WORLD_SHARE] = (
            raw_export_df["benchmark_links_full"] / benchmark_denom
        )
    raw_export_df[COLUMN_RPC] = (raw_export_df[COLUMN_SHARE] + EPS_SHARE) / (
        raw_export_df[COLUMN_WORLD_SHARE] + EPS_SHARE
    )
    raw_export_df = raw_export_df[
        (raw_export_df["country_code"] == "CH") & (raw_export_df[COLUMN_COUNT] > 0)
    ].copy()
    raw_export_df = raw_export_df.drop(columns=["country_code"], errors="ignore")
    df_prepost = finalize_ranked_table_df(
        raw_export_df,
        sort_by=[COLUMN_COUNT, "institution_name"],
        ascending=[False, True],
        top_n=TOP_N,
        shorten_map={"institution_name": "institution"},
    )
    df_prepost["institution_name_short"] = df_prepost["institution_name"]
    df_prepost[COLUMN_COUNT] = df_prepost[COLUMN_COUNT].round(0).astype("Int64")

    df = postprocess_excluded_institutions(df_base, institution_id_col="institution_id")
    df = add_ranking_macro_exclusion_flags(df)
    df[COLUMN_SHARE] = 0.0
    df[COLUMN_WORLD_SHARE] = 0.0
    target_denom = float(df["total_target_links"].iloc[0]) if not df.empty else 0.0
    benchmark_denom = (
        float(df["total_benchmark_links"].iloc[0]) if not df.empty else 0.0
    )
    if target_denom > 0:
        df[COLUMN_SHARE] = df[COLUMN_COUNT] / target_denom
    if benchmark_denom > 0:
        df[COLUMN_WORLD_SHARE] = df["benchmark_links_full"] / benchmark_denom
    df[COLUMN_RPC] = (df[COLUMN_SHARE] + EPS_SHARE) / (
        df[COLUMN_WORLD_SHARE] + EPS_SHARE
    )
    df = df[(df["country_code"] == "CH") & (df[COLUMN_COUNT] > 0)].copy()
    df = df.drop(columns=["country_code"], errors="ignore").copy()
    df = finalize_ranked_table_df(
        df,
        sort_by=[COLUMN_COUNT, "institution_name"],
        ascending=[False, True],
        top_n=TOP_N,
        shorten_map={"institution_name": "institution"},
    )
    df["institution_name_short"] = df["institution_name"]
    df[COLUMN_COUNT] = df[COLUMN_COUNT].round(0).astype("Int64")

    table_df = df.copy()
    table_notes = annotation_notes_for_df(table_df)
    table_df["institution_name"] = table_df.apply(
        lambda row: (
            tex_escape(row["institution_name"]) + ANNOTATION_PLACEHOLDER_MARKER
            if annotation_for_institution_id(row.get("institution_id"))
            else tex_escape(row["institution_name"])
        ),
        axis=1,
    )

    table_tex = build_basic_table_tex(
        table_df,
        columns=TABLE_COLUMNS,
        indicator_catalog_dict=indicator_catalog_dict,
        header_overrides={
            "row_order": "Rank",
            "institution_name": "Institution",
        },
        text_columns={"institution_name"},
        alignments={
            "row_order": "r",
            "institution_name": "l",
            COLUMN_COUNT: "r",
            COLUMN_SHARE: "r",
            COLUMN_WORLD_SHARE: "r",
            COLUMN_RPC: "r",
        },
        resize_mode="max_width",
        row_background_colors=(ROW_BACKGROUND_COLOR_ODD, ROW_BACKGROUND_COLOR_EVEN),
        raw_latex_columns={"institution_name"},
    )
    table_tex = apply_marked_table_row_styles(
        table_tex,
        table_df,
        text_cell_indexes=DISPLAY_EXCLUDED_ROW_TEXT_CELL_INDEXES,
    )
    table_tex = add_table_note_below(table_tex, table_notes)
    table_tex = (
        table_tex
        + r"\vspace{0.4em}" + "\n"
        + r"\begin{minipage}{\linewidth}" + "\n"
        + r"  \tiny" + "\n"
        #+ rf"  \textit{{Note:}} {TABLE_NOTE_TEXT}" + "\n"
        + r"\end{minipage}" + "\n"
    )

    out = asset.inst_dir(inst)
    (out / "table.tex").write_text(table_tex, encoding="utf-8")
    df_prepost.to_csv(out / "data_prepost.csv", index=False)
    df.drop(columns=["institution_id"], errors="ignore").to_csv(out / "data.csv", index=False)
