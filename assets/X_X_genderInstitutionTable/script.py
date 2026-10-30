import pandas as pd

from core.asset import Asset
from utility import get_indicator_catalog_dict


REPORTS = [
    ("ethdomain", "ETH Domain", 1),
    ("ethz", "ETH Zurich", 2),
    ("epfl", "EPFL", 3),
    ("psi", "PSI", 4),
    ("wsl", "WSL", 5),
    ("empa", "Empa", 6),
    ("eawag", "Eawag", 7),
]

INDICATORS = [
    "A_AFF_AUTHORS",
    "A_FEMALE_INST",
    "A_MALE_INST",
    "PA_F_INST",
    "A_ALL_AUTHORS",
    "A_FEMALE_PUBS",
    "A_MALE_PUBS",
    "PA_F_PUBS",
    "RPA_F",
]

TABLE_SECTIONS = [
    (
        "Affiliated authors on own publication set",
        ["A_AFF_AUTHORS", "A_FEMALE_INST", "A_MALE_INST", "PA_F_INST"],
    ),
    (
        "All contributing authors on the same publication set",
        ["A_ALL_AUTHORS", "A_FEMALE_PUBS", "A_MALE_PUBS", "PA_F_PUBS"],
    ),
    ("Relative female representation", ["RPA_F"]),
]

COUNT_METRICS = {
    "A_AFF_AUTHORS",
    "A_FEMALE_INST",
    "A_MALE_INST",
    "A_ALL_AUTHORS",
    "A_FEMALE_PUBS",
    "A_MALE_PUBS",
}
PERCENT_METRICS = {"PA_F_INST", "PA_F_PUBS"}
RATIO_METRICS = {"RPA_F"}


def query_function(y0: int, y1: int) -> str:
    report_values = ",\n                ".join(
        f"('{report_name}', '{report_label}', {report_order})"
        for report_name, report_label, report_order in REPORTS
    )

    return f"""
        WITH target_reports(report_name, report_label, report_order) AS (
            VALUES
                {report_values}
        ),
        report_works AS (
            SELECT DISTINCT
                tr.report_name,
                tr.report_label,
                tr.report_order,
                rm.work_id,
                w.publication_year AS year
            FROM target_reports tr
            JOIN reports.report_membership rm
              ON rm.report_name = tr.report_name
            JOIN core.work w
              ON w.work_id = rm.work_id
            JOIN core.work_to_status s
              ON s.work_id = rm.work_id
            WHERE w.publication_year BETWEEN {y0} AND {y1}
              AND s.is_included = TRUE
        ),
        report_pub_counts AS (
            SELECT
                report_name,
                COUNT(DISTINCT work_id) AS n_pubs
            FROM report_works
            GROUP BY report_name
        ),
        wag_report_author AS (
            SELECT
                rw.report_name,
                wag.author_id,
                BOOL_OR(COALESCE(wag.assigned_to_institution, FALSE)) AS assigned_to_institution,
                MAX(
                    CASE
                        WHEN LOWER(COALESCE(wag.gender_effective, '')) = 'female'
                        THEN 1 ELSE 0
                    END
                ) AS has_female,
                MAX(
                    CASE
                        WHEN LOWER(COALESCE(wag.gender_effective, '')) = 'male'
                        THEN 1 ELSE 0
                    END
                ) AS has_male
            FROM report_works rw
            JOIN reports.work_author_gender wag
              ON wag.work_id = rw.work_id
             AND wag.report_name = rw.report_name
            WHERE wag.author_id IS NOT NULL
            GROUP BY rw.report_name, wag.author_id
        ),
        author_gender AS (
            SELECT
                report_name,
                author_id,
                assigned_to_institution,
                CASE
                    WHEN has_female = 1 AND has_male = 1 THEN 'unknown'
                    WHEN has_female = 1 THEN 'female'
                    WHEN has_male = 1 THEN 'male'
                    ELSE 'unknown'
                END AS gender
            FROM wag_report_author
        ),
        report_counts AS (
            SELECT
                tr.report_name,
                tr.report_label,
                tr.report_order,
                COALESCE(rpc.n_pubs, 0) AS n_pubs,
                COUNT(ag.author_id) AS A_ALL_AUTHORS,
                COUNT(ag.author_id) FILTER (WHERE ag.assigned_to_institution) AS A_AFF_AUTHORS,
                COUNT(ag.author_id) FILTER (
                    WHERE ag.assigned_to_institution AND ag.gender = 'female'
                ) AS A_FEMALE_INST_RAW,
                COUNT(ag.author_id) FILTER (
                    WHERE ag.assigned_to_institution AND ag.gender = 'male'
                ) AS A_MALE_INST_RAW,
                COUNT(ag.author_id) FILTER (WHERE ag.gender = 'female') AS A_FEMALE_PUBS_RAW,
                COUNT(ag.author_id) FILTER (WHERE ag.gender = 'male') AS A_MALE_PUBS_RAW
            FROM target_reports tr
            LEFT JOIN report_pub_counts rpc
              ON rpc.report_name = tr.report_name
            LEFT JOIN author_gender ag
              ON ag.report_name = tr.report_name
            GROUP BY tr.report_name, tr.report_label, tr.report_order, rpc.n_pubs
        )
        SELECT
            report_name,
            report_label,
            report_order,
            n_pubs,
            A_AFF_AUTHORS,
            CASE
                WHEN A_FEMALE_INST_RAW + A_MALE_INST_RAW > 0
                THEN A_FEMALE_INST_RAW ELSE NULL
            END AS A_FEMALE_INST,
            CASE
                WHEN A_FEMALE_INST_RAW + A_MALE_INST_RAW > 0
                THEN A_MALE_INST_RAW ELSE NULL
            END AS A_MALE_INST,
            CASE
                WHEN A_FEMALE_INST_RAW + A_MALE_INST_RAW > 0
                THEN ROUND(
                    CAST(A_FEMALE_INST_RAW AS DOUBLE)
                    / CAST(A_FEMALE_INST_RAW + A_MALE_INST_RAW AS DOUBLE),
                    6
                )
                ELSE NULL
            END AS PA_F_INST,
            A_ALL_AUTHORS,
            CASE
                WHEN A_FEMALE_PUBS_RAW + A_MALE_PUBS_RAW > 0
                THEN A_FEMALE_PUBS_RAW ELSE NULL
            END AS A_FEMALE_PUBS,
            CASE
                WHEN A_FEMALE_PUBS_RAW + A_MALE_PUBS_RAW > 0
                THEN A_MALE_PUBS_RAW ELSE NULL
            END AS A_MALE_PUBS,
            CASE
                WHEN A_FEMALE_PUBS_RAW + A_MALE_PUBS_RAW > 0
                THEN ROUND(
                    CAST(A_FEMALE_PUBS_RAW AS DOUBLE)
                    / CAST(A_FEMALE_PUBS_RAW + A_MALE_PUBS_RAW AS DOUBLE),
                    6
                )
                ELSE NULL
            END AS PA_F_PUBS,
            CASE
                WHEN A_FEMALE_INST_RAW + A_MALE_INST_RAW > 0
                 AND A_FEMALE_PUBS_RAW + A_MALE_PUBS_RAW > 0
                 AND A_FEMALE_PUBS_RAW > 0
                THEN ROUND(
                    (
                        CAST(A_FEMALE_INST_RAW AS DOUBLE)
                        / CAST(A_FEMALE_INST_RAW + A_MALE_INST_RAW AS DOUBLE)
                    )
                    /
                    (
                        CAST(A_FEMALE_PUBS_RAW AS DOUBLE)
                        / CAST(A_FEMALE_PUBS_RAW + A_MALE_PUBS_RAW AS DOUBLE)
                    ),
                    6
                )
                ELSE NULL
            END AS RPA_F
        FROM report_counts
        ORDER BY report_order;
    """


def tex_escape_text(text: str) -> str:
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


def fmt_count(value) -> str:
    if value is None or pd.isna(value):
        return r"\textit{n/a}"
    return f"{int(round(float(value))):,}"


def fmt_pct(value, digits: int = 1) -> str:
    if value is None or pd.isna(value):
        return r"\textit{n/a}"
    return f"{100.0 * float(value):.{digits}f}\\%"


def fmt_float(value, digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return r"\textit{n/a}"
    return f"{float(value):.{digits}f}"


def metric_label(metric: str, indicator_catalog: dict) -> str:
    symbol_tex = str((indicator_catalog.get(metric, {}) or {}).get("symbol_tex", "")).strip()
    if symbol_tex and symbol_tex.lower() not in {"nan", "none"}:
        return f"${symbol_tex}$"
    return tex_escape_text(metric)


asset = Asset(script_file=__file__, institutions=["ethdomain"])
indicator_catalog = get_indicator_catalog_dict()
metric_labels = {metric: metric_label(metric, indicator_catalog) for metric in INDICATORS}


for inst, con in asset.iterate_institutions():
    raw_df = asset.extract(
        con=con,
        inst=inst,
        query=query_function(asset.year_first, asset.year_last),
        out_name="raw_data.csv",
    )

    data_df = raw_df.copy()
    numeric_cols = ["report_order", "n_pubs"] + INDICATORS
    for col in numeric_cols:
        data_df[col] = pd.to_numeric(data_df[col], errors="coerce")

    data_df = data_df.dropna(subset=["report_name", "report_label", "report_order"]).copy()
    data_df["report_order"] = data_df["report_order"].astype(int)
    data_df["report_key"] = data_df["report_name"].where(
        data_df["report_name"] != "ethdomain",
        "overall",
    )
    data_df["id"] = data_df["report_key"]
    data_df = data_df.sort_values("report_order").reset_index(drop=True)

    member_mask = data_df["report_name"] != "ethdomain"
    data_df["A_AFF_AUTHORS_INST"] = data_df["A_AFF_AUTHORS"].where(member_mask)
    data_df["A_ALL_AUTHORS_INST"] = data_df["A_ALL_AUTHORS"].where(member_mask)
    data_df["PA_F_INST_INST"] = data_df["PA_F_INST"].where(member_mask)
    data_df["PA_F_PUBS_INST"] = data_df["PA_F_PUBS"].where(member_mask)
    data_df["RPA_F_INST"] = data_df["RPA_F"].where(member_mask)

    table_rows = []
    for indicator in INDICATORS:
        for report_name, report_label, report_order in REPORTS:
            hit = data_df[data_df["report_name"] == report_name]
            table_rows.append(
                {
                    "indicator": indicator,
                    "report_name": report_name,
                    "report_label": report_label,
                    "report_order": report_order,
                    "value": hit.iloc[0][indicator] if not hit.empty else None,
                }
            )
    table_data_df = pd.DataFrame(table_rows)

    colspec = "@{}l" + "r|rrrrrr" + "@{}"
    n_cols = len(REPORTS) + 1
    lines = []
    lines.append(r"\begin{adjustbox}{max width=\linewidth}")
    lines.append(rf"\begin{{tabular}}{{{colspec}}}")
    lines.append(r"  \toprule")
    lines.append(r"  \multicolumn{2}{c}{} & \multicolumn{6}{c}{\textbf{ETH Domain Members}} \\")
    lines.append(r"  \cmidrule(lr){3-8}")
    lines.append(
        "  Indicator & "
        + r"\shortstack[c]{ETH\\Domain} & \shortstack[c]{ETH\\Zurich} & EPFL & PSI & WSL & Empa & Eawag \\"
    )
    lines.append(r"  \midrule")

    value_map = data_df.set_index("report_name").to_dict(orient="index")
    for section_i, (section_title, section_indicators) in enumerate(TABLE_SECTIONS):
        if section_i > 0:
            lines.append(r"  \midrule")
        lines.append(rf"  \multicolumn{{{n_cols}}}{{c}}{{{section_title}}} \\")
        lines.append(r"  \midrule")

        for indicator in section_indicators:
            values = []
            for report_name, _, _ in REPORTS:
                value = value_map.get(report_name, {}).get(indicator)
                if indicator in COUNT_METRICS:
                    values.append(fmt_count(value))
                elif indicator in PERCENT_METRICS:
                    values.append(fmt_pct(value, 1))
                elif indicator in RATIO_METRICS:
                    values.append(fmt_float(value, 2))
                else:
                    values.append(fmt_count(value))
            lines.append(f"  {metric_labels[indicator]} & " + " & ".join(values) + r" \\")

    lines.append(r"  \bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{adjustbox}")
    lines.append("")

    out = asset.inst_dir(inst)
    data_df.to_csv(out / "data.csv", index=False)
    table_data_df.to_csv(out / "table_data.csv", index=False)
    (out / "table.tex").write_text("\n".join(lines), encoding="utf-8")
