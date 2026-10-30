# asset.py
import os
from pathlib import Path
from typing import Callable, Iterator

import pandas as pd

from utility import asset_base, connect_duckdb, institutions as DEFAULT_INSTITUTIONS

# Canonical display order for cross-institution comparisons (figures, tables)
INSTITUTION_DISPLAY_ORDER = ['ethz', 'epfl', 'psi', 'wsl', 'empa', 'eawag', 'ethdomain']
REPO_ROOT = Path(__file__).resolve().parents[1]
ETH_INTERNAL_EXCLUSIONS_PATH = (
    REPO_ROOT
    / "postprocessing"
    / "institutions_within_eth_to_filter_out"
    / "excluded_institutions.csv"
)
INSTITUTION_POSTPROCESSING_ENV_VAR = "ETH_BIBLIO_ENABLE_INST_POSTPROCESSING"
ROR_RESOLUTION_MODE_ENV_VAR = "ETH_BIBLIO_ROR_RESOLUTION_MODE"
ROR_ALLOW_API_FETCH_ENV_VAR = "ETH_BIBLIO_ROR_ALLOW_API_FETCH"
ROR_SKIP_MISSING_LOOKUP_ENV_VAR = "ETH_BIBLIO_ROR_SKIP_MISSING_LOOKUP"
ROR_API_SLEEP_SEC_ENV_VAR = "ETH_BIBLIO_ROR_API_SLEEP_SEC"

# Project-wide runtime defaults.
# Edit these directly when you want stable, explicit behavior without relying on env vars.
# Dev context: these values are consumed across assets via imports from core.asset.
DEFAULT_INSTITUTION_POSTPROCESSING_ENABLED = True
DEFAULT_ROR_RESOLUTION_MODE = "auto"  # allowed: auto | dump | api
DEFAULT_ROR_ALLOW_API_FETCH = False
DEFAULT_ROR_SKIP_MISSING_LOOKUP = False
DEFAULT_ROR_API_SLEEP_SEC = 0.01  # seconds between API requests, min 0

# DATA_EXTRACT_MODE controls SQL extraction vs cached CSV reuse for assets.
# - "reuse": skip SQL if per-institution CSV cache exists (unless force=True)
# - "refresh": always execute SQL and overwrite cache
# This is centralized here so assets share one standardized switch.
DATA_EXTRACT_MODE = "reuse"  # allowed: reuse | refresh
DEFAULT_TABLE_HEADER_ROTATION_DEG = 60  # default header rotation for trend-table year labels
# Optional env overrides for ad-hoc runs.
# Set to False to ignore ETH_BIBLIO_* env vars and use only the hard-coded defaults above.
USE_ENV_OVERRIDES = False


def _env_flag_enabled(name: str, default: bool = True) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default

    value = raw.strip().lower()
    if value in {"0", "false", "off", "no"}:
        return False
    if value in {"1", "true", "on", "yes"}:
        return True
    return default


def _env_choice(name: str, default: str, allowed: set[str]) -> str:
    raw = os.getenv(name)
    if raw is None:
        return default

    value = raw.strip().lower()
    return value if value in allowed else default


def _env_float(name: str, default: float, min_value: float | None = None) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default

    try:
        value = float(raw.strip())
    except (TypeError, ValueError):
        return default

    if min_value is not None and value < min_value:
        return min_value
    return value


if DEFAULT_ROR_RESOLUTION_MODE not in {"auto", "dump", "api"}:
    raise ValueError("DEFAULT_ROR_RESOLUTION_MODE must be one of: auto, dump, api")

if DEFAULT_ROR_API_SLEEP_SEC < 0:
    raise ValueError("DEFAULT_ROR_API_SLEEP_SEC must be >= 0")

if DATA_EXTRACT_MODE not in {"reuse", "refresh"}:
    raise ValueError("DATA_EXTRACT_MODE must be one of: reuse, refresh")

if USE_ENV_OVERRIDES:
    INSTITUTION_POSTPROCESSING_ENABLED = _env_flag_enabled(
        INSTITUTION_POSTPROCESSING_ENV_VAR,
        default=DEFAULT_INSTITUTION_POSTPROCESSING_ENABLED,
    )
    ROR_RESOLUTION_MODE = _env_choice(
        ROR_RESOLUTION_MODE_ENV_VAR,
        default=DEFAULT_ROR_RESOLUTION_MODE,
        allowed={"auto", "dump", "api"},
    )
    ROR_ALLOW_API_FETCH = _env_flag_enabled(
        ROR_ALLOW_API_FETCH_ENV_VAR,
        default=DEFAULT_ROR_ALLOW_API_FETCH,
    )
    ROR_SKIP_MISSING_LOOKUP = _env_flag_enabled(
        ROR_SKIP_MISSING_LOOKUP_ENV_VAR,
        default=DEFAULT_ROR_SKIP_MISSING_LOOKUP,
    )
    ROR_API_SLEEP_SEC = _env_float(
        ROR_API_SLEEP_SEC_ENV_VAR,
        default=DEFAULT_ROR_API_SLEEP_SEC,
        min_value=0.0,
    )
else:
    INSTITUTION_POSTPROCESSING_ENABLED = DEFAULT_INSTITUTION_POSTPROCESSING_ENABLED
    ROR_RESOLUTION_MODE = DEFAULT_ROR_RESOLUTION_MODE
    ROR_ALLOW_API_FETCH = DEFAULT_ROR_ALLOW_API_FETCH
    ROR_SKIP_MISSING_LOOKUP = DEFAULT_ROR_SKIP_MISSING_LOOKUP
    ROR_API_SLEEP_SEC = DEFAULT_ROR_API_SLEEP_SEC


def get_eth_internal_exclusion_ids() -> list[int]:
    if not ETH_INTERNAL_EXCLUSIONS_PATH.is_file():
        return []

    try:
        df = pd.read_csv(ETH_INTERNAL_EXCLUSIONS_PATH, usecols=["institution_id"])
    except (ValueError, pd.errors.EmptyDataError):
        return []

    ids = pd.to_numeric(df["institution_id"], errors="coerce")
    ids = ids[ids.notna() & (ids > 0)].astype(int)
    return sorted(pd.unique(ids).tolist())


def postprocess_excluded_institutions(
    df: pd.DataFrame,
    *,
    institution_id_col: str = "institution_id",
    reset_index: bool = True,
) -> pd.DataFrame:
    """
    Remove ETH-internal institutions by institution id.

    Toggle with env var ETH_BIBLIO_ENABLE_INST_POSTPROCESSING:
    - 1/true/on/yes => enabled (default)
    - 0/false/off/no => disabled
    """
    out = df.copy()
    if not INSTITUTION_POSTPROCESSING_ENABLED:
        return out

    if institution_id_col not in out.columns:
        return out

    excluded_ids = get_eth_internal_exclusion_ids()
    if not excluded_ids:
        return out

    ids = pd.to_numeric(out[institution_id_col], errors="coerce")
    out = out[~ids.isin(excluded_ids)].copy()

    if reset_index:
        out = out.reset_index(drop=True)
    return out


class Asset:
    """
    Lightweight helper for assets.

    - manages base directory
    - provides DuckDB connection
    - yields institutions
    - standardizes extract/cache/load inside the class
    """

    def __init__(
        self,
        *,
        script_file: str,
        year_first: int = 2014,
        year_last: int = 2023,
        year_range_moving: int = 4,  # effective MA/MS window in years (1 = yearly)
        threshold_is_cohort_reliable: int = 500,
        institutions=DEFAULT_INSTITUTIONS,
        data_extract_mode: str = DATA_EXTRACT_MODE,
        table_header_rotation_deg: float = DEFAULT_TABLE_HEADER_ROTATION_DEG,
    ):
        self.base_dir: Path = asset_base(script_file)
        self.year_first = year_first
        self.year_last = year_last
        self.year_range_moving: int = year_range_moving  # set 1 for yearly window
        self.threshold_is_cohort_reliable: int = threshold_is_cohort_reliable
        self.institutions = list(institutions)
        self.table_header_rotation_deg = float(table_header_rotation_deg)

        mode = (data_extract_mode or DATA_EXTRACT_MODE).strip().lower()
        if mode not in {"reuse", "refresh"}:
            raise ValueError("data_extract_mode must be one of: reuse, refresh")

        self.data_extract_mode = mode
        self.reuse_extract = mode == "reuse"

    def iterate_institutions(self):
        con = self.connect()
        try:
            for inst in self.institutions:
                yield inst, con
        finally:
            con.close()

    def connect(self):
        return connect_duckdb(read_only=True)

    def inst_dir(self, inst: str) -> Path:
        p = self.base_dir / inst
        p.mkdir(parents=True, exist_ok=True)
        return p

    def _normalize_csv_name(self, out_name: str | None) -> str:
        if not out_name:
            return "data.csv"
        return out_name if out_name.endswith(".csv") else f"{out_name}.csv"

    def extract(
        self,
        *,
        con,
        inst: str,
        query: str | Callable[[str], str],
        out_name: str | None = "data.csv",
        force: bool = False,
    ) -> pd.DataFrame:
        """
        Extract data for one institution and cache it in:
          <asset_base>/<inst>/<out_name>.csv

        Behavior:
        - if force=True: always re-run query and overwrite cache
        - elif data_extract_mode="reuse" and cache exists: load cache
        - else: run query and overwrite cache
        """
        path_dir = self.inst_dir(inst)
        filename = self._normalize_csv_name(out_name)
        path_data = path_dir / filename

        use_cache = self.reuse_extract and path_data.is_file() and (not force)

        if use_cache:
            print(inst, "-> data NOT extracted (DATA_EXTRACT_MODE: reuse cache)")
            # Preserve literal country codes like "NA" (Namibia) when reusing cached CSV.
            return pd.read_csv(path_data, keep_default_na=False, na_values=[""])

        sql = query(inst) if callable(query) else query
        df = con.query(sql).df()
        df.to_csv(path_data, index=False)
        print(inst, "-> data extracted")
        return df


