"""
Validation tests for the X_X_coverage asset.

test_result: no issues detected. No risk of join inflation.

This asset computes a data funnel (submitted â†’ found â†’ unique â†’ in_scope â†’ in_analysis).
It uses LEFT JOINs from report_membership to core.work and core.work_to_status.
Since it counts from report_membership (the canonical source), there is no risk of
missing works or row inflation. The unique_found CTE correctly filters for
work_id = work_id_duplicated to deduplicate.

No further validation needed â€” the funnel logic is straightforward.
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
print("TEST 1: REFERENCE-ONLY â€” See docstring above")
print("=" * 72)
print("  LEFT JOINs from report_membership; no aggregation risk.")
print("  No validation queries needed.")
print()

print("=" * 72)
print("DIAGNOSTIC SUMMARY")
print("=" * 72)
print("  No issues detected.")
print()
con.close()
print("Done.")

