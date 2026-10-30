import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from assets.collab_table_style import ROW_BACKGROUND_COLOR_EVEN, ROW_BACKGROUND_COLOR_ODD
from assets.table_asset_common import build_basic_table_tex, finalize_ranked_table_df
from core.asset import Asset
from utility import full_country_name, get_indicator_catalog_dict


COLUMN_COUNT = "C_CITING_COUNTRY"
COLUMN_SHARE = "PC_CITING_COUNTRY"
COLUMN_WORLD_SHARE = "PC_CITING_COUNTRY_WORLD"
COLUMN_RPC = "RPC_CITING_COUNTRY"
TOP_N = 20
EPS_SHARE = 1e-12

TABLE_COLUMNS = [
    "row_order",
    "country_name",
    "country_code",
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
    r"\InstShort{} publications in which the citing country is represented. "
    f"{WORLD_SYMBOL} is the share of global outgoing citation links to "
    "publications from the evaluation period in which the same country is "
    f"represented. {RPC_SYMBOL} is {OBSERVED_SYMBOL} divided by "
    f"{WORLD_SYMBOL}; values above 1 indicate above-benchmark citation "
    "uptake. Shares are non-exclusive because a citing publication can "
    "involve multiple countries."
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

        target_country AS (
            SELECT
                wci.country_id,
                SUM(tce.n_edges) AS target_links_full
            FROM target_citing_edges AS tce
            JOIN marts.work_country_info AS wci
                ON wci.work_id = tce.citing_work_id
            GROUP BY wci.country_id
        ),

        benchmark_country AS (
            SELECT
                wci.country_id,
                SUM(bce.n_edges) AS benchmark_links_full
            FROM benchmark_citing_edges AS bce
            JOIN marts.work_country_info AS wci
                ON wci.work_id = bce.citing_work_id
            GROUP BY wci.country_id
        ),

        totals AS (
            SELECT
                (SELECT SUM(n_edges) FROM target_citing_edges) AS total_target_links,
                (SELECT SUM(n_edges) FROM benchmark_citing_edges) AS total_benchmark_links
        )

        SELECT
            COALESCE(oac.display_name, dc.country_code) AS country_name,
            dc.country_code,
            oac.continent_name,
            COALESCE(tc.target_links_full, 0) AS {COLUMN_COUNT},
            COALESCE(bc.benchmark_links_full, 0) AS benchmark_links_full,
            totals.total_target_links,
            totals.total_benchmark_links
        FROM target_country AS tc
        FULL OUTER JOIN benchmark_country AS bc
            ON tc.country_id = bc.country_id
        JOIN core.dim_country AS dc
            ON dc.country_id = COALESCE(tc.country_id, bc.country_id)
        LEFT JOIN augmented.openalex_countries AS oac
            ON dc.country_code = oac.code
        CROSS JOIN totals
        ORDER BY {COLUMN_COUNT} DESC, country_name ASC;
    """


asset = Asset(script_file=__file__)


for inst, con in asset.iterate_institutions():
    raw_df = asset.extract(
        con=con,
        inst=inst,
        query=query_function(inst, asset.year_first, asset.year_last),
        out_name="data_raw.csv",
    )

    df = raw_df.copy()
    for column in [
        COLUMN_COUNT,
        "benchmark_links_full",
        "total_target_links",
        "total_benchmark_links",
    ]:
        df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0.0)

    df["country_name_full"] = df["country_name"].map(full_country_name)
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

    df = df[df[COLUMN_COUNT] > 0].copy()
    df = finalize_ranked_table_df(
        df,
        sort_by=[COLUMN_COUNT, "country_name"],
        ascending=[False, True],
        top_n=TOP_N,
        shorten_map={"country_name": "country"},
    )
    df["country_name_short"] = df["country_name"]
    df[COLUMN_COUNT] = df[COLUMN_COUNT].round(0).astype("Int64")

    table_df = df.copy()

    table_tex = build_basic_table_tex(
        table_df,
        columns=TABLE_COLUMNS,
        indicator_catalog_dict=indicator_catalog_dict,
        header_overrides={
            "row_order": "Rank",
            "country_name": "Country",
            "country_code": "CC",
        },
        text_columns={
            "country_name",
            "country_code",
        },
        alignments={
            "row_order": "r",
            "country_name": "l",
            "country_code": "c",
            COLUMN_COUNT: "r",
            COLUMN_SHARE: "r",
            COLUMN_WORLD_SHARE: "r",
            COLUMN_RPC: "r",
        },
        resize_mode="max_width",
        row_background_colors=(ROW_BACKGROUND_COLOR_ODD, ROW_BACKGROUND_COLOR_EVEN),
    )

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
    df.to_csv(out / "data.csv", index=False)
    df.to_csv(out / "data_prepost.csv", index=False)
