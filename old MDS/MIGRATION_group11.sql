-- Group 11 — IPCR target description auto-generation tracking
--
-- Backs the auto-generated-vs-customized IPCR target description feature (see
-- REVISION MDs/target_desc.md). Adds a persisted is_auto_description flag to every
-- table that stores a manager/faculty-editable target description, so the backend
-- can tell "still mirroring the master indicator" apart from "user typed custom text"
-- across page reloads and across the multi-role cascade, instead of guessing from a
-- string comparison (which breaks the moment quantity/duration changes after save).
--
-- New rows default to is_auto_description = 1 (auto-mirrored). Existing rows are
-- explicitly backfilled to 0 (treated as already-customized / frozen) so this feature
-- only changes behavior for rows created or edited after this migration runs — no
-- already-committed/printed IPCR changes what it displays. Run the backfill UPDATEs
-- before any application code relying on the new default goes live.

USE ipcr_db;

-- 1) Program Chair / Dean college-wide allocation
ALTER TABLE tbl_draft_allocation
  ADD COLUMN is_auto_description TINYINT(1) NOT NULL DEFAULT 1 AFTER target_duration_unit;
UPDATE tbl_draft_allocation SET is_auto_description = 0;

-- 2) RET Chair — Research Menu rank-based rules
ALTER TABLE tbl_ret_rule_indicators
  ADD COLUMN is_auto_description TINYINT(1) NOT NULL DEFAULT 1 AFTER target_duration_unit;
UPDATE tbl_ret_rule_indicators SET is_auto_description = 0;

-- 3) RET Chair — Direct Assignment
ALTER TABLE tbl_ret_assignments
  ADD COLUMN is_auto_description TINYINT(1) NOT NULL DEFAULT 1 AFTER assigned_by;
UPDATE tbl_ret_assignments SET is_auto_description = 0;

-- 4) RET Chair — Extension Distribution (one-time lock per term; get this right,
--    it cannot be corrected mid-term once distributed)
ALTER TABLE tbl_ret_extension_distribution
  ADD COLUMN is_auto_description TINYINT(1) NOT NULL DEFAULT 1 AFTER distributed_by;
UPDATE tbl_ret_extension_distribution SET is_auto_description = 0;

-- 5) Faculty / Designated Faculty draft targets
ALTER TABLE tbl_draft_targets
  ADD COLUMN is_auto_description TINYINT(1) NOT NULL DEFAULT 1 AFTER is_admin_function;
UPDATE tbl_draft_targets SET is_auto_description = 0;

-- 6) Locked/committed targets (carries the flag forward from tbl_draft_targets at lock time)
ALTER TABLE tbl_committed_targets
  ADD COLUMN is_auto_description TINYINT(1) NOT NULL DEFAULT 1 AFTER print_remarks;
UPDATE tbl_committed_targets SET is_auto_description = 0;
