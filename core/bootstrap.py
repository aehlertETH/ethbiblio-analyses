from __future__ import annotations

from typing import Tuple

import numpy as np
import pandas as pd


def _weighted_mean(values: np.ndarray, weights: np.ndarray | None = None) -> float:
    if values.size == 0:
        return float("nan")
    if weights is None:
        return float(values.mean())
    denominator = weights.sum()
    if denominator == 0:
        return float("nan")
    return float(np.dot(values, weights) / denominator)


def bootstrap_ci(
    values: np.ndarray,
    *,
    weights: np.ndarray | None = None,
    n_bootstrap: int = 1000,
    ci_level: float = 0.95,
    rng: np.random.Generator | None = None,
    batch_size: int = 50,
) -> Tuple[float, float]:
    if values.size == 0:
        return float("nan"), float("nan")
    if n_bootstrap <= 0:
        raise ValueError("n_bootstrap must be > 0")
    if not (0 < ci_level < 1):
        raise ValueError("ci_level must be between 0 and 1")

    if rng is None:
        rng = np.random.default_rng()

    n_rows = values.size
    stats = np.empty(n_bootstrap, dtype=float)
    offset = 0

    while offset < n_bootstrap:
        n_draws = min(batch_size, n_bootstrap - offset)
        idx = rng.integers(0, n_rows, size=(n_draws, n_rows))
        sampled_values = values[idx]

        if weights is None:
            stats[offset : offset + n_draws] = sampled_values.mean(axis=1)
        else:
            sampled_weights = weights[idx]
            numerators = (sampled_values * sampled_weights).sum(axis=1)
            denominators = sampled_weights.sum(axis=1)
            stats[offset : offset + n_draws] = np.divide(
                numerators,
                denominators,
                out=np.full(n_draws, np.nan, dtype=float),
                where=denominators != 0,
            )

        offset += n_draws

    valid_stats = stats[np.isfinite(stats)]
    if valid_stats.size == 0:
        return float("nan"), float("nan")

    alpha = 1.0 - ci_level
    lower = float(np.quantile(valid_stats, alpha / 2.0))
    upper = float(np.quantile(valid_stats, 1.0 - alpha / 2.0))
    return lower, upper


def build_point_and_bounds_by_group(
    df: pd.DataFrame,
    *,
    group_col: str,
    value_col: str,
    out_col: str,
    weights_col: str | None = None,
    n_bootstrap: int = 1000,
    ci_level: float = 0.95,
    random_seed: int = 42,
    round_digits: int | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if group_col not in df.columns:
        raise KeyError(f"Missing group column: {group_col}")
    if value_col not in df.columns:
        raise KeyError(f"Missing value column: {value_col}")
    if weights_col is not None and weights_col not in df.columns:
        raise KeyError(f"Missing weights column: {weights_col}")

    rng = np.random.default_rng(random_seed)
    rows: list[dict[str, float | int | str]] = []

    grouped = df.groupby(group_col, sort=True, dropna=True)
    for group_value, group_df in grouped:
        values = pd.to_numeric(group_df[value_col], errors="coerce").to_numpy(dtype=float)

        if weights_col is None:
            mask = np.isfinite(values)
            clean_values = values[mask]
            clean_weights = None
        else:
            weights = pd.to_numeric(group_df[weights_col], errors="coerce").to_numpy(dtype=float)
            mask = np.isfinite(values) & np.isfinite(weights)
            clean_values = values[mask]
            clean_weights = weights[mask]

        point = _weighted_mean(clean_values, clean_weights)
        lower, upper = bootstrap_ci(
            clean_values,
            weights=clean_weights,
            n_bootstrap=n_bootstrap,
            ci_level=ci_level,
            rng=rng,
        )
        rows.append({group_col: group_value, "point": point, "lower": lower, "upper": upper})

    stats = pd.DataFrame(rows)
    if stats.empty:
        empty = pd.DataFrame(columns=[group_col, out_col])
        return empty.copy(), empty.copy(), empty.copy()

    point_df = stats[[group_col]].copy()
    point_df[out_col] = stats["point"]

    lower_df = stats[[group_col]].copy()
    lower_df[out_col] = stats["lower"]

    upper_df = stats[[group_col]].copy()
    upper_df[out_col] = stats["upper"]

    if round_digits is not None:
        point_df[out_col] = point_df[out_col].round(round_digits)
        lower_df[out_col] = lower_df[out_col].round(round_digits)
        upper_df[out_col] = upper_df[out_col].round(round_digits)

    return point_df, lower_df, upper_df
