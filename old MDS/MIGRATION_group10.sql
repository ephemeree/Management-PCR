-- Group 10 — IPCR Approval Email Notifications
-- Tracks Tier 1 and Tier 2 notification dispatches to ensure idempotency and auditability.

USE ipcr_db;

CREATE TABLE IF NOT EXISTS tbl_ipcr_approval_notifications (
    notification_id  INT NOT NULL AUTO_INCREMENT,
    emp_id           INT NOT NULL,
    term_id          INT NOT NULL,
    tier             ENUM('TIER_1', 'TIER_2') NOT NULL,
    event_type       VARCHAR(60) NOT NULL,
    recipient_emails TEXT NOT NULL,
    sent_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status           ENUM('SENT', 'FAILED', 'DEV_LOGGED') NOT NULL DEFAULT 'SENT',
    error_message    TEXT NULL,
    PRIMARY KEY (notification_id),
    UNIQUE KEY uq_emp_term_tier (emp_id, term_id, tier),
    KEY idx_emp_term (emp_id, term_id),
    CONSTRAINT fk_notif_emp FOREIGN KEY (emp_id) REFERENCES tbl_employee_profiles(emp_id) ON DELETE CASCADE,
    CONSTRAINT fk_notif_term FOREIGN KEY (term_id) REFERENCES tbl_academic_terms(term_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
