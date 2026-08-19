-- Group 8 — Printed IPCR: rating period, institution text, and signatories
-- Applied. Recorded here so a fresh clone can reach the same schema.
USE ipcr_db;

-- 1) Rating period, printed on the IPCR header:
--    "…for the period JANUARY to JUNE 2026."
--    academic_year + semester cannot express this on their own.
ALTER TABLE tbl_academic_terms
  ADD COLUMN period_start DATE NULL AFTER semester,
  ADD COLUMN period_end   DATE NULL AFTER period_start;

-- 2) Institution-level text that appears on printed forms. The roster stores the college
--    as a code ('CICT'); the form prints the full name.
CREATE TABLE tbl_institution_settings (
  setting_key   VARCHAR(60)  NOT NULL,
  setting_value VARCHAR(255) NULL,
  PRIMARY KEY (setting_key)
) ENGINE=InnoDB;

INSERT INTO tbl_institution_settings (setting_key, setting_value) VALUES
  ('college_full_name', 'College of Information and Communications Technology'),
  ('college_code',      'CICT');

-- 3) Who signs each block of the printed IPCR.
--
--    Two of the four blocks are derived from the org chart and two are a fixed person who
--    holds no account in the system, so each block records *how* it is filled:
--      FIXED         -> use full_name / position_title on this row
--      PROGRAM_CHAIR -> the ratee's own Program Chair, matched by specialization
--      DEAN          -> whoever holds designation 'Dean'
--
--    designation_type NULL means the row applies to both form variants.
CREATE TABLE tbl_ipcr_signatories (
  signatory_id     INT NOT NULL AUTO_INCREMENT,
  block_key        ENUM('REVIEWED_BY','APPROVED_BY','ASSESSED_BY','FINAL_RATING_BY') NOT NULL,
  designation_type ENUM('Regular Faculty','Designated Faculty') NULL,
  source           ENUM('FIXED','PROGRAM_CHAIR','DEAN') NOT NULL DEFAULT 'FIXED',
  full_name        VARCHAR(150) NULL,
  position_title   VARCHAR(150) NULL,
  PRIMARY KEY (signatory_id),
  UNIQUE KEY uq_block (block_key, designation_type)
) ENGINE=InnoDB;

-- Seeded to match the sample forms. Head of Office names are left NULL deliberately —
-- they are typed into Admin -> Institution Setup -> Printed IPCR.
INSERT INTO tbl_ipcr_signatories (block_key, designation_type, source, full_name, position_title) VALUES
  ('REVIEWED_BY',     'Regular Faculty',    'PROGRAM_CHAIR', NULL, 'Immediate Supervisor'),
  ('REVIEWED_BY',     'Designated Faculty', 'DEAN',          NULL, 'Immediate Supervisor'),
  ('ASSESSED_BY',     NULL,                 'DEAN',          NULL, 'Supervisor'),
  ('APPROVED_BY',     NULL,                 'FIXED',         NULL, 'Head of Office'),
  ('FINAL_RATING_BY', NULL,                 'FIXED',         NULL, 'Head of Office');

-- 4) Free-text Remarks, printed in the IPCR's Remarks column.
--
-- The paper form carries a short per-row note (the sample Designated IPCR reads
-- "Chairperson, BSDS" against the teaching load row). It is written by hand rather than
-- derived, so this is a plain text field the ratee fills in alongside their other
-- per-target reporting.
ALTER TABLE tbl_committed_targets
  ADD COLUMN print_remarks VARCHAR(255) NULL AFTER efficiency_rating_E;
