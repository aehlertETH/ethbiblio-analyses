import csv
import io
import json
import os
import time
import zipfile
from functools import lru_cache
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import urlopen

import numpy as np
import pandas as pd

from core.asset import (
    REPO_ROOT,
    ROR_ALLOW_API_FETCH,
    ROR_API_SLEEP_SEC,
    ROR_RESOLUTION_MODE,
    ROR_SKIP_MISSING_LOOKUP,
)


ROR_API_BASE = "https://api.ror.org/v2/organizations/"
ROR_DUMP_DIR = REPO_ROOT / "core" / "ror"
ROR_DUMP_GLOB_ENV_VAR = "ETH_BIBLIO_ROR_DUMP_GLOB"
ROR_DUMP_INDEX_SUFFIX = ".index.csv"

# In-process memoization so institution loops do not repeatedly hit disk.
_LOCAL_CACHE_MEMO: dict[str, pd.DataFrame] = {}
_DUMP_LOOKUP_MEMO: pd.DataFrame | None = None
_DUMP_LOOKUP_TOKEN: tuple[str, int] | None = None


def parse_ror_id(ror_url: str) -> str | None:
    if not isinstance(ror_url, str) or not ror_url.strip():
        return None
    parsed = urlparse(ror_url.strip())
    ror_id = parsed.path.strip("/").split("/")[-1]
    return ror_id or None


def _to_float(value: object) -> float:
    if value is None:
        return float("nan")
    text = str(value).strip()
    if not text:
        return float("nan")
    try:
        return float(text)
    except (TypeError, ValueError):
        return float("nan")


def _normalize_mode(mode: str | None) -> str:
    value = (mode or ROR_RESOLUTION_MODE).strip().lower()
    if value not in {"auto", "dump", "api"}:
        return "auto"
    return value


def _empty_ror_df() -> pd.DataFrame:
    return pd.DataFrame(columns=["ror_id", "lat", "lon", "acronym"])


def _normalize_ror_df(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in ["ror_id", "lat", "lon", "acronym"]:
        if col not in out.columns:
            out[col] = np.nan

    out = out[["ror_id", "lat", "lon", "acronym"]].copy()
    out["ror_id"] = out["ror_id"].astype(str).str.strip()
    out = out[out["ror_id"] != ""].copy()
    out["lat"] = pd.to_numeric(out["lat"], errors="coerce")
    out["lon"] = pd.to_numeric(out["lon"], errors="coerce")
    out["acronym"] = out["acronym"].astype("string")
    return out


def _load_cache_file(cache_path: Path) -> pd.DataFrame:
    if not cache_path.is_file():
        return _empty_ror_df()

    try:
        raw = pd.read_csv(cache_path)
    except Exception:
        return _empty_ror_df()

    out = _normalize_ror_df(raw)
    out = out.drop_duplicates(subset=["ror_id"], keep="last")
    return out


def _load_cache_chain(cache_paths: list[Path]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for cache_path in cache_paths:
        cache_df = _load_cache_file(cache_path)
        if not cache_df.empty:
            frames.append(cache_df)

    if not frames:
        return _empty_ror_df()

    out = pd.concat(frames, ignore_index=True)
    out = out.drop_duplicates(subset=["ror_id"], keep="first")
    return out



def _cache_key(path: Path) -> str:
    try:
        return str(path.resolve())
    except Exception:
        return str(path)


def _set_local_cache_memo_df(local_cache_path: Path, cache_df: pd.DataFrame) -> None:
    key = _cache_key(local_cache_path)
    out = _normalize_ror_df(cache_df)
    out = out.drop_duplicates(subset=["ror_id"], keep="first")
    out = out.sort_values("ror_id").reset_index(drop=True)
    _LOCAL_CACHE_MEMO[key] = out


def _get_local_cache_memo_df(local_cache_path: Path) -> pd.DataFrame:
    key = _cache_key(local_cache_path)
    memo = _LOCAL_CACHE_MEMO.get(key)
    if memo is not None:
        return memo.copy()

    cache_df = _load_cache_file(local_cache_path)
    _set_local_cache_memo_df(local_cache_path, cache_df)
    return _LOCAL_CACHE_MEMO[key].copy()


def _has_core_dump() -> bool:
    return _find_dump_zip(ROR_DUMP_DIR) is not None


def _get_dump_lookup_df() -> pd.DataFrame:
    global _DUMP_LOOKUP_MEMO, _DUMP_LOOKUP_TOKEN

    dump_zip = _find_dump_zip(ROR_DUMP_DIR)
    if dump_zip is None:
        return pd.DataFrame(columns=["lat", "lon", "acronym"])

    try:
        token = (str(dump_zip), int(dump_zip.stat().st_mtime_ns))
    except FileNotFoundError:
        return pd.DataFrame(columns=["lat", "lon", "acronym"])

    if _DUMP_LOOKUP_TOKEN == token and _DUMP_LOOKUP_MEMO is not None:
        return _DUMP_LOOKUP_MEMO

    dump_df = load_core_dump_index(ROR_DUMP_DIR)
    if dump_df.empty:
        lookup = pd.DataFrame(columns=["lat", "lon", "acronym"])
    else:
        lookup = dump_df.drop_duplicates(subset=["ror_id"], keep="first").set_index("ror_id")
        lookup = lookup[["lat", "lon", "acronym"]].copy()

    _DUMP_LOOKUP_TOKEN = token
    _DUMP_LOOKUP_MEMO = lookup
    return lookup


def _select_from_dump(ror_ids: list[str]) -> pd.DataFrame:
    if not ror_ids:
        return _empty_ror_df()

    lookup = _get_dump_lookup_df()
    if lookup.empty:
        return _empty_ror_df()

    present = [ror_id for ror_id in ror_ids if ror_id in lookup.index]
    if not present:
        return _empty_ror_df()

    out = lookup.loc[present].reset_index().rename(columns={"index": "ror_id"})
    out = _normalize_ror_df(out)
    out = out.drop_duplicates(subset=["ror_id"], keep="first")
    return out
def _extract_acronym_from_dump(raw: object) -> str | None:
    if raw is None:
        return None

    text = str(raw).strip()
    if not text:
        return None

    for part in text.split(";"):
        token = part.strip()
        if not token:
            continue
        if ":" in token:
            token = token.split(":", 1)[1].strip()
        if token:
            return token
    return None


def _extract_acronym_from_api(payload: dict) -> str | None:
    names = payload.get("names") or []
    for item in names:
        types = [str(t).lower() for t in (item.get("types") or [])]
        if "acronym" in types:
            value = str(item.get("value") or "").strip()
            if value:
                return value

    acronyms = payload.get("acronyms") or []
    if isinstance(acronyms, list):
        for value in acronyms:
            v = str(value).strip()
            if v:
                return v

    return None


def _find_dump_zip(dump_dir: Path) -> Path | None:
    custom_glob = os.getenv(ROR_DUMP_GLOB_ENV_VAR)
    patterns = [custom_glob] if custom_glob else ["*ror*data*.zip", "*.zip"]

    candidates: list[Path] = []
    for pattern in patterns:
        if not pattern:
            continue
        candidates.extend(p for p in dump_dir.glob(pattern) if p.is_file())
        if candidates:
            break

    if not candidates:
        return None

    candidates = sorted(candidates, key=lambda p: p.stat().st_mtime_ns, reverse=True)
    return candidates[0]


def _select_zip_member(names: list[str]) -> str | None:
    csv_candidates = [n for n in names if n.lower().endswith(".csv")]
    json_candidates = [n for n in names if n.lower().endswith(".json")]

    if csv_candidates:
        return sorted(csv_candidates)[0]
    if json_candidates:
        return sorted(json_candidates)[0]
    return None


@lru_cache(maxsize=2)
def _load_dump_index_cached(zip_path: str, mtime_ns: int) -> pd.DataFrame:
    del mtime_ns

    path = Path(zip_path)
    rows: list[dict] = []

    with zipfile.ZipFile(path, "r") as zf:
        member = _select_zip_member(zf.namelist())
        if member is None:
            return _empty_ror_df()

        if member.lower().endswith(".csv"):
            with zf.open(member, "r") as raw:
                text = io.TextIOWrapper(raw, encoding="utf-8", newline="")
                reader = csv.DictReader(text)
                for record in reader:
                    ror_id = parse_ror_id(record.get("id") or "")
                    if not ror_id:
                        continue

                    rows.append(
                        {
                            "ror_id": ror_id,
                            "lat": _to_float(record.get("locations.geonames_details.lat")),
                            "lon": _to_float(record.get("locations.geonames_details.lng")),
                            "acronym": _extract_acronym_from_dump(record.get("names.types.acronym")),
                        }
                    )
        else:
            with zf.open(member, "r") as raw:
                data = json.load(raw)

            if isinstance(data, dict):
                if isinstance(data.get("items"), list):
                    records = data["items"]
                elif isinstance(data.get("organizations"), list):
                    records = data["organizations"]
                else:
                    records = []
            elif isinstance(data, list):
                records = data
            else:
                records = []

            for record in records:
                ror_id = parse_ror_id(record.get("id") or "")
                if not ror_id:
                    continue

                locations = record.get("locations") or []
                details = locations[0].get("geonames_details") if locations else {}

                rows.append(
                    {
                        "ror_id": ror_id,
                        "lat": _to_float((details or {}).get("lat")),
                        "lon": _to_float((details or {}).get("lng")),
                        "acronym": _extract_acronym_from_api(record),
                    }
                )

    if not rows:
        return _empty_ror_df()

    out = pd.DataFrame(rows)
    out = _normalize_ror_df(out)
    out = out.drop_duplicates(subset=["ror_id"], keep="first")
    out = out.sort_values("ror_id").reset_index(drop=True)
    print(f"ROR: loaded core dump index with {len(out)} ids from {path.name}")
    return out


def _dump_index_sidecar_path(dump_zip: Path) -> Path:
    return dump_zip.with_name(f"{dump_zip.name}{ROR_DUMP_INDEX_SUFFIX}")


@lru_cache(maxsize=4)
def _load_dump_index_sidecar_cached(
    sidecar_path: str,
    sidecar_mtime_ns: int,
    zip_mtime_ns: int,
) -> pd.DataFrame:
    if sidecar_mtime_ns < zip_mtime_ns:
        return _empty_ror_df()

    path = Path(sidecar_path)
    try:
        raw = pd.read_csv(path)
    except Exception:
        return _empty_ror_df()

    out = _normalize_ror_df(raw)
    if out.empty:
        return _empty_ror_df()

    out = out.drop_duplicates(subset=["ror_id"], keep="first")
    out = out.sort_values("ror_id").reset_index(drop=True)
    print(f"ROR: loaded cached dump index with {len(out)} ids from {path.name}")
    return out


def _write_dump_index_sidecar(sidecar_path: Path, dump_index: pd.DataFrame) -> None:
    if dump_index.empty:
        return

    try:
        sidecar_path.parent.mkdir(parents=True, exist_ok=True)
        dump_index[["ror_id", "lat", "lon", "acronym"]].to_csv(sidecar_path, index=False)
    except Exception:
        # Non-critical performance cache; ignore write failures.
        return


def load_core_dump_index(dump_dir: Path | None = None) -> pd.DataFrame:
    base_dir = dump_dir or ROR_DUMP_DIR
    dump_zip = _find_dump_zip(base_dir)
    if dump_zip is None:
        return _empty_ror_df()

    try:
        mtime_ns = dump_zip.stat().st_mtime_ns
    except FileNotFoundError:
        return _empty_ror_df()

    sidecar_path = _dump_index_sidecar_path(dump_zip)
    try:
        sidecar_mtime_ns = sidecar_path.stat().st_mtime_ns
    except FileNotFoundError:
        sidecar_mtime_ns = -1

    if sidecar_mtime_ns >= int(mtime_ns):
        from_sidecar = _load_dump_index_sidecar_cached(
            str(sidecar_path),
            int(sidecar_mtime_ns),
            int(mtime_ns),
        )
        if not from_sidecar.empty:
            return from_sidecar.copy()

    out = _load_dump_index_cached(str(dump_zip), int(mtime_ns))
    _write_dump_index_sidecar(sidecar_path, out)
    return out.copy()


def _fetch_ror_metadata(ror_id: str) -> dict:
    url = f"{ROR_API_BASE}{ror_id}"
    try:
        with urlopen(url, timeout=12) as response:
            payload = json.load(response)
    except (HTTPError, URLError, TimeoutError, OSError, ValueError):
        return {"ror_id": ror_id, "lat": np.nan, "lon": np.nan, "acronym": None}

    acronym = _extract_acronym_from_api(payload)

    locations = payload.get("locations") or []
    if not locations:
        return {"ror_id": ror_id, "lat": np.nan, "lon": np.nan, "acronym": acronym}

    details = locations[0].get("geonames_details") or {}
    lat = _to_float(details.get("lat"))
    lon = _to_float(details.get("lng"))
    return {"ror_id": ror_id, "lat": lat, "lon": lon, "acronym": acronym}


def _fetch_many_ror_metadata(
    ror_ids: list[str],
    context: str | None = None,
    sleep_sec: float | None = None,
) -> pd.DataFrame:
    rows: list[dict] = []
    total = len(ror_ids)

    try:
        pause = ROR_API_SLEEP_SEC if sleep_sec is None else float(sleep_sec)
    except (TypeError, ValueError):
        pause = ROR_API_SLEEP_SEC
    pause = max(0.0, pause)

    for i, ror_id in enumerate(ror_ids, start=1):
        rows.append(_fetch_ror_metadata(ror_id))
        if i % 100 == 0:
            prefix = f"{context}: " if context else ""
            print(f"{prefix}ROR API fetch: {i}/{total}")
        if pause > 0:
            time.sleep(pause)

    if not rows:
        return _empty_ror_df()

    out = pd.DataFrame(rows)
    out = _normalize_ror_df(out)
    out = out.drop_duplicates(subset=["ror_id"], keep="last")
    return out


def resolve_ror_metadata(
    ror_ids: list[str],
    *,
    local_cache_path: Path,
    include_acronym: bool = False,
    fallback_cache_paths: list[Path] | None = None,
    mode: str | None = None,
    allow_api_fetch: bool | None = None,
    skip_missing_lookup: bool | None = None,
    api_sleep_sec: float | None = None,
    persist_local: bool = True,
    context: str | None = None,
) -> pd.DataFrame:
    requested = sorted({str(r).strip() for r in ror_ids if str(r).strip()})
    if not requested:
        cols = ["ror_id", "lat", "lon", "acronym"] if include_acronym else ["ror_id", "lat", "lon"]
        return pd.DataFrame(columns=cols)

    mode_norm = _normalize_mode(mode)
    api_allowed = ROR_ALLOW_API_FETCH if allow_api_fetch is None else bool(allow_api_fetch)
    skip_missing = ROR_SKIP_MISSING_LOOKUP if skip_missing_lookup is None else bool(skip_missing_lookup)
    prefix = f"{context}: " if context else ""

    resolved = _empty_ror_df()

    if mode_norm == "auto":
        resolved = _get_local_cache_memo_df(local_cache_path)
        if fallback_cache_paths:
            fallback_df = _load_cache_chain(fallback_cache_paths)
            if not fallback_df.empty:
                if resolved.empty:
                    resolved = fallback_df.copy()
                else:
                    resolved = pd.concat([resolved, fallback_df], ignore_index=True)
                resolved = resolved.drop_duplicates(subset=["ror_id"], keep="first")
    elif mode_norm == "dump":
        print(f"{prefix}ROR mode=dump: ignoring asset-local cache")
        if not _has_core_dump():
            print(f"{prefix}ROR dump not found in {ROR_DUMP_DIR}.")
        else:
            resolved = _select_from_dump(requested)
    elif mode_norm == "api":
        print(f"{prefix}ROR mode=api: forcing refresh from API")
        resolved = _fetch_many_ror_metadata(requested, context=context, sleep_sec=api_sleep_sec)

    resolved_ids = set(resolved["ror_id"].tolist()) if not resolved.empty else set()
    missing = [ror_id for ror_id in requested if ror_id not in resolved_ids]

    if mode_norm == "auto" and missing and not skip_missing:
        if not _has_core_dump():
            if api_allowed:
                print(f"{prefix}ROR dump not found in {ROR_DUMP_DIR}. Falling back to API for {len(missing)} ids.")
            else:
                print(f"{prefix}ROR dump not found in {ROR_DUMP_DIR}; API fallback is disabled.")
        else:
            from_dump = _select_from_dump(missing)
            if not from_dump.empty:
                if resolved.empty:
                    resolved = from_dump.copy()
                else:
                    resolved = pd.concat([resolved, from_dump], ignore_index=True)
                resolved = resolved.drop_duplicates(subset=["ror_id"], keep="first")

            from_dump_ids = set(from_dump["ror_id"].tolist()) if not from_dump.empty else set()
            missing_after_dump = [ror_id for ror_id in missing if ror_id not in from_dump_ids]
            if missing_after_dump:
                if api_allowed:
                    print(
                        f"{prefix}ROR ids missing in core dump: {len(missing_after_dump)}. "
                        "Falling back to API for these ids."
                    )
                else:
                    print(
                        f"{prefix}ROR ids missing in core dump: {len(missing_after_dump)}. "
                        "API fallback is disabled."
                    )
            missing = missing_after_dump

    resolved_ids = set(resolved["ror_id"].tolist()) if not resolved.empty else set()
    missing = [ror_id for ror_id in requested if ror_id not in resolved_ids]

    if mode_norm != "api" and missing and skip_missing:
        print(f"{prefix}Skipping missing ROR lookup; unresolved ids remaining: {len(missing)}")
    elif missing and api_allowed:
        fetched_df = _fetch_many_ror_metadata(missing, context=context, sleep_sec=api_sleep_sec)
        if not fetched_df.empty:
            if resolved.empty:
                resolved = fetched_df.copy()
            else:
                resolved = pd.concat([resolved, fetched_df], ignore_index=True)
            resolved = resolved.drop_duplicates(subset=["ror_id"], keep="first")
    elif missing and not api_allowed:
        print(f"{prefix}ROR API fetch disabled; unresolved ids remaining: {len(missing)}")

    resolved = _normalize_ror_df(resolved)
    resolved = resolved[resolved["ror_id"].isin(requested)].copy()
    resolved = resolved.drop_duplicates(subset=["ror_id"], keep="first")
    resolved = resolved.sort_values("ror_id").reset_index(drop=True)

    unresolved = [ror_id for ror_id in requested if ror_id not in resolved_ids]
    if unresolved:
        print(f"{prefix}ROR unresolved ids after all sources: {len(unresolved)}")

    if persist_local:
        existing = _get_local_cache_memo_df(local_cache_path)
        if resolved.empty:
            cache_out = existing.copy()
        elif existing.empty:
            cache_out = resolved.copy()
        else:
            cache_out = pd.concat([resolved, existing], ignore_index=True)
        cache_out = _normalize_ror_df(cache_out)
        cache_out = cache_out.drop_duplicates(subset=["ror_id"], keep="first")
        cache_out = cache_out.sort_values("ror_id").reset_index(drop=True)

        existing_sorted = existing.sort_values("ror_id").reset_index(drop=True)
        cache_changed = not cache_out.equals(existing_sorted)

        if cache_changed:
            local_cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_out[["ror_id", "lat", "lon", "acronym"]].to_csv(local_cache_path, index=False)

        _set_local_cache_memo_df(local_cache_path, cache_out)

    if include_acronym:
        return resolved[["ror_id", "lat", "lon", "acronym"]].copy()
    return resolved[["ror_id", "lat", "lon"]].copy()


def drop_rows_without_coordinates(
    df: pd.DataFrame,
    *,
    lat_col: str,
    lon_col: str,
    context: str | None = None,
    reset_index: bool = True,
) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    out = df.copy()
    if lat_col not in out.columns or lon_col not in out.columns:
        return out

    out[lat_col] = pd.to_numeric(out[lat_col], errors="coerce")
    out[lon_col] = pd.to_numeric(out[lon_col], errors="coerce")

    missing = out[lat_col].isna() | out[lon_col].isna()
    dropped = int(missing.sum())
    if dropped:
        prefix = f"{context}: " if context else ""
        print(f"{prefix}Dropping rows without exact coordinates: {dropped}")
        out = out.loc[~missing].copy()

    if reset_index:
        out = out.reset_index(drop=True)
    return out

