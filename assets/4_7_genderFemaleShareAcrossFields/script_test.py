"""
Validation checks for 4_7_genderFemaleShareAcrossFields.

Checks:
- Field rows have non-negative publication counts and shares.
- PA_F_INST and PA_F_PUBS are in [0, 1].
- RPA_F equals PA_F_INST / PA_F_PUBS within tolerance.
- Exported delta column equals (PA_F_INST - PA_F_PUBS) * 100.
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
        "P_FRAC_share",
        "A_FEMALE_INST",
        "A_MALE_INST",
        "A_FEMALE_PUBS",
        "A_MALE_PUBS",
        "PA_F_INST",
        "PA_F_PUBS",
        "RPA_F",
        "delta_pa_f_pp",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    assert (df["P_FULL"] >= 0).all(), "Negative P_FULL"
    assert (df["P_FRAC"] >= 0).all(), "Negative P_FRAC"
    assert (df["P_FULL_share"] >= 0).all(), "Negative P_FULL_share"
    assert df["P_FULL_share"].sum() <= 1.0 + 1e-6, "P_FULL_share sum must be <= 1"
    assert (df["P_FRAC_share"] >= 0).all(), "Negative P_FRAC_share"
    assert df["P_FRAC_share"].sum() <= 1.0 + 1e-6, "P_FRAC_share sum must be <= 1"

    assert df["PA_F_INST"].between(0, 1).all(), "PA_F_INST out of bounds"
    assert df["PA_F_PUBS"].between(0, 1).all(), "PA_F_PUBS out of bounds"

    ratio = df["PA_F_INST"] / df["PA_F_PUBS"].where(df["PA_F_PUBS"] > 0)
    ratio_diff = (df["RPA_F"] - ratio).abs().fillna(0.0)
    assert ratio_diff.max() < 1e-6, f"RPA_F mismatch: max abs diff {ratio_diff.max()}"

    delta_expected = (df["PA_F_INST"] - df["PA_F_PUBS"]) * 100.0
    delta_diff = (df["delta_pa_f_pp"] - delta_expected).abs().fillna(0.0)
    assert delta_diff.max() < 1e-6, f"delta_pa_f_pp mismatch: max abs diff {delta_diff.max()}"

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

    print("4_7 field asset validation passed")


if __name__ == "__main__":
    main()
