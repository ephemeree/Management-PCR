-- Group 9 — Direct research assignment description and duration
--
-- Adds target_description, target_duration_value, and target_duration_unit to tbl_ret_assignments
-- so RET Chair directly assigned research targets can carry custom/inherited descriptions and
-- scorable deadlines/durations for Timeliness ratings.

USE ipcr_db;

ALTER TABLE tbl_ret_assignments
  ADD COLUMN target_description    TEXT NULL AFTER target_quantity,
  ADD COLUMN target_duration_value INT NULL AFTER target_description,
  ADD COLUMN target_duration_unit  ENUM('days','weeks','months','semesters') NULL
      AFTER target_duration_value;
