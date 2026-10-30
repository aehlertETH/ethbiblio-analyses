"""
Validation checks for X_X_genderOverallTrend.

Checks:
- MA window labels are complete and unique.
- Count metrics are non-negative.
- Share metrics are bounded in [0, 1].
- RPA_F equals PA_F_INST / PA_F_PUBS where denominator > 0.
- Female+male counts do not exceed corresponding totals.
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

    required = {
        "MA_year",
        "A_AFF_AUTHORS",
        "A_FEMALE_INST",
        "A_MALE_INST",
        "PA_F_INST",
        "A_ALL_AUTHORS",
        "A_FEMALE_PUBS",
        "A_MALE_PUBS",
        "PA_F_PUBS",
        "RPA_F",
    }
    missing = required - set(df.columns)
    if missing:
        raise AssertionError(f"Missing columns: {sorted(missing)}")

    assert df["MA_year"].astype(str).str.contains(r"^\d{4}-\d{4}$").all(), "Invalid MA_year label"
    assert df["MA_year"].nunique() == len(df), "Duplicate MA_year rows"

    numeric_cols = [
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
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    for col in ["A_AFF_AUTHORS", "A_FEMALE_INST", "A_MALE_INST", "A_ALL_AUTHORS", "A_FEMALE_PUBS", "A_MALE_PUBS"]:
        assert (df[col].fillna(0) >= 0).all(), f"Negative values in {col}"

    assert df["PA_F_INST"].dropna().between(0, 1).all(), "PA_F_INST out of bounds"
    assert df["PA_F_PUBS"].dropna().between(0, 1).all(), "PA_F_PUBS out of bounds"

    ratio = df["PA_F_INST"] / df["PA_F_PUBS"].where(df["PA_F_PUBS"] > 0)
    diff = (df["RPA_F"] - ratio).abs().fillna(0.0)
    assert diff.max() < 1e-5, f"RPA_F mismatch: max abs diff {diff.max()}"

    assert (df["A_FEMALE_INST"].fillna(0) + df["A_MALE_INST"].fillna(0) <= df["A_AFF_AUTHORS"].fillna(0) + 1e-9).all(), (
        "A_FEMALE_INST + A_MALE_INST exceeds A_AFF_AUTHORS"
    )
    assert (df["A_FEMALE_PUBS"].fillna(0) + df["A_MALE_PUBS"].fillna(0) <= df["A_ALL_AUTHORS"].fillna(0) + 1e-9).all(), (
        "A_FEMALE_PUBS + A_MALE_PUBS exceeds A_ALL_AUTHORS"
    )

    print("X_X_genderOverallTrend validation passed")


if __name__ == "__main__":
    main()
