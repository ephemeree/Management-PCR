# Recent Updates & Bug Fixes Changelog (recents.md)

This document provides a comprehensive log of recent architectural enhancements, workflow updates, UI/UX redesigns, bug fixes, and database migrations implemented across the **Management-PCR** system.

---

## 📌 Executive Summary

Recent iterations transformed Management-PCR into a complete, end-to-end **SPMS-compliant Performance Commitment and Review** platform. Key milestones include:
* Full implementation of the **Weighted SPMS Scoring Pipeline** and **Printable Official IPCR** short bond paper view.
* Integration of **Self-IPCR capabilities for Deans, Program Chairs, and RET Chairs** alongside Designated and Regular Faculty.
* Comprehensive **Frontend UI/UX Redesign** using modern design tokens, structured cards, status-coded badges, and unified breadcrumb navigation.
* Advanced **Validation & Error-Trapping Suite** with high-priority dialog modals for incomplete forms and target allocations.
* Elimination of critical data-loss bugs in research/extension target submissions and evidence handling.

---

## 🚀 1. Validation, Form Safety & Error-Trapping Updates *(Latest)*

### A. RET Chair Module Validation & Modals
* **Research Rule Assignment Validation (`validateResearchRuleForm`)**:
  * Added mandatory Academic Rank selection check before saving.
  * Ensures at least one research option is selected.
  * Validates that every checked research target includes a positive quantity (`> 0`), target description, and positive deadline duration with unit.
* **Extension Target Distribution Validation (`showConfirmExtDistModal`)**:
  * Traps unpopulated or zero-duration extension targets before opening confirmation modals.
  * Validates target description and duration values.
* **Global High-Priority RET Warning Modal (`#retWarningModal`)**:
  * Implemented an alert modal with `z-index: 2000` to guarantee visibility above any active nested modals.
  * Automatically highlights invalid input fields with `.is-invalid` and `.border-danger`.

### B. Program Chair Target Allocation & Verification Validation
* **Instruction Target Allocation Checks**:
  * Traps missing descriptions, target duration, or quantities when allocating instruction targets to faculty, chairs, and Dean.
* **Evidence Verification Completeness**:
  * Requires verification decisions and remarks before submitting verified packages to the Dean.

### C. Dean Review & Designated Faculty Submission Validation
* **Deadline & Duration Error Trapping**:
  * Blocks IPCR draft submission if any selected core/strategic target lacks a positive deadline duration.
  * Auto-focuses and marks missing inputs without flagging unselected/unchecked items.
* **Dean Review Real-Time Snapshot Tracking**:
  * Tracks original quantities and items via DOM snapshot maps (`checkDeanEdits()`).
  * Dynamically disables the **"Approve IPCR"** button if targets or quantities are modified without resubmission, and re-enables it once values match original submissions.

### D. Admin Institution & Academic Term Trapping
* **Term Activation Trapping**: Prevents overlapping active rating periods and enforces valid date ranges (`Rating Period From/To`).
* **Department & Teaching Load Validations**: Ensures valid hours per week and semester durations per rank or across institution-wide settings.

---

## 🎨 2. Frontend UI/UX Redesign & Modernization

### A. Design System & Layout Overhaul
* **Modern Aesthetic Upgrade**:
  * Implemented modern design aesthetics using Tabler icons and clean typography.
  * High-contrast, accessibility-compliant color coding:
    * 🟢 **Designated Faculty / Chairs**: `#198754` (Forest Green accents).
    * 🔵 **Regular Faculty**: `#0d6efd` / `#206bc4` (Sapphire Blue accents).
    * 🟡 **Pending / Warning States**: Amber `#ffc107`.
    * 🔴 **Returned / Rejected States**: Crimson `#dc3545`.
* **Universal Layout Standard (`app/templates/base.html` & `auth_layout.html`)**:
  * Unified responsive sidebar with role-aware navigation links.
  * Dynamic breadcrumb trail generator via `app/navigation.py`.
  * Clean, distraction-free authentication layout for login and registration.

### B. Dashboard-Specific Enhancements
* **Dean Dashboard (`dean_dashboard.html`)**:
  * Separated Final Verifications into distinct tables for **Approved Designated Faculty** and **Approved Regular Faculty**.
  * Reordered modal actions to adhere to standard UX conventions (`[Close]` on left, `[Approve IPCR]` on right).
  * Removed legacy, unused Batch Approval UI and routes.
* **Program Chair Dashboard (`prog_chair_dashboard.html`)**:
  * Separated Approved Evidence tables for Designated vs. Regular Faculty.
  * Clear multi-stage badges (`Waiting for RET Chair Approval`, `Approved by Both Chairs`).
* **Designated & Regular Faculty Dashboards (`designated_dashboard.html`, `faculty_dashboard.html`)**:
  * Reordered Evidence Gathering modal: File upload & submissions placed at top; Accomplishment summary & ratings placed below.
  * Added **Print IPCR** in-dashboard review section, gated strictly behind final Dean approval (`{% if has_final_ipcr %}`).

---

## ⚙️ 3. Core Workflow & Architecture Enhancements

### A. Dual-Chair Evidence Verification for Regular Faculty
* **Synchronized Program Chair & RET Chair Approval**:
  * Regular Faculty evidence containing Research or Extension targets requires approval from **both** the Program Chair (Instruction/Support) and the RET Chair (Research/Extension).
  * Status remains pending with `Waiting for RET Chair Approval` badge until both chairs complete evaluation (`is_both_approved == True`), after which the package routes to the Dean.

### B. Self-IPCR for Deans, Program Chairs, and RET Chairs
* **Role-Aware Target Selection & Review Lanes**:
  * Deans, Program Chairs, and RET Chairs have access to **"My IPCR"** in the sidebar.
  * **RET Chair Lane**: Restricts selectable indicators to **Research** and **Extension** (`review_lane = 'RET'`).
  * **Program Chair & Designated Lane**: Restricts selectable indicators to **Instruction** and **Support Functions** (`review_lane = 'CHAIR' AND is_core = 1`).
  * Dean approves chair drafts in the unified Draft IPCR Approval tab.

### C. SPMS Scoring Engine & Short Bond Paper Print IPCR
* **Weighted SPMS Calculation Pipeline (`app/models/scoring.py`, `app/models/ipcr_form.py`)**:
  * Calculates individual target ratings: Average of **Quality (Q)**, **Efficiency (E)**, and **Timeliness (T)**.
  * Computes category raw scores and applies category weight percentages (Core, Strategic, Support).
  * Calculates Final Overall Weighted Rating and maps to standard Civil Service Adjectival Ratings:
    * `4.500 - 5.000` : **Outstanding (O)**
    * `3.500 - 4.499` : **Very Satisfactory (VS)**
    * `2.500 - 3.499` : **Satisfactory (S)**
    * `1.500 - 2.499` : **Unsatisfactory (US)**
    * `Below 1.500`   : **Poor (P)**
* **Printable IPCR View (`/faculty/print_ipcr`, `/designated/print_ipcr`, `ipcr_print.html`)**:
  * Pixel-accurate Short Bond Paper (8.5" x 11") printable layout.
  * Includes institution headers, rating period, individual target outputs, numerical ratings, weighted summary table, and required institutional signatories (Ratee, Supervisor, Dean, Head of Agency).
  * Removed deprecated Excel-based DPCR export in favor of dynamic printable IPCRs.

### D. IPCR Locking & State Decoupling
* **Decoupled Dean Approval from Target Commitment**:
  * Dean approval marks the draft as `'Approved'` without immediately locking the database rows.
  * The user explicitly clicks **"Lock My IPCR"** (`/designated/lock_ipcr`), officially committing targets into `tbl_committed_targets` and unlocking Phase 4 (Evidence Gathering).
* **Return & Re-Submission Lifecycle**:
  * Returned IPCRs (`Rejected` with remarks) place the dashboard in a protected view-only mode.
  * Users click **"Re-submit IPCR for Approval"** to re-open the draft for Dean review.

---

## 🐛 4. Resolved Bugs & System Hardening

| Bug / Issue | Root Cause | Resolution | Affected Files |
|---|---|---|---|
| **Research target selection lost on submission** | `submit_faculty_ipcr` re-queried `tbl_academic_terms` independently without accepting `term_id` from the route, causing eligibility mismatches and deleting research rows. | Passed validated `term_id` from route; wrapped execution in explicit transaction (`conn.autocommit = False` with `commit`/`rollback` in `try/finally`). | `app/routes/faculty.py`, `app/models/faculty.py` |
| **Extension targets wiped when term falsy** | Unconditional `DELETE FROM tbl_committed_targets WHERE tc.slug = 'extension'` executed before verifying active term. | Wrapped extension delete inside the same `if active_term_id:` check as the repopulating insert. | `app/models/faculty.py` |
| **Evidence deletion loophole & UI sync** | Deleting evidence file left modal in an unsynchronized state and lacked a non-blocking confirmation dialog. | Implemented custom `showCustomConfirm` modal and dynamic `reloadEvidenceModalSubmissions()` AJAX refresh without closing modal. | `app/templates/faculty_dashboard.html`, `designated_dashboard.html` |
| **Premature Evidence Locking in Phase 4** | Status check checked `'Approved'` (the Phase 2 target approval status), wrongly disabling Phase 4 buttons on first visit. | Removed Phase 2 `'Approved'` string from Phase 4 evidence readiness check; now only locks on actual evidence submission or Dean final approval. | `app/models/faculty.py`, `app/models/designated.py` |
| **Premature appearance in Chair verification** | Query checked `HAVING MAX(ct.status IN ('Approved', ...))` which included Phase 2 draft approvals. | Removed `'Approved'` draft status from chair evidence queries (`get_program_chair_evidence_faculty`, `get_ret_chair_evidence_faculty`). | `app/models/prog_chair.py`, `app/models/ret_chair.py` |
| **SyntaxError in Designated routes** | Misplaced `elif` block following an `else` block in `designated.py`. | Refactored `has_final_ipcr` variable initialization prior to conditional branches. | `app/routes/designated.py` |
| **Dean Review Target Re-add Quantity Reset** | Removing and re-adding a target reset its target quantity to 0 instead of retaining what the faculty submitted. | Preserved submitted target parameters in `originalSubmittedItemsMap` and restored values upon re-selection. | `app/templates/dean_dashboard.html` |

---

## 🗄️ 5. Database Schema & Migration Summary

* **`MIGRATION_group7.sql`**: Added `is_admin_function` flag to master indicators and backfilled indicators for designated faculty.
* **`MIGRATION_group8.sql`**: Added rating period fields (`rating_period_from`, `rating_period_to`) to `tbl_academic_terms`, institution setup tables, signatories configuration, and `print_remarks`.
* **`MIGRATION_group9.sql`**: Added `target_description`, `target_duration_value`, and `target_duration_unit` columns to `tbl_ret_assignments` to support customized research and extension target metadata.

---

## 📋 6. Current System State & Test Script Alignment

All test procedures across **Phases 0 through M** in [TEST_SCRIPT.md](file:///c:/Users/ACER/Documents/Management-PCR/Management-PCR/TEST_SCRIPT.md) are fully aligned with the latest implementation:
1. **Phase 0**: Multi-role authentication & account protection.
2. **Phase A - D**: Institution setup, Dean target cascading, Program Chair & RET Chair distribution.
3. **Phase E - F**: Faculty IPCR creation, selection, review, return/re-submit, and locking.
4. **Phase G - H**: Evidence gathering, Q/E/T scoring, dual-chair verification, and Dean final approval.
5. **Phase I - J**: Designated Faculty & Chair self-IPCR workflows.
6. **Phase K**: Short bond paper IPCR printing and PDF export.
7. **Phase L - M**: Admin maintenance, roster CSV import/backup, and permission controls.
