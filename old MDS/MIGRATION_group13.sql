-- Group 13 — RET Menu lock flag (Extension rank-band lock)
--
-- Backs REVISION MDs/ret_menu_and_extension_distribution_refactor.md. That refactor moves
-- Extension configuration out of the legacy one-time-lock tbl_ret_extension_distribution table
-- and into tbl_ret_rules/tbl_ret_rule_indicators (the same relational rank-band rules table
-- Research already uses), which is normally freely deleted-and-rewritten on every save.
--
-- To preserve the original "distribute once, then locked" safety valve for Extension —
-- deliberately chosen in old MDS/RET_REDESIGN.md so a chair can't accidentally reshuffle
-- workload a faculty member has already started acting on — tbl_ret_rules gets a per-row lock
-- flag. Each row is already scoped to one (academic_rank, category) pair (save_ret_rule inserts
-- a separate row for Research vs Extension), so locking is per rank-band-per-category: an
-- Extension rule can be locked independently of the Research rule for the same band, and the
-- RET Chair can unlock one explicitly when they need to correct it.
--
-- All existing rows today are Research-only (Extension lived in tbl_ret_extension_distribution
-- until this refactor), so defaulting every existing row to unlocked (0) is correct — nothing
-- previously configured was ever "distributed" through this table.

USE ipcr_db;

ALTER TABLE tbl_ret_rules
  ADD COLUMN is_locked TINYINT(1) NOT NULL DEFAULT 0 AFTER required_selections;
