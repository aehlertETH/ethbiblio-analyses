"""Focused tests for the asset cleanup and batch-run commands."""

from __future__ import annotations

import importlib.util
from pathlib import Path


PIPELINE_PATH = Path(__file__).with_name("run_assets.py")


def load_pipeline(tmp_path: Path):
    spec = importlib.util.spec_from_file_location("pipeline_assets_tested", PIPELINE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.REPO_ROOT = tmp_path
    module.ASSETS_DIR = tmp_path / "assets"
    module.ASSETS_DIR.mkdir()
    (module.ASSETS_DIR / "__init__.py").write_text("", encoding="utf-8")
    return module


def write_script(repo_root: Path, asset_id: str, body: str) -> Path:
    asset_dir = repo_root / "assets" / asset_id
    asset_dir.mkdir()
    script_path = asset_dir / "script.py"
    script_path.write_text(body, encoding="utf-8")
    return asset_dir


def success_script(value: str) -> str:
    return f'''from pathlib import Path
base = Path(__file__).parent
unit = base / "ethz"
unit.mkdir(parents=True, exist_ok=True)
(unit / "value.txt").write_text("{value}", encoding="utf-8")
'''


def counter_script(value: str) -> str:
    return f'''from pathlib import Path
base = Path(__file__).parent
counter = base / "runs.txt"
count = int(counter.read_text(encoding="utf-8")) if counter.exists() else 0
counter.write_text(str(count + 1), encoding="utf-8")
unit = base / "ethz"
unit.mkdir(parents=True, exist_ok=True)
(unit / "value.txt").write_text("{value}", encoding="utf-8")
'''


def test_no_argument_call_remains_a_run_alias(tmp_path: Path, monkeypatch):
    pipeline = load_pipeline(tmp_path)
    modes: list[str] = []

    def record_mode(*, mode: str) -> int:
        modes.append(mode)
        return 0

    monkeypatch.setattr(pipeline, "run_assets", record_mode)
    assert pipeline.main([]) == 0
    assert modes == ["new"]


def test_clean_dry_run_preserves_caches_and_sources(tmp_path: Path):
    pipeline = load_pipeline(tmp_path)
    asset_dir = write_script(tmp_path, "alpha", success_script("new"))
    unit_dir = asset_dir / "ethz"
    unit_dir.mkdir()
    (unit_dir / "data.csv").write_text("value\n1\n", encoding="utf-8")
    cache_path = asset_dir / "ror_geo_cache.csv"
    cache_path.write_text("ror_id\n", encoding="utf-8")
    shared_dir = asset_dir / "_shared"
    shared_dir.mkdir()
    (shared_dir / "cached.csv").write_text("value\n", encoding="utf-8")
    source_file = asset_dir / "config_IndTable.txt"
    source_file.write_text("source", encoding="utf-8")
    (tmp_path / "config.yml").write_text("duckdb_path: /tmp/example.duckdb\n", encoding="utf-8")
    (tmp_path / "example.duckdb").write_text("database", encoding="utf-8")
    plotting_cache = tmp_path / ".mplconfig"
    plotting_cache.mkdir()
    (plotting_cache / "font.json").write_text("{}", encoding="utf-8")
    run_state = tmp_path / ".asset-run"
    run_state.mkdir()
    (run_state / "latest.json").write_text("{}", encoding="utf-8")

    assert pipeline.main(["clean", "--dry-run"]) == 0
    assert unit_dir.is_dir()
    assert cache_path.is_file()

    assert pipeline.main(["clean"]) == 0
    assert not unit_dir.exists()
    assert cache_path.is_file()
    assert shared_dir.is_dir()
    assert plotting_cache.is_dir()
    assert run_state.is_dir()
    assert source_file.is_file()
    assert (tmp_path / "config.yml").is_file()
    assert (tmp_path / "example.duckdb").is_file()

    assert pipeline.main(["clean", "--include-caches"]) == 0
    assert not cache_path.exists()
    assert not shared_dir.exists()
    assert not plotting_cache.exists()
    assert not run_state.exists()
    assert source_file.is_file()
    assert (tmp_path / "config.yml").is_file()
    assert (tmp_path / "example.duckdb").is_file()


def test_run_continues_after_failure_and_restores_prior_output(tmp_path: Path):
    pipeline = load_pipeline(tmp_path)
    alpha = write_script(tmp_path, "alpha", success_script("alpha-new"))
    beta = write_script(
        tmp_path,
        "beta",
        '''from pathlib import Path
import sys
base = Path(__file__).parent
unit = base / "ethz"
unit.mkdir(parents=True, exist_ok=True)
(unit / "value.txt").write_text("partial", encoding="utf-8")
sys.exit(3)
''',
    )
    omega = write_script(tmp_path, "_omega", success_script("omega-new"))
    old_output = beta / "ethz"
    old_output.mkdir()
    (old_output / "value.txt").write_text("beta-old", encoding="utf-8")

    assert pipeline.main(["run"]) == 1
    assert (alpha / "ethz" / "value.txt").read_text(encoding="utf-8") == "alpha-new"
    assert (beta / "ethz" / "value.txt").read_text(encoding="utf-8") == "beta-old"
    assert (omega / "ethz" / "value.txt").read_text(encoding="utf-8") == "omega-new"

    manifest = pipeline.load_latest_manifest()
    assert [job["status"] for job in manifest["jobs"]] == [
        "succeeded",
        "failed",
        "succeeded",
    ]
    assert manifest["status"] == "completed_with_failures"
    assert "all configured report units" == manifest["jobs"][1]["unit_scope"]
    assert (tmp_path / manifest["jobs"][1]["log"]).is_file()


def test_resume_and_retry_failed_jobs(tmp_path: Path):
    pipeline = load_pipeline(tmp_path)
    alpha = write_script(tmp_path, "alpha", counter_script("alpha"))
    beta = write_script(
        tmp_path,
        "beta",
        '''from pathlib import Path
import sys
base = Path(__file__).parent
if (base / "fail.flag").exists():
    sys.exit(4)
unit = base / "ethz"
unit.mkdir(parents=True, exist_ok=True)
(unit / "value.txt").write_text("beta", encoding="utf-8")
''',
    )
    (beta / "fail.flag").write_text("fail", encoding="utf-8")

    assert pipeline.main(["run"]) == 1
    assert (alpha / "runs.txt").read_text(encoding="utf-8") == "1"

    manifest = pipeline.load_latest_manifest()
    manifest["status"] = "interrupted"
    manifest["jobs"][1]["status"] = "interrupted"
    pipeline.save_manifest(manifest)
    (beta / "fail.flag").unlink()

    assert pipeline.main(["run", "--resume"]) == 0
    assert (alpha / "runs.txt").read_text(encoding="utf-8") == "1"
    assert (beta / "ethz" / "value.txt").read_text(encoding="utf-8") == "beta"

    (beta / "fail.flag").write_text("fail", encoding="utf-8")
    assert pipeline.main(["run"]) == 1
    (beta / "fail.flag").unlink()
    assert pipeline.main(["run", "--retry-failed"]) == 0
    assert (alpha / "runs.txt").read_text(encoding="utf-8") == "2"


def test_skip_existing_uses_completion_markers_and_script_digest(tmp_path: Path):
    pipeline = load_pipeline(tmp_path)
    alpha = write_script(tmp_path, "alpha", counter_script("alpha"))

    assert pipeline.main(["run"]) == 0
    assert (alpha / "runs.txt").read_text(encoding="utf-8") == "1"

    legacy = write_script(tmp_path, "legacy", counter_script("legacy"))
    legacy_unit = legacy / "ethz"
    legacy_unit.mkdir()
    (legacy_unit / "value.txt").write_text("legacy-output", encoding="utf-8")

    assert pipeline.main(["run", "--skip-existing"]) == 0
    assert (alpha / "runs.txt").read_text(encoding="utf-8") == "1"
    assert (legacy / "runs.txt").read_text(encoding="utf-8") == "1"

    (alpha / "script.py").write_text(counter_script("alpha-new") + "\n# changed\n", encoding="utf-8")
    assert pipeline.main(["run", "--skip-existing"]) == 0
    assert (alpha / "runs.txt").read_text(encoding="utf-8") == "2"
    assert (legacy / "runs.txt").read_text(encoding="utf-8") == "1"


def test_recovery_restores_an_interrupted_transaction(tmp_path: Path):
    pipeline = load_pipeline(tmp_path)
    asset_dir = write_script(tmp_path, "alpha", success_script("new"))
    old_output = asset_dir / "ethz"
    old_output.mkdir()
    (old_output / "value.txt").write_text("old", encoding="utf-8")

    transaction = pipeline.transaction_dir("test-run", "alpha")
    original = transaction / "original"
    original.mkdir(parents=True)
    old_output.replace(original / "ethz")
    partial_output = asset_dir / "ethz"
    partial_output.mkdir()
    (partial_output / "value.txt").write_text("partial", encoding="utf-8")
    pipeline.write_json_atomic(
        pipeline.transaction_metadata_path(transaction),
        {
            "asset_id": "alpha",
            "units": list(pipeline.REPORT_UNITS),
            "state": "active",
        },
    )

    pipeline.recover_transactions()
    assert (asset_dir / "ethz" / "value.txt").read_text(encoding="utf-8") == "old"
    assert not transaction.exists()


