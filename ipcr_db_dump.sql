use ipcr_db;

SET FOREIGN_KEY_CHECKS=0;

CREATE TABLE `tbl_academic_terms` (
  `term_id` int NOT NULL AUTO_INCREMENT,
  `academic_year` varchar(20) NOT NULL,
  `semester` varchar(20) NOT NULL,
  `deadline_date` date DEFAULT NULL,
  `is_active` tinyint(1) DEFAULT '0',
  PRIMARY KEY (`term_id`)
) ENGINE=InnoDB AUTO_INCREMENT=12 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `tbl_addselect_targets` (
  `selection_id` int NOT NULL AUTO_INCREMENT,
  `emp_id` int NOT NULL,
  `indicator_id` int NOT NULL,
  `target_source` varchar(50) NOT NULL COMMENT 'e.g., Research Menu, Designation',
  PRIMARY KEY (`selection_id`),
  KEY `fk_addselect_emp` (`emp_id`),
  KEY `fk_addselect_ind` (`indicator_id`),
  CONSTRAINT `fk_addselect_emp` FOREIGN KEY (`emp_id`) REFERENCES `tbl_employee_profiles` (`emp_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_addselect_ind` FOREIGN KEY (`indicator_id`) REFERENCES `tbl_master_indicators` (`indicator_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `tbl_audit_logs` (
  `log_id` int NOT NULL AUTO_INCREMENT,
  `log_timestamp` datetime DEFAULT CURRENT_TIMESTAMP,
  `actor_id` varchar(50) DEFAULT NULL,
  `action_type` varchar(100) NOT NULL,
  `action_details` text NOT NULL,
  `ip_address` varchar(45) DEFAULT NULL,
  PRIMARY KEY (`log_id`)
) ENGINE=InnoDB AUTO_INCREMENT=44 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `tbl_auth_credentials` (
  `emp_id` int NOT NULL,
  `corporate_email` varchar(150) NOT NULL,
  `password_hash` varchar(255) NOT NULL,
  `last_login` datetime DEFAULT NULL,
  `verification_status` enum('PENDING','APPROVED','REJECTED') DEFAULT 'PENDING',
  PRIMARY KEY (`emp_id`),
  UNIQUE KEY `corporate_email` (`corporate_email`),
  CONSTRAINT `fk_auth_emp` FOREIGN KEY (`emp_id`) REFERENCES `tbl_employee_profiles` (`emp_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `tbl_cascaded_quotas` (
  `quota_id` int NOT NULL AUTO_INCREMENT,
  `term_id` int NOT NULL,
  `indicator_id` int NOT NULL,
  `total_target_value` int NOT NULL,
  `assigned_to_role` varchar(50) NOT NULL,
  PRIMARY KEY (`quota_id`),
  KEY `fk_quota_term` (`term_id`),
  KEY `fk_quota_ind` (`indicator_id`),
  CONSTRAINT `fk_quota_ind` FOREIGN KEY (`indicator_id`) REFERENCES `tbl_master_indicators` (`indicator_id`),
  CONSTRAINT `fk_quota_term` FOREIGN KEY (`term_id`) REFERENCES `tbl_academic_terms` (`term_id`)
) ENGINE=InnoDB AUTO_INCREMENT=162 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `tbl_co_authors` (
  `co_author_id` int NOT NULL AUTO_INCREMENT,
  `evidence_id` int NOT NULL,
  `emp_id` int NOT NULL,
  `claimed` tinyint NOT NULL DEFAULT '0',
  PRIMARY KEY (`co_author_id`),
  KEY `fk_coauth_evid` (`evidence_id`),
  KEY `idx_coauth_loose_emp` (`emp_id`),
  CONSTRAINT `fk_coauth_evid` FOREIGN KEY (`evidence_id`) REFERENCES `tbl_evidence_repo` (`evidence_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `tbl_committed_targets` (
  `target_id` int NOT NULL AUTO_INCREMENT,
  `emp_id` int NOT NULL,
  `indicator_id` int NOT NULL,
  `assigned_quantity` int NOT NULL,
  `status` varchar(50) DEFAULT 'Draft',
  `actual_quantity` int NOT NULL DEFAULT '0',
  PRIMARY KEY (`target_id`),
  KEY `fk_target_emp` (`emp_id`),
  KEY `fk_target_ind` (`indicator_id`),
  CONSTRAINT `fk_target_emp` FOREIGN KEY (`emp_id`) REFERENCES `tbl_employee_profiles` (`emp_id`),
  CONSTRAINT `fk_target_ind` FOREIGN KEY (`indicator_id`) REFERENCES `tbl_master_indicators` (`indicator_id`)
) ENGINE=InnoDB AUTO_INCREMENT=157 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `tbl_designation_targets` (
  `template_id` int NOT NULL AUTO_INCREMENT,
  `designation_role` varchar(50) NOT NULL,
  `indicator_id` int NOT NULL,
  PRIMARY KEY (`template_id`),
  KEY `fk_destarget_ind` (`indicator_id`),
  CONSTRAINT `fk_destarget_ind` FOREIGN KEY (`indicator_id`) REFERENCES `tbl_master_indicators` (`indicator_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `tbl_draft_allocation` (
  `allocation_id` int NOT NULL AUTO_INCREMENT,
  `emp_id` int NOT NULL,
  `indicator_id` int NOT NULL,
  `assigned_quantity` int NOT NULL,
  PRIMARY KEY (`allocation_id`),
  KEY `fk_draftalloc_emp` (`emp_id`),
  KEY `fk_draftalloc_ind` (`indicator_id`),
  CONSTRAINT `fk_draftalloc_emp` FOREIGN KEY (`emp_id`) REFERENCES `tbl_employee_profiles` (`emp_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_draftalloc_ind` FOREIGN KEY (`indicator_id`) REFERENCES `tbl_master_indicators` (`indicator_id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=68 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `tbl_draft_targets` (
  `draft_id` int NOT NULL AUTO_INCREMENT,
  `emp_id` int NOT NULL,
  `indicator_id` int NOT NULL,
  `proposed_quantity` int NOT NULL,
  `review_status` varchar(50) DEFAULT 'Pending Review' COMMENT 'Pending Review, Returned, or Approved',
  `manager_feedback` text,
  PRIMARY KEY (`draft_id`),
  KEY `fk_drafttarget_emp` (`emp_id`),
  KEY `fk_drafttarget_ind` (`indicator_id`),
  CONSTRAINT `fk_drafttarget_emp` FOREIGN KEY (`emp_id`) REFERENCES `tbl_employee_profiles` (`emp_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_drafttarget_ind` FOREIGN KEY (`indicator_id`) REFERENCES `tbl_master_indicators` (`indicator_id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=272 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `tbl_employee_profiles` (
  `emp_id` int NOT NULL AUTO_INCREMENT,
  `employee_id_number` varchar(50) NOT NULL,
  `first_name` varchar(100) NOT NULL,
  `last_name` varchar(100) NOT NULL,
  `college` varchar(100) NOT NULL DEFAULT 'CICT',
  `assigned_program` varchar(100) NOT NULL,
  `academic_rank` varchar(100) NOT NULL,
  `employment_status` varchar(50) NOT NULL,
  `designation` varchar(50) DEFAULT 'None',
  `leave_status` varchar(50) DEFAULT 'Active',
  `specialization` varchar(250) DEFAULT NULL,
  PRIMARY KEY (`emp_id`),
  UNIQUE KEY `employee_id_number` (`employee_id_number`)
) ENGINE=InnoDB AUTO_INCREMENT=99 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `tbl_evidence_repo` (
  `evidence_id` int NOT NULL AUTO_INCREMENT,
  `target_id` int NOT NULL,
  `file_path` varchar(255) NOT NULL,
  `actual_qty_Q` int NOT NULL,
  `timeliness_T` decimal(3,2) DEFAULT NULL,
  `efficiency_rating_E` int DEFAULT NULL,
  `verification_status` varchar(50) DEFAULT 'Pending',
  `supervisor_comment` text,
  PRIMARY KEY (`evidence_id`),
  KEY `fk_evid_target` (`target_id`),
  CONSTRAINT `fk_evid_target` FOREIGN KEY (`target_id`) REFERENCES `tbl_committed_targets` (`target_id`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `tbl_final_scores` (
  `score_id` int NOT NULL AUTO_INCREMENT,
  `emp_id` int NOT NULL,
  `term_id` int NOT NULL,
  `instruction_weighted` decimal(4,2) DEFAULT NULL,
  `ret_weighted` decimal(4,2) DEFAULT NULL,
  `support_weighted` decimal(4,2) DEFAULT NULL,
  `admin_weighted` decimal(4,2) DEFAULT NULL,
  `final_score` decimal(4,2) NOT NULL,
  `adjectival_rating` varchar(50) NOT NULL,
  `dean_approval_status` varchar(50) DEFAULT 'Pending',
  PRIMARY KEY (`score_id`),
  KEY `fk_score_emp` (`emp_id`),
  KEY `fk_score_term` (`term_id`),
  CONSTRAINT `fk_score_emp` FOREIGN KEY (`emp_id`) REFERENCES `tbl_employee_profiles` (`emp_id`),
  CONSTRAINT `fk_score_term` FOREIGN KEY (`term_id`) REFERENCES `tbl_academic_terms` (`term_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `tbl_ipcr_chair_review` (
  `review_id` int NOT NULL AUTO_INCREMENT,
  `emp_id` int NOT NULL,
  `term_id` int NOT NULL,
  `chair_emp_id` int NOT NULL,
  `overall_status` enum('Pending','Approved','Rejected') DEFAULT 'Pending',
  `overall_remarks` text,
  `reviewed_at` timestamp NULL DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`review_id`),
  UNIQUE KEY `uq_review` (`emp_id`,`term_id`)
) ENGINE=InnoDB AUTO_INCREMENT=34 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `tbl_ipcr_chair_review_items` (
  `item_id` int NOT NULL AUTO_INCREMENT,
  `review_id` int NOT NULL,
  `draft_id` int NOT NULL,
  `indicator_id` int NOT NULL,
  `original_quantity` int NOT NULL,
  `reviewed_quantity` int NOT NULL,
  `item_remarks` varchar(1000) DEFAULT NULL,
  PRIMARY KEY (`item_id`),
  KEY `review_id` (`review_id`),
  CONSTRAINT `tbl_ipcr_chair_review_items_ibfk_1` FOREIGN KEY (`review_id`) REFERENCES `tbl_ipcr_chair_review` (`review_id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=263 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `tbl_ipcr_dean_review` (
  `review_id` int NOT NULL AUTO_INCREMENT,
  `emp_id` int NOT NULL,
  `term_id` int NOT NULL,
  `dean_id` int NOT NULL,
  `overall_status` varchar(20) DEFAULT 'Pending',
  `overall_remarks` text,
  `reviewed_at` datetime DEFAULT NULL,
  PRIMARY KEY (`review_id`)
) ENGINE=InnoDB AUTO_INCREMENT=11 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `tbl_ipcr_dean_review_items` (
  `item_id` int NOT NULL AUTO_INCREMENT,
  `review_id` int NOT NULL,
  `draft_id` int DEFAULT NULL,
  `indicator_id` int NOT NULL,
  `original_quantity` int DEFAULT '0',
  `reviewed_quantity` int DEFAULT '0',
  `item_remarks` text,
  PRIMARY KEY (`item_id`)
) ENGINE=InnoDB AUTO_INCREMENT=73 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `tbl_ipcr_ret_review` (
  `review_id` int NOT NULL AUTO_INCREMENT,
  `emp_id` int NOT NULL,
  `term_id` int NOT NULL,
  `ret_chair_emp_id` int NOT NULL,
  `overall_status` enum('Pending','Approved','Rejected') DEFAULT 'Pending',
  `overall_remarks` text,
  `reviewed_at` timestamp NULL DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`review_id`),
  UNIQUE KEY `uq_ret_review` (`emp_id`,`term_id`),
  CONSTRAINT `fk_ret_review_emp` FOREIGN KEY (`emp_id`) REFERENCES `tbl_employee_profiles` (`emp_id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=11 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `tbl_ipcr_ret_review_items` (
  `item_id` int NOT NULL AUTO_INCREMENT,
  `review_id` int NOT NULL,
  `draft_id` int NOT NULL,
  `indicator_id` int NOT NULL,
  `original_quantity` int NOT NULL,
  `reviewed_quantity` int NOT NULL,
  `item_remarks` varchar(1000) DEFAULT NULL,
  PRIMARY KEY (`item_id`),
  KEY `review_id` (`review_id`),
  CONSTRAINT `tbl_ipcr_ret_review_items_ibfk_1` FOREIGN KEY (`review_id`) REFERENCES `tbl_ipcr_ret_review` (`review_id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=37 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `tbl_master_indicators` (
  `indicator_id` int NOT NULL AUTO_INCREMENT,
  `category_id` int NOT NULL,
  `indicator_description` text NOT NULL,
  `efficiency_type` varchar(50) NOT NULL,
  `term_id` int DEFAULT NULL,
  `is_custom` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`indicator_id`),
  KEY `fk_master_cat` (`category_id`),
  CONSTRAINT `fk_master_cat` FOREIGN KEY (`category_id`) REFERENCES `tbl_target_categories` (`category_id`)
) ENGINE=InnoDB AUTO_INCREMENT=83 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `tbl_research_options` (
  `option_id` int NOT NULL AUTO_INCREMENT,
  `term_id` int NOT NULL,
  `academic_rank` varchar(100) NOT NULL,
  `indicator_id` int NOT NULL,
  PRIMARY KEY (`option_id`),
  KEY `fk_opt_term` (`term_id`),
  KEY `fk_opt_indicator` (`indicator_id`),
  CONSTRAINT `fk_opt_indicator` FOREIGN KEY (`indicator_id`) REFERENCES `tbl_master_indicators` (`indicator_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_opt_term` FOREIGN KEY (`term_id`) REFERENCES `tbl_academic_terms` (`term_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `tbl_research_requirements` (
  `req_id` int NOT NULL AUTO_INCREMENT,
  `term_id` int NOT NULL,
  `academic_rank` varchar(100) NOT NULL,
  `required_selections` int NOT NULL DEFAULT '1',
  PRIMARY KEY (`req_id`),
  KEY `fk_req_term` (`term_id`),
  CONSTRAINT `fk_req_term` FOREIGN KEY (`term_id`) REFERENCES `tbl_academic_terms` (`term_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `tbl_ret_rule_indicators` (
  `rule_indicator_id` int NOT NULL AUTO_INCREMENT,
  `rule_id` int NOT NULL,
  `indicator_id` int NOT NULL,
  `target_quantity` int DEFAULT '1',
  PRIMARY KEY (`rule_indicator_id`),
  KEY `rule_id` (`rule_id`),
  KEY `indicator_id` (`indicator_id`),
  CONSTRAINT `tbl_ret_rule_indicators_ibfk_1` FOREIGN KEY (`rule_id`) REFERENCES `tbl_ret_rules` (`rule_id`) ON DELETE CASCADE,
  CONSTRAINT `tbl_ret_rule_indicators_ibfk_2` FOREIGN KEY (`indicator_id`) REFERENCES `tbl_master_indicators` (`indicator_id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=17 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `tbl_ret_rules` (
  `rule_id` int NOT NULL AUTO_INCREMENT,
  `academic_rank` varchar(255) NOT NULL,
  `required_selections` int NOT NULL,
  PRIMARY KEY (`rule_id`)
) ENGINE=InnoDB AUTO_INCREMENT=9 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `tbl_system_access` (
  `emp_id` int NOT NULL,
  `system_role` varchar(50) NOT NULL,
  `account_status` varchar(50) DEFAULT 'Pending',
  PRIMARY KEY (`emp_id`),
  CONSTRAINT `fk_access_emp` FOREIGN KEY (`emp_id`) REFERENCES `tbl_employee_profiles` (`emp_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE `tbl_target_categories` (
  `category_id` int NOT NULL AUTO_INCREMENT,
  `category_name` varchar(100) NOT NULL,
  PRIMARY KEY (`category_id`),
  UNIQUE KEY `category_name` (`category_name`)
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DELIMITER $$
CREATE PROCEDURE `get_user_by_email`(IN p_email VARCHAR(255))
BEGIN
    SELECT 
        a.emp_id,
        a.password_hash,
        a.verification_status,
        s.system_role
    FROM tbl_auth_credentials a
    LEFT JOIN tbl_system_access s ON a.emp_id = s.emp_id
    WHERE a.corporate_email = p_email;
END $$

DELIMITER ;

DELIMITER $$
CREATE PROCEDURE `register_user`(
    IN p_employee_id_number VARCHAR(50),
    IN p_email VARCHAR(150),
    IN p_password_hash VARCHAR(255)
)
BEGIN
    DECLARE v_emp_id INT DEFAULT NULL;
    DECLARE v_designation VARCHAR(50) DEFAULT NULL;
    DECLARE v_role VARCHAR(50) DEFAULT 'FACULTY';
    DECLARE v_exists INT DEFAULT 0;

    -- 1. Find employee profile by Employee ID Number
    SELECT emp_id, designation INTO v_emp_id, v_designation
    FROM tbl_employee_profiles
    WHERE employee_id_number = p_employee_id_number;

    -- If no profile found, raise error
    IF v_emp_id IS NULL THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Employee ID Number is not recognized by HR. Please contact the administrator.';
    END IF;

    -- 2. Check if the employee profile already has credentials (claimed)
    SELECT COUNT(*) INTO v_exists
    FROM tbl_auth_credentials
    WHERE emp_id = v_emp_id;

    IF v_exists > 0 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'This employee account has already been claimed.';
    END IF;

    -- 3. Check if corporate email is already registered to someone else
    SELECT COUNT(*) INTO v_exists
    FROM tbl_auth_credentials
    WHERE corporate_email = p_email;

    IF v_exists > 0 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'This corporate email is already registered to another account.';
    END IF;

    -- 4. Map designation to system role
    IF v_designation = 'Admin' THEN
        SET v_role = 'Admin';
    ELSEIF v_designation = 'Dean' THEN
        SET v_role = 'DEAN';
    ELSEIF v_designation = 'Program Chair' THEN
        SET v_role = 'PROGRAM_CHAIR';
    ELSEIF v_designation = 'RET Chair' THEN
        SET v_role = 'RET_CHAIR';
    ELSEIF v_designation = 'Designated Faculty' THEN
        SET v_role = 'DESIGNATED_FACULTY';
    ELSE
        SET v_role = 'FACULTY';
    END IF;

    -- 5. Create auth credentials (auto-approved)
    INSERT INTO tbl_auth_credentials (emp_id, corporate_email, password_hash, verification_status)
    VALUES (v_emp_id, p_email, p_password_hash, 'APPROVED');

    -- 6. Set system access role and activate status
    INSERT INTO tbl_system_access (emp_id, system_role, account_status)
    VALUES (v_emp_id, v_role, 'Active')
    ON DUPLICATE KEY UPDATE system_role = v_role, account_status = 'Active';

END $$

DELIMITER $$

CREATE TRIGGER `trg_sync_faculty_role` AFTER UPDATE ON `tbl_employee_profiles` FOR EACH ROW BEGIN
    DECLARE v_new_role VARCHAR(50);

    -- Only execute synchronization if the designation column actually changed
    IF OLD.designation <> NEW.designation THEN
        
        -- Determine the matching application role string
        IF NEW.designation = 'Dean' THEN
            SET v_new_role = 'DEAN';
        ELSEIF NEW.designation = 'RET Chair' THEN
            SET v_new_role = 'RET_CHAIR';
        ELSEIF NEW.designation = 'Program Chair' THEN
            SET v_new_role = 'PROGRAM_CHAIR';
        ELSEIF NEW.designation = 'Designated Faculty' THEN
            SET v_new_role = 'DESIGNATED_FACULTY';
        ELSE
            SET v_new_role = 'FACULTY';
        END IF;

        -- Update tbl_system_access if the user has already registered an account
        UPDATE `tbl_system_access`
        SET `system_role` = v_new_role
        WHERE `emp_id` = NEW.emp_id;

    END IF;
END $$

DELIMITER ;

SET FOREIGN_KEY_CHECKS=1;