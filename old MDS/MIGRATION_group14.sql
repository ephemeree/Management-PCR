-- MIGRATION_group14.sql
-- Drop four dead tables.
--
-- Verified before writing this file (against the live ipcr_db, 2026-09-03):
--   * zero references in app/ (.py + .html) and in the root-level scripts
--   * zero rows in each table
--   * no foreign keys, views, triggers or stored procedures point at them
--   * their only remaining mention anywhere is TRUNCATE lines in
--     "old MDS/RESET_for_clean_test.sql" (removed by this migration too --
--     delete those four lines by hand if you keep that script)
--
-- Superseded by:
--   tbl_research_requirements -> tbl_ret_rules
--   tbl_research_options      -> tbl_ret_rule_indicators
--   tbl_addselect_targets     -> tbl_draft_targets (faculty pool selections)
--   tbl_designation_targets   -> tbl_ret_assignments / tbl_ret_extension_distribution
--
-- These tables are children only, so order does not matter and
-- FOREIGN_KEY_CHECKS does not need to be disabled.

DROP TABLE IF EXISTS `tbl_research_options`;
DROP TABLE IF EXISTS `tbl_research_requirements`;
DROP TABLE IF EXISTS `tbl_addselect_targets`;
DROP TABLE IF EXISTS `tbl_designation_targets`;
