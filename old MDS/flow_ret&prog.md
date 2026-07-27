# 2-Step IPCR Approval & Evidence Flow

This document details the step-by-step workflow of the Individual Performance Commitment and Review (IPCR) targets from initial drafting by the faculty member up to the submission of accomplishment evidences.

---

## 🗺️ Process Workflow Diagram

```mermaid
sequenceDiagram
    autonumber
    actor Faculty as Faculty Member
    actor RET as RET Chair
    actor Program as Program Chair
    database DB as MySQL Database

    %% Step 1: Draft & Submit
    Faculty->>DB: Select RET choices & submit draft
    Note over Faculty,DB: Creates records in tbl_draft_targets with status "Pending Review"

    %% Step 2: RET Review
    RET->>DB: Reviews Research & Extension targets
    alt Rejected / Returned
        RET->>DB: Set RET status to 'Rejected'
        DB->>Faculty: Status: "Returned" (Editable draft mode)
    else Approved
        RET->>DB: Set RET status to 'Approved'
        DB->>Program: Status: "Waiting for Approval" (Eligible for Program Chair review)
    end

    %% Step 3: Program Chair Review
    Program->>DB: Reviews Instructions & Support targets
    Note over Program,DB: RET targets are read-only for Program Chair
    alt Rejected / Returned
        Program->>DB: Set Chair status to 'Rejected'
        DB->>Faculty: Status: "Returned" (Editable draft mode)
    else Approved
        Program->>DB: Set Chair status to 'Approved'
        DB->>Faculty: Status: "Approved by Both" (Pending Lock)
    end

    %% Step 4: Lock & Commit
    Faculty->>DB: Click "Lock and Commit IPCR"
    Note over Faculty,DB: Copies draft targets to tbl_committed_targets; locks targets from editing

    %% Step 5: Evidence Gathering
    Faculty->>DB: Upload evidence & accomplishment quantities
    Note over Faculty,DB: Saved in tbl_evidence_attachments; updates tbl_committed_targets.actual_quantity
```

---

## 🔍 Detailed Phase Breakdown

### 1. Draft Target Submission (Faculty)
* **Action:** The faculty member logs in and accesses their **My IPCR** page.
* **Logic:** 
  - Standard Instruction and Support Function targets pre-allocated by the Program Chair are shown automatically.
  - The faculty member chooses their Research and Extension (RET) targets based on active rules set by the RET Chair.
* **Submission:** Upon clicking **Submit IPCR for Approval**, the selections and quantities are written to `tbl_draft_targets` with a review status of `'Pending Review'`.

### 2. Research & Extension (RET) Verification (RET Chair)
* **Action:** The RET Chair accesses the **Commitment Verification** section of their dashboard.
* **Logic:** 
  - The RET Chair reviews only the Research & Extension categories of the faculty member's draft.
  - They can edit quantities or leave remarks per item.
* **Decision:**
  - **Return:** Flips the overall status to `'Rejected'`, unlocking the draft for the faculty member to revise.
  - **Approve:** Marks the RET review as `'Approved'`. This automatically changes the faculty member's overall IPCR status to `'waiting_for_program_chair_review'` (Waiting for Approval).

### 3. Instructional & Support Verification (Program Chair)
* **Action:** The Program Chair accesses **Phase 2: Commitment Verification** on their dashboard.
* **Logic:**
  - The Program Chair reviews the Instructions and Support Functions categories.
  - **Note:** Research & Extension categories are displayed in **read-only mode** with status badges indicating the RET Chair's approval.
* **Decision:**
  - **Return:** Flips the overall status to `'Rejected'`, returning the entire draft to the faculty member.
  - **Approve:** Saves any adjusted quantities to `tbl_draft_targets.proposed_quantity` and sets the chair review status to `'Approved'`. The overall IPCR status updates to `'approved_by_program_chair'` (Approved by Both).

### 4. Locking & Committing Targets (Faculty)
* **Action:** The faculty member logs in, sees the status **Approved by Both**, and clicks **Lock and Commit IPCR**.
* **Logic:**
  - This deletes any existing committed targets for the active term and writes the finalized quantities from `tbl_draft_targets` to `tbl_committed_targets` with the status `'Approved'`.
  - Once locked, target quantities are permanently frozen and cannot be modified by the faculty member or chairs.

### 5. Evidence Submission & Accomplishments (Faculty)
* **Action:** Once locked, the **Evidence Gathering** tab unlocks on the Faculty Dashboard.
* **Logic:**
  - Faculty members see their final committed target quantities.
  - For each target, they enter their achieved accomplishment quantity and upload files (images, PDFs, documents) as proof of accomplishment.
  - The uploads are registered in `tbl_evidence_attachments` and the accomplishment quantities update `tbl_committed_targets.actual_quantity`.
