import re

import pandas as pd


ANNOTATION_PLACEHOLDER_MARKER = r"\textsuperscript{\normalsize OPENALEXMARK}"
ANNOTATION_ROW_TEXT_COLOR = "555555"
ANNOTATION_ROW_PREFIX_RE = re.compile(r"^(\s*(?:\\rowcolor(?:\[[^\]]+\])?\{[^{}]+\}\s*)?)(.*)$")
RANKING_MACRO_EXCLUSION_COL = "exclude_from_ranking_macros"
RANKING_MACRO_EXCLUSION_TRUE_VALUES = {"1", "true", "t", "yes", "y", "on"}

ANNOTATED_INSTITUTIONS = {
    "4210092485": {
        "symbol": "*",
        "exclude_from_ranking_macros": True,
        "error_type": "OpenAlex metadata issue",
        "explanation": (
            r"The marked institution is retained for transparency, but reflects an affiliation error. "
            r"The underlying publications are mostly affiliated with the "
            r"'Institute for Chemical and Bioengineering, ETH Zurich, 8093 Zurich, Switzerland' "
            r"and were incorrectly assigned by OpenAlex to Bioengineering (Switzerland). This record "
            r"should not be interpreted as evidence of a substantive external partner institution."
        ),
    },
    "1299204452": {
        "symbol": r"$\dagger$",
        "exclude_from_ranking_macros": True,
        "error_type": "ROR metadata issue",
        "explanation": (
            r"The marked institution is retained for transparency, but reflects an affiliation metadata issue. "
            r"The institution is part of the University of Bern, but this relationship is not represented "
            r"in ROR or OpenAlex metadata. As a result, it is not integrated under the University of Bern "
            r"in the underlying data and should be interpreted with caution."
        ),
    },
}


def _validate_annotated_institutions() -> None:
    for institution_id, annotation in ANNOTATED_INSTITUTIONS.items():
        if RANKING_MACRO_EXCLUSION_COL not in annotation:
            raise ValueError(
                f"ANNOTATED_INSTITUTIONS[{institution_id!r}] is missing "
                f"{RANKING_MACRO_EXCLUSION_COL!r}"
            )
        if type(annotation[RANKING_MACRO_EXCLUSION_COL]) is not bool:
            raise ValueError(
                f"ANNOTATED_INSTITUTIONS[{institution_id!r}][{RANKING_MACRO_EXCLUSION_COL!r}] "
                "must be a boolean"
            )


_validate_annotated_institutions()
ANNOTATED_INSTITUTION_IDS = set(ANNOTATED_INSTITUTIONS)
RANKING_MACRO_EXCLUDED_INSTITUTION_IDS = {
    institution_id
    for institution_id, annotation in ANNOTATED_INSTITUTIONS.items()
    if annotation[RANKING_MACRO_EXCLUSION_COL]
}


def parse_ranking_macro_exclusion_flag(value: object) -> bool:
    if type(value) is bool:
        return value
    return str(value).strip().lower() in RANKING_MACRO_EXCLUSION_TRUE_VALUES


def is_ranking_macro_excluded_institution_id(institution_id: object) -> bool:
    key = str(institution_id).strip()
    return key in RANKING_MACRO_EXCLUDED_INSTITUTION_IDS


def add_ranking_macro_exclusion_flags(
    df: pd.DataFrame,
    *,
    institution_id_col: str = "institution_id",
    output_col: str = RANKING_MACRO_EXCLUSION_COL,
) -> pd.DataFrame:
    if institution_id_col not in df.columns:
        return df

    out = df.copy()
    ids = out[institution_id_col].astype("string").str.strip()
    out[output_col] = ids.isin(RANKING_MACRO_EXCLUDED_INSTITUTION_IDS).astype(int)
    return out


def ranking_macro_exclusion_mask(
    df: pd.DataFrame,
    *,
    institution_id_col: str = "institution_id",
    exclusion_col: str = RANKING_MACRO_EXCLUSION_COL,
) -> pd.Series:
    if exclusion_col in df.columns:
        return df[exclusion_col].map(parse_ranking_macro_exclusion_flag).fillna(False)

    if institution_id_col in df.columns:
        ids = df[institution_id_col].astype("string").str.strip()
        return ids.isin(RANKING_MACRO_EXCLUDED_INSTITUTION_IDS)

    return pd.Series(False, index=df.index)


def filter_ranking_macro_eligible_rows(
    df: pd.DataFrame,
    *,
    institution_id_col: str = "institution_id",
    exclusion_col: str = RANKING_MACRO_EXCLUSION_COL,
) -> pd.DataFrame:
    mask = ranking_macro_exclusion_mask(
        df,
        institution_id_col=institution_id_col,
        exclusion_col=exclusion_col,
    )
    return df.loc[~mask].copy()


def row_symbol_tex(annotation: dict) -> str:
    if annotation.get("row_symbol_tex"):
        return annotation["row_symbol_tex"]
    return rf"\textsuperscript{{\normalsize {annotation['symbol']}}}"


def note_symbol_tex(annotation: dict) -> str:
    if annotation.get("note_symbol_tex"):
        return annotation["note_symbol_tex"]
    return rf"\textsuperscript{{{annotation['symbol']}}}"


ANNOTATION_NOTES_BY_ID = {
    institution_id: (
        rf"{note_symbol_tex(annotation)} {annotation['error_type']}: {annotation['explanation']}"
    )
    for institution_id, annotation in ANNOTATED_INSTITUTIONS.items()
}


def annotation_for_institution_id(institution_id: object) -> dict | None:
    key = str(institution_id).strip()
    return ANNOTATED_INSTITUTIONS.get(key)


def annotation_note_for_institution_id(institution_id: object) -> str | None:
    key = str(institution_id).strip()
    return ANNOTATION_NOTES_BY_ID.get(key)


def figure_symbol_text(annotation: dict) -> str:
    return str(annotation.get("figure_symbol", annotation["symbol"]))


def figure_note_for_institution_id(institution_id: object) -> str | None:
    annotation = annotation_for_institution_id(institution_id)
    if not annotation:
        return None
    return (
        f"{figure_symbol_text(annotation)} {annotation['error_type']}: "
        f"{annotation['explanation']}"
    )


def annotation_notes_for_df(df: pd.DataFrame) -> list[str]:
    if "institution_id" not in df.columns:
        return []

    notes = []
    seen = set()
    for institution_id in df["institution_id"].astype("string"):
        note = annotation_note_for_institution_id(institution_id)
        if note and note not in seen:
            notes.append(note)
            seen.add(note)
    return notes


def figure_notes_for_df(df: pd.DataFrame) -> list[str]:
    if "institution_id" not in df.columns:
        return []

    notes = []
    seen = set()
    for institution_id in df["institution_id"].astype("string"):
        note = figure_note_for_institution_id(institution_id)
        if note and note not in seen:
            notes.append(note)
            seen.add(note)
    return notes


def add_annotation_symbols_to_labels(
    df: pd.DataFrame,
    *,
    label_col: str = "label_text",
    institution_id_col: str = "institution_id",
) -> pd.DataFrame:
    if label_col not in df.columns or institution_id_col not in df.columns:
        return df

    out = df.copy()
    for idx, row in out.iterrows():
        annotation = annotation_for_institution_id(row.get(institution_id_col))
        if not annotation:
            continue
        label = str(row.get(label_col, "")).strip()
        if not label:
            continue
        out.at[idx, label_col] = label + figure_symbol_text(annotation)
    return out


def color_table_row_text(line: str, text_color: str, cell_indexes: set[int]) -> str:
    if not text_color:
        return line

    row_end = ""
    row_body = line
    if row_body.endswith(r" \\"):
        row_body = row_body[:-3]
        row_end = r" \\"

    cells = row_body.split(" & ")
    if len(cells) < 2:
        return line

    for cell_idx in cell_indexes:
        if cell_idx >= len(cells):
            continue

        if cell_idx == 0:
            match = ANNOTATION_ROW_PREFIX_RE.match(cells[cell_idx])
            if match:
                prefix, cell = match.groups()
                cells[cell_idx] = prefix + rf"\textcolor[HTML]{{{text_color}}}{{{cell}}}"
            continue

        cells[cell_idx] = rf"\textcolor[HTML]{{{text_color}}}{{{cells[cell_idx]}}}"

    return " & ".join(cells) + row_end


def apply_marked_table_row_styles(
    table_tex: str,
    table_df: pd.DataFrame,
    *,
    text_cell_indexes: set[int],
) -> str:
    marked_annotations = []
    if "institution_id" in table_df.columns:
        for _, row in table_df.iterrows():
            annotation = annotation_for_institution_id(row.get("institution_id"))
            if annotation:
                marked_annotations.append(annotation)

    annotation_idx = 0
    lines = []
    for line in table_tex.splitlines():
        if ANNOTATION_PLACEHOLDER_MARKER not in line:
            lines.append(line)
            continue

        if annotation_idx >= len(marked_annotations):
            lines.append(line)
            continue

        annotation = marked_annotations[annotation_idx]
        annotation_idx += 1
        text_color = annotation.get("row_text_color", ANNOTATION_ROW_TEXT_COLOR)
        line = line.replace(ANNOTATION_PLACEHOLDER_MARKER, row_symbol_tex(annotation), 1)
        lines.append(color_table_row_text(line, text_color, text_cell_indexes))

    return "\n".join(lines) + "\n"


def add_table_note_below(table_tex: str, notes: list[str]) -> str:
    if not notes:
        return table_tex
    return (
        r"\begingroup" + "\n"
        + r"\setbox0=\hbox{%" + "\n"
        + table_tex.rstrip() + "\n"
        + r"}%" + "\n"
        + r"\begin{minipage}{\wd0}" + "\n"
        + r"\usebox0" + "\n"
        + r"\vspace{0.45ex}" + "\n"
        + r"\noindent\rule{\linewidth}{0.25pt}" + "\n"
        + r"\vspace{0.25ex}" + "\n"
        + r"{\scriptsize\raggedright "
        + r"\\ ".join(notes)
        + r"\par}" + "\n"
        + r"\end{minipage}" + "\n"
        + r"\endgroup" + "\n"
    )
