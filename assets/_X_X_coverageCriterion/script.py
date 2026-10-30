import shutil

from core.asset import Asset


asset = Asset(script_file=__file__)

SOURCE_ASSET = asset.base_dir.parent / "X_X_coverage"
SOURCE_TO_TARGET = {
    "scope.csv": "data.csv",
    "scope.pdf": "figure.pdf",
    "scope.png": "figure.png",
    "scope.svg": "figure.svg",
}


for inst in asset.institutions:
    source_dir = SOURCE_ASSET / inst
    out = asset.inst_dir(inst)

    missing = [name for name in SOURCE_TO_TARGET if not (source_dir / name).is_file()]
    if missing:
        missing_paths = ", ".join(str(source_dir / name) for name in missing)
        raise FileNotFoundError(
            "This meta asset depends on X_X_coverage scope outputs. "
            f"Missing: {missing_paths}"
        )

    # Clean legacy names from earlier runs of this meta asset.
    for legacy_name in ("scope.csv", "scope.pdf", "scope.png", "scope.svg"):
        legacy_path = out / legacy_name
        if legacy_path.exists():
            legacy_path.unlink()

    for source_name, target_name in SOURCE_TO_TARGET.items():
        shutil.copy2(source_dir / source_name, out / target_name)
