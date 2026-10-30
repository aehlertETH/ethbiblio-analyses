import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from assets.collab_table_style import ROW_BACKGROUND_COLOR_EVEN, ROW_BACKGROUND_COLOR_ODD
from assets.table_asset_common import build_basic_table_tex
from core.asset import Asset, postprocess_excluded_institutions
from utility import (
    full_country_name,
    get_indicator_catalog_dict,
    shorten_country_name,
    shorten_institution_name,
)


SOURCE_ASSET_DIRNAME = "1_4_citingInstOverrepresentation"
SOURCE_FILE = "data_raw.csv"
TOP_N = 20
TOP_VOLUME_POOL = 200
EPS_SHARE = 1e-12

OUT_COL_RANK = "citation_rank_by_volume"
OUT_COL_COUNT = "C_CITING_INST_FULL"
OUT_COL_INCOMING = "PC_CITING_INST_FULL"
OUT_COL_EXPECTED = "PC_CITING_INST_WORLD"
OUT_COL_OVERREP = "RPC_CITING_INST"

TABLE_COLUMNS = [
    "row_order",
    "institution_name",
    "country_code",
    OUT_COL_RANK,
    OUT_COL_COUNT,
    OUT_COL_INCOMING,
    OUT_COL_EXPECTED,
    OUT_COL_OVERREP,
]

TABLE_NOTE_TEXT = ""


def build_table_with_note(
    table_df: pd.DataFrame,
    indicator_catalog_dict: dict[str, dict],
) -> str:
    table_tex = build_basic_table_tex(
        table_df,
        columns=TABLE_COLUMNS,
        indicator_catalog_dict=indicator_catalog_dict,
        header_overrides={
            "row_order": "Rank",
            "institution_name": "Institution",
            "country_code": "CC",
            OUT_COL_RANK: r"\shortstack[c]{Citation Rank\\(abs.)}",
        },
        text_columns={
            "institution_name",
            "country_code",
        },
        alignments={
            "row_order": "r",
            "institution_name": "l",
            "country_code": "c",
            OUT_COL_RANK: "r",
            OUT_COL_COUNT: "r",
            OUT_COL_INCOMING: "r",
            OUT_COL_EXPECTED: "r",
            OUT_COL_OVERREP: "r",
        },
        resize_mode="max_width",
        row_background_colors=(ROW_BACKGROUND_COLOR_ODD, ROW_BACKGROUND_COLOR_EVEN),
    )

    note_text = TABLE_NOTE_TEXT.strip()
    if not note_text:
        return table_tex

    return (
        table_tex
        + r"\vspace{0.4em}" + "\n"
        + r"\begin{minipage}{\linewidth}" + "\n"
        + r"  \tiny" + "\n"
        + rf"  \textit{{Note:}} {note_text}" + "\n"
        + r"\end{minipage}" + "\n"
    )


asset = Asset(script_file=__file__)
indicator_catalog_dict = get_indicator_catalog_dict()
source_asset_dir = asset.base_dir.parent / SOURCE_ASSET_DIRNAME


for inst in asset.institutions:
    source_path = source_asset_dir / inst / SOURCE_FILE
    if not source_path.is_file():
        raise FileNotFoundError(f"Missing source file for {inst}: {source_path}")

    df = pd.read_csv(source_path, keep_default_na=False, na_values=[""])
    df = postprocess_excluded_institutions(df, institution_id_col="institution_id")

    for column in [
        OUT_COL_COUNT,
        "benchmark_links_full",
        "total_target_links",
        "total_benchmark_links",
    ]:
        df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0.0)

    df = df[df[OUT_COL_COUNT] > 0].copy()
    df["institution_name_full"] = df["institution_name"]
    df["country_name_full"] = df["country_name"].map(full_country_name)
    df["country_name_short"] = df["country_name"].map(shorten_country_name)

    target_denom = float(df["total_target_links"].iloc[0]) if not df.empty else 0.0
    benchmark_denom = (
        float(df["total_benchmark_links"].iloc[0]) if not df.empty else 0.0
    )
    df[OUT_COL_INCOMING] = 0.0
    df[OUT_COL_EXPECTED] = 0.0
    if target_denom > 0:
        df[OUT_COL_INCOMING] = df[OUT_COL_COUNT] / target_denom
    if benchmark_denom > 0:
        df[OUT_COL_EXPECTED] = df["benchmark_links_full"] / benchmark_denom
    df[OUT_COL_OVERREP] = (df[OUT_COL_INCOMING] + EPS_SHARE) / (
        df[OUT_COL_EXPECTED] + EPS_SHARE
    )

    df = df.sort_values(
        [OUT_COL_COUNT, "institution_name", "institution_id"],
        ascending=[False, True, True],
        kind="mergesort",
    ).reset_index(drop=True)
    df[OUT_COL_RANK] = df.index + 1

    df = df.head(TOP_VOLUME_POOL).copy()
    df = df.sort_values(
        [OUT_COL_OVERREP, OUT_COL_COUNT, "institution_name", "institution_id"],
        ascending=[False, False, True, True],
        kind="mergesort",
    ).head(TOP_N).reset_index(drop=True)
    df["row_order"] = df.index + 1

    df["institution_name"] = df["institution_name"].map(shorten_institution_name)
    df["institution_name_short"] = df["institution_name"]
    df[OUT_COL_COUNT] = df[OUT_COL_COUNT].round(0).astype("Int64")
    df["benchmark_links_full"] = df["benchmark_links_full"].round(0).astype("Int64")
    df[OUT_COL_RANK] = df[OUT_COL_RANK].astype("Int64")

    table_df = df[TABLE_COLUMNS].copy()
    table_tex = build_table_with_note(table_df, indicator_catalog_dict)

    out = asset.inst_dir(inst)
    (out / "table.tex").write_text(table_tex, encoding="utf-8")
    df.to_csv(out / "data.csv", index=False)
    df.to_csv(out / "data_prepost.csv", index=False)
