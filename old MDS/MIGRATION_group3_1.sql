-- Group 3.1 — Research targets carry a description and a duration
--
-- Recorded after the fact. This DDL was applied by hand during development and never
-- written to a file, so a fresh clone had no way to reach the current schema. The
-- definitions below were read back from the live database.
--
-- Without these columns a research target has no duration, so Timeliness can never be
-- computed for it and every research row rates T as unavailable.

USE ipcr_db;

ALTER TABLE tbl_ret_rule_indicators
  ADD COLUMN target_description    TEXT NULL AFTER target_quantity,
  ADD COLUMN target_duration_value INT NULL AFTER target_description,
  ADD COLUMN target_duration_unit  ENUM('days','weeks','months','semesters') NULL
      AFTER target_duration_value;
