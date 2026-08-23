# D-IPCR Notification System — Complete Technical Documentation & Changelog

This document contains the complete record of all architecture, lifecycle stages, routing rules, template structures, bug fixes, and diagnostic enhancements implemented for the **Strategic Performance Management System (D-IPCR) Notification Engine**.

---

## 1. Architecture & Core Infrastructure

### 1.1 Asynchronous Mail Dispatcher (`app/services/mail_service.py`)
- **Non-Blocking Background Threading**: Dispatches emails asynchronously using Python's `concurrent.futures.ThreadPoolExecutor(max_workers=5)` so user web interactions are instantaneous with zero HTTP latency.
- **Flask-Mail Integration**: Uses Flask-Mail `Message` wrapped inside `app.app_context()` within each worker thread.
- **Recipient Validation**: Ensures clean, sanitized recipient lists, filtering out empty, invalid, or mock placeholder emails.
- **Real-Time Terminal Console Logging**:
  ```text
  [FLASK-MAIL SUCCESS] Email sent to ['user@mail.com'] with Subject: '...'
  [FLASK-MAIL ERROR] Failed to send email via Flask-Mail to [...]: ...
  ```

### 1.2 Base Email Design & Branding (`app/templates/emails/base_email.html`)
- **SPMS University Header**: Modern, branded blue header with clean typography (`#2563eb`).
- **Responsive Card Layout**: Clean structured cards (`info-card`, `info-row`, `info-label`, `info-value`) supporting both desktop and mobile email clients.
- **Status Badges**: Styled color-coded badges (`badge-primary`, `badge-success`, `badge-danger`, `badge-warning`).
- **Call-to-Action Buttons**: Stylized high-contrast direct links (`.btn-action`) navigating directly to the exact review or print stage in the portal.

---

## 2. End-to-End Notification Lifecycle Matrix

| Phase | Event Trigger | Sender Role | Recipient(s) | Review Stage / Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **Target Phase (Step 1)** | Regular Faculty Submits Draft Targets | Regular Faculty | **RET Chair** (`corazonlopez062041@gmail.com`) | `RET Research Target Verification (Step 1)` |
| **Target Phase (Step 2)** | RET Chair Approves Research Targets | RET Chair | **Faculty Member** & **Program Chair** | Notifies faculty of approval and routes IPCR to Program Chair for Step 2 |
| **Target Phase (Step 3)** | Program Chair Approves Targets | Program Chair | **Faculty Member** | Prompts faculty to lock & commit IPCR targets |
| **Target Phase (Designated)** | Designated Faculty / Chair Submits Targets | Designated Faculty / Program Chair / RET Chair | **College Dean** (`deanacccount@gmail.com`) | `Dean Review for [Role] Targets` (includes explicit sender role) |
| **Target Phase (Decision)** | Dean Approves / Returns Designated Targets | College Dean | **Designated Faculty / Chair** | Informs submitter of Dean's decision and overall remarks |
| **Evidence Phase (Regular)** | Regular Faculty Submits Evidence | Regular Faculty | **Program Chair** & **RET Chair** | Notifies Chairs to begin verification of Instruction, Core, and Research/Extension proof files |
| **Evidence Phase (Designated)** | Designated Faculty Submits Evidence | Designated Faculty | **Program Chair** | Notifies Program Chair to verify Instruction, Core, and Support accomplishment files |
| **Evidence Phase (Chairs/Dean)** | Program Chair / RET Chair Submits Own Evidence | Department Chair | **College Dean** | Notifies Dean directly (includes sender role: `RET Chair`, `Program Chair`) |
| **Evidence Phase (Package)** | Program Chair Submits Verified Package to Dean | Program Chair | **College Dean** & **Faculty Member** | Notifies Dean that all evidences are verified and ready for Tier 2 Final Approval |
| **Evidence Phase (Return)** | Reviewer Returns Evidence File | Chair / Dean | **Faculty Member** | Immediate alert detailing which target and file was returned with reviewer comments |
| **Final Phase (Tier 2 Final)** | Dean Grants Final Approval on IPCR & Scores | College Dean | **IPCR Owner Only** *(Faculty / Designated / Chair)* | Delivers final weighted score, adjectival rating, and direct link to printable IPCR (No chairs notified) |

---

## 3. Detailed Notification Specifications

### 3.1 Target Planning Phase

#### A. Regular Faculty Target Submission (`send_target_submission_notification`)
- **Routing Logic**:
  - Checks `tbl_ipcr_ret_review` for `overall_status == 'Approved'`.
  - **If not yet approved**: Strictly routes to the **RET Chair** (`corazonlopez062041@gmail.com`).
  - **If RET approved**: Routes to the **Program Chair** of the faculty member's department.
- **Template**: [`app/templates/emails/target_submission_notice.html`](file:///c:/Users/ACER/Documents/Management-PCR/Management-PCR/app/templates/emails/target_submission_notice.html)

#### B. RET Chair Target Decision (`send_ret_approval_notifications`)
- **Recipients**:
  1. **Faculty Member**: Alerts that research targets are approved and proceeding to Program Chair.
  2. **Program Chair**: Alerts that Step 1 RET review is complete and ready for Program Chair review.
- **Template**: [`app/templates/emails/ret_approved_notice.html`](file:///c:/Users/ACER/Documents/Management-PCR/Management-PCR/app/templates/emails/ret_approved_notice.html)

#### C. Program Chair Target Approval (`send_chair_approval_notification`)
- **Recipient**: **Faculty Member**.
- **Action**: Informs faculty to log in and click **"Lock IPCR"** to commit targets into `tbl_committed_targets`.
- **Template**: [`app/templates/emails/chair_approved_notice.html`](file:///c:/Users/ACER/Documents/Management-PCR/Management-PCR/app/templates/emails/chair_approved_notice.html)

#### D. Designated Faculty / Chair Target Submission (`send_designated_target_submission_notification`)
- **Sender Role Identification**: Identifies whether the submitter is `Designated Faculty`, `RET Chair`, `Program Chair`, or `Dean`.
- **Recipient**: **College Dean**.
- **Email Content**: Includes `Designation / Role` field and tailored review stage (e.g., `Dean Review for RET Chair Targets`).

#### E. Dean Decision on Designated Targets (`send_designated_target_decision_notification`)
- **Recipient**: **Designated Faculty / Chair**.
- **Content**: Approval/rejection status, remarks from the Dean, and direct link to dashboard.
- **Template**: [`app/templates/emails/designated_target_decision.html`](file:///c:/Users/ACER/Documents/Management-PCR/Management-PCR/app/templates/emails/designated_target_decision.html)

---

### 3.2 Accomplishment & Evidence Verification Phase

#### A. Initial Evidence Submission (`send_evidence_submission_notification`)
- **Designated Faculty**: Routes to the **Program Chair** of their department for verification.
- **Regular Faculty**: Routes to both the **Program Chair** (Instruction & Core) and **RET Chair** (Research & Extension).
- **Department Chairs (Self-IPCR)**: Routes directly to the **College Dean** and displays the sender's title (`RET Chair`, `Program Chair`).
- **Template**: [`app/templates/emails/evidence_submission_notice.html`](file:///c:/Users/ACER/Documents/Management-PCR/Management-PCR/app/templates/emails/evidence_submission_notice.html)

#### B. Program Chair Endorses Package to Dean (`send_evidence_package_to_dean_notification`)
- **Trigger**: When the Program Chair verifies all accomplishment evidences for a faculty member and submits the evidence package to the Dean.
- **Recipients**:
  1. **College Dean**: Action required to review and grant final Tier 2 rating and approval.
  2. **Faculty Member**: Confirmation that their verified package has been endorsed to the Dean.
- **Template**: [`app/templates/emails/evidence_package_to_dean.html`](file:///c:/Users/ACER/Documents/Management-PCR/Management-PCR/app/templates/emails/evidence_package_to_dean.html)

#### C. Evidence File Return / Rejection (`send_return_notification`)
- **Trigger**: Reviewer clicks "Return" on any evidence file.
- **Recipient**: **Faculty Member**.
- **Content**: Details the indicator title, target description, returned filename, and reviewer remarks.
- **Template**: [`app/templates/emails/return_notice.html`](file:///c:/Users/ACER/Documents/Management-PCR/Management-PCR/app/templates/emails/return_notice.html)

---

### 3.3 Final Tier 2 Approval & Scoring Phase

#### Final Approval by Dean (`check_and_trigger_tier2_notification`)
- **Recipient Policy**: **Exclusively the IPCR Owner** (Faculty member / Designated faculty / Chair). Program Chair and RET Chair notifications were removed as requested.
- **Dynamic Score Calculation**: Automatically retrieves or computes on-the-fly:
  - **Final Weighted Rating** (e.g. `4.2500` / `3.7200`)
  - **Adjectival Rating** (e.g. `Outstanding`, `Very Satisfactory`, `Satisfactory`)
- **Print Action URL**:
  - Regular Faculty: `.../faculty/print_ipcr`
  - Designated Faculty & Chairs: `.../designated/print_ipcr`
- **Template**: [`app/templates/emails/tier2_final.html`](file:///c:/Users/ACER/Documents/Management-PCR/Management-PCR/app/templates/emails/tier2_final.html)

---

## 4. Key Bug Fixes & Resiliency Enhancements

### 4.1 SQL Schema Compatibility
1. **Removed Non-Existent Column `tc.category_type`**:
   - Fixed `mysql.connector.errors.ProgrammingError: 1054 (42S22): Unknown column 'tc.category_type'` in `app/models/faculty.py`.
2. **Removed Non-Existent Column `ac.username`**:
   - Fixed `Unknown column 'ac.username'` across `notification_service.py` reviewer lookup queries (`_get_dean_info`, `_get_ret_chair_info`, `_get_program_chair_info`).
   - Uses `tbl_auth_credentials.corporate_email` and `tbl_system_access.system_role` exclusively.

### 4.2 Module Export Alignment (`app/services/__init__.py`)
- Replaced obsolete legacy function names with all active notification methods:
  - `send_target_submission_notification`
  - `send_ret_approval_notifications`
  - `send_chair_approval_notification`
  - `send_return_notification`
  - `send_designated_target_submission_notification`
  - `send_designated_target_decision_notification`
  - `send_evidence_submission_notification`
  - `send_evidence_package_to_dean_notification`
  - `check_and_trigger_evidence_approved_notification`
  - `check_and_trigger_tier2_notification`
- Added backward-compatibility alias for `check_and_trigger_tier1_notification`.

### 4.3 Robust Profile Lookups (`_get_faculty_profile`)
- Uses `LEFT JOIN` on `tbl_employee_profiles` and `tbl_auth_credentials` with fallback resolution so profile lookups never return `None` or cause unhandled exceptions.

---

## 5. Diagnostic Tools & Testing Hooks

The following diagnostic endpoints were implemented in [`app/routes/faculty.py`](file:///c:/Users/ACER/Documents/Management-PCR/Management-PCR/app/routes/faculty.py) for testing and verifying email delivery:

- `/faculty/test_ret_mail`: Tests direct email dispatch to the RET Chair (`corazonlopez062041@gmail.com`).
- `/faculty/test_dean_package_mail`: Tests Program Chair evidence package endorsement to the Dean (`deanacccount@gmail.com`).
- `/faculty/test_designated_tier2_mail`: Tests final approval email with numerical and adjectival ratings to Designated Faculty (`mitsuhataki153@gmail.com`).
- `/faculty/test_ret_chair_targets_mail`: Tests RET Chair target submission notification with `Designation / Role: RET Chair` to Dean.
- `/faculty/test_ret_chair_evidence_mail`: Tests RET Chair evidence submission notification with `Designation / Role: RET Chair` to Dean.
- `/faculty/rollback_faculty/<email>`: Completely resets a faculty account (clears draft selections, review records, committed targets, and evidence files) to test from the target selection phase.
