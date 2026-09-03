-- Group 12 — Master Indicators category scope
--
-- Widens tbl_ipcr_categories.designation_type from a 2-value ENUM to VARCHAR(50) so a third
-- scope, 'Master Indicators', can exist alongside 'Regular Faculty' and 'Designated Faculty'.
-- This scope only drives the Admin Dashboard's Master Indicators panel grouping/display — it is
-- never read by scoring, weight rules, or the printed IPCR (those all resolve a concrete
-- Regular/Designated designation before querying this table; see
-- REVISION MDs/category_and_criteria_simplification_plan.md for the full trace). Enforcement of
-- the allowed designation_type values moves from the DB-level ENUM to the app-level
-- CATEGORY_SCOPES check in app/models/criteria.py.
--
-- Seeds the Master Indicators scope mirroring Regular Faculty's verified structure (Instruction
-- -> Strategic Priorities, Research/Extension -> Core Functions, Support -> Support Functions)
-- plus the one category Regular Faculty has no use for: Administrative Functions. All INSERTs are
-- idempotent (INSERT IGNORE against unique keys) so this file is safe to re-run.

USE ipcr_db;

-- 1) Widen the column so a third scope value fits.
ALTER TABLE tbl_ipcr_categories
  MODIFY designation_type VARCHAR(50) NOT NULL;

-- 2) Seed the four Master Indicators categories.
INSERT IGNORE INTO tbl_ipcr_categories (designation_type, category_name, display_order)
VALUES
  ('Master Indicators', 'Strategic Priorities', 10),
  ('Master Indicators', 'Core Functions', 20),
  ('Master Indicators', 'Support Functions', 30),
  ('Master Indicators', 'Administrative Functions', 40);

-- 3) Map target types to those categories, keyed by slug (stable across environments).
INSERT IGNORE INTO tbl_ipcr_category_types (ipcr_category_id, category_id)
SELECT ic.ipcr_category_id, tc.category_id
FROM tbl_ipcr_categories ic
JOIN tbl_target_categories tc ON tc.slug = 'instruction'
WHERE ic.designation_type = 'Master Indicators' AND ic.category_name = 'Strategic Priorities';

INSERT IGNORE INTO tbl_ipcr_category_types (ipcr_category_id, category_id)
SELECT ic.ipcr_category_id, tc.category_id
FROM tbl_ipcr_categories ic
JOIN tbl_target_categories tc ON tc.slug IN ('research', 'extension')
WHERE ic.designation_type = 'Master Indicators' AND ic.category_name = 'Core Functions';

INSERT IGNORE INTO tbl_ipcr_category_types (ipcr_category_id, category_id)
SELECT ic.ipcr_category_id, tc.category_id
FROM tbl_ipcr_categories ic
JOIN tbl_target_categories tc ON tc.slug = 'support'
WHERE ic.designation_type = 'Master Indicators' AND ic.category_name = 'Support Functions';

INSERT IGNORE INTO tbl_ipcr_category_types (ipcr_category_id, category_id)
SELECT ic.ipcr_category_id, tc.category_id
FROM tbl_ipcr_categories ic
JOIN tbl_target_categories tc ON tc.slug = 'administrative'
WHERE ic.designation_type = 'Master Indicators' AND ic.category_name = 'Administrative Functions';
