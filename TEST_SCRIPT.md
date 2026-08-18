# End-to-End Test Script — New Term → Final Rating

Covers the system as it stands after the RET redesign, Dynamic Criteria, Scoring
(S1–S3) and the post-test work (Groups 1–6). Follow top to bottom; each step lists
what to expect.

**Legend:** `[ ]` not tested · `[/]` passed · `[*]` passed with a comment · `[-]` skipped
Add notes under any item as `:your comment` — that's how the last round was fed back
into [`old MDS/POST_TEST_PLAN.md`](old%20MDS/POST_TEST_PLAN.md).

**Accounts needed:** ADMIN · DEAN · PROGRAM_CHAIR · RET_CHAIR · FACULTY (regular) ·
DESIGNATED_FACULTY. Note the Faculty's **academic rank** and **specialization** —
several steps depend on them matching.

> Passwords are bcrypt-hashed. If you don't know one, log in as ADMIN →
> System Security → Reset Password.

### 🔁 Changed since the last run — retest these first

| Where | What changed |
|---|---|
| **A3** | Teaching load now **locks after saving**; an **Edit** button unlocks it |
| **D3** | Extension **checkbox removed** — all extension targets distribute |
| **H** | Evidence viewer is now **truly full-width** (an old `50vw` rule was overriding it) |
| **H** | **RET Chair now has Approve / Return buttons** (they were missing entirely) |
| **H** | Approve/Return no longer embed evidence data in an HTML attribute — this was the likely cause of the **Approve button error**. If it still errors, capture the browser console message. |
| **I** | Designated **Evidence Gathering now has Accomplishment Details** (Completed in, Client Satisfaction, Q·E·T) |
| **I** | Selection table **column widths rebalanced** (description 40%, deadline 220px) |

---

## Phase A — Admin setup

### A1. Open the new term
Admin → **Term Configuration** → set Academic Year, Semester, Deadline → Open Term.

- [ ] New term appears and is marked active; only one term is active.

### A2. Institution Setup — Departments *(new)*
Admin → **Institution Setup** → *Departments / Programs*.

- [ ] Seeded departments are listed (WST / DST / NST / BSDS) with codes and order.
- [ ] **Add Department** — e.g. `MST Program` / code `MST` / order 50 → appears in the table.
- [ ] **Edit** an existing one's code and order → persists.
- [ ] **Deactivate** the one you added → greys out, and its **Status** reads Inactive.

> Renaming a department also renames it on the faculty roster and existing quotas,
> since targets route by that name.

### A3. Institution Setup — Teaching Load *(new)*
Same panel → *Teaching Load*.

- [ ] **Regular Faculty** tab shows `21` hours / `6` months (seeded).
- [ ] **Designated Faculty** tab shows `10` hours / `6` months, independently.
- [ ] Change Regular to `18` hours → Save → reopen and confirm it persisted.
- [ ] Switch Regular to **Per academic rank**, fill Instructor only → Save → reopen,
      confirm it is in per-rank mode and the "all ranks" row is gone.
- [ ] Switch back to **Same for all ranks**, set `21` / `6` months, Save. *(Leave it here.)*
- [ ] After saving, the fields are **locked** — an **Edit** button appears and the Save
      button hides. Pressing **Edit** unlocks them and brings Save back. *(fixed)*

### A4. Criteria (target types)
Admin → **Criteria**.

- [ ] Table lists target types with slug / lane / core / order — **no Weight Group column**.
- [ ] **Add Criterion** — e.g. `Innovation`, lane `CHAIR`, order 60, core ✓ → auto slug `innovation`.
- [ ] **Edit** it — name changes, **slug stays fixed**.
- [ ] **Deactivate** it — row dims but the **Edit / Activate buttons stay clearly clickable**.

### A5. Category Management *(new)*
Admin → Criteria → **Category Management**.

- [ ] **Regular Faculty** lists: Strategic Priorities (A. Instructions) · Core Functions
      (A. Research, B. Extension…) · Support Functions (Support Functions).
- [ ] **Designated Faculty** lists: Strategic Priorities/Support Functions
      (Administrative Functions, Support Functions) · Core Functions (A. Instructions).
- [ ] **Edit** a category → change its assigned target types → saves.
- [ ] **Add Category** for a designation → appears with your chosen target types.

> The key behaviour: **A. Instructions belongs to a different category per designation**
> — Strategic Priorities for Regular, Core Functions for Designated.

### A6. Weight Allocation
Admin → Criteria → **Weight Allocation by Rank**.

- [ ] Columns show **real category names**, not `instruction / ret / support`.

**Regular Faculty**, mode = *General*: Strategic Priorities `50` · Core Functions `40` · Support Functions `10`

- [ ] Row total badge turns green at 100%; red at 90.
- [ ] Saving at 90% is rejected; nothing is stored.
- [ ] Saving at 100% succeeds.

**Designated Faculty**, mode = *General*: Strategic Priorities/Support Functions `75` · Core Functions `25`

- [ ] Saves independently — the Regular tab still shows 50/40/10.
- [ ] Switch Regular to **Specific per Academic Rank**, fill only Instructor at 100%, save,
      reopen → in Specific mode, General row gone.
- [ ] Switch back to **General**, re-enter 50/40/10, save. *(Leave it in General.)*

### A7. Master Indicators
Admin → **Master Indicators** → *Import from Previous Term* (or add manually).

- [ ] Panel is grouped by **IPCR category**, mirroring the DPCR:
      Strategic Priorities → A. Instruction · Core Functions → A. Research + B. Extension ·
      Support Functions.
- [ ] Each category header has an **Add Target** button.
- [ ] Clicking it opens a **modal** with a **Target Type dropdown scoped to that category**.
- [ ] Add a target under Core Functions → choose `A. Research` → it appears under the right sub-heading.
- [ ] An **Other Target Types** section exists at the bottom for Administrative Functions.
- [ ] **Custom Target Items is NOT offered** anywhere as a category to file targets under.

**Set up a Client Satisfaction target** (needed for G3):
- [ ] Edit one indicator → **Efficiency Type = Client Satisfaction** → save.

---

## Phase B — Dean: cascade quotas

Dean dashboard → cascade table.

- [ ] Columns are generated from the **managed departments** plus `RET / Extension` and
      `College-Wide` — the department you added in A2 appears (if still active).
- [ ] Fill quotas for your Faculty's program **and** for RET / Extension.
- [ ] Leave one target with **no allocation**, then press **Cascade Institutional Targets**.
- [ ] A confirmation modal appears and **blocks submission**, listing the unassigned target.
- [ ] Fill it in, press again → modal now shows the target count → **Confirm & Cascade**.

> Skipping this leaves the Program Chair's distribution table and the RET Chair's
> Research/Extension lists empty.

---

## Phase C — Program Chair: distribute targets

- [ ] Each row has a **duration number + unit dropdown**, not free text.
- [ ] Fill quantity, duration (e.g. `6` + `months`), and a target description → Save.
- [ ] Reopen → values persist, including the unit.
- [ ] Re-saving after finalisation is blocked with a warning.

---

## Phase D — RET Chair

### D1. Research menu
RET Chair → **Menu Config**.

- [ ] Form is **Research-only** — no Extension fields.
- [ ] Each research indicator now has an **IPCR description** and **duration + unit** field,
      enabled only when its checkbox is ticked.
- [ ] Pick your Faculty's rank, Research Required = `1`, tick 2 indicators, fill their
      descriptions and durations (e.g. `6 months`) → Save.
- [ ] **Active Research Rules** appears **in the same panel** (no separate nav item).
- [ ] Press **Edit** on the rule → it stays on this panel and repopulates description + duration.

### D2. Direct research assignment
RET Chair → **Target Assignment** → *Assign Research Targets to Faculty*.

- [ ] All regular faculty listed (no access gate).
- [ ] **Assign** on a *different* faculty → modal shows **Research only** → tick one → Save.
- [ ] Button shows a count badge.

### D3. Extension distribution — ⚠ one-time
Same panel → *Distribute Extension Targets to All Faculty*.

- [ ] There is **no checkbox** — every extension target is distributed. *(fixed)*
- [ ] Each extension target has qty / faculty, a **description**, and a **duration + unit**.
- [ ] Fill them in (e.g. qty `1`, `6 months`) → **Distribute** → confirm.
- [ ] Card flips to **Distributed & Locked**; inputs disabled; button gone.
- [ ] Refresh → still locked. *(Cannot be undone — see Reset appendix.)*

---

## Phase E — Faculty: view and submit

Log in as the **FACULTY** whose rank you configured in D1.

- [ ] **Research Menu** shows the rank's indicators.
- [ ] **Extension Targets** card is read-only, lock icon, "Assigned to all faculty".
- [ ] Research reads **"(optional) — up to: 0 / 1"**.
- [ ] **Submit is enabled with 0 research selected** *(research is optional)*.
- [ ] Selecting 1 locks the other (soft cap); unticking releases it.
- [ ] The **Teaching Load** target shows the hours you configured in A3 (e.g. 21).
- [ ] Select 1 research → **Submit IPCR for Review**.

**Assigned research:** log in as the faculty from D2.
- [ ] Their assigned research is **checked and disabled**, badged "Assigned by RET Chair".

**No research menu:** a faculty whose rank has no rules.
- [ ] Still sees the read-only **Extension** card.

---

## Phase F — Reviews and lock

### F1. RET review
- [ ] **Submitted Targets** shows selected Research **and** distributed Extension as
      **read-only rows** ("Distributed to all faculty", 🔒 Not editable).
- [ ] **Unselected Indicators** lists **Research only**.
- [ ] Approve.

> A faculty with no research should not appear in this queue at all.

### F2. Program Chair approval
- [ ] Research shows **Approved by RET Chair**; Extension also shows approved.
- [ ] **Approve IPCR** is enabled → Approve.

### F3. Faculty lock
- [ ] **Lock My IPCR** → committed targets include instruction/support, research,
      extension, and the teaching load.

---

## Phase G — Evidence and scoring

Faculty → **Evidence Gathering**.

### G1. Checklist
- [ ] **Actual Accomplishment** column shows the target sentence with blanks.
- [ ] Badge reads "Time to complete not reported".

### G2. Report a target
- [ ] **Accomplishment Details** card shows the composed sentence, "Completed in",
      the target duration for reference, and status radios.
- [ ] **No "Tag Co-Authors" section** anywhere in the modal.
- [ ] Upload a PDF with a quantity → Accomplished Qty updates.
- [ ] Enter **Completed in** = less than target (e.g. 4 of 6) → status **Completed** → Save.
- [ ] **Computed Rating** badges populate: Q · E · T → Average.
- [ ] The sentence now reads with real values.
- [ ] Selecting a non-Completed status **disables** the "Completed in" field.

**Timeliness spot-checks** (target 6 months):

| Completed in | RT | Expected T |
|---|---|---|
| 4 | .33 | **5** |
| 5 | .17 | **4** |
| 6 | .00 | **3** |
| *Partially completed at deadline* | — | **2** |
| *Not yet begun* | — | **1** |

**Quantity spot-checks** (target qty 10):

| Accomplished | RQn | Expected Q |
|---|---|---|
| 13+ | ≥1.30 | **5** |
| 12 | 1.20 | **4** |
| 10 | 1.00 | **3** |
| 6 | .60 | **2** |
| 5 | .50 | **1** |

### G3. Client Satisfaction
On the target you tagged in A7:
- [ ] Only that target's modal shows the **Client Satisfaction Rating** dropdown.
- [ ] Choosing *Very Satisfactory* → **E = 4**, sentence reads "…with Very Satisfactory rating."
- [ ] Other targets show **no** dropdown.

### G4. Research & Extension timeliness *(new)*
- [ ] The **research** target has a target duration (from D1) and can be scored — `T` is
      not `—` once you report "Completed in".
- [ ] The **extension** target likewise (from D3).

### G5. Summary of Ratings
- [ ] Panel lists each **real category name** with Weight % · Average · Weighted,
      then Total Overall, Final Weighted Rating, Adjectival Rating.
- [ ] Percentages match A6 (50 / 40 / 10).
- [ ] Adjectival matches: ≥4.75 Outstanding · ≥3.75 Very Satisfactory · ≥3.00 Satisfactory ·
      ≥2.01 Unsatisfactory · else Poor.

### G6. Submit evidences
- [ ] **Submit Evidences** → flash message includes the Final Weighted Rating and Adjectival Rating.
- [ ] **Uploading is now locked** — a notice replaces the upload form; existing files still viewable.
- [ ] Verify persisted:

```sql
SELECT f.emp_id, f.final_score, f.adjectival_rating,
       b.weight_group AS category, b.raw_avg, b.weight_pct, b.weighted_value
FROM tbl_final_scores f
LEFT JOIN tbl_final_score_breakdown b ON b.score_id = f.score_id
WHERE f.term_id = (SELECT term_id FROM tbl_academic_terms WHERE is_active = 1);
```

- [ ] One score row + one breakdown row per category; re-submitting does not duplicate.

---

## Phase H — Program Chair verification *(new)*

Program Chair → faculty evidence details modal.

- [ ] **Reported & Rating** column shows *Completed in 4 months of 6 months*, the Client
      Satisfaction rating where applicable, and Q · E · T · Avg badges.
- [ ] The **actual accomplishment sentence** shows under each target description.
- [ ] New **Status** column shows Approved / n Pending / n Returned / No evidence.
- [ ] **View Uploaded Evidence** opens **truly full-screen** (not half-width). *(fixed)*
- [ ] Each file has **Approve** and **Return** buttons.
- [ ] **Return** without a reason is refused; with a reason it saves and the reason displays.
- [ ] After returning, the file badge reads **Returned** and the buttons disappear.

**RET Chair — same controls** *(new)*:
- [ ] RET Chair → evidence details → **View Uploaded Evidence** is full-screen.
- [ ] Each research/extension file has **Approve** and **Return** buttons.
- [ ] Return requires a reason; the reason then displays on the item.

**Back as the Faculty:**
- [ ] The returned file shows **Returned** with the reason on hover.
- [ ] **Uploading is unlocked again** for that target.
- [ ] The returned file no longer counts toward the Accomplished Qty.

---

## Phase I — Designated Faculty

- [ ] Selection table columns are readable — the description no longer squeezes
      Target Qty and Deadline into squares. *(fixed)*
- [ ] Their selection form uses **duration number + unit**.
- [ ] "Add custom target" modal has **Target Duration** value + unit.
- [ ] The **Teaching Load** target shows the Designated hours from A3 (e.g. 10).
- [ ] Submit → **Dean** approves → targets committed with durations intact.
- [ ] Evidence Gathering shows the **Summary of Ratings** using the **Designated** weights
      (Strategic Priorities/Support Functions 75 · Core Functions 25) — *not* 50/40/10.
- [ ] The evidence modal has the **Accomplishment Details** card — composed sentence,
      "Completed in", completion status, and **Computed Rating** badges. *(fixed)*
- [ ] Saving those details persists and the badges update.

---

## Appendix — Known gaps

1. **Rank rules reset each term** by design; redo D1 for a new term.
2. **Extension distribution is permanent** for a term — no unlock in the UI.
3. **Legacy targets** set before the duration work score as un-timed (`T = —`).
4. The **return-reason prompt** is a plain browser dialog, not a styled modal.
5. `Adjectival` efficiency type is available but nothing uses it by default.
6. **Not yet covered by any run:** the faculty-side return checks in Phase H and the
   G6 SQL verification — worth picking up once returns are confirmed working.

## Appendix — Reset for a re-run

```sql
-- Replace 99 with the term you are resetting.
SET @t = 99;

DELETE b FROM tbl_final_score_breakdown b
  JOIN tbl_final_scores f ON b.score_id = f.score_id WHERE f.term_id = @t;
DELETE FROM tbl_final_scores              WHERE term_id = @t;
DELETE FROM tbl_ret_extension_distribution WHERE term_id = @t;  -- clears the one-time lock
DELETE FROM tbl_ret_assignments           WHERE term_id = @t;
DELETE FROM tbl_criteria_weights          WHERE term_id = @t;
DELETE FROM tbl_teaching_load_config      WHERE term_id = @t;

-- Review records
DELETE ri FROM tbl_ipcr_chair_review_items ri
  JOIN tbl_ipcr_chair_review r ON ri.review_id = r.review_id WHERE r.term_id = @t;
DELETE FROM tbl_ipcr_chair_review WHERE term_id = @t;
DELETE ri FROM tbl_ipcr_ret_review_items ri
  JOIN tbl_ipcr_ret_review r ON ri.review_id = r.review_id WHERE r.term_id = @t;
DELETE FROM tbl_ipcr_ret_review WHERE term_id = @t;
DELETE ri FROM tbl_ipcr_dean_review_items ri
  JOIN tbl_ipcr_dean_review r ON ri.review_id = r.review_id WHERE r.term_id = @t;
DELETE FROM tbl_ipcr_dean_review WHERE term_id = @t;

-- Target data (uploaded files on disk are not removed)
DELETE e FROM tbl_evidence_repo e JOIN tbl_committed_targets ct ON e.target_id = ct.target_id
  JOIN tbl_master_indicators mi ON ct.indicator_id = mi.indicator_id WHERE mi.term_id = @t;
DELETE ct FROM tbl_committed_targets ct
  JOIN tbl_master_indicators mi ON ct.indicator_id = mi.indicator_id WHERE mi.term_id = @t;
DELETE dt FROM tbl_draft_targets dt
  JOIN tbl_master_indicators mi ON dt.indicator_id = mi.indicator_id WHERE mi.term_id = @t;
DELETE da FROM tbl_draft_allocation da
  JOIN tbl_master_indicators mi ON da.indicator_id = mi.indicator_id WHERE mi.term_id = @t;
```

> Departments, criteria and IPCR categories are **not** term-scoped, so the reset leaves
> them intact — that is intentional.


