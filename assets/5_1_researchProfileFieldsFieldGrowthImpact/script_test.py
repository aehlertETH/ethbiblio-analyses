"""
Validation checks for 5_1_researchProfileFieldsFieldGrowthImpact.

Checks:
- Required minimal columns exist.
- Selection thresholds are respected.
- Growth percent (stored as fraction) equals (ratio - 1) where ratio is present.
- Layout debug labels stay inside panel-specific x-limits.
"""

from pathlib import Path

import pandas as pd


INST = "ethz"
MIN_OUTPUT_SHARE = 0.01
MIN_OUTPUT_FRAC = 50.0


def main() -> None:
    base = Path(__file__).resolve().parent / INST
    data_path = base / "data.csv"
    debug_path = base / "layout_debug.csv"

    if not data_path.exists():
        raise FileNotFoundError(f"Missing generated data: {data_path}")

    df = pd.read_csv(data_path)
    if df.empty:
        raise AssertionError("No rows in data.csv")

    required = [
        "field",
        "field_category",
        "P_FULL",
        "P_FRAC",
        "R_FULL_FRAC",
        "P_FRAC_share",
        "GROWTH_FIELD_FULL",
        "GROWTH_FIELD_FULL_percentage",
        "MNCS_FRAC",
        "PP_TOPTEN_FRAC",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise AssertionError(f"Missing required columns: {missing}")

    for col in required:
        if col in {"field", "field_category"}:
            continue
        df[col] = pd.to_numeric(df[col], errors="coerce")

    assert (df["P_FRAC_share"] >= MIN_OUTPUT_SHARE - 1e-12).all(), "P_FRAC_share threshold violated"
    assert (df["P_FRAC"] >= MIN_OUTPUT_FRAC - 1e-12).all(), "P_FRAC threshold violated"

    valid_ratio = df["P_FULL"].notna() & df["P_FRAC"].notna() & (df["P_FRAC"] > 0) & df["R_FULL_FRAC"].notna()
    expected_ratio = df.loc[valid_ratio, "P_FULL"] / df.loc[valid_ratio, "P_FRAC"]
    diff_ratio = (df.loc[valid_ratio, "R_FULL_FRAC"] - expected_ratio).abs().fillna(0.0)
    assert diff_ratio.max() < 1e-6, f"R_FULL_FRAC mismatch: max abs diff {diff_ratio.max()}"

    valid_growth = df["GROWTH_FIELD_FULL"].notna() & df["GROWTH_FIELD_FULL_percentage"].notna()
    expected_pct = df.loc[valid_growth, "GROWTH_FIELD_FULL"] - 1.0
    diff_pct = (df.loc[valid_growth, "GROWTH_FIELD_FULL_percentage"] - expected_pct).abs().fillna(0.0)
    assert diff_pct.max() < 1e-6, f"GROWTH_FIELD_FULL_percentage mismatch: max abs diff {diff_pct.max()}"

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

    print("5_1 field growth impact asset validation passed")


if __name__ == "__main__":
    main()
