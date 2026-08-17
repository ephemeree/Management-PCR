-- Group 4 — Category Management
-- Promotes the IPCR "category" (Strategic Priorities / Core Functions / Support
-- Functions) into a first-class, per-designation entity, replacing the hardcoded
-- tbl_target_categories.weight_group column.
USE ipcr_db;

-- 1) New target type used by Designated faculty. Safe to re-run (slug is UNIQUE).
INSERT IGNORE INTO tbl_target_categories
    (category_name, slug, review_lane, is_core, display_order, is_active)
VALUES ('Administrative Functions', 'administrative', 'CHAIR', 1, 15, 1);

-- 2) The IPCR categories that actually carry weight on the printed form.
CREATE TABLE tbl_ipcr_categories (
  ipcr_category_id INT NOT NULL AUTO_INCREMENT,
  designation_type ENUM('Regular Faculty','Designated Faculty') NOT NULL,
  category_name    VARCHAR(120) NOT NULL,
  display_order    INT NOT NULL DEFAULT 100,
  is_active        TINYINT(1) NOT NULL DEFAULT 1,
  PRIMARY KEY (ipcr_category_id),
  UNIQUE KEY uq_ipcr_cat (designation_type, category_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Which target types fall under each category (implicitly per-designation).
CREATE TABLE tbl_ipcr_category_types (
  ipcr_category_id INT NOT NULL,
  category_id      INT NOT NULL,
  PRIMARY KEY (ipcr_category_id, category_id),
  CONSTRAINT fk_ict_cat  FOREIGN KEY (ipcr_category_id) REFERENCES tbl_ipcr_categories(ipcr_category_id) ON DELETE CASCADE,
  CONSTRAINT fk_ict_type FOREIGN KEY (category_id)      REFERENCES tbl_target_categories(category_id)   ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- 3) Seed from the two sample IPCR forms.
INSERT INTO tbl_ipcr_categories (designation_type, category_name, display_order) VALUES
  ('Regular Faculty',    'Strategic Priorities',                   10),
  ('Regular Faculty',    'Core Functions',                         20),
  ('Regular Faculty',    'Support Functions',                      30),
  ('Designated Faculty', 'Strategic Priorities/Support Functions', 10),
  ('Designated Faculty', 'Core Functions',                         20);

INSERT INTO tbl_ipcr_category_types (ipcr_category_id, category_id)
SELECT ic.ipcr_category_id, tc.category_id
FROM tbl_ipcr_categories ic
JOIN tbl_target_categories tc
WHERE (ic.designation_type='Regular Faculty'    AND ic.category_name='Strategic Priorities'                   AND tc.slug='instruction')
   OR (ic.designation_type='Regular Faculty'    AND ic.category_name='Core Functions'                         AND tc.slug IN ('research','extension'))
   OR (ic.designation_type='Regular Faculty'    AND ic.category_name='Support Functions'                      AND tc.slug='support')
   OR (ic.designation_type='Designated Faculty' AND ic.category_name='Strategic Priorities/Support Functions' AND tc.slug IN ('administrative','support'))
   OR (ic.designation_type='Designated Faculty' AND ic.category_name='Core Functions'                         AND tc.slug='instruction');

-- 4) Re-key the weight matrix onto real categories, preserving existing rows.
ALTER TABLE tbl_criteria_weights ADD COLUMN ipcr_category_id INT NULL AFTER designation_type;

UPDATE tbl_criteria_weights w
JOIN tbl_ipcr_categories ic
  ON ic.designation_type = w.designation_type
 AND ic.category_name = CASE w.weight_group
       WHEN 'instruction' THEN IF(w.designation_type='Regular Faculty','Strategic Priorities','Core Functions')
       WHEN 'ret'         THEN 'Core Functions'
       WHEN 'support'     THEN IF(w.designation_type='Regular Faculty','Support Functions','Strategic Priorities/Support Functions')
       WHEN 'admin'       THEN 'Strategic Priorities/Support Functions'
     END
SET w.ipcr_category_id = ic.ipcr_category_id;

-- Drop anything that could not be mapped (e.g. a group with no matching category).
DELETE FROM tbl_criteria_weights WHERE ipcr_category_id IS NULL;

ALTER TABLE tbl_criteria_weights
  DROP INDEX uq_weight,
  DROP COLUMN weight_group,
  MODIFY ipcr_category_id INT NOT NULL,
  ADD UNIQUE KEY uq_weight (term_id, ipcr_category_id, rank_band),
  ADD CONSTRAINT fk_w_ipcr_cat FOREIGN KEY (ipcr_category_id) REFERENCES tbl_ipcr_categories(ipcr_category_id);

-- 5) weight_group on the target TYPE is now redundant — the mapping table replaces it.
ALTER TABLE tbl_target_categories DROP COLUMN weight_group;

-- tbl_final_score_breakdown.weight_group stays a VARCHAR name snapshot so historical
-- ratings survive later renames; no change required.
