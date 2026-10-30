"""
Tests for the WoS vs OpenAlex classification comparison asset.
"""

import sys
import tempfile
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wos_io
from wos_io import normalize_doi, load_wos_folder, load_coverage_bridge

REPO_ROOT = Path(__file__).resolve().parents[2]
WOS_DIR = REPO_ROOT / "data" / "wos_exports"
COVERAGE_DIR = REPO_ROOT / "coverage"


# --- DOI normalization ---

@pytest.mark.parametrize("raw,expected", [
    ("10.1000/xyz", "10.1000/xyz"),
    ("https://doi.org/10.1000/XYZ", "10.1000/xyz"),
    ("http://dx.doi.org/10.1000/ABC", "10.1000/abc"),
    ("DOI:10.1000/FOO", "10.1000/foo"),
    ("", None),
    (None, None),
    (pd.NA, None),
    (float("nan"), None),
    ("nan", None),
    ("not a doi", None),
])
def test_normalize_doi(raw, expected):
    assert normalize_doi(raw) == expected


# --- Tab-delimited parser ---

TAB_FIXTURE = (
    "PT\tAU\tTI\tSO\tDI\tPY\tDT\tWC\tUT\n"
    "J\tSmith, A\tTitle One\tJournal A\t10.1000/a\t2020\tArticle\tPhysics\tWOS:000001\n"
    "J\tJones, B\tTitle Two\tJournal B\t10.1000/b\t2021\tReview\tChemistry\tWOS:000002\n"
)


def test_parse_tab_delimited():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "test.txt"
        p.write_text(TAB_FIXTURE, encoding="utf-8-sig")
        df = load_wos_folder(Path(d))
    assert len(df) == 2
    assert set(df["doi_norm"]) == {"10.1000/a", "10.1000/b"}
    assert "ut" in df.columns
    assert "wos_categories" in df.columns


# --- Tagged plaintext parser ---

TAGGED_FIXTURE = """FN Clarivate Analytics Web of Science
VR 1.0
PT J
AU Author, A
TI Tagged Title
SO Some Journal
DI 10.2000/tagged
PY 2019
DT Article
WC Engineering, Civil
UT WOS:000099

ER

PT J
AU Author, B
TI Another Tagged
SO Another Journal
DI 10.2000/tagged2
PY 2018
DT Article
WC Computer Science
UT WOS:000098

ER
"""


def test_parse_tagged():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "tagged.txt"
        p.write_text(TAGGED_FIXTURE)
        df = load_wos_folder(Path(d))
    assert len(df) == 2
    assert set(df["doi_norm"]) == {"10.2000/tagged", "10.2000/tagged2"}


# --- Real Eawag tagged file (integration test) ---

@pytest.mark.skipif(
    not (WOS_DIR / "eawag" / "savedrecs (10).txt").exists(),
    reason="Eawag tagged fixture not available",
)
def test_parse_eawag_tagged():
    folder = WOS_DIR / "eawag"
    tagged_file = folder / "savedrecs (10).txt"
    with tempfile.TemporaryDirectory() as d:
        target = Path(d) / tagged_file.name
        target.write_bytes(tagged_file.read_bytes())
        df = load_wos_folder(Path(d))
    assert len(df) > 0
    assert df["doi_norm"].notna().sum() > 0


# --- Deduplication ---

def test_dedup_same_file_twice():
    with tempfile.TemporaryDirectory() as d:
        p1 = Path(d) / "copy1.txt"
        p2 = Path(d) / "copy2.txt"
        p1.write_text(TAB_FIXTURE, encoding="utf-8-sig")
        p2.write_text(TAB_FIXTURE, encoding="utf-8-sig")
        df = load_wos_folder(Path(d))
    assert len(df) == 2


# --- Coverage bridge ---

@pytest.mark.skipif(
    not (COVERAGE_DIR / "epfl.xlsx").exists(),
    reason="EPFL coverage file not available",
)
def test_coverage_bridge():
    bridge = load_coverage_bridge(COVERAGE_DIR / "epfl.xlsx")
    assert "doi_norm" in bridge.columns
    assert "work_id" in bridge.columns
    assert bridge["doi_norm"].notna().all()
    assert bridge["work_id"].notna().all()
    assert not bridge["doi_norm"].duplicated().any()
    assert len(bridge) > 100


def test_coverage_bridge_uses_all_dois(monkeypatch):
    def fake_read_excel(*args, **kwargs):
        return pd.DataFrame([
            {
                "dois": "['10.1000/a', 'https://doi.org/10.1000/B']",
                "openalex_work_id": "W123",
            },
            {
                "dois": "",
                "openalex_work_id": "W456",
            },
        ])

    monkeypatch.setattr(wos_io.pd, "read_excel", fake_read_excel)

    bridge = load_coverage_bridge(Path("dummy.xlsx"))
    assert set(bridge["doi_norm"]) == {"10.1000/a", "10.1000/b"}
    assert set(bridge["work_id"]) == {123}


# --- Integration: EPFL end-to-end ---

@pytest.mark.skipif(
    not (WOS_DIR / "epfl").exists() or not (COVERAGE_DIR / "epfl.xlsx").exists(),
    reason="EPFL data not available",
)
def test_epfl_join_integrity():
    from utility import connect_duckdb

    wos = load_wos_folder(WOS_DIR / "epfl")
    bridge = load_coverage_bridge(COVERAGE_DIR / "epfl.xlsx")

    con = connect_duckdb(read_only=True)
    try:
        dwh = con.query("""
            SELECT r.work_id, w.subfield, tt.subfield_name
            FROM reports.report_membership r
            JOIN core.work w ON w.work_id = r.work_id
            LEFT JOIN core.topics_tree tt ON tt.subfield = w.subfield
            WHERE r.report_name = 'epfl' AND r.work_id IS NOT NULL
        """).df()
    finally:
        con.close()

    wos_doi = wos[wos["doi_norm"].notna()]
    matched = wos_doi.merge(bridge, on="doi_norm", how="inner")
    matched = matched.merge(dwh, on="work_id", how="inner")
    matched = matched.drop_duplicates(subset="work_id", keep="first")

    assert len(matched) > 0
    assert matched["work_id"].notna().all()
    assert matched["doi_norm"].notna().all()
    assert not matched["work_id"].duplicated().any()

    sample = matched.sample(n=min(1000, len(matched)), random_state=42)
    assert len(sample) == min(1000, len(matched))
    assert not sample["work_id"].duplicated().any()


# --- Known DOI cross-check ---

@pytest.mark.skipif(
    not (WOS_DIR / "epfl").exists() or not (COVERAGE_DIR / "epfl.xlsx").exists(),
    reason="EPFL data not available",
)
def test_known_doi_in_bridge():
    bridge = load_coverage_bridge(COVERAGE_DIR / "epfl.xlsx")
    known_doi = normalize_doi("10.3389/fnana.2018.00083")
    assert known_doi in bridge["doi_norm"].values
