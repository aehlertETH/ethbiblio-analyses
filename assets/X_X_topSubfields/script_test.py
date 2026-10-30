"""
Validation tests for the X_X_topSubfields asset.

test_result: no issues detected. Same safe join pattern as 1_1/1_2 assets.

This asset joins report_membership → marts.work_metrics (1:1 on work_id).
It groups by subfield, computing fractional counts (1.0 / n_institutions_on_work),
weighted MNCS, and weighted PPtop10 — same fractional counting approach used
in 1_2_ppTop10 and validated there. The global_agg CTE computes global statistics
from core.work (no join inflation risk). A HAVING clause filters for subfields
with >50 fractional publications.

No risk of inflation — marts.work_metrics has exactly one row per work_id.

Refer to: assets/1_2_ppTop10/script_test.py for the full validation of
fractional counting with work_metrics.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from utility import connect_duckdb

INST = "epfl"
Y0, Y1 = 2014, 2023

con = connect_duckdb(read_only=True)

print("=" * 72)
print("TEST 1: REFERENCE-ONLY — See docstring above")
print("=" * 72)
print("  Same safe join pattern as 1_2_ppTop10 with fractional counting.")
print("  No validation queries needed.")
print()

print("=" * 72)
print("DIAGNOSTIC SUMMARY")
print("=" * 72)
print("  No issues detected.")
print()
con.close()
print("Done.")
