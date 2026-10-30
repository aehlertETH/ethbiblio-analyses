import pandas as pd

from core.asset import Asset
from utility import get_indicator_catalog_dict

ROW_ORDER = ["affiliated", "all"]


def q_gender_raw(inst: str, y0: int, y1: int) -> str:
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
        wag_author AS (
            SELECT
                wag.author_id,
                BOOL_OR(wag.assigned_to_institution) AS assigned_to_institution,
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
             AND wag.report_name = '{inst}'
            WHERE wag.author_id IS NOT NULL
            GROUP BY wag.author_id
        )
        SELECT
            author_id,
            assigned_to_institution,
            CASE
                WHEN has_female = 1 AND has_male = 1 THEN 'unknown'
                WHEN has_female = 1 THEN 'female'
                WHEN has_male = 1 THEN 'male'
                ELSE 'unknown'
            END AS gender
        FROM wag_author
        ORDER BY author_id;
    """


def to_bool(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)
    return (
        series.astype("string")
        .str.strip()
        .str.lower()
        .isin({"1", "true", "t", "yes", "y"})
    )


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


def ensuremath_wrap(s: str) -> str:
    if not s:
        return s
    if r"\ensuremath{" in s:
        return s
    return rf"\ensuremath{{{s}}}"


def fmt_count(value) -> str:
    if value is None or pd.isna(value):
        return r"\textit{n/a}"
    return f"{int(round(float(value))):,}"


def fmt_pct(value, digits: int = 1) -> str:
    if value is None or pd.isna(value):
        return r"\textit{n/a}"
    return f"{100.0 * float(value):.{digits}f}\\%"


def build_author_base(raw_df: pd.DataFrame) -> pd.DataFrame:
    if raw_df.empty:
        return pd.DataFrame(columns=["author_id", "assigned_to_institution", "gender"])

    df = raw_df.copy()
    df["author_id"] = pd.to_numeric(df["author_id"], errors="coerce")
    df = df.dropna(subset=["author_id"]).copy()
    if df.empty:
        return pd.DataFrame(columns=["author_id", "assigned_to_institution", "gender"])

    df["author_id"] = df["author_id"].astype("int64")
    df["assigned_to_institution"] = to_bool(df["assigned_to_institution"])
    df["gender"] = (
        df["gender"]
        .astype("string")
        .str.strip()
        .str.lower()
        .where(lambda s: s.isin({"female", "male"}), "unknown")
        .fillna("unknown")
    )

    return df[["author_id", "assigned_to_institution", "gender"]].drop_duplicates()


def build_scope_row(scope: str, df: pd.DataFrame) -> dict[str, str | int | float | None]:
    total = int(len(df))
    female = int((df["gender"] == "female").sum())
    male = int((df["gender"] == "male").sum())
    unknown = int((df["gender"] == "unknown").sum())
    identified = female + male

    pa_identified = (identified / total) if total > 0 else None
    pa_unknown = (unknown / total) if total > 0 else None
    pa_female_identified = (female / identified) if identified > 0 else None
    pa_male_identified = (male / identified) if identified > 0 else None

    return {
        "scope": scope,
        "A_TOTAL_AUTHORS": total,
        "A_IDENTIFIED_AUTHORS": identified,
        "A_UNKNOWN_AUTHORS": unknown,
        "PA_IDENTIFIED_AUTHORS": round(pa_identified, 6) if pa_identified is not None else None,
        "PA_UNKNOWN_AUTHORS": round(pa_unknown, 6) if pa_unknown is not None else None,
        "A_FEMALE_AUTHORS": female,
        "A_MALE_AUTHORS": male,
        "PA_FEMALE_IDENTIFIED": round(pa_female_identified, 6) if pa_female_identified is not None else None,
        "PA_MALE_IDENTIFIED": round(pa_male_identified, 6) if pa_male_identified is not None else None,
    }


def build_table_tex(df: pd.DataFrame) -> str:
    rows = []
    for scope in ROW_ORDER:
        sub = df[df["scope"] == scope]
        if sub.empty:
            rows.append(
                {
                    "scope": scope,
                    "A_TOTAL_AUTHORS": None,
                    "A_IDENTIFIED_AUTHORS": None,
                    "A_UNKNOWN_AUTHORS": None,
                    "PA_IDENTIFIED_AUTHORS": None,
                    "PA_UNKNOWN_AUTHORS": None,
                }
            )
        else:
            rows.append(sub.iloc[0].to_dict())

    lines = []
    lines.append(r"\begin{adjustbox}{max width=\linewidth}")
    lines.append(r"\begin{tabular}{@{}lrrrr@{}}")
    lines.append(r"  \toprule")
    lines.append(r"   & Total authors & Identified & Unknown & Unknown share \\")
    lines.append(r"  \midrule")

    for row in rows:
        if row["scope"] == "affiliated":
            scope_text = "Affiliated authors"
            scope_symbol_tex = str(indicator_catalog_dict["A_AFF_AUTHORS"]["symbol_tex"]).strip()
        else:
            scope_text = "All contributing authors"
            scope_symbol_tex = str(indicator_catalog_dict["A_ALL_AUTHORS"]["symbol_tex"]).strip()

        lines.append(
            "  "
            + tex_escape_text(scope_text)
            + " ("
            + ensuremath_wrap(scope_symbol_tex)
            + ")"
            + " & "
            + " & ".join(
                [
                    fmt_count(row.get("A_TOTAL_AUTHORS")),
                    fmt_count(row.get("A_IDENTIFIED_AUTHORS")),
                    fmt_count(row.get("A_UNKNOWN_AUTHORS")),
                    fmt_pct(row.get("PA_UNKNOWN_AUTHORS"), 1),
                ]
            )
            + r" \\"
        )

    lines.append(r"  \bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{adjustbox}")
    lines.append("")
    return "\n".join(lines)


asset = Asset(script_file=__file__)
indicator_catalog_dict = get_indicator_catalog_dict()

for inst, con in asset.iterate_institutions():
    raw_df = asset.extract(
        con=con,
        inst=inst,
        query=q_gender_raw(inst, asset.year_first, asset.year_last),
        out_name="raw_data.csv",
    )

    author_base = build_author_base(raw_df)

    affiliated_df = author_base[author_base["assigned_to_institution"]].copy()
    all_df = author_base.copy()

    rows = [
        build_scope_row("affiliated", affiliated_df),
        build_scope_row("all", all_df),
    ]

    out_df = pd.DataFrame(rows)
    out_df["row_order"] = out_df["scope"].map({"affiliated": 1, "all": 2}).fillna(99).astype(int)
    out_df = out_df.sort_values(["row_order", "scope"]).reset_index(drop=True)

    out = asset.inst_dir(inst)
    out_df.to_csv(out / "data.csv", index=False)
    (out / "table.tex").write_text(build_table_tex(out_df), encoding="utf-8")
