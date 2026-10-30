from core.asset import Asset
from assets.collaboration_top_partners_common import (
    DOMAIN_MEMBERS,
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
from assets.X_X_collaborationTopPartners.script import (
    EXCLUDE_CHILDREN_FROM_TOP_N,
    EXCLUDE_ETH_UNITS_FROM_TOP_N,
    RECENT_WINDOW,
    TOP_N_MAIN,
    YEARS,
    q_partners_agg,
    q_partners_yearly_wide,
)

asset = Asset(script_file=__file__)

DISPLAY_EXCLUDED_ROW_TEXT_CELL_INDEXES = {0, 1, 2, 3, 5, 7, 8}


def main() -> None:
    con = asset.connect()
    try:
        core_ids, ethdomain_ids, _ = fetch_report_institution_sets(con)
        child_ids = load_child_ids()
        ethdomain_extra_ids = load_ethdomain_extra_ids()

        for inst in DOMAIN_MEMBERS:
            raw_partners = con.execute(q_partners_agg(inst)).df()
            raw_yearly = con.execute(q_partners_yearly_wide(inst)).df()

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
            base_df = filter_min_partner_frac_count(base_df)

            uncapped_internal = sorted_with_row_order(base_df)
            capped_prepost_internal = capped_view(
                base_df,
                top_n=TOP_N_MAIN,
                exclude_children_from_top_n=EXCLUDE_CHILDREN_FROM_TOP_N,
                exclude_eth_units_from_top_n=EXCLUDE_ETH_UNITS_FROM_TOP_N,
            )
            display_base_df = base_df.copy()
            display_uncapped_internal = sorted_with_row_order(display_base_df)
            capped_internal = capped_view(
                display_base_df,
                top_n=TOP_N_MAIN,
                exclude_children_from_top_n=EXCLUDE_CHILDREN_FROM_TOP_N,
                exclude_eth_units_from_top_n=EXCLUDE_ETH_UNITS_FROM_TOP_N,
            )

            raw_yearly_subset = filter_yearly_raw_for_partners(
                raw_yearly,
                uncapped_internal["institution_id"],
            )

            uncapped_export = to_indicator_export(uncapped_internal, YEARS)
            capped_prepost_export = to_indicator_export(capped_prepost_internal, YEARS)
            display_uncapped_export = to_indicator_export(display_uncapped_internal, YEARS)
            capped_export = to_indicator_export(capped_internal, YEARS)
            uncapped_internal_export = round_float_columns_for_stable_csv(uncapped_internal)
            raw_yearly_subset_export = round_float_columns_for_stable_csv(raw_yearly_subset)
            uncapped_export_csv = round_float_columns_for_stable_csv(uncapped_export)
            capped_prepost_export_csv = round_float_columns_for_stable_csv(capped_prepost_export)
            display_uncapped_export_csv = round_float_columns_for_stable_csv(display_uncapped_export)
            capped_export_csv = round_float_columns_for_stable_csv(capped_export)

            out = asset.inst_dir(inst)
            uncapped_internal_export.to_csv(out / "data_raw_partners.csv", index=False)
            raw_yearly_subset_export.to_csv(out / "data_raw_yearly.csv", index=False)

            uncapped_export_csv.to_csv(out / "data_prepost_uncapped.csv", index=False)
            capped_prepost_export_csv.to_csv(out / "data_prepost.csv", index=False)
            display_uncapped_export_csv.to_csv(out / "data_uncapped.csv", index=False)
            capped_export_csv.to_csv(out / "data.csv", index=False)

            table_tex = build_top_partners_table_tex(
                capped_internal,
                YEARS,
                recent_window=RECENT_WINDOW,
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

            print(f"{inst} -> exported OpenAlex-star test top-partners outputs")
    finally:
        con.close()


if __name__ == "__main__":
    main()
