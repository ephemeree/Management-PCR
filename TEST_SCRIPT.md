# End-to-End Test Script — New Term → Final Rating

Covers everything built across the RET redesign, Dynamic Criteria, and the
Scoring work (S1–S3). Follow top to bottom; each step lists what to expect.

**Accounts needed:** ADMIN · DEAN · PROGRAM_CHAIR · RET_CHAIR · FACULTY (regular) ·
DESIGNATED_FACULTY. Note the Faculty's **academic rank** and **specialization** —
several steps depend on them matching.

> Passwords are bcrypt-hashed. If you don't know one, log in as ADMIN →
> System Security → Reset Password to mint a temporary one.

---

## Phase A — Admin: term, criteria, weights

### A1. Open the new term
Admin → **Term Configuration** → set Academic Year, Semester, Deadline → Open Term.

- [/] New term appears and is marked active.
- [/] Only one term is active.

### A2. Load master indicators
Admin → **Master Indicators** → *Import from Previous Term* (or add manually).

- [/] Indicators are listed for the new term.
- [*] The **Category dropdown lists your managed criteria** — not a hardcoded list.
      (This was the bug fixed in Phase 2: it used to offer `B. Research`, which
      didn't match the real `A. Research` and created orphan categories.)
      :remove "Custom Target Items (non core)" function addition -- reason: the designated faculty should be the only one to be able to add Custom Targets. Because in practice, the admin only cascade the targets from the DPCR (Department Level version of the IPCRs, so there wouldnt be any custom targets in there. Custom Targets are given to Designated Faculty by offices outside the Department.)

### A3. Criteria CRUD *(Dynamic Criteria — Phase 2)*
Admin → **Criteria**.

- [/] Table lists the 5 seeded criteria with slug / lane / core / weight group / order.
- [/] **Add Criterion** — e.g. name `Innovation`, lane `CHAIR`, weight group *(blank)*,
      order 60, core ✓. It appears with an auto-generated slug `innovation`.
- [/] **Edit** it — the name changes but the **slug stays fixed**.
- [/] **Deactivate** it — row greys out and it disappears from the Master Indicator
      category dropdown.
- [*] Re-activate (or leave inactive; it won't affect the rest of the test).
      :action buttons are also greyed out. but still works. user might think that it is not clickable.

### A4. Weight allocation *(Phase 3)*
Admin → Criteria → **Weight Allocation by Rank**.

**Regular Faculty tab**, mode = **General**:

| instruction | ret | support |
|---|---|---|
| 50 | 40 | 10 |

- [/] Row total badge turns **green at 100%**; red if you make it 90.
- [/] Saving at 90% is **rejected** with a message; nothing is stored.
- [/] Saving at 100% succeeds.

**Designated Faculty tab**, mode = **General**:

| instruction | ret | support |
|---|---|---|
| 25 | 0 | 75 |

- [/] Saves independently — switching back to the Regular tab still shows 50/40/10.
- [/] Switch Regular to **Specific per Academic Rank**, fill only the Instructor row
      100%, save → reopen and confirm it's in Specific mode and the General row is gone.
- [/] Switch back to **General**, re-enter 50/40/10, save. *(Leave it in General.)*

> Matches the real forms: Regular 50/40/10, Designated 75/25 with no RET bucket.

A4 Comments/Suggestions/Questions: The weight allocation on have the 3 categories: Instruction (Which shouldve been "Strategic Priorities"), Ret (which should've been "Core Functions"), and Support Functions. 

A4 Comments/Suggestions/Questions: If you would look at the files that I sent you (REGULAR FACULTY.pdf, and IPCR-With Designation.pdf), you will see what the Correct Category Names are:
      - Regular Faculty: Strategic Priorities(includes Instruction targets -- Labeled as A. Instruction because thats the only Target type under that category), Core Functions(includes Research and Extension and Training Targets -- Labeled as A. Research, and B. Research and Extension), and Support Functions
      - Designated Faculty: Strategic Priorities/Support Functions(includes Administration Targets -- we dont have this kind of target type yet), and Core Functions.

A4 Comments/Suggestions/Questions: lets add a Category Management (think of a proper term for this): Basically, It manages the Category types for Regular and Designated Faculty(example for regular faculty: Strategic Priorities, Core Functions, Support Functions) and assign which Target types(instructions, research, extension and training, Support, and if there are any added in the Criteria CRUD) are under that category.

A4 Comments/Suggestions/Questions: update weight allocation rank accordingly.

A4 Comments/Suggestions/Questions: Criteria Panel should be next to HR Roster on the Sidebar. So it follows a logical flow.

A4 Comments/Suggestions/Questions: The Categories on the Category Management will then Reflect on the Master Indicator Panel. I suggest that we make the "Add Master Indicator" as a modal, which will only appear after pressing "Add target" button on the Header of the Tables for the Categories.


Phase A Comments/Suggestions/Questions: Add Department Management on the Admin Side: the current departments(DST, WST, NST, RET, BSDS) on the system are hardcoded. We should be able to manage this so the system is scalable.

Phase A Comments/Suggestions/Questions: REFACTOR default teaching load targets. Admin should be able to edit how many hours the REgular Faculty and Designated Faculty's teaching load. Follow the same logic as the weight allocation on Criteria Panel (can set general Teaching load or set different teaching load per rank band, Regular Faculty and Designated Faculty). and automatically set the deadline for this targets to 6 Months (for timeliness score)

---

## Phase B — Dean: cascade quotas

Dean dashboard → cascade targets for the new term.

- [/] Assign quotas to your Faculty's **program/specialization** (needed for the
      Program Chair to see anything).
- [/] Assign quotas to **RET / Extension** (needed for the RET Chair).

> **Gotcha:** if you skip this, the Program Chair's distribution table and the RET
> Chair's Research/Extension option lists will both be empty.

Phase B Comments/Suggestions/Questions: add a confirmation modal when pressing the "Cascade Institutional Targets", and prevent the system on accepting the input when there is a target that has'nt been assigned to at least one department.
---

## Phase C — Program Chair: distribute targets *(S1)*

Program Chair → distribution table.

- [/] Each row has a **duration number + unit dropdown** (days/weeks/months/semesters),
      not a free-text deadline.
- [/] Fill quantity, duration (e.g. `6` + `months`), and an IPCR target description.
- [/] Save → success. Reopen → **values persist**, including the unit.
- [/] Re-saving after finalization is blocked with a warning.

---

## Phase D — RET Chair: research menu, assignment, extension

### D1. Research menu *(R5)*
RET Chair → **Phase 2: Research Menu Configuration**.

- [/] The form is **Research-only** — no Extension count field, no Extension options list.
- [/] Pick your Faculty's academic rank, set Research Required = `1`, check 2 research
      indicators with quantities → Save.
- [/] **Phase 3: Active Research Rules** shows the rule with **only Research columns**.

D1 Comments/Suggestions/Questions: add deadline, and IPCR target Description fields on each research target (to fetch data for scoring).

### D2. Direct research assignment *(R1)*
RET Chair → **Target Assignment** → *Assign Research Targets to Faculty*.

- [/] All regular faculty are listed (no access/eligibility gate — Option B).
- [/] Click **Assign** on a *different* faculty than your main test one → modal shows
      **Research only**, limited to that rank's menu → check one, save.
- [/] Button shows a count badge afterwards.

### D3. Extension distribution *(R4)* — ⚠ one-time
RET Chair → **Target Assignment** → *Distribute Extension Targets to All Faculty*.

- [/] Check 1–2 extension targets, set per-faculty quantity (e.g. `1`) → **Distribute**
      → confirm the dialog.
- [/] Card flips to **"Distributed & Locked"**, inputs disabled, button gone.
- [/] Refresh → **still locked**. This cannot be undone (see Reset appendix).

D3 Comments/Suggestions/Questions: Match the Extension Distribution to how the Program Chair's Target Allocation Looks and works. (with deadline, auto-divide(to all regular faculty), etc.)

Phase D Comments/Suggestions/Questions: lets merge or put the Active Rules panel with the Menu Config panel so that RET Chair wongt have to go to a different panel to check the Active Rules should they decide to edit a Rule (because on the current code, RET chair goes to the Active Rules Panel, and when they press the Edit button, they are brought back to the Menu Config Panel)

---

## Phase E — Faculty: view and submit

Log in as the **FACULTY** whose rank you configured in D1.

- [/] **Research Menu** appears with the rank's indicators.
- [/] **Extension Targets** card shows the distributed targets as **read-only**, with
      a lock icon and "Assigned to all faculty" — you did *not* pick them.
- [/] Research shows **"(optional) — up to: 0 / 1"**.
- [/] **Submit is enabled with 0 research selected** *(research is optional)*.
- [/] Select 1 research → the *other* research option locks (soft cap at 1).
- [/] Uncheck it → the cap releases.
- [/] Select 1 research → **Submit IPCR for Review**.

**Extra check — assigned research:** log in as the faculty from D2.
- [/] Their assigned research is **checked and disabled**, badged "Assigned by RET Chair".

**Extra check — no research menu:** a faculty whose rank has no rules.
- [/] Still sees the read-only **Extension** card.

---

## Phase F — Reviews and lock

### F1. RET review
RET Chair → **Phase 4 / Commitments** → open the faculty's review.

- [/] **Submitted Targets** shows the selected Research **and** the distributed
      Extension as **read-only rows** ("Distributed to all faculty", 🔒 Not editable).
- [/] **Unselected Indicators** lists **Research only** — no extension.
- [/] Approve.

> A faculty with **no research at all** should not appear in this queue — extension
> auto-flows past RET review.

### F2. Program Chair approval
Program Chair → Commitments → open the draft IPCR.

- [/] Research shows **"Approved by RET Chair"**.
- [/] Extension **also** shows approved (it's auto-approved on materialization).
- [/] The **Approve IPCR** button is enabled → Approve.

### F3. Faculty lock
Faculty → **Lock My IPCR**.

- [/] Committed targets include instruction/support, the research, **and** the extension.

---

## Phase G — Evidence and scoring *(S2 / S3)*

Faculty → **Evidence Gathering**.

### G1. Checklist
- [/] New **Actual Accomplishment** column shows the target sentence with blanks,
      e.g. *"____ face to face classes successfully monitored/observed in ____ months."*
- [/] Badge reads "Time to complete not reported".

### G2. Report a target
Click **Add/View Evidence** on a target.

- [/] **Accomplishment Details** card shows the composed sentence, "Completed in",
      the target duration for reference, and status radios.
- [/] Upload a PDF with an accomplished quantity → the Accomplished Qty updates.
- [/] Enter **Completed in** = a value *less than* the target (e.g. 4 of 6) →
      status **Completed** → **Save Details**.
- [/] **Computed Rating** badges populate: Q · E · T → Average.
- [/] The Actual Accomplishment sentence now reads with real values
      (e.g. *"…monitored/observed in 4 months."*).

**Timeliness spot-checks** (change *Completed in*, save, re-open):

| Completed in (target 6 months) | RT | Expected T |
|---|---|---|
| 4 | 1 − 4/6 = .33 | **5** |
| 5 | .17 | **4** |
| 6 | .00 | **3** |
| status = *Partially completed at deadline* | — | **2** |
| status = *Not yet begun* | — | **1** |

- [ ] Selecting a non-Completed status **disables** the "Completed in" field.

**Quantity spot-checks** (target qty 10 — adjust uploaded quantities):

| Accomplished | RQn | Expected Q |
|---|---|---|
| 13+ | ≥1.30 | **5** |
| 12 | 1.20 | **4** |
| 10 | 1.00 | **3** |
| 6 | .60 | **2** |
| 5 | .50 | **1** |

### G3. Client Satisfaction *(optional)*
To exercise the E input, set one indicator's **Efficiency Type = Client Satisfaction**
(Admin → Master Indicators → Edit) *before* locking.

- [-] Only that target's modal shows the **Client Satisfaction Rating** dropdown.
- [-] Choosing *Very Satisfactory* → **E = 4**, and the sentence renders
      *"…with Very Satisfactory rating."*
- [-] Other targets show **no** dropdown (E is derived).

### G4. Summary of Ratings
- [/] **Summary of Ratings** panel lists each weight group with Weight % · Average ·
      Weighted, then Total Overall, Final Weighted Rating, and Adjectival Rating.
- [/] Percentages match Phase A4 (50 / 40 / 10).
- [/] Adjectival matches the band: ≥4.75 Outstanding · ≥3.75 Very Satisfactory ·
      ≥3.00 Satisfactory · ≥2.01 Unsatisfactory · else Poor.

> If you skipped A4, this panel shows a **warning that no weights are configured** —
> that's the correct behaviour, not a bug.

### G5. Submit evidences → persist the score
- [/] **Submit Evidences** → the flash message includes the
      **Final Weighted Rating and Adjectival Rating**.
- [/] Verify persisted:

```sql
SELECT f.emp_id, f.final_score, f.adjectival_rating, b.weight_group, b.raw_avg, b.weight_pct, b.weighted_value
FROM tbl_final_scores f
LEFT JOIN tbl_final_score_breakdown b ON b.score_id = f.score_id
WHERE f.term_id = (SELECT term_id FROM tbl_academic_terms WHERE is_active = 1);
```

- [/] One `tbl_final_scores` row + one breakdown row per weight group.
- [/] Re-submitting does **not** duplicate breakdown rows.

---

Phase G Comments/Suggestions/Questions: Remove Tag Co-Author in Evidence gathering modal.

Phase G Comments/Suggestions/Questions: disable adding evidences once the faculty has submitted their evidence for verification. they should still be allowed to view the evidence they uploaded, but uploading another evidence should be disabled.

## Phase H — Program Chair validation

Program Chair → faculty evidence details modal.

- [/] New **"Reported & Rating"** column shows: *Completed in 4 months of 6 months*,
      the Client Satisfaction rating (only where applicable), and Q · E · T · Avg badges.
- [/] The **actual accomplishment sentence** shows under each target description.
- [/] All read-only — the PC validates, the faculty owns the inputs.

Phase H Comments/Suggestions/Questions: add column in faculty evidence verification modal: Status (verification)
Phase H Comments/Suggestions/Questions: make it so that the View Uploaded evidence modal covers the width of the screen (for better viewing)
Phase H Comments/Suggestions/Questions: add approve and return button on the View Uploaded evidence modal. Returning should ask for a reason for return first before returning to the faculty. Returned evidence should unlock the uploading for Faculty

---

## Phase I — Designated Faculty *(parallel path)*

- [-] Their selection form uses **duration number + unit** (not free text).
- [-] "Add custom target" modal has **Target Duration** value + unit.
- [-] Submit → **Dean** approves → targets committed with durations intact.
- [-] Their scoring uses the **Designated Faculty** weight tab (25/75), not 50/40/10.

Phase I Comments/Suggestions/Questions: update accordingly to fetch data for scoring

---

## Appendix — Known gotchas

1. **Rank rules reset each term.** `tbl_ret_rules` filters by `mi.term_id`, so a new
   term shows no research menu until D1 is redone. By design.
2. **Extension distribution is permanent** for a term. No unlock exists.
3. **Legacy targets** (set before S1) have no structured duration — they score as
   un-timed (T = —). Only newly-set targets have durations.
4. **`verification_status` is never written.** The Verified/Rejected badges render but
   nothing sets them, so the "exclude Rejected evidence from Q" logic is currently
   inert. Known, not yet built.
5. **Efficiency types in use** are only `Quantity-Based` / `Output-Based`. `Adjectival`
   and `Client Satisfaction` must be set manually to exercise those branches.

## Appendix — Reset for a re-run

```sql
-- Replace 99 with the term you are resetting.
SET @t = 99;

DELETE b FROM tbl_final_score_breakdown b
  JOIN tbl_final_scores f ON b.score_id = f.score_id WHERE f.term_id = @t;
DELETE FROM tbl_final_scores            WHERE term_id = @t;
DELETE FROM tbl_ret_extension_distribution WHERE term_id = @t;  -- clears the one-time lock
DELETE FROM tbl_ret_assignments         WHERE term_id = @t;
DELETE FROM tbl_criteria_weights        WHERE term_id = @t;

-- Review records for the term
DELETE ri FROM tbl_ipcr_chair_review_items ri
  JOIN tbl_ipcr_chair_review r ON ri.review_id = r.review_id WHERE r.term_id = @t;
DELETE FROM tbl_ipcr_chair_review WHERE term_id = @t;
DELETE ri FROM tbl_ipcr_ret_review_items ri
  JOIN tbl_ipcr_ret_review r ON ri.review_id = r.review_id WHERE r.term_id = @t;
DELETE FROM tbl_ipcr_ret_review WHERE term_id = @t;
DELETE ri FROM tbl_ipcr_dean_review_items ri
  JOIN tbl_ipcr_dean_review r ON ri.review_id = r.review_id WHERE r.term_id = @t;
DELETE FROM tbl_ipcr_dean_review WHERE term_id = @t;

-- Target data for the term (uploaded files on disk are not removed)
DELETE e FROM tbl_evidence_repo e JOIN tbl_committed_targets ct ON e.target_id = ct.target_id
  JOIN tbl_master_indicators mi ON ct.indicator_id = mi.indicator_id WHERE mi.term_id = @t;
DELETE ct FROM tbl_committed_targets ct
  JOIN tbl_master_indicators mi ON ct.indicator_id = mi.indicator_id WHERE mi.term_id = @t;
DELETE dt FROM tbl_draft_targets dt
  JOIN tbl_master_indicators mi ON dt.indicator_id = mi.indicator_id WHERE mi.term_id = @t;
DELETE da FROM tbl_draft_allocation da
  JOIN tbl_master_indicators mi ON da.indicator_id = mi.indicator_id WHERE mi.term_id = @t;
```
