#!/usr/bin/env python3
"""Clean generated asset outputs or run all asset scripts safely."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = REPO_ROOT / "assets"
REPORT_UNITS = ("empa", "epfl", "psi", "wsl", "ethz", "eawag", "ethdomain")
STATE_DIR_NAME = ".asset-run"

# Any asset folder name containing one of these strings will be skipped.
EXCLUDED_ASSET_PATTERNS = [
    "0_0_asset_example",
    "X_X_wosOpenalexClassificationCompare",
]


def is_excluded_asset(asset_dir_name: str) -> bool:
    return any(
        pattern and pattern in asset_dir_name for pattern in EXCLUDED_ASSET_PATTERNS
    )


def iter_asset_modules() -> tuple[list[str], list[str]]:
    primary_modules: list[str] = []
    secondary_modules: list[str] = []

    for child in sorted(ASSETS_DIR.iterdir(), key=lambda path: path.name):
        if not child.is_dir() or not (child / "script.py").is_file():
            continue
        if is_excluded_asset(child.name):
            continue

        module = f"assets.{child.name}.script"
        if child.name.startswith("_"):
            secondary_modules.append(module)
        else:
            primary_modules.append(module)

    return primary_modules, secondary_modules


def iter_asset_jobs() -> list[dict[str, str]]:
    primary_modules, secondary_modules = iter_asset_modules()
    jobs: list[dict[str, str]] = []
    for module in primary_modules + secondary_modules:
        asset_id = module.removeprefix("assets.").removesuffix(".script")
        jobs.append({"asset_id": asset_id, "module": module})
    return jobs


def state_dir() -> Path:
    return REPO_ROOT / STATE_DIR_NAME


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_run_id() -> str:
    moment = datetime.now(timezone.utc)
    return moment.strftime("%Y%m%dT%H%M%S") + f"{moment.microsecond:06d}Z"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temporary_path = Path(handle.name)
    os.replace(temporary_path, path)


def relative_to_repo(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def is_safe_repo_path(path: Path) -> bool:
    try:
        path.resolve().relative_to(REPO_ROOT.resolve())
    except ValueError:
        return False
    return True


def remove_path(path: Path, *, dry_run: bool) -> bool:
    if not path.exists() and not path.is_symlink():
        return False
    if not is_safe_repo_path(path):
        raise ValueError(f"Refusing to remove a path outside the repository: {path}")

    print(f"[REMOVE] {relative_to_repo(path)}")
    if dry_run:
        return True

    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()
    return True


def compact_paths(paths: list[Path]) -> list[Path]:
    selected: list[Path] = []
    for path in sorted(set(paths), key=lambda item: (len(item.parts), str(item))):
        if any(parent == path or parent in path.parents for parent in selected):
            continue
        selected.append(path)
    return selected


def clean_targets(*, include_caches: bool) -> list[Path]:
    targets: list[Path] = []

    for job in iter_asset_jobs():
        asset_dir = ASSETS_DIR / job["asset_id"]
        for unit in REPORT_UNITS:
            path = asset_dir / unit
            if path.exists() or path.is_symlink():
                targets.append(path)

    if not include_caches:
        return compact_paths(targets)

    for asset_dir in ASSETS_DIR.iterdir():
        if not asset_dir.is_dir() or not (asset_dir / "script.py").is_file():
            continue
        for path in (asset_dir / "ror_geo_cache.csv", asset_dir / "_shared"):
            if path.exists() or path.is_symlink():
                targets.append(path)

    for path in REPO_ROOT.rglob("__pycache__"):
        if path.is_dir() and not path.is_symlink():
            targets.append(path)
    for path in REPO_ROOT.rglob("*.pyc"):
        if path.is_file() or path.is_symlink():
            targets.append(path)
    for path in REPO_ROOT.rglob(".mplconfig"):
        if path.is_dir() and not path.is_symlink():
            targets.append(path)

    run_state = state_dir()
    if run_state.exists() or run_state.is_symlink():
        targets.append(run_state)
    return compact_paths(targets)


def clean_assets(*, include_caches: bool, dry_run: bool) -> int:
    targets = clean_targets(include_caches=include_caches)
    scope = "unit outputs and caches" if include_caches else "unit outputs"
    print(f"Cleaning {scope}: {len(targets)} path(s).")
    if dry_run:
        print("Dry run: no files will be removed.")

    removed = 0
    for path in targets:
        removed += int(remove_path(path, dry_run=dry_run))

    print(f"{'Would remove' if dry_run else 'Removed'}: {removed} path(s).")
    print(
        "Retained: asset scripts, asset-root configuration and source files, "
        "shared runtime files, config.yml, and DuckDB files."
    )
    return 0


def run_manifest_path(run_id: str) -> Path:
    return state_dir() / "runs" / f"{run_id}.json"


def latest_run_path() -> Path:
    return state_dir() / "latest.json"


def completion_path(asset_id: str) -> Path:
    return state_dir() / "completions" / f"{asset_id}.json"


def transaction_dir(run_id: str, asset_id: str) -> Path:
    return state_dir() / "transactions" / run_id / asset_id


def transaction_metadata_path(path: Path) -> Path:
    return path / "transaction.json"


def save_manifest(manifest: dict[str, Any]) -> None:
    run_id = str(manifest["run_id"])
    write_json_atomic(run_manifest_path(run_id), manifest)
    write_json_atomic(latest_run_path(), {"run_id": run_id})


def load_latest_manifest() -> dict[str, Any]:
    latest = read_json(latest_run_path())
    if not latest or not isinstance(latest.get("run_id"), str):
        raise ValueError("No previous asset run is available.")
    manifest = read_json(run_manifest_path(latest["run_id"]))
    if not manifest:
        raise ValueError("The latest asset-run manifest is unavailable or invalid.")
    return manifest


def completion_is_valid(asset_id: str, script_path: Path) -> bool:
    completion = read_json(completion_path(asset_id))
    if not completion or completion.get("script_sha256") != sha256_file(script_path):
        return False

    unit_dirs = completion.get("unit_dirs")
    if not isinstance(unit_dirs, list) or not unit_dirs:
        return False

    asset_dir = ASSETS_DIR / asset_id
    return all(
        isinstance(unit, str)
        and unit in REPORT_UNITS
        and (asset_dir / unit).is_dir()
        for unit in unit_dirs
    )


def new_manifest(*, skip_existing: bool) -> dict[str, Any]:
    run_id = new_run_id()
    jobs: list[dict[str, Any]] = []
    for job in iter_asset_jobs():
        asset_id = job["asset_id"]
        script_path = ASSETS_DIR / asset_id / "script.py"
        status = "skipped_existing" if skip_existing and completion_is_valid(asset_id, script_path) else "pending"
        jobs.append(
            {
                **job,
                "script_sha256": sha256_file(script_path),
                "unit_scope": "all configured report units",
                "units": list(REPORT_UNITS),
                "status": status,
            }
        )
    return {
        "schema_version": 1,
        "run_id": run_id,
        "created_at": utc_now(),
        "status": "running",
        "jobs": jobs,
    }


def restore_transaction(path: Path) -> None:
    if not path.exists():
        return
    metadata = read_json(transaction_metadata_path(path)) or {}
    if metadata.get("state") == "committed":
        shutil.rmtree(path)
        return

    asset_id = str(metadata.get("asset_id") or path.name)
    if Path(asset_id).name != asset_id:
        raise ValueError(f"Invalid transaction asset identifier: {asset_id}")
    asset_dir = ASSETS_DIR / asset_id
    if not asset_dir.is_dir():
        raise ValueError(f"Transaction asset directory is unavailable: {asset_dir}")

    original_dir = path / "original"
    if metadata:
        units = [unit for unit in metadata.get("units", []) if unit in REPORT_UNITS]
    elif original_dir.is_dir():
        units = [item.name for item in original_dir.iterdir() if item.name in REPORT_UNITS]
    else:
        units = []

    for unit in units:
        target = asset_dir / unit
        backup = original_dir / unit
        if target.exists() or target.is_symlink():
            remove_path(target, dry_run=False)
        if backup.exists() or backup.is_symlink():
            backup.replace(target)
    shutil.rmtree(path)


def recover_transactions() -> None:
    transactions_root = state_dir() / "transactions"
    if not transactions_root.is_dir():
        return

    for run_dir in sorted(transactions_root.iterdir()):
        if not run_dir.is_dir():
            continue
        for path in sorted(run_dir.iterdir()):
            if not path.is_dir():
                continue
            metadata = read_json(transaction_metadata_path(path)) or {}
            if metadata.get("state") == "committed":
                shutil.rmtree(path)
                continue
            print(f"[RECOVER] {relative_to_repo(path)}")
            restore_transaction(path)
        if run_dir.exists() and not any(run_dir.iterdir()):
            run_dir.rmdir()
    if transactions_root.exists() and not any(transactions_root.iterdir()):
        transactions_root.rmdir()


def prepare_transaction(run_id: str, asset_id: str) -> Path:
    asset_dir = ASSETS_DIR / asset_id
    path = transaction_dir(run_id, asset_id)
    original_dir = path / "original"
    original_dir.mkdir(parents=True, exist_ok=False)

    moved_units: list[str] = []
    for unit in REPORT_UNITS:
        source = asset_dir / unit
        if source.exists() or source.is_symlink():
            source.replace(original_dir / unit)
            moved_units.append(unit)

    write_json_atomic(
        transaction_metadata_path(path),
        {
            "schema_version": 1,
            "asset_id": asset_id,
            "units": list(REPORT_UNITS),
            "moved_units": moved_units,
            "state": "active",
        },
    )
    return path


def commit_transaction(path: Path) -> None:
    metadata = read_json(transaction_metadata_path(path)) or {}
    metadata["state"] = "committed"
    write_json_atomic(transaction_metadata_path(path), metadata)
    shutil.rmtree(path)


def execute_module(module: str, log_path: Path) -> int:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as log_handle:
        process = subprocess.Popen(
            [sys.executable, "-m", module],
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        try:
            assert process.stdout is not None
            for line in process.stdout:
                sys.stdout.write(line)
                log_handle.write(line)
            return process.wait()
        except KeyboardInterrupt:
            if process.poll() is None:
                process.send_signal(signal.SIGINT)
                process.wait()
            raise


def error_summary(log_path: Path, returncode: int | None = None) -> str:
    try:
        output = log_path.read_text(encoding="utf-8", errors="replace").strip()
    except FileNotFoundError:
        output = ""
    tail = output[-2000:] if output else "No process output was captured."
    prefix = f"exit code {returncode}" if returncode is not None else "runner error"
    return f"{prefix}: {tail}"


def run_job(manifest: dict[str, Any], job: dict[str, Any]) -> tuple[int, str | None]:
    run_id = str(manifest["run_id"])
    asset_id = str(job["asset_id"])
    try:
        transaction = prepare_transaction(run_id, asset_id)
    except KeyboardInterrupt:
        incomplete = transaction_dir(run_id, asset_id)
        if incomplete.exists():
            restore_transaction(incomplete)
        raise
    except Exception as exc:
        incomplete = transaction_dir(run_id, asset_id)
        if incomplete.exists():
            restore_transaction(incomplete)
        return 1, f"runner error: {exc}"
    log_path = state_dir() / "logs" / run_id / f"{asset_id}.log"
    job["started_at"] = utc_now()
    job["log"] = relative_to_repo(log_path)
    job["status"] = "running"
    save_manifest(manifest)

    try:
        returncode = execute_module(str(job["module"]), log_path)
    except KeyboardInterrupt:
        restore_transaction(transaction)
        raise
    except Exception as exc:
        restore_transaction(transaction)
        return 1, f"runner error: {exc}"

    if returncode != 0:
        restore_transaction(transaction)
        return returncode, error_summary(log_path, returncode)

    try:
        commit_transaction(transaction)
    except Exception as exc:
        return 1, f"runner error: {exc}"
    present_units = [
        unit for unit in REPORT_UNITS if (ASSETS_DIR / asset_id / unit).is_dir()
    ]
    write_json_atomic(
        completion_path(asset_id),
        {
            "schema_version": 1,
            "asset_id": asset_id,
            "script_sha256": job["script_sha256"],
            "unit_dirs": present_units,
            "completed_at": utc_now(),
        },
    )
    return 0, None


def finish_manifest(manifest: dict[str, Any]) -> int:
    statuses = [job.get("status") for job in manifest["jobs"]]
    if "interrupted" in statuses:
        manifest["status"] = "interrupted"
        exit_code = 130
    elif "failed" in statuses:
        manifest["status"] = "completed_with_failures"
        exit_code = 1
    else:
        manifest["status"] = "completed"
        exit_code = 0
    manifest["finished_at"] = utc_now()
    save_manifest(manifest)
    return exit_code


def run_assets(*, mode: str) -> int:
    recover_transactions()

    if mode == "new":
        manifest = new_manifest(skip_existing=False)
    elif mode == "skip_existing":
        manifest = new_manifest(skip_existing=True)
    else:
        manifest = load_latest_manifest()
        if mode == "resume":
            if manifest.get("status") not in {"running", "interrupted"}:
                raise ValueError("The latest run is complete. Use --retry-failed for failed jobs.")
            for job in manifest["jobs"]:
                if job.get("status") in {"pending", "interrupted", "running"}:
                    job["status"] = "pending"
        elif mode == "retry_failed":
            for job in manifest["jobs"]:
                if job.get("status") == "failed":
                    job["status"] = "pending"
                    job["retry_count"] = int(job.get("retry_count", 0)) + 1
        manifest["status"] = "running"
        manifest["resumed_at"] = utc_now()

    save_manifest(manifest)
    jobs_to_run = [job for job in manifest["jobs"] if job.get("status") == "pending"]
    print(f"Asset jobs selected: {len(jobs_to_run)}")
    if EXCLUDED_ASSET_PATTERNS:
        print(f"Excluded patterns: {EXCLUDED_ASSET_PATTERNS}")

    for job in jobs_to_run:
        print(f"[RUN] {job['module']}")
        try:
            returncode, summary = run_job(manifest, job)
        except KeyboardInterrupt:
            job["status"] = "interrupted"
            job["finished_at"] = utc_now()
            job["error_summary"] = "Interrupted by user."
            manifest["status"] = "interrupted"
            save_manifest(manifest)
            print("Interrupted. Run again with --resume to continue pending jobs.")
            return 130

        job["finished_at"] = utc_now()
        job["returncode"] = returncode
        if returncode == 0:
            job["status"] = "succeeded"
            job.pop("error_summary", None)
            print(f"[OK] {job['module']}")
        else:
            job["status"] = "failed"
            job["error_summary"] = summary
            print(f"[FAILED] {job['module']}: {summary}", file=sys.stderr)
        save_manifest(manifest)

    exit_code = finish_manifest(manifest)
    failed = sum(job.get("status") == "failed" for job in manifest["jobs"])
    skipped = sum(job.get("status") == "skipped_existing" for job in manifest["jobs"])
    succeeded = sum(job.get("status") == "succeeded" for job in manifest["jobs"])
    print(f"Finished: {succeeded} succeeded, {failed} failed, {skipped} skipped.")
    if failed:
        print("Use --retry-failed to run only failed jobs.", file=sys.stderr)
    return exit_code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Clean generated asset outputs or run all asset scripts."
    )
    subparsers = parser.add_subparsers(dest="command")

    clean_parser = subparsers.add_parser("clean", help="Remove generated asset outputs.")
    clean_parser.add_argument(
        "--include-caches",
        action="store_true",
        help="Also remove asset-local and Python caches plus asset-run state.",
    )
    clean_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List removal targets without changing files.",
    )

    run_parser = subparsers.add_parser("run", help="Run all asset scripts.")
    run_modes = run_parser.add_mutually_exclusive_group()
    run_modes.add_argument(
        "--resume",
        action="store_true",
        help="Continue pending or interrupted jobs from the latest incomplete run.",
    )
    run_modes.add_argument(
        "--retry-failed",
        action="store_true",
        help="Retry only failed jobs from the latest run.",
    )
    run_modes.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip only assets with a verified runner completion marker.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    command = args.command or "run"

    try:
        if command == "clean":
            return clean_assets(
                include_caches=bool(args.include_caches), dry_run=bool(args.dry_run)
            )
        if command == "run":
            if args.command is None:
                mode = "new"
            elif args.resume:
                mode = "resume"
            elif args.retry_failed:
                mode = "retry_failed"
            elif args.skip_existing:
                mode = "skip_existing"
            else:
                mode = "new"
            return run_assets(mode=mode)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

