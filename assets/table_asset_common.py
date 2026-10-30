from __future__ import annotations

from typing import Callable

import pandas as pd

from utility import shorten_country_name, shorten_institution_name


def tex_escape(text: object) -> str:
    return (
        str("" if text is None else text)
        .replace("\\", r"\textbackslash{}")
        .replace("{", r"\{")
        .replace("}", r"\}")
        .replace("_", r"\_")
        .replace("%", r"\%")
        .replace("&", r"\&")
        .replace("#", r"\#")
    )


def shorten_table_text_columns(
    df: pd.DataFrame,
    shorten_map: dict[str, str | Callable[[object], str]] | None = None,
) -> pd.DataFrame:
    out = df.copy()
    if not shorten_map:
        return out

    for column, rule in shorten_map.items():
        if column not in out.columns:
            continue

        if callable(rule):
            fn = rule
        elif rule == "institution":
            fn = lambda value: shorten_institution_name(None if pd.isna(value) else value)
        elif rule == "country":
            fn = lambda value: shorten_country_name(None if pd.isna(value) else value)
        else:
            raise ValueError(f"Unsupported shortening rule {rule!r} for column {column!r}")

        out[column] = out[column].map(fn)

    return out


def finalize_ranked_table_df(
    df: pd.DataFrame,
    *,
    sort_by: list[str],
    ascending: list[bool],
    top_n: int | None = None,
    shorten_map: dict[str, str | Callable[[object], str]] | None = None,
    row_order_col: str = "row_order",
    constants: dict[str, object] | None = None,
) -> pd.DataFrame:
    out = shorten_table_text_columns(df, shorten_map=shorten_map)
    out = out.sort_values(sort_by, ascending=ascending, kind="mergesort").reset_index(drop=True)
    if top_n is not None:
        out = out.head(top_n).reset_index(drop=True)
    out[row_order_col] = out.index + 1

    if constants:
        for key, value in constants.items():
            out[key] = value

    return out


def _parse_digits(raw: object) -> int | None:
    if raw is None or pd.isna(raw):
        return None
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _strip_trailing_zeros(text: str) -> str:
    if "." not in text:
        return text
    return text.rstrip("0").rstrip(".")


def _format_number(num: float, digits: int | None) -> str:
    if digits is None:
        base = f"{num:,.12f}"
        base = _strip_trailing_zeros(base)
    else:
        base = f"{num:,.{digits}f}"
    return base.replace(",", "{,}")


def _clean_meta_text(raw: object) -> str:
    if raw is None or pd.isna(raw):
        return ""
    text = str(raw).strip()
    return "" if text.lower() == "nan" else text


def _normalize_hex_color(color: str) -> str | None:
    raw = str(color).strip()
    if raw.startswith("#"):
        raw = raw[1:]
    if len(raw) != 6:
        return None
    if any(ch not in "0123456789abcdefABCDEF" for ch in raw):
        return None
    return raw.upper()


def build_rowcolor_command(color: str) -> str:
    raw = str(color).strip()
    if not raw:
        return ""
    hex_color = _normalize_hex_color(raw)
    if hex_color is not None:
        return rf"\rowcolor[HTML]{{{hex_color}}} "
    return rf"\rowcolor{{{raw}}} "


def resolve_latex_header(
    column: str,
    *,
    indicator_catalog_dict: dict[str, dict] | None = None,
    header_overrides: dict[str, str] | None = None,
) -> str:
    if header_overrides and column in header_overrides:
        return header_overrides[column]

    meta = (indicator_catalog_dict or {}).get(column, {})
    symbol_tex = _clean_meta_text(meta.get("symbol_tex"))
    if symbol_tex:
        return rf"\ensuremath{{{symbol_tex}}}"

    return tex_escape(column.replace("_", " ").title())


def format_table_cell(
    column: str,
    value: object,
    *,
    indicator_catalog_dict: dict[str, dict] | None = None,
    text_columns: set[str] | None = None,
    raw_latex_columns: set[str] | None = None,
) -> str:
    if value is None or pd.isna(value):
        return ""

    if raw_latex_columns and column in raw_latex_columns:
        return str(value)

    if text_columns and column in text_columns:
        return tex_escape(value)

    meta = (indicator_catalog_dict or {}).get(column, {})
    raw = str(value)
    num = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(num):
        return tex_escape(raw)

    digits = _parse_digits(meta.get("display_digits"))
    prefix = _clean_meta_text(meta.get("display_prefix"))
    suffix = _clean_meta_text(meta.get("display_suffix"))
    display_type = _clean_meta_text(meta.get("display_type"))
    type_suffix = ""

    if display_type == "percentage":
        num = float(num) * 100.0
        type_suffix = r"\%"

    base = _format_number(float(num), digits)
    if digits is None:
        base = _strip_trailing_zeros(base)

    return f"{prefix}{base}{suffix}{type_suffix}"


def build_basic_table_tex(
    df: pd.DataFrame,
    *,
    columns: list[str],
    indicator_catalog_dict: dict[str, dict] | None = None,
    header_overrides: dict[str, str] | None = None,
    text_columns: set[str] | None = None,
    raw_latex_columns: set[str] | None = None,
    alignments: dict[str, str] | None = None,
    resize_mode: str = "always",
    row_background_colors: tuple[str, str] | None = None,
) -> str:
    table_df = df.copy()
    colspec = "@{}" + "".join((alignments or {}).get(column, "l" if text_columns and column in text_columns else "r") for column in columns) + "@{}"

    lines: list[str] = []
    if resize_mode == "always":
        lines.append(r"\resizebox{\linewidth}{!}{%")
    elif resize_mode == "max_width":
        lines.append(r"\begin{adjustbox}{max width=\linewidth}")
    elif resize_mode != "none":
        raise ValueError(f"Unsupported resize_mode {resize_mode!r}")

    lines.append(r"\begin{tabular}{" + colspec + r"}")
    lines.append(r"  \toprule")
    lines.append(
        "  " + " & ".join(
            resolve_latex_header(
                column,
                indicator_catalog_dict=indicator_catalog_dict,
                header_overrides=header_overrides,
            )
            for column in columns
        ) + r" \\"
    )
    lines.append(r"  \midrule")

    for idx, (_, row) in enumerate(table_df.iterrows()):
        row_prefix = ""
        if row_background_colors:
            odd_color, even_color = row_background_colors
            row_color = odd_color if idx % 2 == 0 else even_color
            row_prefix = build_rowcolor_command(row_color)
        lines.append(
            "  " + row_prefix + " & ".join(
                format_table_cell(
                    column,
                    row.get(column, ""),
                    indicator_catalog_dict=indicator_catalog_dict,
                    text_columns=text_columns,
                    raw_latex_columns=raw_latex_columns,
                )
                for column in columns
            ) + r" \\"
        )

    lines.append(r"  \bottomrule")
    lines.append(r"\end{tabular}")
    if resize_mode == "always":
        lines.append(r"}")
    elif resize_mode == "max_width":
        lines.append(r"\end{adjustbox}")
    return "\n".join(lines) + "\n"
