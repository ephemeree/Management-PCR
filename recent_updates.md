# Comprehensive System Updates & Workflow Enhancements

This document summarizes all functional updates, UI/UX redesigns, error-trapping enhancements, and database queries implemented across the Management-PCR system.

---

## 1. Dean Dashboard & Verification Workflows

* **Removed Batch Approval Tab**: Completely removed the unused Batch Approval tab, legacy routes, and redundant backend queries from the Dean's dashboard.
* **Final Approval Modal Button Order**: Reordered the footer buttons in the Dean Final Evidence Verification modal (`#deanEvidenceModal` in `dean_dashboard.html`) to follow standard UI conventions:
  * **Left**: `Close` button
  * **Right**: `Approve IPCR` button (`[Close] [Approve IPCR]`)
* **Separated Final Verifications Tables**: Split the **Approved Final Verifications** section in `dean_dashboard.html` into two separate, styled tables:
  1. **Approved Designated Faculty Final Verifications** *(Top table with green accent border `#198754`)*.
  2. **Approved Regular Faculty Final Verifications** *(Bottom table with blue accent border `#0d6efd`)*.
* **Backend Query Updates**: Updated `get_dean_evidence_faculty` in `app/models/dean.py` to retrieve `ep.designation` and `sa.system_role` via `LEFT JOIN tbl_system_access`, enabling precise filtering between Designated and Regular Faculty.
* **Tables & Views Used**: `tbl_committed_targets`, `tbl_employee_profiles`, `tbl_system_access`, `tbl_master_indicators`.

---

## 2. Evidence Gathering & Submission Locking

* **Modal Layout Reordering**: Reordered `evidenceGatheringModal` in both `faculty_dashboard.html` and `designated_dashboard.html`:
  * **Top**: Upload New Evidence form & Current Submissions list (placed directly beneath the target header).
  * **Bottom**: Accomplishment Details card (composed accomplishment sentence, duration input, completion status radio buttons, client satisfaction rating, and remarks).
* **Custom Evidence Deletion Modal**: Replaced standard browser `confirm()` with a styled `showCustomConfirm` modal (`Remove Evidence File?`). Confirming deletion keeps the evidence modal open and dynamically refreshes the evidence list via `reloadEvidenceModalSubmissions()`.
* **Strict Verification State Locking**:
  * Evidence gathering is locked whenever evidence is submitted for verification or when the Dean completes final verification (`has_final_ipcr == True` / `status == 'Dean Approved'`).
  * Action buttons dynamically update:
    * `"Add/View Evidence"` (Primary Blue) when editable.
    * `"View Evidences"` (Secondary Gray) when submitted and pending verification.
    * `"View Evidences (Approved)"` (Outline Secondary) when final verification is completed by the Dean.
  * Inputs (file upload, duration, completion status, efficiency rating, remarks) are disabled, save buttons are hidden, and delete buttons are removed when locked.
  * Bottom status badges dynamically display `"Evidences Submitted for Verification"` or `"Final Verification Completed & Approved by Dean"`.
* **Fixed Pre-mature Evidence Locking**:
  * Removed `'Approved'` (the initial target commitment status set when IPCR draft is approved in Phase 2) from evidence readiness status checks in `app/models/faculty.py` and `app/models/designated.py`.
  * Resolved the bug where faculty members entering Phase 4 for the first time were incorrectly flagged as "Evidences Submitted" with disabled buttons.
* **Tables Used**: `tbl_evidence_repo`, `tbl_committed_targets`, `tbl_master_indicators`.

---

## 3. Program Chair & RET Chair Evidence Verification

* **Separated Approved Evidence Tables**: Split approved evidence submissions in `prog_chair_dashboard.html` into two separate tables:
  1. **Approved Designated Faculty Evidences** *(Top table with green accent border `#198754`)*.
  2. **Approved Regular Faculty Evidences** *(Bottom table with blue accent border `#0d6efd`)*.
* **Dual-Chair Approval Workflow for Regular Faculty**:
  * Regular Faculty evidence submissions remain in the pending **Faculty Evidence Submissions** table as long as `is_both_approved` is `False`.
  * Displays status badge `Waiting for RET Chair Approval` when the Program Chair approves Instruction/Support targets while Research/Extension targets await RET Chair approval.
  * Regular Faculty move to **Approved Regular Faculty Evidences** only when **BOTH** Program Chair AND RET Chair have approved all target evidence (`is_both_approved == True`).
* **Evidence Query Filter Fix**: Removed target status `'Approved'` (Phase 2 draft approval status) from `HAVING MAX(CASE WHEN ct.status IN (...))` in `get_program_chair_evidence_faculty` (`prog_chair.py`) and `get_ret_chair_evidence_faculty` (`ret_chair.py`). Faculty who have not submitted Phase 4 evidence no longer appear prematurely in chair evidence verification tables.
* **Tables Used**: `tbl_committed_targets`, `tbl_evidence_repo`, `tbl_employee_profiles`, `tbl_system_access`, `tbl_master_indicators`, `tbl_target_categories`.

---

## 4. Designated Faculty Dashboard & Print IPCR

* **In-Dashboard Print Review Section**:
  * Updated the **Print IPCR** sidebar tab in `designated_dashboard.html` to open an in-dashboard review section (`nav-print-ipcr`), matching the Regular Faculty dashboard design.
  * Displays full **Finalized IPCR Details**:
    * **Target & Ratings Table**: Output / MFO, Success Indicator (Target + Measure), Actual Accomplishments, Rating (Q, E, T, Average), and Remarks.
    * **Summary of Ratings Table**: Category breakdown, Weight (%), Raw Average, Weighted Rating, Total Overall Rating, Final Weighted Rating, and Adjectival Rating.
  * Includes a top header **Print IPCR** button that opens the printable short bond paper template (`/designated/print_ipcr`) in a new window for printing or saving as PDF.
* **Print Tab Visibility Control**: Gated the **Print IPCR** tab in `designated_dashboard.html` so it only appears after the Dean completes final verification (`{% if has_final_ipcr %}`).
* **Tables & Models Used**: `tbl_committed_targets`, `tbl_master_indicators`, `tbl_ipcr_categories`, `tbl_employee_profiles`, `build_ipcr_form()`.

---

## 5. Backend Syntax & Code Cleanup

* **SyntaxError Fix**: Resolved `SyntaxError: 'elif' block follows an 'else' block` in `app/routes/designated.py` by initializing `has_final_ipcr` prior to conditional blocks.
* **Unused Code Cleanup**: Purged unused routes, legacy batch approval functions, and dead code across `app/routes/dean.py`, `app/routes/designated.py`, `app/routes/prog_chair.py`, `app/models/prog_chair.py`, `app/models/dean.py`, and `app/models/faculty.py`.

---

## 6. Program Chair, RET Chair & Dean IPCR Review & Approval by Dean

* **Expanded Draft Submissions Scope**:
  * Updated `get_designated_draft_submissions` in `app/models/dean.py` to include `DEAN`, `PROGRAM_CHAIR`, `RET_CHAIR`, and `DESIGNATED_FACULTY`.
  * Allows Program Chairs, RET Chairs, and the Dean's own submitted draft IPCRs to appear in the Dean's **IPCR Draft Approval** tab (`#nav-draft-ipcr`).
* **Sidebar "My IPCR" Access**:
  * Passed `has_own_ipcr=True` in `prog_chair_dashboard` (`app/routes/prog_chair.py`), `ret_chair_dashboard` (`app/routes/ret_chair.py`), and `dean_dashboard` (`app/routes/dean.py`).
  * Enables the **My IPCR** sidebar link under *My Performance* across all administrative/chair dashboards.
* **Role-Based Available Indicators Filtering**:
  * Updated `get_available_master_indicators` (`app/models/dean.py`) and `get_designated_selectable_indicators` (`app/models/designated.py`):
    * **RET Chair**: Only **Research** and **Extension** indicators (`review_lane = 'RET'`) are selectable or appear in unselected pools.
    * **Program Chair & Designated Faculty**: **Instructions** and **Support Functions** (`review_lane = 'CHAIR' AND is_core = 1`).
* **Real-Time Edit Detection & Snapshot Comparison**:
  * Implemented session snapshots in `openDeanReview()` (`dean_dashboard.html`).
  * The **"Approve IPCR"** button is enabled by default for pending submissions.
  * Real-time DOM validation (`checkDeanEdits()`) immediately disables the Approve button if reviewed quantities, items, or indicators are modified.
  * Undoing changes back to their initial state dynamically **re-enables the Approve button** in real time.
* **Universal Remove & Metadata Preservation on Re-Add**:
  * Added remove buttons (`<i class="bi bi-trash-fill"></i>`) to all core and strategic review rows in the Dean review modal.
  * Removing a target returns it dynamically to the **Unselected Indicators** (or College-Wide Targets) table.
  * Re-adding previously submitted indicators restores their original submitted quantities, descriptions, and categories from `originalSubmittedItemsMap` rather than resetting to 0.

---

## 7. IPCR Locking, Return & Re-Submission Flow

* **Decoupled Approval from Locking**:
  * Updated `submit_dean_review_decision` in `app/models/dean.py` so Dean approval sets review status to `'Approved'` and syncs quantities without prematurely committing into `tbl_committed_targets`.
  * Created `lock_and_commit_designated_ipcr` in `app/models/designated.py` and endpoint `/designated/lock_ipcr` in `app/routes/designated.py`.
  * The faculty/chair member explicitly clicks **"Lock My IPCR"** upon Dean approval to commit targets and unlock **Evidence Gathering**.
* **View-Only Mode on Return (`can_edit = False`)**:
  * When the Dean returns the IPCR with remarks (`overall_status == 'Rejected'`), the reviewee's IPCR dashboard enters view-only mode.
  * Inputs, checkboxes, and the "Add Target" button are disabled to preserve review integrity.
  * Added a **"Re-submit IPCR for Approval"** button and endpoint `/designated/resubmit_ipcr` in `app/routes/designated.py` to reset draft target statuses to `'Pending Review'` and return the draft to the Dean's approval tab.
* **Deadline Error Trapping on Submission**:
  * Added frontend and backend error trapping in `designated_dashboard.html` and `submit_designated_ipcr_route` (`app/routes/designated.py`).
  * Prevents submission if any **selected** target or custom target is missing a positive deadline (target duration).
  * Automatically highlights invalid fields in red (`is-invalid`) and sets focus. Unselected / unchecked targets are excluded from validation and do not block submission.

---

## 8. Multi-Role Evidence Verification & Routing to Dean

* **Program Chair Evidence Verification Scope**:
  * Updated `get_program_chair_evidence_faculty` in `app/models/prog_chair.py` to include evidence submissions from `RET_CHAIR`, `PROGRAM_CHAIR`, `DESIGNATED_FACULTY`, and `DEAN`.
* **Forwarding Evidence to Dean**:
  * Updated `submit_designated_evidences` in `app/models/designated.py` to set status to `'Submitted to Dean'`.
  * Program Chair forwarding via `submit_evidence_package_to_dean` routes approved evidence packages directly into the Dean's **Final Verification** section (`#nav-final-verification`).
* **Approved Designated Faculty & Chairs Table Partitioning**:
  * Updated evidence partitioning in both `app/routes/prog_chair.py` and `app/routes/dean.py` using `_is_designated_or_chair_or_dean()`.
  * Approved evidence packages for the **Dean, Program Chairs, and RET Chairs** are properly routed into the **Approved Designated Faculty & Chairs** tables on both Program Chair and Dean dashboards.
