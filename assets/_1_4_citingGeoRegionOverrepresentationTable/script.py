import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from assets.collab_table_style import ROW_BACKGROUND_COLOR_EVEN, ROW_BACKGROUND_COLOR_ODD
from assets.table_asset_common import build_basic_table_tex, tex_escape
from core.asset import Asset
from utility import shorten_institution_name


SOURCE_ASSET_DIRNAME = "1_4_citingGeoInstitutionContourOverlayZoomCounts"
SOURCE_SUBSET_FILE = "data_interpretation_region_subset.csv"
TOP_N = 12
ANCHOR_DISPLAY_COUNT = 10

OUT_COL_CLUSTER = "region_label"
OUT_COL_COUNTRIES = "dominant_countries"
OUT_COL_SURFACE_TARGET = "surface_target_share_pct"
OUT_COL_SURFACE_BENCH = "surface_benchmark_share_pct"
OUT_COL_SURFACE_DELTA = "surface_delta_pp"
OUT_COL_WEIGHTED_LIFT = "surface_weighted_lift_ratio"
OUT_COL_PEAK_LIFT = "surface_peak_lift_ratio"
OUT_COL_ANCHOR_N = "anchor_institutions_n"
OUT_COL_ANCHOR_LIST = "anchor_institutions"

TABLE_COLUMNS = [
    OUT_COL_CLUSTER,
    OUT_COL_COUNTRIES,
    OUT_COL_SURFACE_TARGET,
    OUT_COL_SURFACE_BENCH,
    OUT_COL_SURFACE_DELTA,
    OUT_COL_WEIGHTED_LIFT,
    OUT_COL_PEAK_LIFT,
    OUT_COL_ANCHOR_N,
    OUT_COL_ANCHOR_LIST,
]

TABLE_NOTE_TEXT = (
    "Clusters are derived from connected components of contour-grid cells with lift >=1.25x "
    "(log2 lift >=0.322), after excluding low-mass cells where target+benchmark surface mass is "
    "<=0.05\\% of the global maximum. Components use 8-neighbor connectivity and a minimum size of "
    "10 cells (one cell approx. 77km x 77km). Shown are clusters with observed surface share >=0.50\\%. Anchor institutions are "
    "the geocoded institutions in the top-200 by absolute incoming citation volume (excluding the "
    "focal institution), assigned to a cluster by grid-cell overlap (or nearest cluster cell "
    "within radius 2). Dominant countries are shown by anchor citation volume (top 3), while "
    f"displayed anchor institutions (top {ANCHOR_DISPLAY_COUNT}) are selected by lowest combined rank of anchor "
    "citation volume and overrepresentation (lift ratio). Clusters are ordered by "
    "observed surface share (ties by peak lift, then anchor citation volume) and only the top 12 "
    "clusters are shown."
)


def shorten_geo_label(value: object) -> str:
    text = "" if value is None else str(value)
    replacements = {
        "United States of America": "USA",
        "Russian Federation": "Russia",
        "Korea, Republic of": "South Korea",
        "United Kingdom of Great Britain and Northern Ireland": "United Kingdom",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def format_pct(value: object) -> str:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(numeric):
        return "n/a"
    return f"{float(numeric):.3f}%"


def format_pp(value: object) -> str:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(numeric):
        return "n/a"
    return f"{float(numeric):.3f} pp"


def format_ratio(value: object) -> str:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(numeric):
        return "n/a"
    return f"{float(numeric):.2f}x"


def format_anchor_institutions(value: object) -> str:
    raw = "" if value is None else str(value)
    parts = [p.strip() for p in raw.split(";") if p.strip()]
    if not parts:
        return ""
    shortened = [shorten_institution_name(part) for part in parts]
    escaped = [tex_escape(part) for part in shortened]
    return r"\shortstack[l]{" + r" \\ ".join(escaped) + "}"


def format_geo_stack(value: object) -> str:
    raw = "" if value is None else str(value)
    parts = [p.strip() for p in raw.split(";") if p.strip()]
    if not parts:
        return ""
    escaped = [tex_escape(part) for part in parts]
    return r"\shortstack[l]{" + r" \\ ".join(escaped) + "}"


asset = Asset(script_file=__file__)
source_asset_dir = asset.base_dir.parent / SOURCE_ASSET_DIRNAME

for inst in asset.institutions:
    source_path = source_asset_dir / inst / SOURCE_SUBSET_FILE
    if not source_path.is_file():
        raise FileNotFoundError(f"Missing source file for {inst}: {source_path}")

    df = pd.read_csv(source_path, keep_default_na=False, na_values=[""])
    df = df.head(TOP_N).copy()

    for col in [
        "region_rank",
        OUT_COL_SURFACE_TARGET,
        OUT_COL_SURFACE_BENCH,
        OUT_COL_SURFACE_DELTA,
        OUT_COL_WEIGHTED_LIFT,
        OUT_COL_PEAK_LIFT,
        OUT_COL_ANCHOR_N,
    ]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df[OUT_COL_CLUSTER] = df[OUT_COL_CLUSTER].map(shorten_geo_label)
    df[OUT_COL_COUNTRIES] = df[OUT_COL_COUNTRIES].map(shorten_geo_label)

    export_df = df[
        [
            "region_rank",
            OUT_COL_CLUSTER,
            OUT_COL_COUNTRIES,
            OUT_COL_SURFACE_TARGET,
            OUT_COL_SURFACE_BENCH,
            OUT_COL_SURFACE_DELTA,
            OUT_COL_WEIGHTED_LIFT,
            OUT_COL_PEAK_LIFT,
            OUT_COL_ANCHOR_N,
            "anchor_institutions",
            "anchor_target_share_pct",
            "anchor_benchmark_share_pct",
        ]
    ].copy()

    table_df = export_df[TABLE_COLUMNS].copy()
    table_df[OUT_COL_SURFACE_TARGET] = table_df[OUT_COL_SURFACE_TARGET].map(format_pct)
    table_df[OUT_COL_SURFACE_BENCH] = table_df[OUT_COL_SURFACE_BENCH].map(format_pct)
    table_df[OUT_COL_SURFACE_DELTA] = table_df[OUT_COL_SURFACE_DELTA].map(format_pp)
    table_df[OUT_COL_WEIGHTED_LIFT] = table_df[OUT_COL_WEIGHTED_LIFT].map(format_ratio)
    table_df[OUT_COL_PEAK_LIFT] = table_df[OUT_COL_PEAK_LIFT].map(format_ratio)
    table_df[OUT_COL_CLUSTER] = table_df[OUT_COL_CLUSTER].map(format_geo_stack)
    table_df[OUT_COL_COUNTRIES] = table_df[OUT_COL_COUNTRIES].map(format_geo_stack)
    table_df[OUT_COL_ANCHOR_LIST] = table_df[OUT_COL_ANCHOR_LIST].map(
        format_anchor_institutions
    )

    table_tex = build_basic_table_tex(
        table_df,
        columns=TABLE_COLUMNS,
        header_overrides={
            OUT_COL_CLUSTER: "Cluster region",
            OUT_COL_COUNTRIES: r"\shortstack[c]{Dominant\\countries}",
            OUT_COL_SURFACE_TARGET: r"\shortstack[c]{Observed\\share}",
            OUT_COL_SURFACE_BENCH: r"\shortstack[c]{Expected\\share}",
            OUT_COL_SURFACE_DELTA: r"\shortstack[c]{Delta\\(pp)}",
            OUT_COL_WEIGHTED_LIFT: r"\shortstack[c]{Weighted\\lift}",
            OUT_COL_PEAK_LIFT: r"\shortstack[c]{Peak\\lift}",
            OUT_COL_ANCHOR_N: r"\shortstack[c]{Anchor\\inst. n}",
            OUT_COL_ANCHOR_LIST: rf"\shortstack[c]{{Anchor institutions\\(top {ANCHOR_DISPLAY_COUNT})}}",
        },
        text_columns={
            OUT_COL_SURFACE_TARGET,
            OUT_COL_SURFACE_BENCH,
            OUT_COL_SURFACE_DELTA,
            OUT_COL_WEIGHTED_LIFT,
            OUT_COL_PEAK_LIFT,
        },
        raw_latex_columns={OUT_COL_CLUSTER, OUT_COL_COUNTRIES, OUT_COL_ANCHOR_LIST},
        alignments={
            OUT_COL_CLUSTER: "l",
            OUT_COL_COUNTRIES: "l",
            OUT_COL_SURFACE_TARGET: "r",
            OUT_COL_SURFACE_BENCH: "r",
            OUT_COL_SURFACE_DELTA: "r",
            OUT_COL_WEIGHTED_LIFT: "r",
            OUT_COL_PEAK_LIFT: "r",
            OUT_COL_ANCHOR_N: "r",
            OUT_COL_ANCHOR_LIST: "l",
        },
        resize_mode="max_width",
        row_background_colors=(ROW_BACKGROUND_COLOR_ODD, ROW_BACKGROUND_COLOR_EVEN),
    )

    table_tex = (
        table_tex
        + r"\vspace{0.4em}"
        + "\n"
        + r"\begin{minipage}{\linewidth}"
        + "\n"
        + r"  \tiny"
        + "\n"
        + rf"  \textit{{Note:}} {TABLE_NOTE_TEXT}"
        + "\n"
        + r"\end{minipage}"
        + "\n"
    )

    export_df["region_rank"] = export_df["region_rank"].round(0).astype("Int64")
    export_df[OUT_COL_ANCHOR_N] = export_df[OUT_COL_ANCHOR_N].round(0).astype("Int64")

    out = asset.inst_dir(inst)
    (out / "table.tex").write_text(table_tex, encoding="utf-8")
    export_df.to_csv(out / "data.csv", index=False)
    export_df.to_csv(out / "data_prepost.csv", index=False)
