import pandas as pd

from core.asset import Asset
from assets.collaboration_top_partners_common import (
    DOMAIN_MEMBERS,
    DOMAIN_REPORT,
    add_partner_flags,
    add_share_and_change_columns,
    add_year_columns_from_raw,
    build_top_partners_table_tex,
    capped_view,
    fetch_report_institution_sets,
    filter_min_partner_frac_count,
    filter_yearly_raw_for_partners,
    finalize_collab_ratio,
    load_child_ids,
    load_ethdomain_extra_ids,
    round_float_columns_for_stable_csv,
    sorted_with_row_order,
    to_indicator_export,
)
from assets.openalex_annotation_common import (
    ANNOTATED_INSTITUTION_IDS,
    ANNOTATION_NOTES_BY_ID,
    ANNOTATION_PLACEHOLDER_MARKER,
    apply_marked_table_row_styles,
)

asset = Asset(script_file=__file__)

TOP_N_MAIN = 40
EXCLUDE_CHILDREN_FROM_TOP_N = True
EXCLUDE_ETH_UNITS_FROM_TOP_N = True
DISPLAY_EXCLUDED_ROW_TEXT_CELL_INDEXES = {0, 1, 2, 3, 5, 7, 8, 9, 10, 11, 12, 13, 14}

YEAR_FIRST = asset.year_first
YEAR_LAST = asset.year_last
YEARS = list(range(YEAR_FIRST, YEAR_LAST + 1))
RECENT_WINDOW = max(1, int(asset.year_range_moving))
RECENT_END = YEAR_LAST
RECENT_START = max(YEAR_FIRST, RECENT_END - RECENT_WINDOW + 1)
BASELINE_START = YEAR_FIRST
BASELINE_END = RECENT_START - 1


def q_partners_agg_ethdomain() -> str:
    member_list_sql = ", ".join([f"'{m}'" for m in DOMAIN_MEMBERS])

    member_case_cols = []
    member_select_cols = []
    for member in DOMAIN_MEMBERS:
        member_case_cols.append(
            f"SUM(CASE WHEN mpl.domain_member = '{member}' THEN mpl.weight_frac ELSE 0 END) AS frac_{member}"
        )
        member_select_cols.append(f"COALESCE(ma.frac_{member}, 0) AS frac_{member}")

    member_case_sql = ",\n                ".join(member_case_cols)
    member_select_sql = ",\n            ".join(member_select_cols)

    return f"""
        WITH member_inst_ids AS (
            SELECT DISTINCT
                report_name AS member_inst,
                institution_id
            FROM reports.report_institutions_ids
            WHERE report_name IN ({member_list_sql})
        ),
        domain_works AS (
            SELECT DISTINCT
                rm.work_id,
                wm.publication_year,
                wm.norm_vs_mean,
                wm.is_top10,
                wm.cohort_is_reliable,
                1.0 / wm.n_institutions_on_work AS weight_work_frac
            FROM reports.report_membership rm
            JOIN marts.work_metrics wm
              ON wm.work_id = rm.work_id
            WHERE rm.report_name = '{DOMAIN_REPORT}'
              AND wm.publication_year BETWEEN {YEAR_FIRST} AND {YEAR_LAST}
              AND wm.n_institutions_on_work > 0
        ),
        domain_partner_links AS (
            SELECT DISTINCT
                dw.work_id,
                dw.publication_year,
                wii.institution_id,
                wii.weight_frac,
                dw.norm_vs_mean,
                dw.is_top10,
                dw.cohort_is_reliable,
                dw.weight_work_frac
            FROM domain_works dw
            JOIN marts.work_institution_info wii
              ON wii.work_id = dw.work_id
        ),
        collab_works AS (
            SELECT DISTINCT
                work_id,
                publication_year,
                weight_work_frac
            FROM domain_partner_links
        ),
        totals AS (
            SELECT
                (SELECT SUM(weight_work_frac) FROM collab_works) AS p_collab_frac,
                (SELECT SUM(CASE WHEN publication_year BETWEEN {RECENT_START} AND {RECENT_END} THEN weight_work_frac ELSE 0 END) FROM collab_works) AS p_collab_frac_recent,
                (SELECT SUM(CASE WHEN publication_year BETWEEN {BASELINE_START} AND {BASELINE_END} THEN weight_work_frac ELSE 0 END) FROM collab_works) AS p_collab_frac_baseline,
                (SELECT SUM(weight_work_frac) FROM domain_works) AS p_frac
        ),
        member_works AS (
            SELECT DISTINCT
                rm.report_name AS domain_member,
                rm.work_id,
                wm.publication_year
            FROM reports.report_membership rm
            JOIN marts.work_metrics wm
              ON wm.work_id = rm.work_id
            WHERE rm.report_name IN ({member_list_sql})
              AND wm.publication_year BETWEEN {YEAR_FIRST} AND {YEAR_LAST}
        ),
        member_partner_links AS (
            SELECT DISTINCT
                mw.domain_member,
                mw.work_id,
                mw.publication_year,
                wii.institution_id,
                wii.weight_frac
            FROM member_works mw
            JOIN marts.work_institution_info wii
              ON wii.work_id = mw.work_id
            LEFT JOIN member_inst_ids sid
              ON sid.member_inst = mw.domain_member
             AND sid.institution_id = wii.institution_id
            WHERE sid.institution_id IS NULL
        ),
        member_agg AS (
            SELECT
                mpl.institution_id,
                {member_case_sql}
            FROM member_partner_links mpl
            GROUP BY mpl.institution_id
        )
        SELECT
            dpl.institution_id,
            di.name AS institution_name,
            dc.country_code,
            COUNT(DISTINCT dpl.work_id) AS full_count,
            SUM(dpl.weight_frac) AS frac_count,
            COUNT(DISTINCT CASE WHEN dpl.publication_year BETWEEN {RECENT_START} AND {RECENT_END} THEN dpl.work_id END) AS full_recent,
            SUM(CASE WHEN dpl.publication_year BETWEEN {RECENT_START} AND {RECENT_END} THEN dpl.weight_frac ELSE 0 END) AS frac_recent,
            COUNT(DISTINCT CASE WHEN dpl.publication_year BETWEEN {BASELINE_START} AND {BASELINE_END} THEN dpl.work_id END) AS full_baseline,
            SUM(CASE WHEN dpl.publication_year BETWEEN {BASELINE_START} AND {BASELINE_END} THEN dpl.weight_frac ELSE 0 END) AS frac_baseline,
            SUM(CASE WHEN dpl.cohort_is_reliable = TRUE THEN dpl.weight_frac * dpl.norm_vs_mean ELSE 0 END)
                / NULLIF(SUM(CASE WHEN dpl.cohort_is_reliable = TRUE THEN dpl.weight_frac ELSE 0 END), 0) AS mncs,
            SUM(CASE WHEN dpl.cohort_is_reliable = TRUE THEN dpl.weight_frac * CAST(dpl.is_top10 AS DOUBLE) ELSE 0 END)
                / NULLIF(SUM(CASE WHEN dpl.cohort_is_reliable = TRUE THEN dpl.weight_frac ELSE 0 END), 0) AS pp_top10,
            t.p_collab_frac,
            t.p_collab_frac_recent,
            t.p_collab_frac_baseline,
            t.p_frac,
            {member_select_sql}
        FROM domain_partner_links dpl
        LEFT JOIN member_agg ma
          ON ma.institution_id = dpl.institution_id
        LEFT JOIN core.dim_institution di
          ON di.institution_id = dpl.institution_id
        LEFT JOIN core.dim_country dc
          ON dc.country_id = di.country_id
        CROSS JOIN totals t
        GROUP BY
            dpl.institution_id,
            di.name,
            dc.country_code,
            t.p_collab_frac,
            t.p_collab_frac_recent,
            t.p_collab_frac_baseline,
            t.p_frac,
            {', '.join([f'ma.frac_{m}' for m in DOMAIN_MEMBERS])}
        ORDER BY SUM(dpl.weight_frac) DESC, di.name ASC;
    """


def q_partners_yearly_wide_ethdomain() -> str:
    full_cols = ",\n            ".join(
        [
            f"SUM(CASE WHEN py.publication_year = {year} THEN py.full_count ELSE 0 END) AS \"{year}\""
            for year in YEARS
        ]
    )
    frac_cols = ",\n            ".join(
        [
            f"SUM(CASE WHEN py.publication_year = {year} THEN py.frac_count ELSE 0 END) AS \"{year}\""
            for year in YEARS
        ]
    )

    return f"""
        WITH domain_works AS (
            SELECT DISTINCT
                rm.work_id,
                wm.publication_year
            FROM reports.report_membership rm
            JOIN marts.work_metrics wm
              ON wm.work_id = rm.work_id
            WHERE rm.report_name = '{DOMAIN_REPORT}'
              AND wm.publication_year BETWEEN {YEAR_FIRST} AND {YEAR_LAST}
        ),
        domain_partner_links AS (
            SELECT DISTINCT
                dw.work_id,
                dw.publication_year,
                wii.institution_id,
                wii.weight_frac
            FROM domain_works dw
            JOIN marts.work_institution_info wii
              ON wii.work_id = dw.work_id
        ),
        partner_year AS (
            SELECT
                institution_id,
                publication_year,
                COUNT(DISTINCT work_id) AS full_count,
                SUM(weight_frac) AS frac_count
            FROM domain_partner_links
            GROUP BY institution_id, publication_year
        )
        SELECT
            py.institution_id,
            di.name AS institution_name,
            dc.country_code,
            'P_FULL' AS metric_kind,
            {full_cols}
        FROM partner_year py
        LEFT JOIN core.dim_institution di
          ON di.institution_id = py.institution_id
        LEFT JOIN core.dim_country dc
          ON dc.country_id = di.country_id
        GROUP BY py.institution_id, di.name, dc.country_code

        UNION ALL

        SELECT
            py.institution_id,
            di.name AS institution_name,
            dc.country_code,
            'P_FRAC' AS metric_kind,
            {frac_cols}
        FROM partner_year py
        LEFT JOIN core.dim_institution di
          ON di.institution_id = py.institution_id
        LEFT JOIN core.dim_country dc
          ON dc.country_id = di.country_id
        GROUP BY py.institution_id, di.name, dc.country_code

        ORDER BY institution_id, metric_kind;
    """


def main() -> None:
    con = asset.connect()
    try:
        core_ids, ethdomain_ids, _ = fetch_report_institution_sets(con)
        child_ids = load_child_ids()
        ethdomain_extra_ids = load_ethdomain_extra_ids()

        raw_partners = con.execute(q_partners_agg_ethdomain()).df()
        raw_yearly = con.execute(q_partners_yearly_wide_ethdomain()).df()

        base_df = raw_partners.copy()
        base_df = add_partner_flags(
            base_df,
            core_ids=core_ids,
            child_ids=child_ids,
            ethdomain_ids=ethdomain_ids,
            ethdomain_extra_ids=ethdomain_extra_ids,
        )
        base_df = add_year_columns_from_raw(base_df, raw_yearly, YEARS, metric_kind="P_FRAC")
        base_df = add_share_and_change_columns(base_df)
        base_df = finalize_collab_ratio(base_df)

        source_internal = sorted_with_row_order(base_df)
        filtered_base_df = filter_min_partner_frac_count(base_df)

        uncapped_internal = sorted_with_row_order(filtered_base_df)
        capped_prepost_internal = capped_view(
            filtered_base_df,
            top_n=TOP_N_MAIN,
            exclude_children_from_top_n=EXCLUDE_CHILDREN_FROM_TOP_N,
            exclude_eth_units_from_top_n=EXCLUDE_ETH_UNITS_FROM_TOP_N,
        )
        display_base_df = filtered_base_df.copy()
        display_uncapped_internal = sorted_with_row_order(display_base_df)
        capped_internal = capped_view(
            display_base_df,
            top_n=TOP_N_MAIN,
            exclude_children_from_top_n=EXCLUDE_CHILDREN_FROM_TOP_N,
            exclude_eth_units_from_top_n=EXCLUDE_ETH_UNITS_FROM_TOP_N,
        )

        raw_yearly_subset = filter_yearly_raw_for_partners(
            raw_yearly,
            source_internal["institution_id"],
        )

        uncapped_export = to_indicator_export(uncapped_internal, YEARS)
        capped_prepost_export = to_indicator_export(capped_prepost_internal, YEARS)
        display_uncapped_export = to_indicator_export(display_uncapped_internal, YEARS)
        capped_export = to_indicator_export(capped_internal, YEARS)
        source_internal_export = round_float_columns_for_stable_csv(source_internal)
        raw_yearly_subset_export = round_float_columns_for_stable_csv(raw_yearly_subset)
        uncapped_export_csv = round_float_columns_for_stable_csv(uncapped_export)
        capped_prepost_export_csv = round_float_columns_for_stable_csv(capped_prepost_export)
        display_uncapped_export_csv = round_float_columns_for_stable_csv(display_uncapped_export)
        capped_export_csv = round_float_columns_for_stable_csv(capped_export)

        out = asset.inst_dir(DOMAIN_REPORT)
        source_internal_export.to_csv(out / "data_raw_partners.csv", index=False)
        raw_yearly_subset_export.to_csv(out / "data_raw_yearly.csv", index=False)

        uncapped_export_csv.to_csv(out / "data_prepost_uncapped.csv", index=False)
        capped_prepost_export_csv.to_csv(out / "data_prepost.csv", index=False)
        display_uncapped_export_csv.to_csv(out / "data_uncapped.csv", index=False)
        capped_export_csv.to_csv(out / "data.csv", index=False)

        table_tex = build_top_partners_table_tex(
            capped_internal,
            YEARS,
            recent_window=RECENT_WINDOW,
            decomposition_members=DOMAIN_MEMBERS,
            marked_institution_ids=ANNOTATED_INSTITUTION_IDS,
            marked_institution_marker=ANNOTATION_PLACEHOLDER_MARKER,
            marked_institution_notes_by_id=ANNOTATION_NOTES_BY_ID,
            marked_institution_note_mode="below_table",
            marked_institution_note_font=r"\scriptsize",
            marked_institution_note_rule=True,
            marked_institution_note_line_spread="0.90",
        )
        table_tex = apply_marked_table_row_styles(
            table_tex,
            capped_internal,
            text_cell_indexes=DISPLAY_EXCLUDED_ROW_TEXT_CELL_INDEXES,
        )
        (out / "table.tex").write_text(table_tex, encoding="utf-8")

        print("ethdomain -> exported canonical top-partners outputs")
    finally:
        con.close()


if __name__ == "__main__":
    main()
