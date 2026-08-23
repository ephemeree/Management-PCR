# Comprehensive IPCR Notification Workflow Implementation Plan

## Overview
This plan establishes an end-to-end notification system across the D-IPCR system covering both **Target Phase** and **Accomplishment/Evidence Phase** workflows. It handles all state changes involving **Submit**, **Review**, **Approve**, **Return / Reject**, and **Verify** actions across Regular Faculty, Designated Faculty / Program Chairs, RET Chairs, and the College Dean.

---

## 1. Workflow Discovery & Current Status Audit

| # | Workflow / Action Trigger | Triggering Role | Route / Handler Method | Target Recipient(s) | Current Status | Proposed Notification |
|---|---|---|---|---|---|---|
| **1** | **Faculty Submits Draft IPCR Targets** | Regular Faculty | `POST /faculty/submit_ipcr`<br>`submit_faculty_ipcr` | **RET Chair** (if research targets selected)<br>or **Program Chair** (if non-research) | ❌ Missing | Email to RET/Program Chair: Faculty submitted draft IPCR targets pending review. |
| **2** | **RET Chair Approves Research Targets** | RET Chair | `POST /ret_chair/decide_ipcr`<br>`decide_ret_review` | **Faculty** & **Program Chair** / **Dean** (Tier 1) | ⚠️ Partial (Tier 1 only) | If Chair also approved &rarr; Trigger Tier 1. If Chair hasn't reviewed &rarr; Notify Program Chair that RET review is complete and ready for Chair review. |
| **3** | **RET Chair Returns Research Targets** | RET Chair | `POST /ret_chair/decide_ipcr`<br>`decide_ret_review` | **Faculty Member** | ✅ Implemented | Send return email with item modifications and reviewer remarks. |
| **4** | **Program Chair Approves IPCR Targets** | Program Chair | `POST /prog_chair/decide_ipcr`<br>`decide_chair_review` | **Faculty** (Tier 1) | ✅ Implemented | Trigger Tier 1 notification when both Chair and RET approve. |
| **5** | **Program Chair Returns IPCR Targets** | Program Chair | `POST /prog_chair/decide_ipcr`<br>`decide_chair_review` | **Faculty Member** | ✅ Implemented | Send return email with item modifications and reviewer remarks. |
| **6** | **Designated Faculty Submits Draft IPCR** | Designated Faculty / Chair | `POST /designated/submit`<br>`POST /designated/resubmit_ipcr` | **College Dean** | ❌ Missing | Email to Dean: Designated Faculty submitted draft IPCR targets for review. |
| **7** | **Dean Approves Designated Draft IPCR** | College Dean | `POST /dean/submit_review_decision`<br>`submit_dean_review_decision` | **Designated Faculty Member** | ❌ Missing | Email to Designated Faculty: Draft IPCR targets approved by Dean; ready for locking. |
| **8** | **Dean Returns Designated Draft IPCR** | College Dean | `POST /dean/submit_review_decision`<br>`submit_dean_review_decision` | **Designated Faculty Member** | ❌ Missing | Email to Designated Faculty: Draft IPCR targets returned with Dean's remarks & adjustments. |
| **9** | **Faculty Submits Evidence Package** | Regular Faculty | `POST /faculty/submit_evidence`<br>`submit_faculty_evidences` | **Program Chair** (and **RET Chair** if research present) | ❌ Missing | Email to Chair/RET: Faculty submitted evidence files for verification. |
| **10** | **Designated Faculty Submits Evidence Package** | Designated Faculty | `POST /designated/submit_evidence`<br>`submit_designated_evidences` | **College Dean** | ❌ Missing | Email to Dean: Designated faculty submitted evidence files for verification. |
| **11** | **Program Chair Submits Evidence Package to Dean** | Program Chair | `POST /prog_chair/submit_to_dean`<br>`submit_evidence_package_to_dean` | **College Dean** | ❌ Missing | Email to Dean: Faculty evidence package verified by Chair and ready for final Tier 2 approval. |
| **12** | **Dean Approves Final Evidence Package (Tier 2)** | College Dean | `POST /dean/approve_package` | **Faculty Member**, **Program Chair**, **RET Chair** | ✅ Implemented | Send Tier 2 Final Approval email with score rating and print link. |
| **13** | **Dean Returns IPCR / Evidence to Faculty** | College Dean | `POST /dean/return_to_faculty/<emp_id>` | **Faculty Member** & **Program Chair** | ❌ Missing | Email to Faculty & Chair: Evidence package returned by Dean for revisions. |

---

## 2. Architecture & Design

### Email Templates to Create / Update (`app/templates/emails/`):
1. **`target_submission_notice.html`**: Notifies Reviewer (RET Chair / Program Chair / Dean) that draft IPCR targets are submitted and pending review.
2. **`designated_target_decision.html`**: Notifies Designated Faculty of Dean's review outcome (Approved to lock or Returned for revision).
3. **`ret_to_chair_handoff.html`**: Notifies Program Chair that RET Chair has completed research review and the IPCR is now ready for Chair review.
4. **`evidence_submission_notice.html`**: Notifies Reviewer (Chair / Dean) that a faculty member submitted their evidence files / accomplishments.
5. **`evidence_package_to_dean.html`**: Notifies Dean that Program Chair verified the faculty's evidence and escalated the package for Tier 2 Final Approval.
6. **`evidence_returned_notice.html`**: Notifies Faculty (and Chair) when Dean returns an evidence package.

### Service Layer Enhancements (`app/services/notification_service.py`):
Add modular, async, safe notification helper functions:
- `send_target_submission_notification(...)`
- `send_designated_target_decision_notification(...)`
- `send_ret_to_chair_handoff_notification(...)`
- `send_evidence_submission_notification(...)`
- `send_evidence_package_to_dean_notification(...)`
- `send_evidence_return_notification(...)`

All functions will:
- Safely query recipient emails (`tbl_auth_credentials`, `tbl_system_access`, `tbl_employee_profiles`).
- Render rich HTML & plaintext email templates with actionable direct URLs.
- Dispatch asynchronously via `mail_service.send_async_email` to never block HTTP request cycles.
- Handle database operations safely without rolling back core business transactions if an email dispatch is interrupted.

---

## 3. Proposed File Changes

### [NEW] Email Templates
- [`app/templates/emails/target_submission_notice.html`](file:///c:/Users/ACER/Documents/Management-PCR/Management-PCR/app/templates/emails/target_submission_notice.html)
- [`app/templates/emails/designated_target_decision.html`](file:///c:/Users/ACER/Documents/Management-PCR/Management-PCR/app/templates/emails/designated_target_decision.html)
- [`app/templates/emails/ret_to_chair_handoff.html`](file:///c:/Users/ACER/Documents/Management-PCR/Management-PCR/app/templates/emails/ret_to_chair_handoff.html)
- [`app/templates/emails/evidence_submission_notice.html`](file:///c:/Users/ACER/Documents/Management-PCR/Management-PCR/app/templates/emails/evidence_submission_notice.html)
- [`app/templates/emails/evidence_package_to_dean.html`](file:///c:/Users/ACER/Documents/Management-PCR/Management-PCR/app/templates/emails/evidence_package_to_dean.html)
- [`app/templates/emails/evidence_returned_notice.html`](file:///c:/Users/ACER/Documents/Management-PCR/Management-PCR/app/templates/emails/evidence_returned_notice.html)

### [MODIFY] Service Layer
- [`app/services/notification_service.py`](file:///c:/Users/ACER/Documents/Management-PCR/Management-PCR/app/services/notification_service.py): Implement all new notification dispatch methods and recipient resolution helpers.

### [MODIFY] Route Handlers
- [`app/routes/faculty.py`](file:///c:/Users/ACER/Documents/Management-PCR/Management-PCR/app/routes/faculty.py): Wire triggers in `/submit_ipcr` and `/submit_evidence`.
- [`app/routes/designated.py`](file:///c:/Users/ACER/Documents/Management-PCR/Management-PCR/app/routes/designated.py): Wire triggers in `/submit`, `/resubmit_ipcr`, and `/submit_evidence`.
- [`app/routes/ret_chair.py`](file:///c:/Users/ACER/Documents/Management-PCR/Management-PCR/app/routes/ret_chair.py): Wire trigger when RET approves and Program Chair review is pending next.
- [`app/routes/prog_chair.py`](file:///c:/Users/ACER/Documents/Management-PCR/Management-PCR/app/routes/prog_chair.py): Wire trigger in `/submit_to_dean`.
- [`app/routes/dean.py`](file:///c:/Users/ACER/Documents/Management-PCR/Management-PCR/app/routes/dean.py): Wire triggers in `/submit_review_decision` (for designated faculty) and `/return_to_faculty/<emp_id>`.

### [MODIFY] Automated Unit Tests
- [`test_notifications.py`](file:///c:/Users/ACER/Documents/Management-PCR/Management-PCR/test_notifications.py): Add unit tests covering every new notification workflow and verify all mock dispatches.

---

## 4. Verification Plan

### Automated Tests
- Run `python test_notifications.py` to verify:
  1. Regular target submission notification triggers (RET vs Chair routing).
  2. RET-to-Chair handoff notification triggers.
  3. Designated target submission & decision notification triggers.
  4. Evidence submission & escalation notification triggers.
  5. Return notifications for both targets and evidence.

### Manual Verification
- Test running `python run.py` locally and verify that with `MAIL_SUPPRESS_SEND=true` or live SMTP, all notification dispatches log formatted email payloads without blocking the application.
