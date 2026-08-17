-- Group 5 — Department Management + configurable Teaching Load
USE ipcr_db;

-- 1) Departments / programs. department_name matches tbl_employee_profiles.specialization
--    and tbl_cascaded_quotas.assigned_to_role, which is how targets are routed today.
CREATE TABLE tbl_departments (
  department_id   INT NOT NULL AUTO_INCREMENT,
  department_name VARCHAR(100) NOT NULL,
  department_code VARCHAR(20)  NULL,
  display_order   INT NOT NULL DEFAULT 100,
  is_active       TINYINT(1) NOT NULL DEFAULT 1,
  PRIMARY KEY (department_id),
  UNIQUE KEY uq_department (department_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

INSERT INTO tbl_departments (department_name, department_code, display_order) VALUES
  ('WST Program',  'WST',  10),
  ('DST Program',  'DST',  20),
  ('NST Program',  'NST',  30),
  ('BSDS Program', 'BSDS', 40);

-- Pick up any specialization already in use that is not in the seed list.
INSERT IGNORE INTO tbl_departments (department_name, department_code, display_order)
SELECT DISTINCT ep.specialization, LEFT(ep.specialization, 10), 100
FROM tbl_employee_profiles ep
WHERE ep.specialization IS NOT NULL AND ep.specialization <> '';

-- 2) Teaching load configuration. Mirrors the weight-allocation pattern:
--    rank_band = 'General' applies to every rank; otherwise it is a specific band.
--    The duration drives the Timeliness rating for the teaching load target.
CREATE TABLE tbl_teaching_load_config (
  config_id        INT NOT NULL AUTO_INCREMENT,
  term_id          INT NOT NULL,
  designation_type ENUM('Regular Faculty','Designated Faculty') NOT NULL,
  rank_band        VARCHAR(50) NOT NULL DEFAULT 'General',
  hours            INT NOT NULL,
  duration_value   INT NOT NULL DEFAULT 6,
  duration_unit    ENUM('days','weeks','months','semesters') NOT NULL DEFAULT 'months',
  PRIMARY KEY (config_id),
  UNIQUE KEY uq_teaching_load (term_id, designation_type, rank_band),
  CONSTRAINT fk_tl_term FOREIGN KEY (term_id) REFERENCES tbl_academic_terms(term_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- Seed the active term with the values currently hardcoded in the app
-- (21 hours regular, 10 hours designated), defaulting to a 6-month duration.
INSERT INTO tbl_teaching_load_config (term_id, designation_type, rank_band, hours, duration_value, duration_unit)
SELECT t.term_id, 'Regular Faculty', 'General', 21, 6, 'months'
FROM tbl_academic_terms t WHERE t.is_active = 1;

INSERT INTO tbl_teaching_load_config (term_id, designation_type, rank_band, hours, duration_value, duration_unit)
SELECT t.term_id, 'Designated Faculty', 'General', 10, 6, 'months'
FROM tbl_academic_terms t WHERE t.is_active = 1;

-- 3) Extension distribution needs a description and duration so distributed extension
--    targets can be scored for Timeliness (same gap research had before Group 3.1).
ALTER TABLE tbl_ret_extension_distribution
  ADD COLUMN target_description    TEXT NULL AFTER target_quantity,
  ADD COLUMN target_duration_value INT NULL AFTER target_description,
  ADD COLUMN target_duration_unit  ENUM('days','weeks','months','semesters') NULL
      AFTER target_duration_value;
