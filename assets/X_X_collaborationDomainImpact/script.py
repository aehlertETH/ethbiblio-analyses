from itertools import combinations_with_replacement

import pandas as pd

from core.asset import Asset, INSTITUTION_DISPLAY_ORDER
from utility import get_indicator_catalog_dict, get_unit_params_dict

INSTITUTIONS = [i for i in INSTITUTION_DISPLAY_ORDER if i != "ethdomain"]
CELL_HIGHLIGHT = r"\cellcolor[HTML]{D3DEEF}"

asset = Asset(script_file=__file__)
unit_params_dict = get_unit_params_dict()
indicator_catalog_dict = get_indicator_catalog_dict()

y0 = asset.year_first
y1 = asset.year_last


def q_diagonal(inst: str) -> str:
    return f"""
        WITH all_works AS (
            SELECT DISTINCT rm.work_id
            FROM reports.report_membership AS rm
            INNER JOIN core.work AS w
                ON w.work_id = rm.work_id
            WHERE rm.report_name = '{inst}'
              AND w.publication_year BETWEEN {y0} AND {y1}
        ),
        mncs_base AS (
            SELECT
                m.norm_vs_mean,
                m.n_institutions_on_work
            FROM all_works aw
            INNER JOIN marts.work_citation_metrics AS m
                ON m.work_id = aw.work_id
            WHERE m.cohort_is_reliable = TRUE
              AND m.n_institutions_on_work > 0
        )
        SELECT
            (SELECT COUNT(*) FROM all_works) AS p_full,
            ROUND(
                SUM(norm_vs_mean / n_institutions_on_work)
                / NULLIF(SUM(1.0 / n_institutions_on_work), 0),
            2) AS mncs
        FROM mncs_base;
    """


def q_pair(inst_a: str, inst_b: str) -> str:
    return f"""
        WITH copubs AS (
            SELECT DISTINCT rm1.work_id
            FROM reports.report_membership rm1
            INNER JOIN reports.report_membership rm2
                ON rm2.work_id = rm1.work_id
            INNER JOIN core.work w
                ON w.work_id = rm1.work_id
            WHERE rm1.report_name = '{inst_a}'
              AND rm2.report_name = '{inst_b}'
              AND w.publication_year BETWEEN {y0} AND {y1}
        ),
        mncs_base AS (
            SELECT
                m.norm_vs_mean,
                m.n_institutions_on_work
            FROM copubs c
            INNER JOIN marts.work_citation_metrics AS m
                ON m.work_id = c.work_id
            WHERE m.cohort_is_reliable = TRUE
              AND m.n_institutions_on_work > 0
        )
        SELECT
            (SELECT COUNT(*) FROM copubs) AS p_full,
            ROUND(
                SUM(norm_vs_mean / n_institutions_on_work)
                / NULLIF(SUM(1.0 / n_institutions_on_work), 0),
            2) AS mncs
        FROM mncs_base;
    """


def ensuremath_wrap(s: str) -> str:
    if not s:
        return s
    if r"\ensuremath{" in s:
        return s
    return rf"\ensuremath{{{s}}}"


def fmt_count(v) -> str:
    if v is None or pd.isna(v):
        return r"\textit{n/a}"
    return f"{int(v):,}".replace(",", "{,}")


def fmt_float(v, digits: int = 2) -> str:
    if v is None or pd.isna(v):
        return r"\textit{n/a}"
    return f"{float(v):.{digits}f}"


def fmt_cell(value: str, highlight: bool = False) -> str:
    if highlight:
        return f"{CELL_HIGHLIGHT} {value}"
    return value


def get_inst_label(inst: str) -> str:
    return unit_params_dict.get(inst, {}).get("InstShort", inst.upper())


def get_metric_labels() -> tuple[str, str]:
    p_full_symbol_tex = (indicator_catalog_dict.get("P_FULL", {}) or {}).get("symbol_tex", "").strip()
    p_full_label = ensuremath_wrap(p_full_symbol_tex) if p_full_symbol_tex else "P[full]"
    mncs_symbol_tex = (indicator_catalog_dict.get("C_MNCS_FRAC", {}) or {}).get("symbol_tex", "").strip()
    mncs_label = ensuremath_wrap(mncs_symbol_tex) if mncs_symbol_tex else "MNCS"
    return p_full_label, mncs_label


def build_complete_matrix(raw_df: pd.DataFrame) -> pd.DataFrame:
    lookup = {
        (str(row.row_inst), str(row.col_inst)): (
            int(row.p_full),
            float(row.mncs) if pd.notna(row.mncs) else None,
        )
        for row in raw_df.itertuples(index=False)
    }

    rows = []
    for row_inst in INSTITUTIONS:
        for col_inst in INSTITUTIONS:
            p_full, mncs = lookup.get((row_inst, col_inst), (0, None))
            rows.append(
                {
                    "row_inst": row_inst,
                    "col_inst": col_inst,
                    "p_full": p_full,
                    "mncs": mncs,
                }
            )
    return pd.DataFrame(rows)


def build_lookup(df: pd.DataFrame) -> dict[tuple[str, str], tuple[int, float | None]]:
    return {
        (str(row.row_inst), str(row.col_inst)): (
            int(row.p_full),
            float(row.mncs) if pd.notna(row.mncs) else None,
        )
        for row in df.itertuples(index=False)
    }


def build_unit_summary_df(df: pd.DataFrame, focal_inst: str) -> pd.DataFrame:
    lookup = build_lookup(df)
    ordered_insts = [focal_inst] + [inst for inst in INSTITUTIONS if inst != focal_inst]
    rows = []
    for idx, inst in enumerate(ordered_insts, start=1):
        p_full, mncs = lookup[(inst, focal_inst)]
        rows.append(
            {
                "institution_id": inst,
                "institution_name": get_inst_label(inst),
                "P_FULL": p_full,
                "C_MNCS_FRAC": mncs,
                "row_order": idx,
            }
        )
    return pd.DataFrame(rows)


def build_unit_table_tex(summary_df: pd.DataFrame, focal_inst: str) -> str:
    p_full_label, mncs_label = get_metric_labels()
    ordered_names = summary_df["institution_name"].tolist()

    pfull_cells = []
    mncs_cells = []
    for row in summary_df.itertuples(index=False):
        is_self = row.institution_id == focal_inst
        pfull_cells.append(fmt_cell(fmt_count(row.P_FULL), highlight=is_self))
        mncs_cells.append(fmt_cell(fmt_float(row.C_MNCS_FRAC), highlight=is_self))

    lines = [
        r"\begin{tabular}{@{}l" + "r" * len(ordered_names) + r"@{}}",
        r"  \toprule",
        r"  Indicator & " + " & ".join(r"\textbf{" + name + "}" for name in ordered_names) + r" \\",
        r"  \midrule",
        f"  {p_full_label} & " + " & ".join(pfull_cells) + r" \\",
        f"  {mncs_label} & " + " & ".join(mncs_cells) + r" \\",
        r"  \bottomrule",
        r"\end{tabular}",
    ]
    return "\n".join(lines) + "\n"


con = asset.connect()
rows = []
for inst in INSTITUTIONS:
    result = con.execute(q_diagonal(inst)).fetchone()
    rows.append(
        {
            "row_inst": inst,
            "col_inst": inst,
            "p_full": int(result[0]),
            "mncs": float(result[1]) if result[1] is not None else None,
        }
    )

for inst_a, inst_b in combinations_with_replacement(INSTITUTIONS, 2):
    if inst_a == inst_b:
        continue
    result = con.execute(q_pair(inst_a, inst_b)).fetchone()
    p_full = int(result[0])
    mncs = float(result[1]) if result[1] is not None else None
    rows.append({"row_inst": inst_a, "col_inst": inst_b, "p_full": p_full, "mncs": mncs})
    rows.append({"row_inst": inst_b, "col_inst": inst_a, "p_full": p_full, "mncs": mncs})
con.close()

matrix_df = build_complete_matrix(pd.DataFrame(rows))
for inst in INSTITUTIONS:
    unit_summary_df = build_unit_summary_df(matrix_df, inst)
    out = asset.inst_dir(inst)
    unit_summary_df.to_csv(out / "data.csv", index=False)
    (out / "table.tex").write_text(build_unit_table_tex(unit_summary_df, inst), encoding="utf-8")

ethdomain_out = asset.inst_dir("ethdomain")
(ethdomain_out / "data.csv").unlink(missing_ok=True)
(ethdomain_out / "table.tex").unlink(missing_ok=True)

print(f"exported to {len(INSTITUTIONS)} unit folders; removed ethdomain special-case outputs")
