# Recent System Updates: Features, Error Trapping & Tables Used

This document summarizes the functional updates made to the Program Chair's target allocation, the Dean's final verification process, and the Faculty's Print IPCR workflow.

## 1. Program Chair: Target Allocation
* **Added Feature / Error Trapping**: Prevent finalization of target allocations if there is at least one missing or empty input field. Ensures complete data integrity before targets are pushed to faculty.
* **Tables Used**: `tbl_cascaded_quotas`, `tbl_committed_targets`

## 2. Dean Dashboard: Final Verification
* **Added Feature**: IPCR Summary breakdown (Strategic, Core, Support) and Final Adjectival Rating are now displayed on the final verification confirmation prompt, allowing the Dean to review the computed scores before approving.
* **Added Feature / Error Trapping**: Removed the "Return to Faculty" option during this specific final verification step. This establishes a strict, one-way approval flow once the evaluation reaches this phase.
* **Tables Used**: `tbl_committed_targets` (updates status to 'Dean Approved')

## 3. Faculty Dashboard: Print IPCR Flow
* **Added Feature / Error Trapping**: Strict visibility control for the "Print IPCR" tab. The tab and its content are fully hidden and locked until the IPCR is officially approved by the Dean.
* **Added Feature**: Displays the finalized score breakdown (two tables) reflecting the exact metrics from the Dean's view. The main "Print IPCR" action currently serves as a functional placeholder ("feature coming soon").
* **Tables Used**: `tbl_committed_targets` (checks for 'Dean Approved' status), `tbl_ipcr_ratings` (retrieves final computed scores)

## 4. Backend Stability Fixes
* **Error Trapping**: Updated cursor data handling in `compute_ipcr_score` (`scoring.py`) to safely parse both dictionary and tuple returns. This resolves crashing bugs (`KeyError: 0` and `AttributeError`) that occurred due to mixed cursor types across different routes.
* **Tables Used**: `tbl_employee_profiles` (queried for designation and academic rank)
