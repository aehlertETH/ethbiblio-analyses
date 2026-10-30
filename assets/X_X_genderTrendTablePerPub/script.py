import pandas as pd

from core.asset import Asset
from utility import get_indicator_catalog_dict


MA_YEAR_COL = "MA_year"
OVERALL_LABEL = "Overall"
INDICATORS = [
    "A_AFF_AUTHORS_AVG_PUB",
    "A_FEMALE_INST_AVG_PUB",
    "PA_F_INST_AVG_PUB",
    "PA_F_INST_SHARE_AVG_PUB",
    "A_ALL_AUTHORS_AVG_PUB",
    "A_FEMALE_PUBS_AVG_PUB",
    "PA_F_PUBS_AVG_PUB",
    "PA_F_PUBS_SHARE_AVG_PUB",
    "RPA_F_AVG_PUB",
    "RPA_F_SHARE_AVG_PUB",
]
TABLE_SECTIONS = [
    (
        "Affiliated authors on own publication set",
        [
            "A_AFF_AUTHORS_AVG_PUB",
            "A_FEMALE_INST_AVG_PUB",
            "PA_F_INST_AVG_PUB",
            "PA_F_INST_SHARE_AVG_PUB",
        ],
    ),
    (
        "All contributing authors on the same publication set",
        [
            "A_ALL_AUTHORS_AVG_PUB",
            "A_FEMALE_PUBS_AVG_PUB",
            "PA_F_PUBS_AVG_PUB",
            "PA_F_PUBS_SHARE_AVG_PUB",
        ],
    ),
    ("Relative female representation", ["RPA_F_AVG_PUB", "RPA_F_SHARE_AVG_PUB"]),
]
AVG_METRICS = {
    "A_AFF_AUTHORS_AVG_PUB",
    "A_FEMALE_INST_AVG_PUB",
    "A_ALL_AUTHORS_AVG_PUB",
    "A_FEMALE_PUBS_AVG_PUB",
}
PERCENT_METRICS = {
    "PA_F_INST_AVG_PUB",
    "PA_F_INST_SHARE_AVG_PUB",
    "PA_F_PUBS_AVG_PUB",
    "PA_F_PUBS_SHARE_AVG_PUB",
}
RATIO_METRICS = {"RPA_F_AVG_PUB", "RPA_F_SHARE_AVG_PUB"}


def query_function(inst: str, y0: int, y1: int) -> str:
    return f"""
        WITH report_works AS (
            SELECT DISTINCT
                rm.work_id,
                w.publication_year AS year
            FROM reports.report_membership rm
            JOIN core.work w
              ON w.work_id = rm.work_id
            JOIN core.work_to_status s
              ON s.work_id = rm.work_id
            WHERE rm.report_name = '{inst}'
              AND w.publication_year BETWEEN {y0} AND {y1}
              AND s.is_included = TRUE
        ),
        wag_work_author AS (
            SELECT
                rw.work_id,
                rw.year,
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
            LEFT JOIN reports.work_author_gender wag
              ON wag.work_id = rw.work_id
             AND wag.report_name = '{inst}'
             AND wag.author_id IS NOT NULL
            GROUP BY rw.work_id, rw.year, wag.author_id
        ),
        author_gender AS (
            SELECT
                work_id,
                year,
                author_id,
                assigned_to_institution,
                CASE
                    WHEN has_female = 1 AND has_male = 1 THEN 'unknown'
                    WHEN has_female = 1 THEN 'female'
                    WHEN has_male = 1 THEN 'male'
                    ELSE 'unknown'
                END AS gender
            FROM wag_work_author
            WHERE author_id IS NOT NULL
        ),
        per_work AS (
            SELECT
                rw.work_id,
                rw.year,
                COUNT(ag.author_id) FILTER (WHERE ag.assigned_to_institution) AS aff_authors,
                COUNT(ag.author_id) FILTER (
                    WHERE ag.assigned_to_institution AND ag.gender = 'female'
                ) AS aff_female,
                COUNT(ag.author_id) FILTER (
                    WHERE ag.assigned_to_institution AND ag.gender = 'male'
                ) AS aff_male,
                COUNT(ag.author_id) FILTER (
                    WHERE ag.assigned_to_institution AND ag.gender = 'unknown'
                ) AS aff_unknown,
                COUNT(ag.author_id) AS all_authors,
                COUNT(ag.author_id) FILTER (WHERE ag.gender = 'female') AS all_female,
                COUNT(ag.author_id) FILTER (WHERE ag.gender = 'male') AS all_male,
                COUNT(ag.author_id) FILTER (WHERE ag.gender = 'unknown') AS all_unknown
            FROM report_works rw
            LEFT JOIN author_gender ag
              ON ag.work_id = rw.work_id
            GROUP BY rw.work_id, rw.year
        )
        SELECT *
        FROM per_work
        ORDER BY year, work_id;
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


def fmt_float(value, digits: int) -> str:
    if value is None or pd.isna(value):
        return r"\textit{n/a}"
    return f"{float(value):.{digits}f}"


def fmt_pct(value, digits: int) -> str:
    if value is None or pd.isna(value):
        return r"\textit{n/a}"
    return f"{100.0 * float(value):.{digits}f}\\%"


def metric_label(metric: str, indicator_catalog: dict) -> str:
    symbol_tex = str((indicator_catalog.get(metric, {}) or {}).get("symbol_tex", "")).strip()
    if symbol_tex and symbol_tex.lower() not in {"nan", "none"}:
        return f"${symbol_tex}$"
    return tex_escape_text(metric)


asset = Asset(script_file=__file__)
indicator_catalog = get_indicator_catalog_dict()
metric_labels = {metric: metric_label(metric, indicator_catalog) for metric in INDICATORS}
rotation_raw = float(getattr(asset, "table_header_rotation_deg", 60))
header_rotation = int(rotation_raw) if float(rotation_raw).is_integer() else rotation_raw
ma_window = max(1, int(asset.year_range_moving))
window_starts = list(range(asset.year_first, asset.year_last - ma_window + 2))
window_labels = [f"{year}-{year + ma_window - 1}" for year in window_starts]


for inst, con in asset.iterate_institutions():
    raw_df = asset.extract(
        con=con,
        inst=inst,
        query=query_function(inst, asset.year_first, asset.year_last),
        out_name="raw_data.csv",
    )

    df = raw_df.copy()
    numeric_cols = [
        "work_id",
        "year",
        "aff_authors",
        "aff_female",
        "aff_male",
        "aff_unknown",
        "all_authors",
        "all_female",
        "all_male",
        "all_unknown",
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["work_id", "year"]).copy()
    if not df.empty:
        df["year"] = df["year"].astype(int)
        df = df.sort_values(["year", "work_id"]).drop_duplicates(subset=["work_id"], keep="first")

    rows = []
    periods = [
        (label, year, year + ma_window - 1, False)
        for label, year in zip(window_labels, window_starts)
    ]
    periods.append((OVERALL_LABEL, asset.year_first, asset.year_last, True))

    for label, y0, y1, is_full_period in periods:
        sub = df[(df["year"] >= y0) & (df["year"] <= y1)].copy()
        n_pubs = int(sub["work_id"].nunique()) if not sub.empty else 0

        if n_pubs > 0:
            aff_authors_avg = float(sub["aff_authors"].mean())
            aff_female_avg = float(sub["aff_female"].mean())
            aff_male_avg = float(sub["aff_male"].mean())
            all_authors_avg = float(sub["all_authors"].mean())
            all_female_avg = float(sub["all_female"].mean())
            all_male_avg = float(sub["all_male"].mean())
        else:
            aff_authors_avg = 0.0
            aff_female_avg = 0.0
            aff_male_avg = 0.0
            all_authors_avg = 0.0
            all_female_avg = 0.0
            all_male_avg = 0.0

        aff_known_avg = aff_female_avg + aff_male_avg
        all_known_avg = all_female_avg + all_male_avg
        pa_f_inst = aff_female_avg / aff_known_avg if aff_known_avg > 0 else None
        pa_f_pubs = all_female_avg / all_known_avg if all_known_avg > 0 else None
        rpa_f = pa_f_inst / pa_f_pubs if pa_f_inst is not None and pa_f_pubs not in (None, 0) else None
        aff_known = sub["aff_female"] + sub["aff_male"] if not sub.empty else pd.Series(dtype="float64")
        all_known = sub["all_female"] + sub["all_male"] if not sub.empty else pd.Series(dtype="float64")
        aff_pub_share = sub.loc[aff_known > 0, "aff_female"] / aff_known.loc[aff_known > 0]
        all_pub_share = sub.loc[all_known > 0, "all_female"] / all_known.loc[all_known > 0]
        pa_f_inst_share_avg = float(aff_pub_share.mean()) if not aff_pub_share.empty else None
        pa_f_pubs_share_avg = float(all_pub_share.mean()) if not all_pub_share.empty else None
        rpa_f_share_avg = (
            pa_f_inst_share_avg / pa_f_pubs_share_avg
            if pa_f_inst_share_avg is not None and pa_f_pubs_share_avg not in (None, 0)
            else None
        )

        rows.append(
            {
                MA_YEAR_COL: label,
                "start_year": y0,
                "end_year": y1,
                "is_full_period": is_full_period,
                "n_pubs": n_pubs,
                "A_AFF_AUTHORS_AVG_PUB": round(aff_authors_avg, 6),
                "A_FEMALE_INST_AVG_PUB": round(aff_female_avg, 6),
                "PA_F_INST_AVG_PUB": round(pa_f_inst, 6) if pa_f_inst is not None else None,
                "PA_F_INST_SHARE_AVG_PUB": (
                    round(pa_f_inst_share_avg, 6) if pa_f_inst_share_avg is not None else None
                ),
                "A_ALL_AUTHORS_AVG_PUB": round(all_authors_avg, 6),
                "A_FEMALE_PUBS_AVG_PUB": round(all_female_avg, 6),
                "PA_F_PUBS_AVG_PUB": round(pa_f_pubs, 6) if pa_f_pubs is not None else None,
                "PA_F_PUBS_SHARE_AVG_PUB": (
                    round(pa_f_pubs_share_avg, 6) if pa_f_pubs_share_avg is not None else None
                ),
                "RPA_F_AVG_PUB": round(rpa_f, 6) if rpa_f is not None else None,
                "RPA_F_SHARE_AVG_PUB": round(rpa_f_share_avg, 6) if rpa_f_share_avg is not None else None,
                "id": label,
            }
        )

    data_df = pd.DataFrame(rows)
    table_data_df = data_df.melt(
        id_vars=[MA_YEAR_COL],
        value_vars=INDICATORS,
        var_name="indicator",
        value_name="value",
    )

    header_labels = window_labels + [OVERALL_LABEL]
    colspec = "@{}l" + ("r" * len(window_labels)) + "|r@{}"
    n_cols = len(header_labels) + 1

    lines = []
    lines.append(r"\begin{adjustbox}{max width=\linewidth}%")
    lines.append(rf"\begin{{tabular}}{{{colspec}}}")
    lines.append(r"  \toprule")
    header_cells = [
        rf"\rotatebox[origin=c]{{{header_rotation}}}{{{tex_escape_text(label)}}}"
        for label in header_labels
    ]
    lines.append("  Indicator & " + " & ".join(header_cells) + r" \\")
    lines.append(r"  \midrule")

    value_map = data_df.set_index(MA_YEAR_COL).to_dict(orient="index")
    for section_i, (section_title, section_indicators) in enumerate(TABLE_SECTIONS):
        if section_i > 0:
            lines.append(r"  \midrule")
        lines.append(rf"  \multicolumn{{{n_cols}}}{{c}}{{{section_title}}} \\")
        lines.append(r"  \midrule")

        for indicator in section_indicators:
            values = []
            for label in header_labels:
                value = value_map.get(label, {}).get(indicator)
                if indicator in PERCENT_METRICS:
                    values.append(fmt_pct(value, 1))
                elif indicator in RATIO_METRICS:
                    values.append(fmt_float(value, 2))
                else:
                    values.append(fmt_float(value, 2))
            lines.append(f"  {metric_labels[indicator]} & " + " & ".join(values) + r" \\")

    lines.append(r"  \bottomrule")
    lines.append(r"\end{tabular}%")
    lines.append(r"\end{adjustbox}")
    lines.append("")

    out = asset.inst_dir(inst)
    data_df.to_csv(out / "data.csv", index=False)
    table_data_df.to_csv(out / "table_data.csv", index=False)
    (out / "table.tex").write_text("\n".join(lines), encoding="utf-8")
