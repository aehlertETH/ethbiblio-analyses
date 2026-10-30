"""
Validation checks for X_X_genderCoverageTable.

Checks:
- Rows for affiliated and all scopes exist.
- identified + unknown = total.
- Share columns are in [0, 1].
- Share arithmetic matches counts.
- female + male = identified.
"""

from pathlib import Path

import pandas as pd


INST = "ethz"


def main() -> None:
    path = Path(__file__).resolve().parent / INST / "data.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing generated data: {path}")

    df = pd.read_csv(path)
    if df.empty:
        raise AssertionError("No rows in data.csv")

    required_cols = {
        "scope",
        "A_TOTAL_AUTHORS",
        "A_IDENTIFIED_AUTHORS",
        "A_UNKNOWN_AUTHORS",
        "PA_IDENTIFIED_AUTHORS",
        "PA_UNKNOWN_AUTHORS",
        "A_FEMALE_AUTHORS",
        "A_MALE_AUTHORS",
        "PA_FEMALE_IDENTIFIED",
        "PA_MALE_IDENTIFIED",
    }
    missing = required_cols - set(df.columns)
    if missing:
        raise AssertionError(f"Missing columns: {sorted(missing)}")

    scopes = set(df["scope"].astype(str).str.strip().tolist())
    assert {"affiliated", "all"}.issubset(scopes), "Missing expected scope rows"

    numeric_cols = [
        "A_TOTAL_AUTHORS",
        "A_IDENTIFIED_AUTHORS",
        "A_UNKNOWN_AUTHORS",
        "PA_IDENTIFIED_AUTHORS",
        "PA_UNKNOWN_AUTHORS",
        "A_FEMALE_AUTHORS",
        "A_MALE_AUTHORS",
        "PA_FEMALE_IDENTIFIED",
        "PA_MALE_IDENTIFIED",
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    assert (df["A_TOTAL_AUTHORS"] >= 0).all(), "Negative total authors"
    assert (df["A_IDENTIFIED_AUTHORS"] >= 0).all(), "Negative identified authors"
    assert (df["A_UNKNOWN_AUTHORS"] >= 0).all(), "Negative unknown authors"

    assert (df["A_IDENTIFIED_AUTHORS"] + df["A_UNKNOWN_AUTHORS"] == df["A_TOTAL_AUTHORS"]).all(), (
        "identified + unknown must equal total"
    )

    for col in ["PA_IDENTIFIED_AUTHORS", "PA_UNKNOWN_AUTHORS", "PA_FEMALE_IDENTIFIED", "PA_MALE_IDENTIFIED"]:
        assert df[col].dropna().between(0, 1).all(), f"{col} out of bounds"

    share_identified = df["A_IDENTIFIED_AUTHORS"] / df["A_TOTAL_AUTHORS"].where(df["A_TOTAL_AUTHORS"] > 0)
    share_unknown = df["A_UNKNOWN_AUTHORS"] / df["A_TOTAL_AUTHORS"].where(df["A_TOTAL_AUTHORS"] > 0)

    diff_identified = (df["PA_IDENTIFIED_AUTHORS"] - share_identified).abs().fillna(0.0)
    diff_unknown = (df["PA_UNKNOWN_AUTHORS"] - share_unknown).abs().fillna(0.0)
    assert diff_identified.max() < 1e-5, f"PA_IDENTIFIED_AUTHORS mismatch: {diff_identified.max()}"
    assert diff_unknown.max() < 1e-5, f"PA_UNKNOWN_AUTHORS mismatch: {diff_unknown.max()}"

    assert (df["A_FEMALE_AUTHORS"] + df["A_MALE_AUTHORS"] == df["A_IDENTIFIED_AUTHORS"]).all(), (
        "female + male must equal identified"
    )

    female_share = df["A_FEMALE_AUTHORS"] / df["A_IDENTIFIED_AUTHORS"].where(df["A_IDENTIFIED_AUTHORS"] > 0)
    male_share = df["A_MALE_AUTHORS"] / df["A_IDENTIFIED_AUTHORS"].where(df["A_IDENTIFIED_AUTHORS"] > 0)

    diff_female = (df["PA_FEMALE_IDENTIFIED"] - female_share).abs().fillna(0.0)
    diff_male = (df["PA_MALE_IDENTIFIED"] - male_share).abs().fillna(0.0)
    assert diff_female.max() < 1e-5, f"PA_FEMALE_IDENTIFIED mismatch: {diff_female.max()}"
    assert diff_male.max() < 1e-5, f"PA_MALE_IDENTIFIED mismatch: {diff_male.max()}"

    affiliated_total = float(df.loc[df["scope"] == "affiliated", "A_TOTAL_AUTHORS"].iloc[0])
    all_total = float(df.loc[df["scope"] == "all", "A_TOTAL_AUTHORS"].iloc[0])
    assert affiliated_total <= all_total + 1e-9, "Affiliated total exceeds all-author total"

    print("X_X_genderCoverageTable validation passed")


if __name__ == "__main__":
    main()
