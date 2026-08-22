-- Group 7 — Administrative (oversight) targets on a designated faculty's own IPCR
USE ipcr_db;

-- 1) A Program Chair holds their department's cascaded quota *whole* as an oversight
-- accountability, and may separately hold the same indicator as their own allocated
-- teaching work. The two rate under different IPCR categories, so the target type alone
-- cannot decide the category — this flag does.
--
--   is_admin_function = 1  -> rolls up under the designated faculty's
--                             Strategic Priorities/Support Functions category (75%)
--   is_admin_function = 0  -> follows the normal target type -> category mapping
ALTER TABLE tbl_draft_targets
  ADD COLUMN is_admin_function TINYINT(1) NOT NULL DEFAULT 0 AFTER review_status;

ALTER TABLE tbl_committed_targets
  ADD COLUMN is_admin_function TINYINT(1) NOT NULL DEFAULT 0 AFTER status;

-- 2) Collation repair.
--
-- Tables added by the earlier migrations in this track were created with an explicit
-- COLLATE=utf8mb4_general_ci, while the original schema uses the server default
-- utf8mb4_0900_ai_ci. Comparing a VARCHAR from one against a VARCHAR from the other fails
-- outright with "Illegal mix of collations" — hit when matching
-- tbl_cascaded_quotas.assigned_to_role against tbl_departments.department_name.
--
-- The application works around that one case, but the mismatch will keep biting any future
-- join, so normalise the tables onto the schema default.
ALTER TABLE tbl_departments               CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
ALTER TABLE tbl_teaching_load_config      CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
ALTER TABLE tbl_ipcr_categories           CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
ALTER TABLE tbl_ipcr_category_types       CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
ALTER TABLE tbl_criteria_weights          CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
ALTER TABLE tbl_final_score_breakdown     CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
ALTER TABLE tbl_ret_assignments           CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
ALTER TABLE tbl_ret_extension_distribution CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;

-- Verify afterwards — this should return no rows:
--   SELECT TABLE_NAME, TABLE_COLLATION FROM information_schema.TABLES
--   WHERE TABLE_SCHEMA = 'ipcr_db' AND TABLE_COLLATION <> 'utf8mb4_0900_ai_ci';

-- 3) Backfill is_admin_function on existing designated-faculty targets.
--
-- A designated faculty's Core Functions are only their personal teaching work: the mandatory
-- teaching load plus whatever instruction the Program Chair allocated to them. Everything
-- else they carry — targets picked from the Instruction/Support pool, custom items, and a
-- chair's oversight cascades — belongs to Strategic Priorities/Support Functions.
--
-- Rows committed before this column existed all default to 0, so every one of them counted
-- as a Core Function. That is why a Designated Faculty with 3 core + 1 strategic target
-- showed 4 core + 0 strategic, leaving the 75% category empty and the rating at "Poor".
--
-- Regular Faculty are untouched: the flag has no meaning for them.

UPDATE tbl_committed_targets ct
JOIN tbl_master_indicators mi ON ct.indicator_id = mi.indicator_id
JOIN tbl_employee_profiles ep ON ct.emp_id = ep.emp_id
SET ct.is_admin_function = 1
WHERE ep.designation IS NOT NULL
  AND ep.designation NOT IN ('Regular Faculty', 'Admin')
  AND COALESCE(ct.target_description, mi.indicator_description) NOT LIKE '%Teaching Load%'
  AND NOT EXISTS (
      SELECT 1 FROM tbl_draft_allocation da
      JOIN tbl_master_indicators mi2 ON da.indicator_id = mi2.indicator_id
      JOIN tbl_target_categories tc2 ON mi2.category_id = tc2.category_id
      WHERE da.emp_id = ct.emp_id AND da.indicator_id = ct.indicator_id
        AND tc2.slug = 'instruction' AND COALESCE(da.assigned_quantity, 0) > 0);

UPDATE tbl_draft_targets dt
JOIN tbl_master_indicators mi ON dt.indicator_id = mi.indicator_id
JOIN tbl_employee_profiles ep ON dt.emp_id = ep.emp_id
SET dt.is_admin_function = 1
WHERE ep.designation IS NOT NULL
  AND ep.designation NOT IN ('Regular Faculty', 'Admin')
  AND COALESCE(dt.target_description, mi.indicator_description) NOT LIKE '%Teaching Load%'
  AND NOT EXISTS (
      SELECT 1 FROM tbl_draft_allocation da
      JOIN tbl_master_indicators mi2 ON da.indicator_id = mi2.indicator_id
      JOIN tbl_target_categories tc2 ON mi2.category_id = tc2.category_id
      WHERE da.emp_id = dt.emp_id AND da.indicator_id = dt.indicator_id
        AND tc2.slug = 'instruction' AND COALESCE(da.assigned_quantity, 0) > 0);
