## Changes Implemented

### 1. Database Layer
- Added `tbl_ipcr_ret_review` to store RET Chair's review header logic.
- Added `tbl_ipcr_ret_review_items` to store RET Chair's reviewed quantities and item-specific remarks.

### 2. Backend Models
- **[ret_chair.py](file:///home/buzz/Projects/Management-PCR/app/models/ret_chair.py)**: Added DB helpers `get_pending_ret_draft_ipcrs`, `get_or_create_ret_review`, `get_ret_review_items`, `update_ret_review_item`, `decide_ret_review`, and `get_faculty_ret_review_status` to handle RET Chair specific workflows.
- **[prog_chair.py](file:///home/buzz/Projects/Management-PCR/app/models/prog_chair.py)**: Modified `get_review_items` to join with `tbl_draft_targets` and fetch `review_status` as `draft_status` for indicators, enabling the Program Chair to verify if RET targets are approved.
- **[faculty.py](file:///home/buzz/Projects/Management-PCR/app/models/faculty.py)**: Modified `submit_faculty_ipcr` to reset the RET review status and clean up items upon any new submission or resubmission.

### 3. Backend Routes
- **[ret_chair.py](file:///home/buzz/Projects/Management-PCR/app/routes/ret_chair.py)**:
  - Added AJAX GET `/ret_chair/review_ipcr/<int:emp_id>` route to fetch data for the review modal.
  - Added AJAX POST `/ret_chair/edit_review_item` route to update reviewed quantities inline.
  - Added POST `/ret_chair/decide_ipcr` route to approve/reject the RET targets.
  - Updated the main dashboard route to fetch and display pending RET drafts count.
- **[faculty.py](file:///home/buzz/Projects/Management-PCR/app/routes/faculty.py)**:
  - Updated the dashboard route to load RET review status and updated submission checks so that RET Chair rejections allow edits and resubmission.

### 4. Frontend Dashboards
- **[ret_chair_dashboard.html](file:///home/buzz/Projects/Management-PCR/app/templates/ret_chair_dashboard.html)**:
  - Populated Phase 4 dynamically with regular faculty drafts.
  - Added a purple-themed Bootstrap modal to review RET targets, save edits, write overall remarks, and approve/reject.
  - Connected Phase 4 actions to dynamic modal-opening and decision forms.
- **[prog_chair_dashboard.html](file:///home/buzz/Projects/Management-PCR/app/templates/prog_chair_dashboard.html)**:
  - Added visual badges in the review modal to distinguish approved and awaiting-approval RET choices.
  - Automatically disabled the "Approve Draft" button and showed a warning banner if any RET targets are still awaiting RET Chair approval.
- **[faculty_dashboard.html](file:///home/buzz/Projects/Management-PCR/app/templates/faculty_dashboard.html)**:
  - Added warning, info, and success banners to indicate whether the IPCR is waiting for RET Chair or Program Chair approval.
  - Rendered a red alert banner when selections are returned by the RET Chair.
  - Ensured RET checkboxes remain interactive if returned by the RET Chair, but locked if waiting for review or returned by the Program Chair (standard workloads returned).

---

## Bug Fixes

### 1. Program Chair Modal RET Status Synchronization
- **Problem**: When a faculty member's RET targets were approved by the RET Chair, they did not sync properly into the Program Chair's review modal or show up as `Approved`. They were either omitted when creating/updating the review items because the SQL queries only matched items with status `('Pending Review', 'Waiting for Approval')`, or they showed up with old quantities because quantities weren't synced.
- **Fixes**:
  - Modified `get_or_create_chair_review` in [prog_chair.py](file:///home/buzz/Projects/Management-PCR/app/models/prog_chair.py) to support targets with `Approved` status.
  - Added an auto-synchronization update query to update the Program Chair's `original_quantity` and `reviewed_quantity` fields for Research and Extension categories from the RET Chair's final values in `tbl_draft_targets`.
  - Added the `'draft_status': item['draft_status']` parameter to the serialized review dictionary in [prog_chair.py](file:///home/buzz/Projects/Management-PCR/app/routes/prog_chair.py) review route so the frontend receives the actual status.

### 2. Disappearing RET Targets on Overall Rejection/Re-submission
- **Problem**: When the Program Chair returned/rejected the draft IPCR, the RET choices on the faculty dashboard were locked/disabled (because they were either already approved or currently pending with the RET Chair). Since disabled inputs are not submitted by the browser, the POST payload was empty. The backend logic subsequently deleted all existing Research & Extension targets and inserted nothing, leaving them empty on both dashboards.
- **Fixes**:
  - Modified `decide_chair_review` in [prog_chair.py](file:///home/buzz/Projects/Management-PCR/app/models/prog_chair.py) to only flip standard workloads (`A. Instructions` and `Support Functions`) to `'Returned'` upon rejection. Approved or pending RET targets remain intact.
  - Updated `submit_faculty_ipcr` in [app/models/faculty.py](file:///home/buzz/Projects/Management-PCR/app/models/faculty.py) to run a check on whether RET choices are editable by the user. If they are locked/disabled (i.e. not returned/rejected by the RET Chair), they are preserved and never deleted or overwritten during re-submission.

### 3. Program Chair Dashboard Count & Faculty Banner Mismatches
- **Problem**:
  1. Approved RET targets were excluded from the Program Chair's dashboard pending count list because of the `IN ('Pending Review', 'Waiting for Approval')` SQL status restriction.
  2. The faculty dashboard showed double banners ("Waiting for RET approval" and "Approved by program chair") once the Program Chair approved the draft but before it was locked.
  3. Resubmitting draft IPCRs unconditionally reset the RET Chair review status back to `'Pending'` and cleared items even if the RET choices were already approved.
- **Fixes**:
  - Expanded `get_pending_draft_ipcrs` in [app/models/prog_chair.py](file:///home/buzz/Projects/Management-PCR/app/models/prog_chair.py) to include `'Approved'` and `'Returned'` statuses when counting targets.
  - Adjusted the waiting alert banners condition in [app/templates/faculty_dashboard.html](file:///home/buzz/Projects/Management-PCR/app/templates/faculty_dashboard.html) to hide themselves if the Program Chair has already approved.
  - Updated step 8b in [app/models/faculty.py](file:///home/buzz/Projects/Management-PCR/app/models/faculty.py) to only reset RET reviews on resubmission if `ret_editable` is `True` (preserving `'Approved'` RET reviews).
