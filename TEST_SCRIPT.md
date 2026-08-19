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

> **Two different fields, easy to confuse.** `system_role` decides which dashboard someone
> logs into. `designation` (their job title, on the Admin roster) decides whether they have
> an IPCR of their own and which weight table rates it. A Program Chair has both: role
> `PROGRAM_CHAIR` *and* designation `Program Chair`. For Phase J, check the roster has the
> right **designation** on each chair and on the Dean, or their My IPCR will not appear.

> Passwords are bcrypt-hashed. If you don't know one, log in as ADMIN →
> System Security → Reset Password.

### 🔁 Changed since the last run — retest these first

**Fixes to what you reported:**

| Where | What changed |
|---|---|
| **A3** | Teaching load **locks after saving**; an **Edit** button unlocks it |
| **D3** | Extension **checkbox removed** — all extension targets distribute |
| **H** | Evidence viewer is now **truly full-width** in *both* Program Chair and RET Chair (each template had its own `50vw` rule) |
| **H** | **RET Chair gained Approve / Return buttons** — they were missing entirely |
| **H** | RET Chair's viewer said *"No evidence files available"* despite a count — the lookup table was declared but never filled |
| **H** | Evidence data no longer sits inside an HTML attribute, where an apostrophe in a return reason broke the buttons |
| **I** | Designated **Evidence Gathering** has the Accomplishment Details card |
| **I** | Selection table column widths rebalanced |

**New — Phase J:** Program Chair, RET Chair and Dean now have their own IPCR.

| What | Detail |
|---|---|
| Own IPCR | Their **designation** (job title) decides they have one; previously only `system_role = DESIGNATED_FACULTY` could reach it, so chairs were locked out entirely |
| Correct weights | `'Program Chair'` / `'RET Chair'` / `'Dean'` matched neither weight table, so their IPCR could not be scored at all. All now rate against **Designated Faculty (75/25)** |
| Oversight targets | A chair's IPCR auto-fills with their department's (or RET's) cascaded quotas at **full quantity** |
| Navigation | Opening My IPCR **keeps your own sidebar**; its items link back to the section you came from |
| Category fix | A designated faculty's self-selected targets were counted as **Core Functions**. Only the teaching load and Program-Chair-allocated instruction are Core; everything else is **Strategic Priorities/Support** |

**New — Phase K:** the IPCR can now be printed.

| What | Detail |
|---|---|
| Print IPCR | Replaces the "coming soon" placeholder. Renders the real form — Regular and Designated variants differ in column header, opening sentence, categories and weights |
| Config | Admin → Institution Setup → **Printed IPCR** sets the college name and who signs each block; Term Configuration gains a **rating period** |
| Remarks | A free-text note per target, entered on the evidence modal, printed in the form's Remarks column |
| Category order fix | The Summary of Ratings listed categories **alphabetically**. Now I / II / III order — this affected the dashboards too, not only the printed form |

> Needs [`old MDS/MIGRATION_group7.sql`](old%20MDS/MIGRATION_group7.sql) (the `is_admin_function`
> columns **and** the backfill) and [`old MDS/MIGRATION_group8.sql`](old%20MDS/MIGRATION_group8.sql)
> (rating period, institution settings, signatories, `print_remarks`). The collation-repair
> section of group 7 is optional cleanup and changes no behaviour.

---

## Phase A — Admin setup

### A1. Open the new term
Admin → **Term Configuration** → set Academic Year, Semester, Deadline → Open Term.

- [ ] The form has **Rating Period From / To** alongside the deadline.
- [ ] Set them (e.g. `2026-01-01` to `2026-06-30`) — the printed IPCR header reads
      *"for the period JANUARY to JUNE 2026"*. Leaving them blank prints a blank.
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

### A3b. Institution Setup — Printed IPCR *(new)*
Same panel → *Printed IPCR*.

- [ ] **College Full Name** is pre-filled with *College of Information and Communications
      Technology*; the code reads `CICT`.
- [ ] Four signature blocks are listed: **Reviewed by · Approved by · Assessed by ·
      Final Rating by**.
- [ ] "Filled from" offers **A named person / Their Program Chair / The Dean**.
- [ ] Choosing a derived option **disables** the Name field — those follow the roster.
- [ ] Type the real **Head of Office** name on *Approved by* and *Final Rating by* → Save →
      reopen and confirm both persisted.
- [ ] Saving a *named person* block with an empty name is refused.

> Blocks with no name render blank on the printed form, exactly as the paper version is
> issued. Fill these in before Phase K or the signature lines will be empty.

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

- [ ] Note what you cascade to each department and to RET — Phase J checks those exact
      numbers reappear on the matching chair's own IPCR.

> Skipping this leaves the Program Chair's distribution table and the RET Chair's
> Research/Extension lists empty — and leaves both chairs' own IPCRs empty too.

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
- [ ] A **Remarks** field is present *(new)*. Type a short note (e.g. `Chairperson, BSDS`)
      → Save → reopen the modal and confirm it is still there. Phase K checks it prints.

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

**Category split — the counts must match the two sections on My IPCR** *(fixed)*:
- [ ] Count the targets in **1. Core Functions** and in **2. Strategic Priorities & Support
      Functions** on the My IPCR page.
- [ ] The **Summary of Ratings** shows those same two counts. A target sitting in section 2
      must **not** be counted under Core Functions.
- [ ] Only the **teaching load** and **Program-Chair-allocated instruction** are Core.
      Anything selected from the pool, any custom item, and any oversight cascade is
      Strategic Priorities/Support — *even when its target type is Instruction*.
- [ ] Neither weighted category shows **0 targets** while the other holds them all.
- [ ] The Adjectival Rating is believable — an IPCR with good ratings should not read *Poor*
      because one category was left empty.
- [ ] The evidence modal has the **Accomplishment Details** card — composed sentence,
      "Completed in", completion status, and **Computed Rating** badges. *(fixed)*
- [ ] Saving those details persists and the badges update.

---

## Phase J — Chairs' and Dean's own IPCR *(new)*

Everyone who is not Regular Faculty is rated as **Designated Faculty**, whichever dashboard
they log into. Run this after Phase B so there are cascaded quotas to pick up.

### J1. Access and navigation
- [ ] As **PROGRAM_CHAIR**: sidebar shows **My Performance → My IPCR**.
- [ ] Clicking it opens the IPCR page **with your Program Chair navigation still present**
      (Target Allocation · Commitments · Grading Engine · Evidence Verification).
- [ ] Clicking one of those returns you to your dashboard **on that exact section**.
- [ ] Same for **RET_CHAIR** and **DEAN**, each showing their own items.
- [ ] Regular **FACULTY** has **no** My IPCR item — they use their own dashboard.
- [ ] **ADMIN** has none either, and visiting `/designated/` directly is refused.

### J2. Oversight targets — Program Chair
The chair answers for their department's whole cascaded number, while separately dividing
that same number among their faculty.

- [ ] Their **Strategic Priorities/Support Functions** section is pre-filled with **every**
      target the Dean cascaded to their department — instruction, support, administrative alike.
- [ ] Quantities are the **full quota**, not a share: cascade `Instruction 1 = 5` to WST in
      Phase B and the WST chair's IPCR reads **5**.
- [ ] Those rows are **editable**, not locked.
- [ ] A chair whose department received nothing sees none.

### J3. Oversight targets — RET Chair
- [ ] Pre-filled with everything cascaded to **RET / Extension**, at full quantity.

### J4. Dean
- [ ] **No auto-selected targets at all** — the section starts empty.
- [ ] Can still add targets from the selectable pool.

### J5. Claimed targets are not selectable
- [ ] A target cascaded to a department or to RET does **not** appear in the pool anyone can
      select from — it already has an owner.
- [ ] Another Designated Faculty sees only unclaimed instruction/support targets.
- [ ] Compare: the pool should be visibly shorter than the full indicator list.

### J6. The same indicator, both ways
- [ ] A chair may hold one indicator **twice** — the oversight copy (full quota) and their
      own allocated teaching work.
- [ ] In **Summary of Ratings** the oversight copy sits under **Strategic Priorities/Support
      Functions (75%)** and the personal copy under **Core Functions (25%)**.
- [ ] The **Teaching Load** target shows the *Designated* hours from A3 (e.g. 10), not 21.
- [ ] Run the **category split** checks from Phase I here too — the same rule decides which
      of a chair's targets are Core and which are Strategic.

### J7. Dean can see the chairs
- [ ] Dean → **Target Assignment** lists Program Chairs and the RET Chair among designated
      faculty. They were filtered out before, so the Dean could not assign to them at all.

---

## Phase K — Print IPCR *(new)*

Run after Phase G so there are ratings to print, and after **A3b** so the signatories are set.

### K1. Regular Faculty
Faculty → **Print IPCR** (opens in a new tab).

- [ ] The button opens the form — it no longer shows "coming soon".
- [ ] Title reads **INDIVIDUAL PERFORMANCE COMMITMENT AND REVIEW (IPCR)**.
- [ ] Opening sentence: *"I, NAME, faculty member of the College of Information and
      Communications Technology, … for the period JANUARY to JUNE 2026."*
- [ ] First column header is **MFO/PAP**.
- [ ] Sections in order: **I. Strategic Priorities (50%) · II. Core Functions (40%) ·
      III. Support Functions (10%)**.
- [ ] Sub-sections under Core Functions read **A. Research** then **B. Extension…** —
      not reversed, not alphabetical.
- [ ] Rating columns are **Q¹ E² T³ A⁴** and match the badges on your evidence panel.
- [ ] **Final Average Rating** row is present.
- [ ] Summary box lists the categories in **I / II / III** order with their weights,
      then Total Overall → Final Weighted → **Adjectival Rating inside the box**.
- [ ] Legend, and the **Discussed with / Assessed by / Final Rating by** footer.
- [ ] Signature names match what you set in A3b.

### K2. Designated Faculty
Designated Faculty (or a chair via **My IPCR → Print IPCR**).

- [ ] First column header is **Output**, not MFO/PAP.
- [ ] Opening sentence names their role — a Program Chair reads *"Program Chairperson of
      the BSDS program of the…"*.
- [ ] Sections: **I. Strategic Priorities/Support Functions (75%) · II. Core Functions (25%)**.
- [ ] Sub-section under I is **A. Administrative Functions**.
- [ ] Summary box uses **75 / 25**, not 50/40/10.

### K3. Remarks
- [ ] The note typed in G2 appears in the **Remarks** column against that target.
- [ ] Clearing it and saving leaves the column blank (not whitespace).

### K4. Draft vs final
- [ ] Before the Dean approves, a red **DRAFT** banner appears at the top.
- [ ] After **Dean approval**, the banner is gone.
- [ ] A faculty who has not locked their IPCR is redirected with
      *"No committed IPCR to print yet — lock your IPCR first."*

### K5. Print settings
Press **Print / Save as PDF**, then check **More settings**:

- [ ] Paper size **Letter 8.5 × 11**, Layout **Landscape**, Scale **100**.
- [ ] An outer **border frames the whole form** on every page.
- [ ] The toolbar buttons do **not** appear on the printed page.
- [ ] Text is legible at 100% — no clipped columns.

> A typical form runs to **2 sheets**: the targets fill page 1, the summary box and
> signature footer take page 2. That is expected — the sample IPCR runs to 3.

---

## Appendix — Known gaps

1. **Rank rules reset each term** by design; redo D1 for a new term.
2. **Extension distribution is permanent** for a term — no unlock in the UI.
3. **Legacy targets** set before the duration work score as un-timed (`T = —`).
4. The **return-reason prompt** is a plain browser dialog, not a styled modal.
5. `Adjectival` efficiency type is available but nothing uses it by default.
6. **Not yet covered by any run:** the faculty-side return checks in Phase H and the
   G6 SQL verification — worth picking up once returns are confirmed working.
7. **The Dean's own oversight set is intentionally empty** (J4). If the Dean should carry
   College-Wide quotas on their own IPCR, that is not built.
8. **A weighted category with no targets contributes nothing**, which deflates the final
   rating rather than renormalising. The case that surfaced this turned out to be the
   categorisation bug above, not a policy problem — so no gate was built. If a genuinely
   empty category ever appears, that decision is still open.
9. **Eight tables carry a different collation** from the original schema (a defect in the
   earlier migrations). Harmless today; the repair is in `MIGRATION_group7.sql`.
10. **Signatory rules are unconfirmed for two cases**: who reviews the Dean's own IPCR, and
    a non-chair designated faculty's. The latter currently inherits the Designated row and
    resolves to the Dean. Both are editable in A3b.
11. **Export DPCR has been removed** from the Dean dashboard (adviser's call — the system
    no longer needs it). Its template file had already been deleted, so the button was
    broken anyway. Print IPCR is now the system's only document output.

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

> Clearing `tbl_draft_targets` and `tbl_committed_targets` also clears the chairs' own IPCRs,
> including their oversight rows. Those repopulate from `tbl_cascaded_quotas` as soon as the
> chair reopens My IPCR, so re-running Phase B is not required.


