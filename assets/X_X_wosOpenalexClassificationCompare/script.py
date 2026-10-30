"""
WoS vs OpenAlex classification comparison.

For each institution with WoS exports, this asset:
1. Merges and deduplicates all savedrecs .txt files
2. Joins to DWH publications via DOI (using coverage xlsx as bridge)
3. Attaches OpenAlex subfield/field/domain from DuckDB
4. Writes full matched CSVs, tables and a comparison figure
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    PLOTLY_AVAILABLE = True
except ModuleNotFoundError:
    go = None
    make_subplots = None
    PLOTLY_AVAILABLE = False

from core.asset import Asset, REPO_ROOT
from wos_io import load_wos_folder, load_coverage_bridge
if PLOTLY_AVAILABLE:
    from core.plot_style import apply_style

INSTITUTIONS = ["empa", "epfl", "psi", "wsl", "ethz", "eawag"]
ETHDOMAIN_INST = "ethdomain"
WOS_DIR = REPO_ROOT / "data" / "wos_exports"
COVERAGE_DIR = REPO_ROOT / "coverage"
N_TABLE_ROWS = 20
N_TABLE_EXAMPLE_ROWS = 15
OUTPUT_COLS = [
    "member_institution", "work_id", "doi_norm", "ut", "title", "source",
    "wos_year", "publication_year", "document_type",
    "wos_categories", "wos_category_primary",
    "subfield_name", "field_name", "domain_name",
    "type_is_proceedings",
]

asset = Asset(script_file=__file__, institutions=INSTITUTIONS)

DWH_QUERY = """
SELECT r.work_id, w.publication_year, w.subfield,
       tt.subfield_name, tt.field_name, tt.domain_name,
       w.type_is_proceedings
FROM reports.report_membership r
JOIN core.work w ON w.work_id = r.work_id
LEFT JOIN core.topics_tree tt ON tt.subfield = w.subfield
WHERE r.report_name = '{inst}' AND r.work_id IS NOT NULL
"""

summary_rows = []


def latex_escape(value) -> str:
    text = "" if pd.isna(value) else str(value)
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    for raw, escaped in replacements.items():
        text = text.replace(raw, escaped)
    return text


def truncate_for_table(value, max_len: int = 68) -> str:
    text = "" if pd.isna(value) else str(value).strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 3].rstrip() + "..."


def write_table_outputs(crosstab: pd.DataFrame, out_dir: Path, inst: str, n_matched: int) -> None:
    inst_label = "ETH Domain" if inst == ETHDOMAIN_INST else inst.upper()
    matched_label = f"{n_matched:,}"

    body_lines = [
        r"\small",
        r"\begin{tabularx}{\linewidth}{@{}>{\raggedright\arraybackslash}X>{\raggedright\arraybackslash}Xr@{}}",
        r"\toprule",
        r"\textbf{WoS Primary Category} & \textbf{OpenAlex Subfield} & \textbf{N} \\",
        r"\midrule",
    ]
    for _, row in crosstab.head(N_TABLE_ROWS).iterrows():
        body_lines.append(
            f"{latex_escape(row['wos_category_primary'])} & "
            f"{latex_escape(row['subfield_name'])} & "
            f"{int(row['count']):,} \\\\"
        )
    body_lines.extend([r"\bottomrule", r"\end{tabularx}"])

    (out_dir / "table.tex").write_text("\n".join(body_lines) + "\n", encoding="utf-8")

    standalone_lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        rf"\caption{{Top {N_TABLE_ROWS} WoS category $\times$ OpenAlex subfield mappings ({inst_label}, $n={matched_label}$ matched publications)}}",
        rf"\label{{tab:wos-oa-{inst}}}",
        *body_lines,
        r"\end{table}",
    ]
    (out_dir / "table_no_examples.tex").write_text("\n".join(standalone_lines) + "\n", encoding="utf-8")

    example_lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        rf"\caption{{Top {N_TABLE_EXAMPLE_ROWS} WoS category $\times$ OpenAlex subfield mappings with example titles ({inst_label}, $n={matched_label}$ matched publications)}}",
        rf"\label{{tab:wos-oa-{inst}-examples}}",
        r"\scriptsize",
        r"\renewcommand{\arraystretch}{1.2}",
        r"\begin{tabularx}{\textwidth}{@{}p{2.8cm}p{2.8cm}rX@{}}",
        r"\toprule",
        r"\textbf{WoS Category} & \textbf{OpenAlex Subfield} & \textbf{N} & \textbf{Example Titles} \\",
        r"\midrule",
    ]
    for _, row in crosstab.head(N_TABLE_EXAMPLE_ROWS).iterrows():
        examples = []
        for title in str(row["example_titles"]).split(" | "):
            title = title.strip()
            if title:
                examples.append(r"\textbullet~" + latex_escape(truncate_for_table(title)))
        example_lines.append(
            f"{latex_escape(row['wos_category_primary'])} & "
            f"{latex_escape(row['subfield_name'])} & "
            f"{int(row['count']):,} & "
            f"{'  '.join(examples)} \\\\"
        )
    example_lines.extend([r"\bottomrule", r"\end{tabularx}", r"\end{table}"])
    (out_dir / "table_with_examples.tex").write_text("\n".join(example_lines) + "\n", encoding="utf-8")

matched_frames = []

for inst, con in asset.iterate_institutions():
    wos_folder = WOS_DIR / inst
    coverage_file = COVERAGE_DIR / f"{inst}.xlsx"
    out_dir = asset.inst_dir(inst)

    if not wos_folder.exists() or not list(wos_folder.glob("*.txt")):
        print(f"{inst}: no WoS exports found, skipping")
        continue
    if not coverage_file.exists():
        print(f"{inst}: no coverage file found, skipping")
        continue

    print(f"\n{'='*60}\n  {inst.upper()}\n{'='*60}")

    # 1. Load and deduplicate WoS
    wos = load_wos_folder(wos_folder)
    n_wos_total = len(wos)
    n_with_doi = wos["doi_norm"].notna().sum()
    print(f"  WoS records: {n_wos_total} (deduped), {n_with_doi} with DOI")

    # 2. Load coverage bridge
    bridge = load_coverage_bridge(coverage_file)
    print(f"  Coverage bridge: {len(bridge)} DOI→work_id mappings")

    # 3. Query DWH for subfields
    sql = DWH_QUERY.format(inst=inst)
    dwh = con.query(sql).df()
    print(f"  DWH works: {len(dwh)}")

    # 4. Join: WoS → bridge → DWH
    wos_doi = wos[wos["doi_norm"].notna()].copy()
    matched = wos_doi.merge(bridge, on="doi_norm", how="inner")
    matched = matched.merge(dwh, on="work_id", how="inner")
    matched = matched.drop_duplicates(subset="work_id", keep="first")
    n_matched = len(matched)
    print(f"  Matched: {n_matched}")

    # Derive primary WoS category (first in semicolon-delimited list)
    matched["wos_category_primary"] = (
        matched["wos_categories"]
        .fillna("")
        .str.split(";")
        .str[0]
        .str.strip()
    )

    matched["member_institution"] = inst
    matched_frames.append(matched.copy())

    # 5. Select output columns
    existing_cols = [c for c in OUTPUT_COLS if c in matched.columns]

    # 6. Write CSVs
    matched[existing_cols].to_csv(out_dir / "data.csv", index=False)
    matched[existing_cols].to_csv(out_dir / "matched_all.csv", index=False)

    match_rate = n_matched / n_with_doi if n_with_doi > 0 else 0
    summary = pd.DataFrame([{
        "institution": inst,
        "wos_total_deduped": n_wos_total,
        "wos_with_doi": int(n_with_doi),
        "matched": n_matched,
        "match_rate": round(match_rate, 4),
        "doi_available_rate": round(n_with_doi / n_wos_total, 4) if n_wos_total > 0 else 0,
    }])
    summary.to_csv(out_dir / "match_summary.csv", index=False)

    crosstab = (
        matched.groupby(["wos_category_primary", "subfield_name"])
        .agg(
            count=("work_id", "size"),
            example_titles=("title", lambda t: " | ".join(t.dropna().head(3))),
        )
        .reset_index()
        .sort_values("count", ascending=False)
    )
    crosstab.to_csv(out_dir / "match_crosstab.csv", index=False)
    write_table_outputs(crosstab, out_dir, inst, n_matched)

    if PLOTLY_AVAILABLE:
        # 7. Figure: top-15 WoS categories vs top-15 OpenAlex subfields
        top_wos = (
            matched["wos_category_primary"]
            .value_counts()
            .head(15)
            .iloc[::-1]
        )
        top_oa = (
            matched["subfield_name"]
            .value_counts()
            .head(15)
            .iloc[::-1]
        )

        fig = make_subplots(
            rows=1, cols=2,
            subplot_titles=("WoS Primary Category (top 15)", "OpenAlex Subfield (top 15)"),
            horizontal_spacing=0.35,
        )
        fig.add_trace(
            go.Bar(x=top_wos.values, y=top_wos.index, orientation="h", marker_color="#1f77b4"),
            row=1, col=1,
        )
        fig.add_trace(
            go.Bar(x=top_oa.values, y=top_oa.index, orientation="h", marker_color="#ff7f0e"),
            row=1, col=2,
        )
        fig.update_layout(
            showlegend=False,
            height=500,
            width=1200,
            title_text=f"{inst.upper()} — WoS vs OpenAlex classification (n={n_matched})",
        )
        apply_style(fig)

        fig.write_image(str(out_dir / "figure.png"), scale=2)
        fig.write_image(str(out_dir / "figure.pdf"))
        fig.write_image(str(out_dir / "figure.svg"))
    else:
        print("  Plotly not available; skipped figure regeneration")

    summary_rows.append({
        "inst": inst,
        "wos_deduped": n_wos_total,
        "wos_with_doi": int(n_with_doi),
        "matched": n_matched,
        "doi_rate": n_with_doi / n_wos_total if n_wos_total > 0 else 0,
        "match_rate": match_rate,
    })

# Final console report
print(f"\n\n{'='*60}")
print("  SUMMARY")
print(f"{'='*60}")
print(f"{'inst':<10} {'wos_deduped':>12} {'with_doi':>8} {'matched':>8} {'doi_rate':>9} {'match_rate':>10}")
print("-" * 60)
for row in summary_rows:
    print(
        f"{row['inst']:<10} {row['wos_deduped']:>12} {row['wos_with_doi']:>8} "
        f"{row['matched']:>8} {row['doi_rate']:>8.1%} {row['match_rate']:>9.1%}"
    )
print()

if matched_frames:
    out_dir = asset.inst_dir(ETHDOMAIN_INST)
    ethdomain = (
        pd.concat(matched_frames, ignore_index=True)
        .sort_values(["work_id", "member_institution"])
        .drop_duplicates(subset="work_id", keep="first")
        .copy()
    )
    n_matched = len(ethdomain)
    existing_cols = [c for c in OUTPUT_COLS if c in ethdomain.columns]
    ethdomain[existing_cols].to_csv(out_dir / "data.csv", index=False)
    ethdomain[existing_cols].to_csv(out_dir / "matched_all.csv", index=False)

    member_summaries = []
    for inst in INSTITUTIONS:
        summary_file = asset.inst_dir(inst) / "match_summary.csv"
        if summary_file.exists():
            member_summaries.append(pd.read_csv(summary_file))
    if member_summaries:
        member_summary = pd.concat(member_summaries, ignore_index=True)
        n_wos_total = int(member_summary["wos_total_deduped"].sum())
        n_with_doi = int(member_summary["wos_with_doi"].sum())
    else:
        n_wos_total = 0
        n_with_doi = 0

    match_rate = n_matched / n_with_doi if n_with_doi > 0 else 0
    summary = pd.DataFrame([{
        "institution": ETHDOMAIN_INST,
        "wos_total_deduped": n_wos_total,
        "wos_with_doi": n_with_doi,
        "matched": n_matched,
        "match_rate": round(match_rate, 4),
        "doi_available_rate": round(n_with_doi / n_wos_total, 4) if n_wos_total > 0 else 0,
    }])
    summary.to_csv(out_dir / "match_summary.csv", index=False)

    crosstab = (
        ethdomain.groupby(["wos_category_primary", "subfield_name"])
        .agg(
            count=("work_id", "size"),
            example_titles=("title", lambda t: " | ".join(t.dropna().head(3))),
        )
        .reset_index()
        .sort_values("count", ascending=False)
    )
    crosstab.to_csv(out_dir / "match_crosstab.csv", index=False)
    write_table_outputs(crosstab, out_dir, ETHDOMAIN_INST, n_matched)

    if PLOTLY_AVAILABLE:
        top_wos = (
            ethdomain["wos_category_primary"]
            .value_counts()
            .head(15)
            .iloc[::-1]
        )
        top_oa = (
            ethdomain["subfield_name"]
            .value_counts()
            .head(15)
            .iloc[::-1]
        )

        fig = make_subplots(
            rows=1, cols=2,
            subplot_titles=("WoS Primary Category (top 15)", "OpenAlex Subfield (top 15)"),
            horizontal_spacing=0.35,
        )
        fig.add_trace(
            go.Bar(x=top_wos.values, y=top_wos.index, orientation="h", marker_color="#1f77b4"),
            row=1, col=1,
        )
        fig.add_trace(
            go.Bar(x=top_oa.values, y=top_oa.index, orientation="h", marker_color="#ff7f0e"),
            row=1, col=2,
        )
        fig.update_layout(
            showlegend=False,
            height=500,
            width=1200,
            title_text=f"ETH Domain — WoS vs OpenAlex classification (n={n_matched})",
        )
        apply_style(fig)

        fig.write_image(str(out_dir / "figure.png"), scale=2)
        fig.write_image(str(out_dir / "figure.pdf"))
        fig.write_image(str(out_dir / "figure.svg"))
    else:
        print(f"{ETHDOMAIN_INST}: Plotly not available; skipped figure regeneration")
