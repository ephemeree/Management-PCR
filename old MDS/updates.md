# System Updates & Enhancements Summary

This document summarizes all the recent updates and modifications implemented across the IPCR (Individual Performance Commitment and Review) management system.

---

## 1. Documentation & Visual Flows
* **Mermaid Flowchart Added:**
  * Updated [flow.md](file:///c:/Users/Nitro%205/Documents/Capstone%20system/Management-PCR/flow.md) with a comprehensive `Mermaid` flowchart showing the database lifecycle and table transitions from the initial workload distribution to draft submissions, chair reviews, decisions, and locking.

---

## 2. Regular Faculty Dashboard
* **Removed Redundant Alerts:**
  * Removed the duplicate `"IPCR is Locked (View-Only Mode)"` warning banner at the top of [faculty_dashboard.html](file:///c:/Users/Nitro%205/Documents/Capstone%20system/Management-PCR/app/templates/faculty_dashboard.html). The more descriptive black banner remains active.
* **Separated Instructions & Support Functions:**
  * Removed **Research** and **Extension** targets from the core left-hand column list (to avoid redundancy, as they are already managed in the dedicated checklist menus on the right).
  * Split the core workloads card into two distinct cards:
    * **A. Instructions** (blue styled card)
    * **B. Support Functions** (orange/warning styled card)
* **Jinja2 Namespace Scoping Fix:**
  * Resolved a bug where the `"No strategic workloads assigned."` empty-state row was shown even when workloads were present. Loop variables were updated to use Jinja2 `namespace` check objects (`ns_inst.has_core` / `ns_supp.has_core`) to persist scope outside the iteration loops.
* **Submission Status Labeling:**
  * Renamed status badges and messages for first-time submissions:
    * Top right status badge updated from `"Pending Chair Approval"` to `"Waiting for Review"`.
    * Bottom right alert text updated from `"Your IPCR is currently locked pending approval."` to `"Your IPCR is currently waiting for review."`.

---

## 3. Program Chair Dashboard & Backend Database logic
* **Header Label Standardization:**
  * Renamed target allocation headers in Phase 1 of [prog_chair_dashboard.html](file:///c:/Users/Nitro%205/Documents/Capstone%20system/Management-PCR/app/templates/prog_chair_dashboard.html) from "Instructions" and "Support Functions" to **"A. Instructions"** and **"B. Support Functions"** to align labels with the regular faculty dashboard.
* **Approved & Locked IPCRs List:**
  * Created database query function [get_locked_faculty_ipcrs](file:///c:/Users/Nitro%205/Documents/Capstone%20system/Management-PCR/app/models/prog_chair.py#L152-L187) in the chair models.
  * Added controller integration in [prog_chair.py](file:///c:/Users/Nitro%205/Documents/Capstone%20system/Management-PCR/app/routes/prog_chair.py#L14-L66) to query and pass `locked_drafts` to the template.
  * Added a new **"Approved & Locked IPCRs"** table in [prog_chair_dashboard.html](file:///c:/Users/Nitro%205/Documents/Capstone%20system/Management-PCR/app/templates/prog_chair_dashboard.html) to display all faculty members who have locked their final evaluation targets for the active term.
* **Dedicated Read-Only Modal:**
  * Designed and added a new modal (`#viewLockedIpcrModal`) for viewing final locked targets.
  * Removed all inputs, remarks, textareas, return buttons, and approval buttons. It displays only final targets, original/reviewed quantities, and chair remarks in a clean static grid.
  * Configured dynamic JavaScript loaders (`.open-view-locked-modal` handler) to populate this modal via AJAX.

---

## 4. Designated Faculty / Chair — Oversight Target & Evidence Pipeline Fixes (2026-08-22)

A Program Chair, RET Chair or Dean can legitimately hold the **same indicator twice** on their
own IPCR: once as their personal Core Function share (e.g. a Program Chair's own teaching
allocation), and once as their Strategic Priorities/Support Functions **Departmental Oversight**
row (the department's/RET's *whole* cascaded quota, via `get_oversight_targets`). Every bug in
this section traces back to code elsewhere in the pipeline that assumed an `indicator_id` — or a
person's evidence status — was unique/singular in a way that stopped being true once that dual
row became correctly populated.

### 4.1 Duplicate Core Function rows / missing oversight rows on submit
* [app/templates/designated_dashboard.html](../app/templates/designated_dashboard.html) rendered
  both the personal row (Table 1: Core Functions) and the oversight row (Table 2: Strategic
  Priorities & Support Functions) with form fields keyed only by `indicator_id`
  (`selected_indicators[]`, `target_qty_<id>`, `target_dur_value_<id>`/`target_dur_unit_<id>`).
  When both rows shared an indicator, their fields collided in the submitted form: the id came
  through twice, and [`submit_designated_ipcr`](../app/models/designated.py) categorised **both**
  submissions as Core Function (its `is_core` check only looks at `indicator_id`), producing
  duplicate Core Function rows in `tbl_draft_targets`/`tbl_committed_targets` and losing the
  Strategic Priorities entry entirely.
* Fixed by deriving the Departmental Oversight row **server-side**, the same way the mandatory
  Teaching Load already was — never trusted from the form. `submit_designated_ipcr` now computes
  `oversight_rows` via `get_oversight_targets`, skips only the *pure*-oversight submissions from
  the form (`oversight_indicator_ids - core_indicator_ids`, so a dual id's real personal
  submission is kept), and inserts the oversight row itself with quantity from the Dean's cascade.
* [app/routes/designated.py](../app/routes/designated.py) dedupes `selected_indicators[]`
  (`dict.fromkeys`) before building `selected_targets`, and skips route-level validation for
  Departmental Oversight ids (which never render a `target_qty_<id>` field, so they'd otherwise
  fail the ">0 quantity" check even though they're valid).
* The Departmental Oversight row's **deadline** is real chair input (there's no server source for
  it, unlike quantity) — its qty/duration/checkbox inputs now use `_adm`-suffixed field names
  (`target_dur_value_<id>_adm`, etc.) so they never collide with a same-indicator personal row.
* [`get_designated_committed_targets`](../app/models/designated.py) additionally joined
  `tbl_committed_targets` to `tbl_draft_targets` on `emp_id + indicator_id` only — once a person
  correctly has two committed rows for one indicator, that join fanned out and duplicated both on
  display. Joined on `is_admin_function` too so each committed row pairs 1:1 with its own draft row.
* Added `is_oversight_cascade` (narrower than `is_admin_function`, which is also `1` for any
  freely-picked Strategic Priorities/Support item) so the "Departmental Oversight — Fixed Quota"
  badge and field locking only apply to genuine oversight rows, not regular picks.
* `get_designated_selectable_indicators`'s RET branch (RET Chair's free-pick pool) now excludes
  indicators already claimed as RET's Departmental Oversight quota — RET has no personal
  allocation table equivalent, so any RET indicator there was always purely a stray duplicate.

### 4.2 Dean review — oversight row miscategorised as Core Function
* [`get_dean_review_items`](../app/models/dean.py) determined `is_core` from whether the person
  had *any* personal allocation for that indicator (`da.allocation_id IS NOT NULL`), not whether
  *this specific review row* was the personal one — so a chair's oversight row for the same
  indicator was flagged Core too, and the real Strategic Priorities entry vanished from the Dean's
  modal. Fixed by joining `tbl_draft_targets.is_admin_function` through and gating on it.

### 4.3 Dean review modal — "Approve" button permanently locked
* [app/templates/dean_dashboard.html](../app/templates/dean_dashboard.html)'s `checkDeanEdits()`
  compared quantities against an initial snapshot **keyed by `indicator_id`** to decide whether
  the Dean had modified anything. With two rows sharing an indicator_id, one row's quantity
  silently overwrote the other's in that lookup, so the comparison always found a "mismatch" and
  permanently disabled Approve — even with zero real edits.
* Every review item now carries a stable `_key` (the review item's own unique id), used instead of
  `indicator_id` for the edit-detection snapshot/comparison, the qty/remark input handlers, and
  the remove-item button — eliminating the collision at its source rather than special-casing it.

### 4.4 Evidence verification — Program Chair review step skipped
* [`submit_designated_evidences`](../app/models/designated.py) always set evidence status straight
  to `Submitted to Dean`, for everyone using the shared `/designated/` flow — so a plain Designated
  Faculty's evidence reached the Dean's Final Verification queue, fully approvable, before their
  Program Chair had reviewed a single file.
* Now branches on `designation`: a plain Designated Faculty gets `Submitted` (routes to Program
  Chair review first, same as Regular Faculty); a Program Chair/RET Chair/Dean's own evidence
  still goes straight to `Submitted to Dean`, since there's no one else positioned to review it.
* [`get_dean_evidence_faculty`](../app/models/dean.py) had its own independent version of the same
  bug — a broad `OR` clause let *any* non-Regular-Faculty designation into the Dean's queue at the
  earlier `Submitted` status. Simplified to the single correct gate: `Submitted to Dean` /
  `Dean Approved`.

### 4.5 Program Chair evidence-verification modal — table layout mismatch
* The modal in [prog_chair_dashboard.html](../app/templates/prog_chair_dashboard.html) grouped a
  faculty member's targets by raw `category_name` (up to 5 sections: Strategic/Research/
  Extension/Support/Others) for everyone. For a Designated Faculty, that doesn't match their own
  "My IPCR" page, which shows exactly **2** tables (Core Functions; Strategic Priorities & Support
  Functions) driven by `is_admin_function` — the same category (e.g. Instruction) can be either,
  depending on whether it's personal teaching work or an oversight quota.
* [`prog_chair_faculty_evidence_details`](../app/routes/prog_chair.py) now returns `is_designated`
  and (for a designated faculty/chair) `is_core = not is_admin_function` per target; the modal's
  grouping branches on that flag to render the same two tables instead of the category breakdown.
  Regular Faculty keeps the original category-based grouping unchanged.
