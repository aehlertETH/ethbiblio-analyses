"""
Interdisciplinarity asset (top subfields by volume): Work-level Rao-Stirling
integration index.

Same analysis as X_X_interdisciplinarity but the quadrant plot shows the
top-12 subfields ranked by fractional publication count (volume) rather than
by odds-ratio (specialisation).  The volume ranking comes from X_X_topSubfields.

    d_ij = 0.0   same subfield
    d_ij = 1/3   same field, different subfield
    d_ij = 2/3   same domain, different field
    d_ij = 1.0   different domain

Per institution outputs:
  data.csv                 - one row per work with rs_w
  data_bysubfield.csv      - one row per citing subfield at the institution
  figure_quadrant.*        - top-12 subfield quadrant plot (institution-specific)
  figure_institution.*     - cross-institution weighted mean RS_w (shared)
  figure_impact.*          - cross-institution Spearman rho (shared)

Global output:
  data_world_baseline.csv  - worldwide mean RS_w per citing subfield
"""

from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from core.asset import Asset, INSTITUTION_DISPLAY_ORDER
from core.bootstrap import build_point_and_bounds_by_group
from core.interdisciplinarity import MIN_REFS, W_SAME_DOMAIN, W_SAME_FIELD, compute_rs_vectorized
from core.number_format import format_half_up
from core.plot_style import apply_style
from utility import get_unit_params_dict

# ------------------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------------------

RELOAD_FROM_CSV = False  # Set True to regenerate figures from existing CSVs without DuckDB
MIN_OUTPUT_SHARE = 0.01
MIN_OUTPUT_FRAC = 50.0
TOP_SUBFIELDS_LIMIT = 12
ROUND_DIGITS = 10

asset = Asset(script_file=__file__)
all_insts = list(INSTITUTION_DISPLAY_ORDER)
unit_params = get_unit_params_dict()
world_baseline_path = asset.base_dir / "data_world_baseline.csv"


def _inst_label(inst: str) -> str:
    return unit_params.get(inst, {}).get("InstShort", inst.upper())


# ------------------------------------------------------------------------------
# SQL extraction
# ------------------------------------------------------------------------------

REFS_QUERY = """
WITH subfield_tree AS (
    SELECT DISTINCT
        subfield,
        subfield_name,
        field,
        field_name,
        domain,
        domain_name
    FROM core.topics_tree
),
inst_works AS (
    SELECT DISTINCT
        cw.work_id,
        cw.publication_year,
        st.subfield       AS citing_subfield,
        st.subfield_name  AS citing_subfield_name,
        st.field          AS citing_field,
        st.field_name     AS citing_field_name,
        st.domain         AS citing_domain,
        st.domain_name    AS citing_domain_name,
        wm.n_institutions_on_work,
        wm.norm_vs_mean,
        wm.cohort_is_reliable
    FROM reports.report_membership rm
    JOIN core.work cw
      ON cw.work_id = rm.work_id
    JOIN marts.work_metrics wm
      ON wm.work_id = rm.work_id
    JOIN subfield_tree st
      ON st.subfield = cw.subfield
    WHERE rm.report_name = '{inst}'
      AND cw.publication_year BETWEEN {y0} AND {y1}
      AND wm.n_institutions_on_work > 0
      AND wm.has_references = 1
),
ref_counts AS (
    SELECT
        iw.work_id,
        st.subfield AS cited_subfield,
        st.field    AS cited_field,
        st.domain   AS cited_domain,
        COUNT(*)    AS n_refs_in_subfield
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
    iw.publication_year,
    iw.citing_subfield,
    iw.citing_subfield_name,
    iw.citing_field,
    iw.citing_field_name,
    iw.citing_domain,
    iw.citing_domain_name,
    iw.n_institutions_on_work,
    iw.norm_vs_mean,
    iw.cohort_is_reliable,
    rc.cited_subfield,
    rc.cited_field,
    rc.cited_domain,
    rc.n_refs_in_subfield,
    SUM(rc.n_refs_in_subfield) OVER (PARTITION BY iw.work_id) AS total_refs
FROM inst_works iw
JOIN ref_counts rc
  ON rc.work_id = iw.work_id
"""


WORLD_BASELINE_QUERY = """
WITH subfield_tree AS (
    SELECT DISTINCT
        subfield,
        subfield_name,
        field,
        field_name,
        domain,
        domain_name
    FROM core.topics_tree
),
world_works AS (
    SELECT
        w.work_id,
        st.subfield      AS citing_subfield,
        st.subfield_name AS citing_subfield_name,
        st.field_name    AS citing_field_name,
        st.domain_name   AS citing_domain_name
    FROM core.work w
    JOIN marts.work_metrics wm
      ON wm.work_id = w.work_id
    JOIN subfield_tree st
      ON st.subfield = w.subfield
    WHERE w.publication_year BETWEEN {y0} AND {y1}
      AND wm.n_institutions_on_work > 0
      AND wm.has_references = 1
),
ref_counts AS (
    SELECT
        ww.work_id,
        ww.citing_subfield,
        ww.citing_subfield_name,
        ww.citing_field_name,
        ww.citing_domain_name,
        st.subfield AS cited_subfield,
        st.field    AS cited_field,
        st.domain   AS cited_domain,
        COUNT(*)    AS n_refs_in_subfield
    FROM world_works ww
    JOIN core.refs r
      ON r.citing_id = ww.work_id
    JOIN core.work cw2
      ON cw2.work_id = r.cited_id
    JOIN subfield_tree st
      ON st.subfield = cw2.subfield
    GROUP BY
        ww.work_id,
        ww.citing_subfield,
        ww.citing_subfield_name,
        ww.citing_field_name,
        ww.citing_domain_name,
        st.subfield,
        st.field,
        st.domain
),
ref_totals AS (
    SELECT
        *,
        SUM(n_refs_in_subfield) OVER (PARTITION BY work_id) AS total_refs
    FROM ref_counts
),
q_tbl AS (
    SELECT
        *,
        n_refs_in_subfield::DOUBLE / total_refs::DOUBLE AS q,
        POWER(n_refs_in_subfield::DOUBLE / total_refs::DOUBLE, 2) AS q2
    FROM ref_totals
    WHERE total_refs >= {min_refs}
),
c_tbl AS (
    SELECT
        work_id,
        ANY_VALUE(citing_subfield) AS citing_subfield,
        ANY_VALUE(citing_subfield_name) AS citing_subfield_name,
        ANY_VALUE(citing_field_name) AS citing_field_name,
        ANY_VALUE(citing_domain_name) AS citing_domain_name,
        1.0 - SUM(q2) AS c_cross_all
    FROM q_tbl
    GROUP BY work_id
),
d_tbl AS (
    SELECT
        work_id,
        SUM(POWER(dom_q, 2) - dom_q2) AS d_cross_domain
    FROM (
        SELECT
            work_id,
            cited_domain,
            SUM(q) AS dom_q,
            SUM(q2) AS dom_q2
        FROM q_tbl
        GROUP BY work_id, cited_domain
    )
    GROUP BY work_id
),
f_tbl AS (
    SELECT
        work_id,
        SUM(POWER(fld_q, 2) - fld_q2) AS f_cross_field
    FROM (
        SELECT
            work_id,
            cited_field,
            SUM(q) AS fld_q,
            SUM(q2) AS fld_q2
        FROM q_tbl
        GROUP BY work_id, cited_field
    )
    GROUP BY work_id
),
work_rs AS (
    SELECT
        c.work_id,
        c.citing_subfield,
        c.citing_subfield_name,
        c.citing_field_name,
        c.citing_domain_name,
        (
            c.c_cross_all
            - (1.0 - {w_same_domain}) * d.d_cross_domain
            - ({w_same_domain} - {w_same_field}) * f.f_cross_field
        ) AS rs_w
    FROM c_tbl c
    JOIN d_tbl d ON d.work_id = c.work_id
    JOIN f_tbl f ON f.work_id = c.work_id
)
SELECT
    citing_subfield,
    ANY_VALUE(citing_subfield_name) AS citing_subfield_name,
    ANY_VALUE(citing_field_name) AS citing_field_name,
    ANY_VALUE(citing_domain_name) AS citing_domain_name,
    AVG(rs_w) AS world_mean_rs_w,
    COUNT(*) AS world_n_works
FROM work_rs
GROUP BY citing_subfield
ORDER BY world_mean_rs_w;
"""


# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------

def _subfield_label(subfield_name: str, field_name: str) -> str:
    return f"{subfield_name} ({field_name})"


def _fractional_mncs(group: pd.DataFrame) -> float:
    valid = group[
        group["norm_vs_mean"].notna()
        & group["n_institutions_on_work"].gt(0)
        & (group["cohort_is_reliable"].fillna(False) == True)
    ]
    if valid.empty:
        return float("nan")

    weights = 1.0 / valid["n_institutions_on_work"]
    return float((valid["norm_vs_mean"] * weights).sum() / weights.sum())


def _safe_read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


SUBFIELD_VOLUME_QUERY = """
WITH subfield_volume AS (
    SELECT
        w.subfield AS citing_subfield,
        SUM(CASE WHEN wm.n_institutions_on_work > 0
                 THEN 1.0 / wm.n_institutions_on_work ELSE 0 END) AS P_FRAC
    FROM reports.report_membership rm
    JOIN core.work w ON w.work_id = rm.work_id
    JOIN marts.work_metrics wm ON wm.work_id = rm.work_id
    WHERE rm.report_name = '{inst}'
      AND w.publication_year BETWEEN {y0} AND {y1}
    GROUP BY w.subfield
),
subfield_volume_with_share AS (
    SELECT
        citing_subfield,
        P_FRAC,
        P_FRAC / NULLIF(SUM(P_FRAC) OVER (), 0) AS P_FRAC_share
    FROM subfield_volume
)
SELECT
    citing_subfield,
    P_FRAC,
    P_FRAC_share
FROM subfield_volume_with_share
ORDER BY P_FRAC DESC
"""


def _subfield_volumes(con, inst: str) -> pd.DataFrame:
    return con.query(
        SUBFIELD_VOLUME_QUERY.format(
            inst=inst, y0=asset.year_first, y1=asset.year_last,
        )
    ).df()


def _scale_sizes(values: np.ndarray, min_px: float = 10.0, max_px: float = 34.0) -> list[float]:
    v = values.astype(float)
    if len(v) == 0:
        return []
    v_min, v_max = float(v.min()), float(v.max())
    if v_max <= v_min:
        return [0.5 * (min_px + max_px)] * len(v)
    return (min_px + (max_px - min_px) * (v - v_min) / (v_max - v_min)).tolist()


def _build_world_baseline(con) -> pd.DataFrame:
    baseline_df = con.execute(
        WORLD_BASELINE_QUERY.format(
            y0=asset.year_first,
            y1=asset.year_last,
            min_refs=MIN_REFS,
            w_same_domain=W_SAME_DOMAIN,
            w_same_field=W_SAME_FIELD,
        )
    ).df()
    baseline_df["subfield_label"] = baseline_df.apply(
        lambda r: _subfield_label(r["citing_subfield_name"], r["citing_field_name"]),
        axis=1,
    )
    baseline_df["world_mean_rs_w"] = baseline_df["world_mean_rs_w"].round(ROUND_DIGITS)
    baseline_df.to_csv(world_baseline_path, index=False)
    return baseline_df


def _load_world_baseline() -> pd.DataFrame:
    if world_baseline_path.exists():
        return pd.read_csv(world_baseline_path)
    with asset.connect() as con:
        return _build_world_baseline(con)


def _compute_label_positions(
    xs: np.ndarray,
    ys: np.ndarray,
    texts: list[str],
    marker_sizes: np.ndarray,
    x_range: tuple[float, float],
    y_range: tuple[float, float],
    font_size: float = 9.0,
    n_iterations: int = 500,
) -> list[tuple[float, float]]:
    """Force-directed label placement.

    Works in a normalised [0,1]x[0,1] coordinate system so that
    repulsion forces are isotropic, then maps back to data units.
    """
    n = len(xs)
    if n == 0:
        return []

    x_min, x_max = x_range
    y_min, y_max = y_range
    x_span = x_max - x_min
    y_span = y_max - y_min

    nx = (xs - x_min) / x_span
    ny = (ys - y_min) / y_span

    char_w_norm = 0.0075
    label_h_norm = 0.038
    half_h = label_h_norm / 2.0
    half_ws = np.array([len(t) * char_w_norm / 2.0 for t in texts])

    marker_r = marker_sizes / 900.0 * 0.4

    lx = nx.copy().astype(float)
    ly = ny.copy().astype(float)
    for i in range(n):
        if ny[i] >= 0.5:
            ly[i] = ny[i] + label_h_norm * 1.5
        else:
            ly[i] = ny[i] - label_h_norm * 1.5

    def _rect_overlap(ax, ay, ahw, ahh, bx, by, bhw, bhh):
        ox = (ahw + bhw) - abs(ax - bx)
        oy = (ahh + bhh) - abs(ay - by)
        if ox > 0 and oy > 0:
            return ox, oy
        return 0.0, 0.0

    for iteration in range(n_iterations):
        t = iteration / n_iterations
        step = 0.3 * (1.0 - 0.8 * t)

        for i in range(n):
            fx, fy = 0.0, 0.0

            for j in range(n):
                if i == j:
                    continue
                ox, oy = _rect_overlap(
                    lx[i], ly[i], half_ws[i], half_h,
                    lx[j], ly[j], half_ws[j], half_h,
                )
                if ox > 0 and oy > 0:
                    dx = lx[i] - lx[j]
                    dy = ly[i] - ly[j]
                    if abs(dx) < 1e-9 and abs(dy) < 1e-9:
                        dx = 0.001 * (1 if i > j else -1)
                        dy = 0.001 * (1 if (i % 2 == 0) else -1)
                    mag = (dx * dx + dy * dy) ** 0.5
                    push = min(ox, oy) * 2.0
                    fx += push * dx / mag
                    fy += push * dy / mag

            for j in range(n):
                dx = lx[i] - nx[j]
                dy = ly[i] - ny[j]
                ox, oy = _rect_overlap(
                    lx[i], ly[i], half_ws[i], half_h,
                    nx[j], ny[j], marker_r[j], marker_r[j],
                )
                if ox > 0 and oy > 0:
                    if abs(dx) < 1e-9 and abs(dy) < 1e-9:
                        dy = label_h_norm
                    mag = (dx * dx + dy * dy) ** 0.5
                    push = min(ox, oy) * 1.5
                    fx += push * dx / mag
                    fy += push * dy / mag

            pad = 0.01
            left_pen = (pad + half_ws[i]) - lx[i]
            if left_pen > 0:
                fx += left_pen * 3.0
            right_pen = lx[i] + half_ws[i] - (1.0 - pad)
            if right_pen > 0:
                fx -= right_pen * 3.0
            bot_pen = (pad + half_h) - ly[i]
            if bot_pen > 0:
                fy += bot_pen * 3.0
            top_pen = ly[i] + half_h - (1.0 - pad)
            if top_pen > 0:
                fy -= top_pen * 3.0

            spring_k = 0.05
            fx += spring_k * (nx[i] - lx[i])
            fy += spring_k * (ny[i] - ly[i])

            lx[i] += step * fx
            ly[i] += step * fy

            lx[i] = np.clip(lx[i], half_ws[i] + pad, 1.0 - half_ws[i] - pad)
            ly[i] = np.clip(ly[i], half_h + pad, 1.0 - half_h - pad)

    out_x = lx * x_span + x_min
    out_y = ly * y_span + y_min
    return list(zip(out_x.tolist(), out_y.tolist()))


def _plot_quadrant(inst: str, df_plot: pd.DataFrame) -> None:
    if df_plot.empty:
        return

    ref_x = float(df_plot["world_mean_rs_w"].median())
    x_vals = df_plot["world_mean_rs_w"]
    y_vals = df_plot["excess_rs_w"]
    marker_sizes = np.asarray(_scale_sizes(df_plot["n_works"].to_numpy()))

    x_pad = max((x_vals.max() - x_vals.min()) * 0.18, 0.02)
    x_min = float(x_vals.min() - x_pad)
    x_max = float(x_vals.max() + x_pad)
    max_abs_y = max(abs(float(y_vals.min())), abs(float(y_vals.max())), 0.02)
    y_min = -1.25 * max_abs_y
    y_max = 1.25 * max_abs_y

    label_texts = [
        f"{name} ({format_half_up(mncs, 2)})" if pd.notna(mncs) else name
        for name, mncs in zip(df_plot["citing_subfield_name"], df_plot["mncs"])
    ]

    label_positions = _compute_label_positions(
        x_vals.to_numpy(),
        y_vals.to_numpy(),
        label_texts,
        marker_sizes,
        (x_min, x_max),
        (y_min, y_max),
    )

    fig = go.Figure(
        go.Scatter(
            x=x_vals,
            y=y_vals,
            mode="markers",
            showlegend=False,
            marker=dict(
                color="#4B86C8",
                size=marker_sizes.tolist(),
                opacity=0.9,
                line=dict(width=1.2, color="#FFFFFF"),
            ),
            text=df_plot["citing_subfield_name"],
            customdata=np.column_stack(
                [
                    df_plot["n_works"].to_numpy(),
                    df_plot["mean_rs_w"].to_numpy(),
                    df_plot["world_mean_rs_w"].to_numpy(),
                    df_plot["excess_rs_w"].to_numpy(),
                    df_plot["citing_domain_name"].to_numpy(),
                    df_plot["mncs"].to_numpy(),
                ]
            ),
            hovertemplate=(
                "<b>%{text}</b><br>"
                "Domain:           %{customdata[4]}<br>"
                "Institution RS_w: %{customdata[1]:.3f}<br>"
                "Worldwide RS_w:   %{customdata[2]:.3f}<br>"
                "Excess:           %{customdata[3]:+.3f}<br>"
                "MNCS:             %{customdata[5]:.2f}<br>"
                "n works: %{customdata[0]:,}<br>"
                "<extra></extra>"
            ),
        )
    )
    x_span = x_max - x_min
    y_span = y_max - y_min
    arrow_threshold = max(x_span * 0.02, y_span * 0.02)
    for idx, (lx, ly) in enumerate(label_positions):
        px, py = float(x_vals.iloc[idx]), float(y_vals.iloc[idx])
        dist = ((lx - px) ** 2 + (ly - py) ** 2) ** 0.5
        show_arrow = dist > arrow_threshold
        fig.add_annotation(
            x=px, y=py,
            ax=lx, ay=ly,
            xref="x", yref="y",
            axref="x", ayref="y",
            text=label_texts[idx],
            showarrow=show_arrow,
            arrowhead=0,
            arrowwidth=0.8,
            arrowcolor="#AAAAAA",
            font=dict(size=12, color="#222222"),
            xanchor="center",
            yanchor="middle",
        )

    quad_fill = "rgba(75,134,200,0.06)"
    fig.add_shape(type="rect", x0=x_min, x1=ref_x, y0=0.0, y1=y_max, fillcolor=quad_fill, line_width=0, layer="below")
    fig.add_shape(type="rect", x0=ref_x, x1=x_max, y0=y_min, y1=0.0, fillcolor=quad_fill, line_width=0, layer="below")
    fig.add_shape(type="rect", x0=ref_x, x1=x_max, y0=0.0, y1=y_max, fillcolor="rgba(0,0,0,0)", line_width=0, layer="below")
    fig.add_shape(type="rect", x0=x_min, x1=ref_x, y0=y_min, y1=0.0, fillcolor="rgba(0,0,0,0)", line_width=0, layer="below")

    fig.add_vline(x=ref_x, line_dash="solid", line_color="#555555", line_width=2)
    fig.add_hline(y=0.0, line_dash="solid", line_color="#555555", line_width=2)
    apply_style(fig)

    fig.add_annotation(x=x_min, y=y_max, xanchor="left", yanchor="top",
                        text="Less interdisciplinary subfield,\ninstitution more interdisciplinary", showarrow=False, font=dict(size=12, color="#888888"))
    fig.add_annotation(x=x_max, y=y_max, xanchor="right", yanchor="top",
                        text="More interdisciplinary subfield,\ninstitution more interdisciplinary", showarrow=False, font=dict(size=12, color="#888888"))
    fig.add_annotation(x=x_min, y=y_min, xanchor="left", yanchor="bottom",
                        text="Less interdisciplinary subfield,\ninstitution less interdisciplinary", showarrow=False, font=dict(size=12, color="#888888"))
    fig.add_annotation(x=x_max, y=y_min, xanchor="right", yanchor="bottom",
                        text="More interdisciplinary subfield,\ninstitution less interdisciplinary", showarrow=False, font=dict(size=12, color="#888888"))

    fig.update_layout(
        height=640,
        width=900,
        xaxis=dict(
            title="Subfield interdisciplinarity (worldwide)",
            range=[x_min, x_max],
        ),
        yaxis=dict(
            title=f"{_inst_label(inst)}'s interdisciplinarity (compared to subfield average)",
            range=[y_min, y_max],
            zeroline=False,
        ),
        margin=dict(l=70, r=40, t=30, b=80),
    )
    out = asset.inst_dir(inst)
    for ext in ("figure_quadrant.svg", "figure.svg", "figure_quadrant.png", "figure.png", "figure_quadrant.pdf", "figure.pdf"):
        fig.write_image(out / ext)


# ------------------------------------------------------------------------------
# Phase 0 - Worldwide baseline (subfield only)
# ------------------------------------------------------------------------------

print("Building/loading worldwide subfield baseline...")
world_baseline = _load_world_baseline()
if world_baseline.empty:
    raise RuntimeError("Worldwide baseline is empty; cannot build quadrant figure.")


# ------------------------------------------------------------------------------
# Phase 1 - Per-institution extraction + RS_w + subfield aggregates
# ------------------------------------------------------------------------------

_META_COLS = [
    "work_id",
    "publication_year",
    "citing_subfield",
    "citing_subfield_name",
    "citing_field",
    "citing_field_name",
    "citing_domain",
    "citing_domain_name",
    "n_institutions_on_work",
    "norm_vs_mean",
    "cohort_is_reliable",
]

_SUBFIELD_GROUP_COLS = [
    "citing_subfield",
    "citing_subfield_name",
    "citing_field_name",
    "citing_domain_name",
]

if RELOAD_FROM_CSV:
    for inst in asset.institutions:
        out_dir = asset.inst_dir(inst)
        bysubfield_path = out_dir / "data_bysubfield.csv"
        if not bysubfield_path.exists():
            print(f"  {inst}: data_bysubfield.csv not found, skipping")
            continue
        subfield_agg = pd.read_csv(bysubfield_path, keep_default_na=False, na_values=[""])
        if "P_FRAC" not in subfield_agg.columns:
            print(f"  {inst}: data_bysubfield.csv has no P_FRAC column, rerun extraction first")
            continue
        if "P_FRAC_share" not in subfield_agg.columns:
            print(f"  {inst}: data_bysubfield.csv has no P_FRAC_share column, rerun extraction first")
            continue

        eligible_subfields = subfield_agg[
            (subfield_agg["P_FRAC"] >= MIN_OUTPUT_FRAC)
            & (subfield_agg["P_FRAC_share"] >= MIN_OUTPUT_SHARE)
        ].copy()
        top_ids = set(
            eligible_subfields.nlargest(TOP_SUBFIELDS_LIMIT, "P_FRAC")["citing_subfield"].tolist()
        )
        if not top_ids:
            print(f"  {inst}: no top subfields by volume, skipping quadrant")
            continue

        plot_q = subfield_agg[
            (subfield_agg["citing_subfield"].isin(top_ids))
            & (subfield_agg["P_FRAC"] >= MIN_OUTPUT_FRAC)
            & (subfield_agg["P_FRAC_share"] >= MIN_OUTPUT_SHARE)
        ].copy()
        if plot_q.empty:
            print(
                f"  {inst}: no top subfields pass P_FRAC >= {MIN_OUTPUT_FRAC} "
                f"and P_FRAC_share >= {MIN_OUTPUT_SHARE}, skipping quadrant"
            )
            continue

        _plot_quadrant(inst, plot_q.reset_index(drop=True))
else:
    for inst, con in asset.iterate_institutions():
        refs_df = con.query(
            REFS_QUERY.format(inst=inst, y0=asset.year_first, y1=asset.year_last)
        ).df()
        if refs_df.empty:
            print(f"  {inst}: no reference data, skipping")
            continue

        rs_series = compute_rs_vectorized(refs_df)
        if rs_series.empty:
            print(f"  {inst}: no works with >= {MIN_REFS} refs with known subfield, skipping")
            continue

        meta_df = refs_df.drop_duplicates("work_id")[_META_COLS]
        work_df = meta_df.merge(rs_series.reset_index(), on="work_id", how="inner")
        work_df = work_df.sort_values("work_id").reset_index(drop=True)
        work_df[["norm_vs_mean", "rs_w"]] = work_df[["norm_vs_mean", "rs_w"]].round(ROUND_DIGITS)
        out_dir = asset.inst_dir(inst)
        work_df.to_csv(out_dir / "data.csv", index=False)

        subfield_agg = (
            work_df.groupby(_SUBFIELD_GROUP_COLS)
            .apply(
                lambda grp: pd.Series(
                    {
                        "n_works": grp["rs_w"].count(),
                        "mean_rs_w": grp["rs_w"].mean(),
                        "mncs": _fractional_mncs(grp),
                    }
                )
            )
            .reset_index()
            .sort_values("citing_subfield", ascending=True)
        )
        subfield_agg["subfield_label"] = subfield_agg.apply(
            lambda r: _subfield_label(r["citing_subfield_name"], r["citing_field_name"]),
            axis=1,
        )
        subfield_agg = subfield_agg.merge(
            world_baseline[
                [
                    "citing_subfield",
                    "world_mean_rs_w",
                    "world_n_works",
                    "subfield_label",
                ]
            ],
            on=["citing_subfield", "subfield_label"],
            how="inner",
        )
        subfield_agg = subfield_agg.merge(_subfield_volumes(con, inst), on="citing_subfield", how="left")
        subfield_agg["excess_rs_w"] = subfield_agg["mean_rs_w"] - subfield_agg["world_mean_rs_w"]
        subfield_agg[["mean_rs_w", "mncs", "world_mean_rs_w", "excess_rs_w"]] = (
            subfield_agg[["mean_rs_w", "mncs", "world_mean_rs_w", "excess_rs_w"]]
            .round(ROUND_DIGITS)
        )
        subfield_agg.to_csv(out_dir / "data_bysubfield.csv", index=False)

        eligible_subfields = subfield_agg[
            (subfield_agg["P_FRAC"] >= MIN_OUTPUT_FRAC)
            & (subfield_agg["P_FRAC_share"] >= MIN_OUTPUT_SHARE)
        ].copy()
        top_ids = set(
            eligible_subfields.nlargest(TOP_SUBFIELDS_LIMIT, "P_FRAC")["citing_subfield"].tolist()
        )
        if not top_ids:
            print(f"  {inst}: no top subfields by volume, skipping quadrant")
            continue

        plot_q = subfield_agg[
            (subfield_agg["citing_subfield"].isin(top_ids))
            & (subfield_agg["P_FRAC"] >= MIN_OUTPUT_FRAC)
            & (subfield_agg["P_FRAC_share"] >= MIN_OUTPUT_SHARE)
        ].copy()
        if plot_q.empty:
            print(
                f"  {inst}: no top subfields pass P_FRAC >= {MIN_OUTPUT_FRAC} "
                f"and P_FRAC_share >= {MIN_OUTPUT_SHARE}, skipping quadrant"
            )
            continue

        _plot_quadrant(inst, plot_q.reset_index(drop=True))

print("Figure B (subfield quadrant) exported.")


# ------------------------------------------------------------------------------
# Phase 2 - Cross-institution figures (A and C)
# ------------------------------------------------------------------------------

def _spearman_r(x: np.ndarray, y: np.ndarray) -> float:
    if len(x) < 3:
        return float("nan")
    rx = np.argsort(np.argsort(x)).astype(float)
    ry = np.argsort(np.argsort(y)).astype(float)
    rx -= rx.mean()
    ry -= ry.mean()
    denom = np.sqrt((rx**2).sum() * (ry**2).sum())
    return float((rx * ry).sum() / denom) if denom > 0 else float("nan")


def _bootstrap_spearman_ci(
    x: np.ndarray,
    y: np.ndarray,
    n_bootstrap: int = 1000,
    ci_level: float = 0.95,
    seed: int = 42,
) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    n = len(x)
    if n < 20:
        return float("nan"), float("nan")
    rhos = np.array(
        [_spearman_r(x[idx := rng.integers(0, n, n)], y[idx]) for _ in range(n_bootstrap)]
    )
    rhos = rhos[np.isfinite(rhos)]
    if rhos.size == 0:
        return float("nan"), float("nan")
    alpha = 1.0 - ci_level
    return float(np.quantile(rhos, alpha / 2)), float(np.quantile(rhos, 1 - alpha / 2))


all_frames: list[pd.DataFrame] = []
for inst in all_insts:
    p = asset.inst_dir(inst) / "data.csv"
    if p.exists():
        df = pd.read_csv(p)
        df["institution"] = inst
        all_frames.append(df)

if all_frames:
    combined_all = pd.concat(all_frames, ignore_index=True)
else:
    combined_all = pd.DataFrame()

if not combined_all.empty:
    combined_all["weight"] = 1.0 / combined_all["n_institutions_on_work"]

    point_df, lower_df, upper_df = build_point_and_bounds_by_group(
        combined_all,
        group_col="institution",
        value_col="rs_w",
        out_col="mean_rs_w",
        weights_col="weight",
        n_bootstrap=1000,
        random_seed=42,
        round_digits=4,
    )

    inst_stats = (
        point_df.merge(lower_df.rename(columns={"mean_rs_w": "lower"}), on="institution")
        .merge(upper_df.rename(columns={"mean_rs_w": "upper"}), on="institution")
        .set_index("institution")
        .reindex(all_insts)
        .reset_index()
    )
    inst_stats["label"] = inst_stats["institution"].map(_inst_label)
    inst_stats_sorted = inst_stats.sort_values("mean_rs_w", ascending=True)

    fig_a = go.Figure(
        go.Bar(
            x=inst_stats_sorted["mean_rs_w"],
            y=inst_stats_sorted["label"],
            orientation="h",
            marker_color="#4B86C8",
            error_x=dict(
                type="data",
                symmetric=False,
                array=(inst_stats_sorted["upper"] - inst_stats_sorted["mean_rs_w"]).tolist(),
                arrayminus=(inst_stats_sorted["mean_rs_w"] - inst_stats_sorted["lower"]).tolist(),
                color="#888888",
                thickness=1.5,
                width=4,
            ),
            hovertemplate="<b>%{y}</b><br>Mean RS_w: %{x:.3f}<extra></extra>",
        )
    )
    apply_style(fig_a)
    x_max = inst_stats_sorted["upper"].max(skipna=True)
    fig_a.update_layout(
        height=300,
        width=700,
        xaxis=dict(
            title="Mean work-level RS integration index (95% CI)",
            range=[0, min(1.0, x_max * 1.15) if pd.notna(x_max) else 1.0],
        ),
        margin=dict(l=100, r=40, t=30, b=50),
    )

    first_inst = next((i for i in all_insts if (asset.inst_dir(i) / "data.csv").exists()), None)
    first_out: Path | None = asset.inst_dir(first_inst) if first_inst else None
    if first_out:
        for ext in ("figure_institution.svg", "figure_institution.png", "figure_institution.pdf"):
            fig_a.write_image(first_out / ext)
        for inst in all_insts:
            if inst == first_inst:
                continue
            out = asset.inst_dir(inst)
            for ext in ("figure_institution.svg", "figure_institution.png", "figure_institution.pdf"):
                src = first_out / ext
                if src.exists():
                    shutil.copy2(src, out / ext)

    print("\nMean RS_w per institution (fractionally weighted, 95% bootstrap CI):")
    for _, row in inst_stats.iterrows():
        lo = f"{row['lower']:.4f}" if pd.notna(row["lower"]) else "n/a"
        hi = f"{row['upper']:.4f}" if pd.notna(row["upper"]) else "n/a"
        pt = f"{row['mean_rs_w']:.4f}" if pd.notna(row["mean_rs_w"]) else "n/a"
        print(f"  {row['institution']:12s}: {pt}  [{lo}, {hi}]")

    spearman_rows: list[dict] = []
    for inst in all_insts:
        p = asset.inst_dir(inst) / "data.csv"
        if not p.exists():
            continue
        df_inst = pd.read_csv(p)
        imp = df_inst[
            (df_inst["cohort_is_reliable"] == 1) & df_inst["norm_vs_mean"].notna()
        ].dropna(subset=["rs_w", "norm_vs_mean"])
        if len(imp) < 20:
            continue
        x = imp["rs_w"].to_numpy()
        y = imp["norm_vs_mean"].to_numpy()
        rho = _spearman_r(x, y)
        lo, hi = _bootstrap_spearman_ci(x, y, n_bootstrap=1000, seed=42)
        spearman_rows.append(
            {
                "institution": inst,
                "label": _inst_label(inst),
                "rho": rho,
                "lower": lo,
                "upper": hi,
                "n_works": len(imp),
            }
        )
        print(f"  {inst:12s}: rho={rho:.3f}  [{lo:.3f}, {hi:.3f}]  n={len(imp):,}")

    if spearman_rows:
        sp_df = (
            pd.DataFrame(spearman_rows)
            .set_index("institution")
            .reindex(all_insts)
            .reset_index()
            .dropna(subset=["rho"])
            .sort_values("rho", ascending=True)
        )

        fig_c = go.Figure(
            go.Bar(
                x=sp_df["rho"],
                y=sp_df["label"],
                orientation="h",
                marker_color=["#D94F3D" if r < 0 else "#4B86C8" for r in sp_df["rho"]],
                error_x=dict(
                    type="data",
                    symmetric=False,
                    array=(sp_df["upper"] - sp_df["rho"]).tolist(),
                    arrayminus=(sp_df["rho"] - sp_df["lower"]).tolist(),
                    color="#888888",
                    thickness=1.5,
                    width=4,
                ),
                text=[f"ρ={format_half_up(r, 3)}  (n={n:,})" for r, n in zip(sp_df["rho"], sp_df["n_works"])],
                textposition="outside",
                hovertemplate="<b>%{y}</b><br>Spearman ρ: %{x:.3f}<extra></extra>",
            )
        )
        fig_c.add_vline(x=0, line_dash="dash", line_color="#888888")
        apply_style(fig_c)
        rho_abs_max = sp_df[["rho", "upper", "lower"]].abs().max().max()
        fig_c.update_layout(
            height=300,
            width=750,
            xaxis=dict(
                title="Spearman ρ (RS_w vs MNCS, 95% CI)",
                range=[-(rho_abs_max * 1.4), rho_abs_max * 1.4],
                zeroline=False,
            ),
            margin=dict(l=100, r=160, t=30, b=50),
        )

        if first_out:
            for ext in ("figure_impact.svg", "figure_impact.png", "figure_impact.pdf"):
                fig_c.write_image(first_out / ext)
            for inst in all_insts:
                if inst == first_inst:
                    continue
                out = asset.inst_dir(inst)
                for ext in ("figure_impact.svg", "figure_impact.png", "figure_impact.pdf"):
                    src = first_out / ext
                    if src.exists():
                        shutil.copy2(src, out / ext)
        print("\nFigure C (Spearman rho) exported.")
