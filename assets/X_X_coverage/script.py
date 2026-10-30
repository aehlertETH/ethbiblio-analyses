import plotly.graph_objects as go
import pandas as pd

from core.asset import Asset
from core.plot_style import apply_style
from utility import get_unit_params_dict, get_indicator_catalog_dict

RELOAD_FROM_CSV = False  # Set True to regenerate figures from existing raw.csv without DuckDB


# ---------------------------------------------------------------------------
# Metadata: funnel steps and scope inclusion criteria
# ---------------------------------------------------------------------------

FUNNEL_STEPS = [
    #  key                          display_name                              description
    ("COV_WORKS_SUBMITTED_TOTAL", "Submitted (all years)",                 "Total lines submitted by the institution"),
    ("COV_WORKS_IN_RANGE",        "In evaluation period ({y0}-{y1})",      "Works with a publication year within {y0}-{y1} (out-of-window works excluded)"),
    ("COV_WORKS_FOUND_OPENALEX",  "Found in OpenAlex",                     "Works matched to an OpenAlex record"),
    ("COV_WORKS_UNIQUE",          "Unique works",                          "Unique works (after removing duplicates)"),
    ("COV_WORKS_IN_SCOPE",        "In scope",                              "Works passing all inclusion criteria"),
]

SCOPE_CRITERIA = [
    #  column_name                short_label           description
    ("is_english",             "In English",         "Published in English"),
    ("has_authorship",         "Has authorship",     "At least one author affiliation identified"),
    ("has_subfield",           "Has subfield",       "Assigned to at least one research subfield"),
    ("has_referenced_works",   "Has references",     "Contains at least one cited reference"),
    ("is_core_or_proceedings", "Core / proceedings", "Published in a core journal or conference proceedings"),
    ("is_not_retracted",       "Not retracted",      "Work has not been retracted"),
    ("is_not_paratext",        "Not paratext",       "Not classified as paratext (e.g. front matter, index)"),
]


# ---------------------------------------------------------------------------
# SQL query
# ---------------------------------------------------------------------------

def q_coverage(inst: str, y0: int, y1: int) -> str:
    """
    Return all coverage and scope metrics for *inst* in a single wide row.

    Pipeline
    --------
    submitted_total - every line the institution sent us (all years)
    in_range        - submitted works with a matched publication_year within
                      y0-y1 (plus unmatched whose year is unknown). Works
                      matched in OpenAlex but published outside the window are
                      excluded here so they do not inflate the denominator.
                      Institutions typically submit one extra year on each side
                      of the evaluation period, so this step is expected to drop
                      a meaningful fraction.
    found           - in-range lines where we matched a work_id_duplicated in OA
    unique          - found works after de-duplication (work_id = work_id_duplicated)
    in_scope        - unique works where is_included = TRUE (all 7 criteria met)

    Scope criteria (is_english, has_authorship, ...) are counted among
    *unique* found works already restricted to y0-y1.
    """
    return f"""
        WITH all_rows AS (
            SELECT
                r.work_id,
                r.work_id_duplicated,
                s.publication_year,
                s.is_included,
                s.is_english,
                s.has_authorship,
                s.has_subfield,
                s.has_referenced_works,
                s.is_core_or_proceedings,
                s.is_not_retracted,
                s.is_not_paratext
            FROM reports.report_membership r
            LEFT JOIN core.work w
              ON w.work_id = r.work_id
            LEFT JOIN core.work_to_status s
              ON s.work_id = r.work_id
            WHERE r.report_name = '{inst}'
        ),

        -- Keep works matched within the evaluation window, plus unmatched
        -- submissions whose year is unknown (publication_year IS NULL).
        base AS (
            SELECT * FROM all_rows
            WHERE (publication_year BETWEEN {y0} AND {y1}
                   OR publication_year IS NULL)
        ),

        unique_found AS (
            SELECT * FROM base
            WHERE work_id = work_id_duplicated
        )

        SELECT
            -- funnel counts
            (SELECT COUNT(*)                   FROM all_rows)       AS n_submitted_total,
            (SELECT COUNT(*)                   FROM base)           AS n_in_range,
            (SELECT COUNT(work_id_duplicated)  FROM base)           AS n_found,
            (SELECT COUNT(*)                   FROM unique_found)   AS n_unique,
            (SELECT SUM(is_included)           FROM unique_found)   AS n_in_scope,

            -- scope criteria (among unique found works within y0-y1)
            (SELECT SUM(is_english)             FROM unique_found) AS n_is_english,
            (SELECT SUM(has_authorship)         FROM unique_found) AS n_has_authorship,
            (SELECT SUM(has_subfield)           FROM unique_found) AS n_has_subfield,
            (SELECT SUM(has_referenced_works)   FROM unique_found) AS n_has_referenced_works,
            (SELECT SUM(is_core_or_proceedings) FROM unique_found) AS n_is_core_or_proceedings,
            (SELECT SUM(is_not_retracted)       FROM unique_found) AS n_is_not_retracted,
            (SELECT SUM(is_not_paratext)        FROM unique_found) AS n_is_not_paratext;
    """


# ---------------------------------------------------------------------------
# Build outputs (steps 2-5) from a single raw row
# ---------------------------------------------------------------------------

def build_outputs(row, out, y0, y1):
    counts = {
        "COV_WORKS_SUBMITTED_TOTAL": int(row["n_submitted_total"]),
        "COV_WORKS_IN_RANGE":        int(row["n_in_range"]),
        "COV_WORKS_FOUND_OPENALEX":  int(row["n_found"]),
        "COV_WORKS_UNIQUE":          int(row["n_unique"]),
        "COV_WORKS_IN_SCOPE":        int(row["n_in_scope"]),
    }
    in_evaluation = counts["COV_WORKS_IN_RANGE"]

    funnel = pd.DataFrame([
        {
            "step": key,
            "display_name": display.format(y0=y0, y1=y1),
            "description": desc.format(y0=y0, y1=y1),
            "n_works": counts[key],
        }
        for key, display, desc in FUNNEL_STEPS
    ])

    if in_evaluation > 0:
        funnel["pct_of_in_evaluation"] = round(
            100.0 * funnel["n_works"] / in_evaluation, 2
        )
    else:
        funnel["pct_of_in_evaluation"] = 0.0

    # Step-to-step retention: what fraction of the previous step is retained.
    funnel["pct_of_previous"] = round(
        100.0 * funnel["n_works"] / funnel["n_works"].shift(1), 2
    )

    # Indicator extraction contract: one row, indicator IDs as columns.
    pd.DataFrame([counts]).to_csv(out / "data.csv", index=False)
    # Keep detailed funnel table for plotting/debugging.
    funnel.to_csv(out / "data_figure.csv", index=False)

    # 3) Scope criteria breakdown -> scope.csv
    #    Computed on unique found works within the evaluation window.
    n_unique = counts["COV_WORKS_UNIQUE"]
    scope_rows = []
    for crit, display, desc in SCOPE_CRITERIA:
        n_ok = int(row[f"n_{crit}"])
        scope_rows.append(
            {
                "criterion": crit,
                "display_name": display,
                "description": desc,
                "n_meeting": n_ok,
                "n_not_meeting": n_unique - n_ok,
                "pct_meeting": round(100.0 * n_ok / n_unique, 2)
                if n_unique > 0
                else 0.0,
            }
        )
    scope = pd.DataFrame(scope_rows)
    scope.to_csv(out / "scope.csv", index=False)

    # 4) Funnel chart -> figure.svg / .png / .pdf
    # Reverse category input so "Submitted" appears at the top of the chart.
    plot_df = funnel.iloc[::-1].reset_index(drop=True)
    plot_df["label"] = plot_df.apply(
        lambda r: f"{int(r['n_works']):,} ({r['pct_of_in_evaluation']:.0f}%)",
        axis=1,
    )

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            y=plot_df["display_name"],
            x=plot_df["n_works"],
            orientation="h",
            text=plot_df["label"],
            textposition="outside",
            cliponaxis=False,
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Count: %{x:,.0f}<br>"
                "% of in evaluation period: %{customdata:.1f}%<extra></extra>"
            ),
            customdata=plot_df["pct_of_in_evaluation"],
            showlegend=False,
        )
    )

    apply_style(fig)
    max_val = plot_df["n_works"].max()
    fig.update_layout(
        xaxis_title="Number of works",
        xaxis_title_standoff=4,
        xaxis_range=[0, max_val * 1.55],
        xaxis_tickformat=",.0f",
        yaxis_title=None,
        title=None,
        margin=dict(b=55),
        height=200,
        width=550,
    )

    fig.write_image(out / "figure.svg")
    fig.write_image(out / "figure.png")
    fig.write_image(out / "figure.pdf")

    # 5) Scope criteria chart -> scope.svg / .png / .pdf
    scope_plot = scope.iloc[::-1].reset_index(drop=True)
    scope_plot["label"] = scope_plot.apply(
        lambda r: (
            f"{int(r['n_meeting']):,} / {n_unique:,} ({r['pct_meeting']:.1f}%)"
        ),
        axis=1,
    )

    fig_scope = go.Figure()
    fig_scope.add_trace(
        go.Bar(
            y=scope_plot["display_name"],
            x=scope_plot["pct_meeting"],
            orientation="h",
            text=scope_plot["label"],
            textposition="outside",
            cliponaxis=False,
            showlegend=False,
            hovertemplate=(
                "<b>%{y}</b><br>"
                "%{x:.1f}% of works<extra></extra>"
            ),
        )
    )

    apply_style(fig_scope)
    fig_scope.update_layout(
        xaxis_title="% of unique works meeting criterion",
        xaxis_title_standoff=4,
        xaxis_range=[0, 140],
        yaxis_title=None,
        title=None,
        margin=dict(b=65),
        height=280,
        width=750,
    )

    fig_scope.write_image(out / "scope.svg")
    fig_scope.write_image(out / "scope.png")
    fig_scope.write_image(out / "scope.pdf")


# ---------------------------------------------------------------------------
# Asset setup
# ---------------------------------------------------------------------------

asset = Asset(script_file=__file__)
unit_params_dict = get_unit_params_dict()
indicator_catalog_dict = get_indicator_catalog_dict()

y0, y1 = asset.year_first, asset.year_last


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

if RELOAD_FROM_CSV:
    for inst in asset.institutions:
        out = asset.inst_dir(inst)
        raw = pd.read_csv(out / "raw.csv", keep_default_na=False, na_values=[""])
        build_outputs(raw.iloc[0], out, y0, y1)
else:
    for inst, con in asset.iterate_institutions():
        raw = asset.extract(
            con=con,
            inst=inst,
            #force = True,
            query=q_coverage(inst, y0, y1),
            out_name="raw.csv",
        )
        build_outputs(raw.iloc[0], asset.inst_dir(inst), y0, y1)
