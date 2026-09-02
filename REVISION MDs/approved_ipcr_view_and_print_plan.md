# Implementation Plan: View & Print Approved IPCR (Post-Lock)

> **Document Status**: Ready for Review & Implementation  
> **Target Scope**: Regular Faculty Dashboard, Designated Faculty Dashboard, Print IPCR Template (`ipcr_print.html`), and Form Builder (`ipcr_form.py`).

---

## 1. Executive Summary

In the SPMS / Philippine CSC Performance Management framework, the **IPCR** is utilized across two critical phases of the academic term:
1. **Target Commitment Stage (Beginning of Term / Post-Lock)**: The faculty member commits to specific MFOs/Outputs, success indicators, target descriptions, deadlines, and quantities. After supervisor/Dean review and locking, this forms the official **Approved Performance Commitment**.
2. **Evaluation & Rating Stage (End of Term / Post-Dean Approval)**: Actual accomplishments are reported against each commitment, evidence files are evaluated, and Q/E/T scores are computed and finalized.

### The Problem
Currently, the "Print IPCR" navigation tab (`nav-print-ipcr`) and print preview in both `faculty_dashboard.html` and `designated_dashboard.html` are strictly gated behind `{% if has_final_ipcr %}` (which requires final Dean review at the end of the semester). Faculty members cannot view or print their approved commitment form right after their draft targets are approved and locked.

### The Solution
Unlock the view and print capability immediately once draft targets are locked (`is_locked` / `is_committed`), distinguishing clearly between:
- **Approved Performance Commitment Form** (Post-Lock, during evidence gathering)
- **Final Evaluated & Rated IPCR Form** (Post-Dean Approval)

---

## 2. Architecture & Workflow

```mermaid
flowchart TD
    subgraph Draft_Phase [1. Draft Target Setting & Review]
        A[Faculty Submits Draft Targets] --> B[Chair / RET / Dean Review & Approval]
        B --> C[Faculty Clicks 'Lock My IPCR']
    end

    subgraph Lock_Phase [2. Target Commitment (Post-Lock)]
        C --> D[Targets Committed to tbl_committed_targets]
        D --> E[Status: Locked & Committed]
        E --> F1[Unlock 'Print IPCR' Navigation Tab]
        E --> F2["Add 'View & Print Approved IPCR' Buttons<br/>(Overview, My IPCR, Evidence Gathering)"]
        F1 & F2 --> G["ipcr_print.html (Stage: Commitment)<br/>Header: APPROVED PERFORMANCE COMMITMENT<br/>Clean Target Commitment Layout"]
    end

    subgraph Evaluation_Phase [3. Accomplishment & Scoring (End of Term)]
        E --> H[Evidence Gathering & Accomplishment Submission]
        H --> I[Reviewers & Dean Verify Scores]
        I --> J[Dean Approves Final IPCR Package]
        J --> K["has_final_ipcr = True"]
        K --> L["ipcr_print.html (Stage: Final Evaluation)<br/>Header: FINAL EVALUATED & RATED IPCR<br/>Populated Ratings Q/E/T & Accomplishments"]
    end
```

---

## 3. Detailed Component Changes

### A. Backend Model: `app/models/ipcr_form.py`
Enhance `build_ipcr_form()` to classify the document stage and provide semantic display metadata:

- Add `form_stage`:
  - `'final_evaluation'`: when all targets have `STATUS_DEAN_APPROVED` (`is_final = True`).
  - `'commitment'`: when targets exist in `tbl_committed_targets` but final evaluation is not yet complete (`is_final = False`).
- Add `stage_title`:
  - `"INDIVIDUAL PERFORMANCE COMMITMENT AND REVIEW (IPCR) - TARGET COMMITMENT"` or `"APPROVED PERFORMANCE COMMITMENT"` vs `"INDIVIDUAL PERFORMANCE COMMITMENT AND REVIEW (IPCR) - FINAL EVALUATION"`.
- Provide helper flags:
  - `show_ratings`: `True` only when in `final_evaluation` or when actual ratings are present.

---

### B. Print Template: `app/templates/ipcr_print.html`
1. **Notice Banner**:
   - Replace the generic draft alert (`DRAFT — this IPCR has not been approved by the Dean yet...`) with contextual banners:
     - **Commitment Mode**:
       ```html
       {% if form.form_stage == 'commitment' %}
       <div class="commitment-notice d-print-none">
           <i class="ti ti-circle-check"></i>
           <strong>Approved Performance Commitment</strong> — Targets are locked and approved.
           Actual accomplishments and Q/E/T ratings will be completed at the end of the rating period.
       </div>
       {% endif %}
       ```
2. **Table Presentation**:
   - When printing in commitment mode, ensure empty accomplishment and rating cells display cleanly without unformatted `None` or clutter.

---

### C. Faculty Dashboard: `app/templates/faculty_dashboard.html`
1. **Sidebar Navigation**:
   - Change:
     ```jinja2
     {% if has_final_ipcr %}
     <button class="nav-item" data-section="nav-print-ipcr" ...>
     ```
     to:
     ```jinja2
     {% if is_locked or has_final_ipcr %}
     <button class="nav-item" data-section="nav-print-ipcr" onclick="showSection('nav-print-ipcr')">
         <i class="ti ti-printer" aria-hidden="true"></i>
         <span class="nav-text">Print IPCR</span>
     </button>
     {% endif %}
     ```
2. **Action Buttons**:
   - In `#nav-overview` (Status Card): Add a "View / Print Approved IPCR" button when `is_locked`.
   - In `#nav-ipcr` (Locked Alert): Add an instant button:
     ```html
     <button type="button" class="btn btn-outline-primary shadow-sm" onclick="window.open('{{ url_for('faculty.faculty_print_ipcr') }}', '_blank')">
         <i class="ti ti-printer me-1"></i> View &amp; Print Approved IPCR
     </button>
     ```
   - In `#nav-evidence` (Header): Add a direct link/button to view the committed IPCR targets.
3. **Print Section (`#nav-print-ipcr`)**:
   - Update visibility to `{% if is_locked or has_final_ipcr %}`.
   - Dynamic description:
     - If `has_final_ipcr`: "Your IPCR is approved by Dean with final ratings and ready for official print."
     - If `is_locked`: "Your IPCR performance targets are approved and locked. You may review and print your official Performance Commitment form."

---

### D. Designated Faculty Dashboard: `app/templates/designated_dashboard.html`
Apply symmetric updates to the Designated Faculty flow:
1. Sidebar item: `{% if is_committed or has_final_ipcr %}`.
2. Section `#nav-print-ipcr`: `{% if is_committed or has_final_ipcr %}`.
3. Direct action button on the locked IPCR alert card and Evidence Gathering header.

---

## 4. Verification & QA Plan

| Test Case | Role | Expected Result |
| :--- | :--- | :--- |
| **Drafting Phase (Pre-Lock)** | Regular / Designated Faculty | "Print IPCR" tab is not visible; direct URL access gracefully warns to lock first. |
| **Post-Lock (Evidence Phase)** | Regular Faculty | "Print IPCR" tab is visible; direct buttons appear in Overview, My IPCR, and Evidence headers; print preview shows "Approved Performance Commitment". |
| **Post-Lock (Evidence Phase)** | Designated Faculty / Chair | "Print IPCR" tab is visible; prints landscape SPMS form with Output columns and Dean signatory block. |
| **Final Review Phase** | Regular / Designated Faculty | Once Dean approves final rating, print preview renders final Q/E/T scores, weighted rating summary, and final evaluator signatories. |
| **Physical / PDF Printing** | All | Print dialog (`Ctrl+P` / `window.print()`) formats on landscape A4/Letter cleanly without UI toolbars or screen notices. |
