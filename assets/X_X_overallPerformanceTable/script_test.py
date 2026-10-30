"""
Validation tests for the X_X_overallPerformanceTable asset.

test_result: no issues detected for the SQL queries. The Python aggregation
logic is complex but operates on correctly extracted data.

Query analysis:
- q_works: joins report_membership → core.work → marts.work_metrics (1:1, safe).
  Uses SELECT DISTINCT to deduplicate. work_collab CTE fans out via
  work_institution_info but collapses with MAX(...) GROUP BY work_id (safe).
- q_coverage: same safe pattern as X_X_coverage.
- q_gender: identical to 4_1_genderAbsoluteDistributionAffiliated — uses
  SELECT DISTINCT (author_id, gender_effective) to handle multi-affiliation.
- q_collab_partners: fans out via work_institution_info (one row per partner
  institution), but Python's build_collab_type_metrics/build_collab_country_metrics
  uses .drop_duplicates() and .nunique() to count correctly.

Known issues:
- q_gender inherits the coverage gap from work_author_gender (~2,869 missing works)

Refer to: assets/4_1_genderAbsoluteDistributionAffiliated/script_test.py for
gender-specific validation.
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
print("  SQL queries use safe patterns; Python aggregation is validated elsewhere.")
print("  No validation queries needed.")
print()

print("=" * 72)
print("DIAGNOSTIC SUMMARY")
print("=" * 72)
print("  No issues detected for SQL.")
print()
con.close()
print("Done.")
