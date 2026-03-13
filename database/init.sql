CREATE DATABASE IF NOT EXISTS `ipcr_db`;
USE `ipcr_db`;

-- CLUSTER 1: SECURE AUTHENTICATION & HR PROFILES
CREATE TABLE `tbl_employee_profiles` (
    `emp_id` INT AUTO_INCREMENT PRIMARY KEY,
    `employee_id_number` VARCHAR(50) UNIQUE NOT NULL,
    `first_name` VARCHAR(100) NOT NULL,
    `last_name` VARCHAR(100) NOT NULL,
    `academic_rank` VARCHAR(100) NOT NULL,
    `employment_status` VARCHAR(50) NOT NULL,
    `designation` VARCHAR(50) DEFAULT 'None',
    `leave_status` VARCHAR(50) DEFAULT 'Active'
) ENGINE=InnoDB;

CREATE TABLE `tbl_auth_credentials` (
    `emp_id` INT PRIMARY KEY,
    `corporate_email` VARCHAR(150) UNIQUE NOT NULL,
    `password_hash` VARCHAR(255) NOT NULL,
    `last_login` DATETIME,
    CONSTRAINT `fk_auth_emp` FOREIGN KEY (`emp_id`) REFERENCES `tbl_employee_profiles`(`emp_id`)
) ENGINE=InnoDB;

CREATE TABLE `tbl_system_access` (
    `emp_id` INT PRIMARY KEY,
    `system_role` VARCHAR(50) NOT NULL,
    `account_status` VARCHAR(50) DEFAULT 'Pending',
    CONSTRAINT `fk_access_emp` FOREIGN KEY (`emp_id`) REFERENCES `tbl_employee_profiles`(`emp_id`)
) ENGINE=InnoDB;

-- CLUSTER 2: SYSTEM LOOKUPS
CREATE TABLE `tbl_academic_terms` (
    `term_id` INT AUTO_INCREMENT PRIMARY KEY,
    `academic_year` VARCHAR(20) NOT NULL,
    `semester` VARCHAR(20) NOT NULL,
    `is_active` TINYINT(1) DEFAULT 0
) ENGINE=InnoDB;

CREATE TABLE `tbl_target_categories` (
    `category_id` INT AUTO_INCREMENT PRIMARY KEY,
    `category_name` VARCHAR(100) UNIQUE NOT NULL
) ENGINE=InnoDB;

CREATE TABLE `tbl_master_indicators` (
    `indicator_id` INT AUTO_INCREMENT PRIMARY KEY,
    `category_id` INT NOT NULL,
    `indicator_description` TEXT NOT NULL,
    `efficiency_type` VARCHAR(50) NOT NULL,
    CONSTRAINT `fk_master_cat` FOREIGN KEY (`category_id`) REFERENCES `tbl_target_categories`(`category_id`)
) ENGINE=InnoDB;

-- CLUSTER 3: RULES & TARGET CASCADING
CREATE TABLE `tbl_designation_targets` (
    `template_id` INT AUTO_INCREMENT PRIMARY KEY,
    `designation_role` VARCHAR(50) NOT NULL,
    `indicator_id` INT NOT NULL,
    CONSTRAINT `fk_destarget_ind` FOREIGN KEY (`indicator_id`) REFERENCES `tbl_master_indicators`(`indicator_id`)
) ENGINE=InnoDB;

CREATE TABLE `tbl_cascaded_quotas` (
    `quota_id` INT AUTO_INCREMENT PRIMARY KEY,
    `term_id` INT NOT NULL,
    `indicator_id` INT NOT NULL,
    `total_target_value` INT NOT NULL,
    `assigned_to_role` VARCHAR(50) NOT NULL,
    CONSTRAINT `fk_quota_term` FOREIGN KEY (`term_id`) REFERENCES `tbl_academic_terms`(`term_id`),
    CONSTRAINT `fk_quota_ind` FOREIGN KEY (`indicator_id`) REFERENCES `tbl_master_indicators`(`indicator_id`)
) ENGINE=InnoDB;

-- CLUSTER 4: TRANSACTIONS & EVIDENCE VERIFICATION
CREATE TABLE `tbl_committed_targets` (
    `target_id` INT AUTO_INCREMENT PRIMARY KEY,
    `emp_id` INT NOT NULL,
    `term_id` INT NOT NULL,
    `indicator_id` INT NOT NULL,
    `assigned_quantity` INT NOT NULL,
    `status` VARCHAR(50) DEFAULT 'Draft',
    CONSTRAINT `fk_target_emp` FOREIGN KEY (`emp_id`) REFERENCES `tbl_employee_profiles`(`emp_id`),
    CONSTRAINT `fk_target_term` FOREIGN KEY (`term_id`) REFERENCES `tbl_academic_terms`(`term_id`),
    CONSTRAINT `fk_target_ind` FOREIGN KEY (`indicator_id`) REFERENCES `tbl_master_indicators`(`indicator_id`)
) ENGINE=InnoDB;

CREATE TABLE `tbl_evidence_repo` (
    `evidence_id` INT AUTO_INCREMENT PRIMARY KEY,
    `target_id` INT NOT NULL,
    `file_path` VARCHAR(255) NOT NULL,
    `actual_qty_Q` INT NOT NULL,
    `timeliness_T` DECIMAL(3,2),
    `efficiency_rating_E` INT,
    `verification_status` VARCHAR(50) DEFAULT 'Pending',
    `supervisor_comment` TEXT,
    CONSTRAINT `fk_evid_target` FOREIGN KEY (`target_id`) REFERENCES `tbl_committed_targets`(`target_id`)
) ENGINE=InnoDB;

CREATE TABLE `tbl_co_authors` (
    `co_author_id` INT AUTO_INCREMENT PRIMARY KEY,
    `evidence_id` INT NOT NULL,
    `emp_id` INT NOT NULL,
    CONSTRAINT `fk_coauth_evid` FOREIGN KEY (`evidence_id`) REFERENCES `tbl_evidence_repo`(`evidence_id`),
    CONSTRAINT `fk_coauth_emp` FOREIGN KEY (`emp_id`) REFERENCES `tbl_employee_profiles`(`emp_id`)
) ENGINE=InnoDB;

-- CLUSTER 5: ANALYTICS & COMPUTATION
CREATE TABLE `tbl_final_scores` (
    `score_id` INT AUTO_INCREMENT PRIMARY KEY,
    `emp_id` INT NOT NULL,
    `term_id` INT NOT NULL,
    `instruction_weighted` DECIMAL(4,2),
    `ret_weighted` DECIMAL(4,2),
    `support_weighted` DECIMAL(4,2),
    `admin_weighted` DECIMAL(4,2),
    `final_score` DECIMAL(4,2) NOT NULL,
    `adjectival_rating` VARCHAR(50) NOT NULL,
    `dean_approval_status` VARCHAR(50) DEFAULT 'Pending',
    CONSTRAINT `fk_score_emp` FOREIGN KEY (`emp_id`) REFERENCES `tbl_employee_profiles`(`emp_id`),
    CONSTRAINT `fk_score_term` FOREIGN KEY (`term_id`) REFERENCES `tbl_academic_terms`(`term_id`)
) ENGINE=InnoDB;


