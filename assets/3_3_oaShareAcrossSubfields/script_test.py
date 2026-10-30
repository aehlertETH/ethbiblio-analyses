"""
Validation checks for 3_3_oaShareAcrossSubfieldsMatplotlib.

Checks:
- Subfield rows have non-negative publication counts (full + fractional).
- OA publication shares are in [0, 1] for full and fractional counting.
- Ratios equal institution share / field share within tolerance.
- Exported delta column equals (OA_PP_inst - OA_PP_field) * 100.
- Layout debug labels are inside panel-specific x-limits (no spillover).
"""

from pathlib import Path

import pandas as pd


INST = "ethz"


def main() -> None:
    base = Path(__file__).resolve().parent / INST
    data_path = base / "data.csv"
    debug_path = base / "layout_debug.csv"

    if not data_path.exists():
        raise FileNotFoundError(f"Missing generated data: {data_path}")

    df = pd.read_csv(data_path)
    if df.empty:
        raise AssertionError("No rows in data.csv")

    numeric_cols = [
        "P_FULL",
        "P_FULL_share",
        "P_FRAC",
        "OA_P_FULL_inst",
        "OA_P_INST_FRAC",
        "OA_PP_INST_FULL",
        "OA_PP_INST_FRAC",
        "OA_PP_FIELD_FULL",
        "OA_PP_FIELD_FRAC",
        "R_OA_FULL",
        "R_OA_FRAC",
        "OA_PP_INST",
        "OA_PP_FIELD",
        "RPP_OA",
        "delta_oa_pp",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    assert (df["P_FULL"] >= 0).all(), "Negative P_FULL"
    assert (df["P_FRAC"] >= 0).all(), "Negative P_FRAC"
    assert (df["P_FULL_share"] >= 0).all(), "Negative P_FULL_share"
    assert df["P_FULL_share"].sum() <= 1.0 + 1e-6, "P_FULL_share sum must be <= 1"

    assert df["OA_PP_INST_FULL"].between(0, 1).all(), "OA_PP_INST_FULL out of bounds"
    assert df["OA_PP_INST_FRAC"].between(0, 1).all(), "OA_PP_INST_FRAC out of bounds"
    assert df["OA_PP_FIELD_FULL"].between(0, 1).all(), "OA_PP_FIELD_FULL out of bounds"
    assert df["OA_PP_FIELD_FRAC"].between(0, 1).all(), "OA_PP_FIELD_FRAC out of bounds"

    ratio_full = df["OA_PP_INST_FULL"] / df["OA_PP_FIELD_FULL"].where(df["OA_PP_FIELD_FULL"] > 0)
    ratio_frac = df["OA_PP_INST_FRAC"] / df["OA_PP_FIELD_FRAC"].where(df["OA_PP_FIELD_FRAC"] > 0)

    diff_full = (df["R_OA_FULL"] - ratio_full).abs().fillna(0.0)
    diff_frac = (df["R_OA_FRAC"] - ratio_frac).abs().fillna(0.0)

    # Ratios are rounded to 3 decimals in SQL output.
    assert diff_full.max() < 5e-3, f"R_OA_FULL mismatch: max abs diff {diff_full.max()}"
    assert diff_frac.max() < 5e-3, f"R_OA_FRAC mismatch: max abs diff {diff_frac.max()}"

    delta_expected = (df["OA_PP_INST"] - df["OA_PP_FIELD"]) * 100.0
    delta_diff = (df["delta_oa_pp"] - delta_expected).abs().fillna(0.0)
    assert delta_diff.max() < 1e-6, f"delta_oa_pp mismatch: max abs diff {delta_diff.max()}"

    if not debug_path.exists():
        raise FileNotFoundError(f"Missing layout debug data: {debug_path}")

    debug_df = pd.read_csv(debug_path)
    if debug_df.empty:
        raise AssertionError("No rows in layout_debug.csv")

    for col in ["text_x", "axis_xlim_max"]:
        debug_df[col] = pd.to_numeric(debug_df[col], errors="coerce")

    outside = debug_df[debug_df["text_x"] > debug_df["axis_xlim_max"] + 1e-9]
    assert outside.empty, "Found label x-position outside axis limit"

    negative_x = debug_df[debug_df["text_x"] < -1e-9]
    assert negative_x.empty, "Found negative label x-position"

    print("3_3 asset validation passed")


if __name__ == "__main__":
    main()
