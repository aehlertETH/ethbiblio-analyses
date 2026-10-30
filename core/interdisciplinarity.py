from __future__ import annotations

import pandas as pd


MIN_REFS = 5
W_SAME_FIELD = 1.0 / 3.0
W_SAME_DOMAIN = 2.0 / 3.0


def compute_rs_vectorized(df: pd.DataFrame) -> pd.Series:
    """
    Compute work-level Rao-Stirling integration scores from subfield-level
    reference counts.

    Required columns:
      work_id, cited_field, cited_domain, n_refs_in_subfield, total_refs
    """
    required = {"work_id", "cited_field", "cited_domain", "n_refs_in_subfield", "total_refs"}
    missing = required.difference(df.columns)
    if missing:
        raise KeyError(f"Missing columns for Rao-Stirling calculation: {sorted(missing)}")

    tmp = df.copy()
    tmp["n_refs_in_subfield"] = pd.to_numeric(tmp["n_refs_in_subfield"], errors="coerce")
    tmp["total_refs"] = pd.to_numeric(tmp["total_refs"], errors="coerce")
    tmp = tmp.dropna(subset=["work_id", "cited_field", "cited_domain", "n_refs_in_subfield", "total_refs"])
    tmp = tmp[tmp["total_refs"] >= MIN_REFS].copy()
    if tmp.empty:
        return pd.Series(dtype=float, name="rs_w")

    tmp["q"] = tmp["n_refs_in_subfield"] / tmp["total_refs"]
    tmp["q2"] = tmp["q"] ** 2

    c_cross_all = 1.0 - tmp.groupby("work_id")["q2"].sum()

    dom_grp = tmp.groupby(["work_id", "cited_domain"])
    dom_cross = (dom_grp["q"].sum() ** 2 - dom_grp["q2"].sum()).groupby(level="work_id").sum()

    fld_grp = tmp.groupby(["work_id", "cited_field"])
    fld_cross = (fld_grp["q"].sum() ** 2 - fld_grp["q2"].sum()).groupby(level="work_id").sum()

    rs = (
        c_cross_all
        - (1.0 - W_SAME_DOMAIN) * dom_cross
        - (W_SAME_DOMAIN - W_SAME_FIELD) * fld_cross
    )
    return rs.rename("rs_w")
