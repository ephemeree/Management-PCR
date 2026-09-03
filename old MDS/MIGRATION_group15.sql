-- MIGRATION_group15.sql
-- Repair orphaned review data and add the foreign keys that let it accumulate.
--
-- Background: tbl_draft_targets rows are deleted and recreated on every faculty
-- resubmit, but no *_review_items table had a foreign key on draft_id, so review
-- items were left pointing at draft rows that no longer exist. As of writing:
-- 228 dean + 146 chair + 63 ret orphaned items, all belonging to CLOSED terms
-- (zero in the active term). tbl_ipcr_dean_review_items had no foreign key at all.
--
-- Section 1 removes the existing damage; section 2 makes it structurally impossible.
--
-- Run AFTER MIGRATION_group14.sql.

-- =============================================================================
-- 1. CLEANUP  (must run before the constraints below, or the ALTERs will fail)
-- =============================================================================

-- Review headers whose subject or reviewer no longer exists. One such chair row
-- exists today (both its emp_id and chair_emp_id point at a deleted employee);
-- the ret/dean statements are no-ops now but guard against drift before this runs.
-- Child items follow via the existing ON DELETE CASCADE.

DELETE cr FROM tbl_ipcr_chair_review cr
LEFT JOIN tbl_employee_profiles e ON e.emp_id = cr.emp_id
LEFT JOIN tbl_employee_profiles c ON c.emp_id = cr.chair_emp_id
LEFT JOIN tbl_academic_terms t ON t.term_id = cr.term_id
WHERE e.emp_id IS NULL OR c.emp_id IS NULL OR t.term_id IS NULL;

DELETE rr FROM tbl_ipcr_ret_review rr
LEFT JOIN tbl_employee_profiles c ON c.emp_id = rr.ret_chair_emp_id
LEFT JOIN tbl_academic_terms t ON t.term_id = rr.term_id
WHERE c.emp_id IS NULL OR t.term_id IS NULL;

DELETE dr FROM tbl_ipcr_dean_review dr
LEFT JOIN tbl_employee_profiles e ON e.emp_id = dr.emp_id
LEFT JOIN tbl_employee_profiles d ON d.emp_id = dr.dean_id
LEFT JOIN tbl_academic_terms t ON t.term_id = dr.term_id
WHERE e.emp_id IS NULL OR d.emp_id IS NULL OR t.term_id IS NULL;

-- Dean review items whose parent review is gone (no FK existed to prevent this).

DELETE dri FROM tbl_ipcr_dean_review_items dri
LEFT JOIN tbl_ipcr_dean_review dr ON dr.review_id = dri.review_id
WHERE dr.review_id IS NULL;

-- The orphaned items themselves: review rows pointing at deleted draft targets.

DELETE ri FROM tbl_ipcr_chair_review_items ri
LEFT JOIN tbl_draft_targets d ON d.draft_id = ri.draft_id
WHERE d.draft_id IS NULL;

DELETE ri FROM tbl_ipcr_ret_review_items ri
LEFT JOIN tbl_draft_targets d ON d.draft_id = ri.draft_id
WHERE d.draft_id IS NULL;

DELETE dri FROM tbl_ipcr_dean_review_items dri
LEFT JOIN tbl_draft_targets d ON d.draft_id = dri.draft_id
WHERE d.draft_id IS NULL;

-- Items referencing a deleted master indicator (none today; guards the FK below).

DELETE ri FROM tbl_ipcr_chair_review_items ri
LEFT JOIN tbl_master_indicators mi ON mi.indicator_id = ri.indicator_id
WHERE mi.indicator_id IS NULL;

DELETE ri FROM tbl_ipcr_ret_review_items ri
LEFT JOIN tbl_master_indicators mi ON mi.indicator_id = ri.indicator_id
WHERE mi.indicator_id IS NULL;

DELETE dri FROM tbl_ipcr_dean_review_items dri
LEFT JOIN tbl_master_indicators mi ON mi.indicator_id = dri.indicator_id
WHERE mi.indicator_id IS NULL;

-- =============================================================================
-- 2. CONSTRAINTS
-- =============================================================================

-- draft_id must be nullable to carry ON DELETE SET NULL. This is deliberate:
-- CASCADE would erase a Program Chair's reviewed_quantity adjustments every time
-- a faculty member resubmits (which deletes and recreates their draft rows).
-- A NULL draft_id fails the `ri.draft_id = dt.draft_id` joins in exactly the same
-- way a dangling id does today, so no query result changes. The one NULL-sensitive
-- spot, the NOT IN anti-join in app/models/dean.py, already wraps it in
-- COALESCE(draft_id, 0).
--
-- tbl_ipcr_dean_review_items.draft_id is already nullable.

ALTER TABLE tbl_ipcr_chair_review_items MODIFY COLUMN draft_id int NULL;

ALTER TABLE tbl_ipcr_ret_review_items MODIFY COLUMN draft_id int NULL;

-- Review headers. The subject (emp_id) cascades, matching the existing
-- fk_ret_review_emp. The reviewer (chair_emp_id / dean_id / ret_chair_emp_id) uses
-- the default RESTRICT: cascading there would mean deleting one Program Chair wipes
-- every review they ever signed. Nothing in the application deletes employees, so
-- RESTRICT cannot block any existing code path.

ALTER TABLE tbl_ipcr_chair_review
  ADD CONSTRAINT fk_chair_review_emp FOREIGN KEY (emp_id)
      REFERENCES tbl_employee_profiles (emp_id) ON DELETE CASCADE,
  ADD CONSTRAINT fk_chair_review_term FOREIGN KEY (term_id)
      REFERENCES tbl_academic_terms (term_id) ON DELETE CASCADE,
  ADD CONSTRAINT fk_chair_review_chair FOREIGN KEY (chair_emp_id)
      REFERENCES tbl_employee_profiles (emp_id);

-- tbl_ipcr_ret_review already has fk_ret_review_emp on emp_id and uq_ret_review.

ALTER TABLE tbl_ipcr_ret_review
  ADD CONSTRAINT fk_ret_review_term FOREIGN KEY (term_id)
      REFERENCES tbl_academic_terms (term_id) ON DELETE CASCADE,
  ADD CONSTRAINT fk_ret_review_chair FOREIGN KEY (ret_chair_emp_id)
      REFERENCES tbl_employee_profiles (emp_id);

-- The dean review is the only one of the three with no UNIQUE (emp_id, term_id);
-- nothing currently stops a duplicate dean review for the same person and term.

ALTER TABLE tbl_ipcr_dean_review
  ADD UNIQUE KEY uq_dean_review (emp_id, term_id),
  ADD CONSTRAINT fk_dean_review_emp FOREIGN KEY (emp_id)
      REFERENCES tbl_employee_profiles (emp_id) ON DELETE CASCADE,
  ADD CONSTRAINT fk_dean_review_term FOREIGN KEY (term_id)
      REFERENCES tbl_academic_terms (term_id) ON DELETE CASCADE,
  ADD CONSTRAINT fk_dean_review_dean FOREIGN KEY (dean_id)
      REFERENCES tbl_employee_profiles (emp_id);

-- Review items.
--
-- indicator_id cascades to match the ON DELETE CASCADE already on
-- tbl_draft_targets.indicator_id, so deleting a master indicator cleans up
-- consistently instead of becoming a new blocker on the Admin delete path.
--
-- UNIQUE (review_id, draft_id) is what the existing INSERT IGNORE in
-- app/models/dean.py was written to rely on. It is NOT keyed on indicator_id:
-- tbl_ipcr_dean_review_items has 24 legitimate duplicate (review_id, indicator_id)
-- pairs. MySQL permits repeated NULLs in a unique index, so items whose draft is
-- later deleted do not collide.

ALTER TABLE tbl_ipcr_chair_review_items
  ADD UNIQUE KEY uq_chair_review_item (review_id, draft_id),
  ADD CONSTRAINT fk_chair_item_draft FOREIGN KEY (draft_id)
      REFERENCES tbl_draft_targets (draft_id) ON DELETE SET NULL,
  ADD CONSTRAINT fk_chair_item_ind FOREIGN KEY (indicator_id)
      REFERENCES tbl_master_indicators (indicator_id) ON DELETE CASCADE;

ALTER TABLE tbl_ipcr_ret_review_items
  ADD UNIQUE KEY uq_ret_review_item (review_id, draft_id),
  ADD CONSTRAINT fk_ret_item_draft FOREIGN KEY (draft_id)
      REFERENCES tbl_draft_targets (draft_id) ON DELETE SET NULL,
  ADD CONSTRAINT fk_ret_item_ind FOREIGN KEY (indicator_id)
      REFERENCES tbl_master_indicators (indicator_id) ON DELETE CASCADE;

ALTER TABLE tbl_ipcr_dean_review_items
  ADD UNIQUE KEY uq_dean_review_item (review_id, draft_id),
  ADD CONSTRAINT fk_dean_item_review FOREIGN KEY (review_id)
      REFERENCES tbl_ipcr_dean_review (review_id) ON DELETE CASCADE,
  ADD CONSTRAINT fk_dean_item_draft FOREIGN KEY (draft_id)
      REFERENCES tbl_draft_targets (draft_id) ON DELETE SET NULL,
  ADD CONSTRAINT fk_dean_item_ind FOREIGN KEY (indicator_id)
      REFERENCES tbl_master_indicators (indicator_id) ON DELETE CASCADE;

-- Remaining unenforced references.
--
-- master_indicators.term_id is what makes every term-scoped query work (drafts and
-- committed targets carry no term_id of their own and resolve the term through this
-- column), yet it had no constraint. RESTRICT: nothing deletes terms.

ALTER TABLE tbl_master_indicators
  ADD CONSTRAINT fk_master_ind_term FOREIGN KEY (term_id)
      REFERENCES tbl_academic_terms (term_id);

ALTER TABLE tbl_co_authors
  ADD CONSTRAINT fk_coauth_emp FOREIGN KEY (emp_id)
      REFERENCES tbl_employee_profiles (emp_id) ON DELETE CASCADE;
