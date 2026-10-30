from dataclasses import dataclass
from pathlib import Path

import pandas as pd





# Queries below:

def q_productivity (inst: str, year_first: int | None = None, year_last: int | None = None) -> str:
    year_first = REPORT_DEFAULTS.year_first if year_first is None else year_first
    year_last = REPORT_DEFAULTS.year_last if year_last is None else year_last

    return f"""
        SELECT
            w.publication_year As year,
            COUNT(DISTINCT w.work_id) AS full_count,
            ROUND(SUM(wii.weight_frac), 2) AS fractional_count
        FROM marts.work_institution_info wii
        JOIN core.work w
            ON wii.work_id = w.work_id
        WHERE wii.institution_id IN (
        SELECT institution_id
        FROM reports.report_institutions_ids
        WHERE report_name = '{inst}'
        )
        AND w.publication_year BETWEEN {year_first} AND {year_last}
        GROUP BY w.publication_year
        ORDER BY w.publication_year;
        """


def q_sizedependence_indicators (inst: str, year_first: int | None = None, year_last: int | None = None) -> str:
    year_first = REPORT_DEFAULTS.year_first if year_first is None else year_first
    year_last = REPORT_DEFAULTS.year_last if year_last is None else year_last

    # inst not needed in this query

    return f"""SELECT
                    r.report_name,
                    SUM(wii.weight_full) AS p_full,
                    ROUND(SUM(wii.weight_frac), 4) AS p_frac,
                    COUNT(DISTINCT CASE WHEN wm.is_top10 = 1 THEN wii.work_id END) AS p_top10
                FROM marts.work_institution_info wii
                JOIN reports.report_institutions_ids r
                    ON wii.institution_id = r.institution_id
                JOIN marts.work_metrics wm
                    ON wii.work_id = wm.work_id
                JOIN core.work as w
                    ON wii.work_id = w.work_id
                WHERE w.publication_year BETWEEN {year_first} AND {year_last}
                GROUP BY r.report_name
                ORDER BY
                    report_name ASC;
                """

