# End-to-End Test Script — Full System

Covers every role and every feature in the system. Phases run in order: each one sets up
what the next needs. Where a phase can be skipped, it says so.

**Legend:** `[ ]` not tested · `[/]` passed · `[*]` passed with a comment · `[-]` skipped
Add notes under any item as `:your comment`.

---

## Accounts you need

| Role (`system_role`) | Designation on the roster | Used in |
|---|---|---|
| ADMIN | `Admin` | 0, A, L, M |
| DEAN | `Dean` | 0, B, F, H, I, J, K, M |
| PROGRAM_CHAIR | `Program Chair` | 0, C, F, H, J, K, M |
| RET_CHAIR | `RET Chair` | 0, D, F, H, J, K, M |
| FACULTY | `Regular Faculty` | 0, E, F, G, K, M |
| DESIGNATED_FACULTY | `Designated Faculty` | 0, I, J, K, M |

You also need a **second Regular Faculty** (different person, same department) for the
permission checks in Phase M, and ideally a **second Program Chair** in another department.

> ### ⚠ Two different fields, easy to confuse
> `system_role` decides **which dashboard** you land on at login.
> `designation` decides **whether you have an IPCR of your own** and **which weight table**
> rates it. A Program Chair has both: role `PROGRAM_CHAIR` *and* designation `Program Chair`.
> If a chair's designation is wrong, their My IPCR silently will not appear.

> **Migrations required:** `MIGRATION_group7.sql` (the `is_admin_function` column **and** its
> backfill) and `MIGRATION_group8.sql` (rating period, institution settings, signatories,
> `print_remarks`). The collation-repair section of group 7 is optional and changes nothing.

---

## Coverage map

| Phase | What it covers |
|---|---|
| **0** | Login, logout, registration, bad credentials |
| **A** | Admin: term, departments, teaching load, printed-IPCR config, criteria, categories, weights, indicators |
| **B** | Dean: cascade quotas to departments / RET / College-Wide |
| **C** | Program Chair: distribute to faculty **and to chairs/Dean** |
| **D** | RET Chair: research menu, direct assignment, extension distribution |
| **E** | Regular Faculty: select and submit |
| **F** | RET review → PC review → return/resubmit → lock |
| **G** | Evidence upload, accomplishment reporting, Q/E/T scoring |
| **H** | Verification by Program Chair, RET Chair and Dean |
| **I** | Designated Faculty: full cycle including custom targets |
| **J** | Program Chair / RET Chair / Dean own IPCR |
| **K** | Print IPCR, both variants |
| **L** | Admin maintenance: roster, CSV import, backup, accounts |
| **M** | Permissions and security |

---

## Phase 0 — Login and accounts

- [ ] Each of the six accounts logs in and lands on **its own dashboard**.
- [ ] Wrong password is rejected with a message, and does **not** reveal whether the email exists.
- [ ] **Logout** returns to the login page; pressing Back does not restore the dashboard.
- [ ] Visiting a dashboard URL while logged out redirects to login.
- [ ] **Register** a new account → it is created as unapproved and **cannot log in** until
      an Admin approves it.

---

## Phase A — Admin setup

### A1. Open the term
Admin → **Term Configuration**.

- [ ] Form has Academic Year, Semester, Submission Deadline, and **Rating Period From / To**.
- [ ] Set the period (e.g. `2026-01-01` → `2026-06-30`) — Phase K prints
      *"for the period JANUARY to JUNE 2026"*.
- [ ] Open the term → it becomes active and **every other term is deactivated**.

A1 Comment/Suggestion/Question: What if we remove the deadline field from the form, seems redundant especially when we now have the correct data to collect for printing. 

### A2. Departments
Admin → **Institution Setup** → *Departments / Programs*.

- [ ] Seeded departments listed with codes and display order.
- [ ] **Add** `MST Program` / `MST` / order 50 → appears.
- [ ] **Edit** its code and order → persists.
- [ ] **Deactivate** it → greys out, Status reads Inactive, and it disappears from the
      Dean's cascade columns in Phase B.

> Renaming a department also renames it on the faculty roster and on existing quotas,
> because targets route by that name.

### A3. Teaching load
Same panel → *Teaching Load*.

- [ ] **Regular Faculty** shows `21` hours / `6` months; **Designated Faculty** shows `10` / `6`.
- [ ] Change Regular to `18` → Save → reopen → persisted.
- [ ] Switch to **Per academic rank**, fill Instructor only → Save → reopen → in per-rank
      mode, the "all ranks" row gone.
- [ ] Switch back to **Same for all ranks**, set `21` / `6 months`, Save. *(Leave it here.)*
- [ ] After saving, fields are **locked**; an **Edit** button unlocks them and Save returns.

### A4. Printed IPCR configuration
Same panel → *Printed IPCR*.

- [ ] **College Full Name** pre-filled; code reads `CICT`.
- [ ] Four blocks listed: Reviewed by · Approved by · Assessed by · Final Rating by.
- [ ] "Filled from" offers **A named person / Their Program Chair / The Dean**.
- [ ] Choosing a derived option **disables** the Name field.
- [ ] Enter the **Head of Office** name on *Approved by* and *Final Rating by* → Save → persists.
- [ ] Saving a *named person* block with an empty name is refused.
- [ ] **Self-heal:** if the signatory table is ever emptied, opening this panel recreates
      the five standard blocks; names already configured are left untouched.

### A5. Criteria (target types)
Admin → **Criteria**.

- [ ] Table shows slug / lane / core / order — **no Weight Group column**.
- [ ] **Add** `Innovation`, lane `CHAIR`, order 60, core ✓ → slug auto-generates as `innovation`.
- [ ] The form has an optional **Slug** field, with a note naming the built-in slugs the
      code matches on. Leaving it blank generates one from the name.
- [ ] **Edit** it — the name changes but the **slug stays fixed**.
- [ ] **Deactivate** it — the row dims but Edit / Activate stay clearly clickable.
- [ ] Reactivate it, or leave it inactive — either way it must not break Phase A7.

### A6. Category Management
Admin → Criteria → **Category Management**.

- [ ] **Regular Faculty**: Strategic Priorities (Instructions) · Core Functions (Research,
      Extension) · Support Functions.
- [ ] **Designated Faculty**: Strategic Priorities/Support Functions (Administrative,
      Support) · Core Functions (Instructions).
- [ ] **Edit** a category, change its target types → saves.
- [ ] **Add** a category for a designation → appears with the types you chose.

> The key behaviour: **Instructions belongs to a different category per designation** —
> Strategic Priorities for Regular, Core Functions for Designated.

### A7. Weight allocation
Admin → Criteria → **Weight Allocation by Rank**.

- [ ] Columns show **real category names**, not `instruction / ret / support`.
- [ ] **Regular Faculty**, General: `50` / `40` / `10`. Total badge turns green at 100, red at 90.
- [ ] Saving at 90% is **rejected** and stores nothing.
- [ ] Saving at 100% succeeds.
- [ ] **Designated Faculty**, General: `75` / `25` → saves independently; Regular still 50/40/10.
- [ ] Switch Regular to **Per Academic Rank**, fill Instructor at 100%, save, reopen →
      per-rank mode, General row gone.
- [ ] Switch back to **General**, re-enter 50/40/10, save. *(Leave it here.)*
- [ ] **Copy weights from previous term** brings the earlier term's values in.

### A8. Master indicators
Admin → **Master Indicators**.

- [ ] **Import from Previous Term** populates the pool (or add manually).
- [ ] Panel is grouped by **IPCR category**, mirroring the DPCR.
- [ ] Each category header has **Add Target**; it opens a modal with a **Target Type
      dropdown scoped to that category**.
- [ ] Add one under Core Functions → choose `Research` → lands under the right sub-heading.
- [ ] **Edit** an indicator's description and efficiency type → persists.
- [ ] **Delete** an indicator that has no targets against it → removed.
- [ ] An **Other Target Types** section exists for Administrative Functions.
- [ ] **Custom Target Items is NOT offered** as a category to file targets under.

**Set up for later phases:**
- [ ] Set one indicator to **Efficiency Type = Client Satisfaction** *(needed for G3)*.
- [ ] Create at least one **Administrative Functions** indicator *(needed for J2)*.

---

## Phase B — Dean: cascade quotas

Dean → **Quota Cascading**.

- [ ] Columns are generated from the **managed departments** plus `RET / Extension` and
      `College-Wide`. The department deactivated in A2 is **absent**.
- [ ] Fill quotas for your Faculty's department, for **RET / Extension**, and at least one
      **College-Wide**.
- [ ] Cascade an **Administrative Functions** target to a department *(feeds J2)*.
- [ ] Leave one target unallocated → press **Cascade Institutional Targets** → a
      confirmation modal appears and **blocks submission**, naming the unassigned target.
- [ ] Fill it → press again → modal shows the target count → **Confirm & Cascade**.
- [ ] Reopen: the saved quotas are still there.

> Record what you cascade to each department and to RET — phases C and J check those
> exact numbers reappear.

---

## Phase C — Program Chair: distribute targets

Program Chair → **Target Allocation**.

- [ ] The list shows the department's **Regular Faculty**.
- [ ] It **also shows the Dean, the Program Chair themselves, the RET Chair and any other
      designated faculty** in that department. *(fixed — they were missing entirely)*
- [ ] Each row has a **duration number + unit dropdown**, not free text.
- [ ] Fill quantity, duration (`6` + `months`) and a target description → Save.
- [ ] **Allocate instruction to the Dean, the Program Chair and the RET Chair** —
      Phase J checks these appear in their Core Functions.
- [ ] Reopen → values persist including the unit.
- [ ] Support-type targets are offered to **Regular Faculty only**, not to designated faculty.
- [ ] Re-saving after finalisation is blocked with a warning.

---

## Phase D — RET Chair

### D1. Research menu
RET Chair → **Menu Config**.

- [ ] Form is **Research-only** — no Extension fields.
- [ ] Each research indicator has an **IPCR description** and **duration + unit**, enabled
      only when its checkbox is ticked.
- [ ] Pick your Faculty's rank, Research Required = `1`, tick 2 indicators, fill their
      descriptions and durations → Save.
- [ ] **Active Research Rules** appears **in the same panel** (no separate nav item).
- [ ] **Edit** a rule → stays on this panel and repopulates description + duration.
- [ ] **Delete** a rule → removed, and the faculty of that rank no longer see a menu.
      *(Re-create it before Phase E.)*

### D2. Direct research assignment
RET Chair → **Target Assignment**.

- [ ] All regular faculty are listed.
- [ ] **Assign** on a *different* faculty → modal shows **Research only** → tick one → Save.
- [ ] The button shows a count badge.
- [ ] Reopen the editor → the assignment is still ticked.

### D3. Extension distribution — ⚠ one-time
Same panel → *Distribute Extension Targets to All Faculty*.

- [ ] There is **no checkbox** — every extension target is distributed.
- [ ] Each has qty / faculty, a **description**, and **duration + unit**.
- [ ] Fill them (`1`, `6 months`) → **Distribute** → confirm.
- [ ] Card flips to **Distributed & Locked**; inputs disabled; button gone.
- [ ] Refresh → still locked. *(Cannot be undone — see the Reset appendix.)*

---

## Phase E — Regular Faculty: select and submit

Log in as the FACULTY whose rank you configured in D1.

- [ ] **Research Menu** shows that rank's indicators.
- [ ] **Extension Targets** card is read-only with a lock icon.
- [ ] Research reads **"(optional) — up to: 0 / 1"**.
- [ ] **Submit is enabled with 0 research selected** *(research is optional)*.
- [ ] Selecting 1 locks the other; unticking releases it.
- [ ] The **Teaching Load** target shows the hours configured in A3 (e.g. 21).
- [ ] Instruction/support targets allocated in Phase C appear with their durations.
- [ ] Select 1 research → **Submit IPCR for Review**.
- [ ] After submitting, the selection is **read-only**.

**Assigned research** — log in as the faculty from D2:
- [ ] Their assigned research is **checked and disabled**, badged "Assigned by RET Chair".

**No research menu** — a faculty whose rank has no rule:
- [ ] Still sees the read-only **Extension** card, and can still submit.

---

## Phase F — Reviews, return, and lock

### F1. RET review
RET Chair → **Commitments**.

- [ ] **Submitted Targets** shows selected Research **and** distributed Extension as
      read-only rows ("Distributed to all faculty", 🔒 Not editable).
- [ ] **Unselected Indicators** lists **Research only**.
- [ ] Edit a reviewed quantity and add an item remark → Save → persists.
- [ ] **Approve**.

> A faculty with no research should not appear in this queue at all.

### F2. Program Chair review
Program Chair → **Commitments**.

- [ ] Research shows **Approved by RET Chair**; Extension shows approved.
- [ ] Edit a reviewed quantity + remark on one item → Save → persists.
- [ ] **Return** the IPCR with remarks → the faculty sees a *Returned* alert with them.

### F3. Faculty resubmit
Back as the faculty:
- [ ] The returned IPCR is **editable again**, and the chair's remarks are visible.
- [ ] Adjust and **resubmit** → returns to the chair's queue.

### F4. Approve and lock
- [ ] Program Chair **approves** → faculty sees approval.
- [ ] Faculty presses **Lock My IPCR** → committed targets include instruction/support,
      research, extension and the teaching load, with durations intact.
- [ ] After locking, the IPCR can no longer be edited.

---

## Phase G — Evidence and scoring

Faculty → **Evidence Gathering**.

### G1. Checklist
- [ ] **Actual Accomplishment** column shows the target sentence with blanks.
- [ ] Badge reads "Time to complete not reported".

### G2. Report a target
- [ ] **Accomplishment Details** card shows the composed sentence, "Completed in",
      the target duration for reference, and status radios.
- [ ] There is **no "Tag Co-Authors" section** anywhere in the modal.
- [ ] Upload a PDF with a quantity → **Accomplished Qty** updates.
- [ ] Upload a second file → quantity accumulates.
- [ ] **Delete** one of your own files → quantity drops back.
- [ ] Enter **Completed in** = 4 of 6 → status **Completed** → Save.
- [ ] **Computed Rating** badges populate: Q · E · T → Average.
- [ ] The sentence now reads with real values.
- [ ] Selecting a non-Completed status **disables** the "Completed in" field.
- [ ] Type a **Remarks** note (e.g. `Chairperson, BSDS`) → Save → reopen → still there.

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
On the indicator tagged in A8:
- [ ] Only that target's modal shows the **Client Satisfaction Rating** dropdown.
- [ ] *Very Satisfactory* → **E = 4**, sentence reads "…with Very Satisfactory rating."
- [ ] Other targets show **no** dropdown.

### G4. Research & Extension timeliness
- [ ] The **research** target has a duration (from D1) — `T` is not `—` once reported.
- [ ] The **extension** target likewise (from D3).

### G5. Summary of Ratings
- [ ] Lists each **real category name** with Weight % · Average · Weighted, then
      Total Overall → Final Weighted → Adjectival.
- [ ] Categories are in **I / II / III order**, not alphabetical.
- [ ] Percentages match A7 (50 / 40 / 10).
- [ ] Adjectival matches: ≥4.75 Outstanding · ≥3.75 Very Satisfactory · ≥3.00 Satisfactory ·
      ≥2.01 Unsatisfactory · else Poor.

### G6. Submit evidences
- [ ] **Submit Evidences** → flash message includes the Final Weighted Rating and Adjectival.
- [ ] **Uploading is now locked** — a notice replaces the form; existing files still viewable.
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

## Phase H — Verification

### H1. Program Chair
Program Chair → **Evidence Verification** → a faculty's details modal.

- [ ] **Reported & Rating** column shows *Completed in 4 months of 6 months*, the Client
      Satisfaction rating where applicable, and Q · E · T · Avg badges.
- [ ] The **actual accomplishment sentence** shows under each target description.
- [ ] **Status** column shows Approved / n Pending / n Returned / No evidence.
- [ ] **View Uploaded Evidence** opens **truly full-screen**, and the file renders.
- [ ] Each file has **Approve** and **Return**.
- [ ] **Return** without a reason is refused; with a reason it saves and displays.
- [ ] After deciding, that file's buttons disappear.

### H2. RET Chair
RET Chair → evidence details.

- [ ] Research/extension evidence is listed — the viewer is **not empty** when a count shows.
- [ ] Viewer opens full-screen; **Approve / Return** present and working.
- [ ] Return requires a reason; the reason displays on the item.

### H3. Faculty sees the return
- [ ] The returned file shows **Returned** with its reason.
- [ ] **Uploading is unlocked again** for that target only.
- [ ] The returned file no longer counts toward Accomplished Qty, and the rating updates.
- [ ] Re-upload and re-submit → back to Pending.

### H4. Dean
Dean → **Final Verification**.

- [ ] Faculty with submitted evidence are listed.
- [ ] Dean can open the evidence viewer and **Approve / Return** files.
- [ ] **Approve Package** → the faculty's targets become **Dean Approved**.
- [ ] **Return to Faculty** sends it back with remarks.

---

## Phase I — Designated Faculty (full cycle)

Log in as DESIGNATED_FACULTY.

- [ ] Selection table columns are readable — the description does not squeeze Target Qty
      and Deadline into squares.
- [ ] Selection uses **duration number + unit**.
- [ ] The **Teaching Load** target shows the *Designated* hours from A3 (e.g. 10).
- [ ] Instruction allocated by their Program Chair in Phase C appears under **Core Functions**.
- [ ] Targets picked from the pool land under **Strategic Priorities/Support Functions**.
- [ ] **Add custom target** modal has description, quantity and **Target Duration** value + unit.
- [ ] A custom target saves and appears under Strategic Priorities/Support Functions.
- [ ] **Submit** → the Dean sees it in **IPCR Draft Approval**.
- [ ] Dean edits a quantity, adds a remark, and **returns** it → designated faculty sees remarks.
- [ ] **Resubmit** → back to the Dean.
- [ ] Dean **approves** → designated faculty can **Lock** → targets committed with durations.
- [ ] Evidence Gathering has the **Accomplishment Details** card (sentence, Completed in,
      completion status, Client Satisfaction where applicable, Q·E·T badges).
- [ ] Saving those details persists and the badges update.
- [ ] **Summary of Ratings** uses the **Designated** weights (75 / 25) — *not* 50/40/10.

**Category split — the counts must match the two sections on My IPCR:**
- [ ] Count the targets in **1. Core Functions** and **2. Strategic Priorities & Support
      Functions** on the My IPCR page.
- [ ] The Summary of Ratings shows **those same two counts**.
- [ ] Only the **teaching load** and **Program-Chair-allocated instruction** are Core.
      Pool selections, custom items and oversight cascades are Strategic Priorities/Support
      — *even when their target type is Instruction*.
- [ ] Neither weighted category shows **0 targets** while the other holds them all.

---

## Phase J — Program Chair / RET Chair / Dean own IPCR

Run after B and C so there are cascades and allocations to pick up.

### J1. Access and navigation
- [ ] As **PROGRAM_CHAIR**: sidebar shows **My Performance → My IPCR**.
- [ ] It opens **with your Program Chair navigation still present**.
- [ ] Clicking one of those items returns you to your dashboard **on that exact section**.
- [ ] Same for **RET_CHAIR** and **DEAN**, each showing their own items.
- [ ] Regular **FACULTY** has **no** My IPCR item.
- [ ] **ADMIN** has none, and `/designated/` directly is refused.

### J2. Core Functions — the instruction they were allocated
- [ ] **Program Chair**: the instruction allocated to them in Phase C appears under
      **Core Functions**, with the mandatory teaching load. *(fixed)*
- [ ] **RET Chair**: same.
- [ ] **Dean**: same.
- [ ] Quantities and durations match what the Program Chair entered.

### J3. Strategic Priorities/Support — oversight cascades
- [ ] **Program Chair**: pre-filled with **every** target the Dean cascaded to their
      department, at **full quota** (cascade `5` to WST → the WST chair reads **5**).
- [ ] Rows are **editable**, not locked.
- [ ] **RET Chair**: pre-filled with everything cascaded to **RET / Extension**, full quantity.
- [ ] **Dean**: **no auto-selected targets at all** — the section starts empty.
- [ ] All of them can still add from the selectable pool.

### J4. Claimed targets are not selectable
- [ ] A target cascaded to a department or to RET does **not** appear in the pool anyone
      can select from.
- [ ] Another Designated Faculty sees only unclaimed instruction/support targets.

### J5. The same indicator, both ways
- [ ] A chair may hold one indicator **twice** — the oversight copy (full quota) and their
      own allocated teaching work.
- [ ] In Summary of Ratings the oversight copy sits under **Strategic Priorities/Support
      (75%)** and the personal copy under **Core Functions (25%)**.

### J6. Dean sees the chairs
- [ ] Dean → **Target Assignment** lists Program Chairs and the RET Chair among designated
      faculty.
- [ ] Assign a **College-Wide** target to one of them → it appears on their IPCR.

### J7. Full cycle
- [ ] A chair submits their own IPCR → Dean reviews → approves → chair locks.
- [ ] The chair's Summary of Ratings shows both categories populated.

---

## Phase K — Print IPCR

Run after G (ratings exist) and A4 (signatories set).

### K1. Regular Faculty
Faculty → **Print IPCR** (new tab).

- [ ] Title reads **INDIVIDUAL PERFORMANCE COMMITMENT AND REVIEW (IPCR)**.
- [ ] Opening: *"I, NAME, faculty member of the College of Information and Communications
      Technology, … for the period JANUARY to JUNE 2026."*
- [ ] First column header is **MFO/PAP**.
- [ ] Sections: **I. Strategic Priorities (50%) · II. Core Functions (40%) ·
      III. Support Functions (10%)**.
- [ ] Under Core Functions: **A. Research** then **B. Extension…**, in that order.
- [ ] Rating columns **Q¹ E² T³ A⁴** match the badges on the evidence panel.
- [ ] **Final Average Rating** row present.
- [ ] Summary box in **I / II / III** order, then Total Overall → Final Weighted →
      **Adjectival Rating inside the box**.
- [ ] Legend and the **Discussed with / Assessed by / Final Rating by** footer.
- [ ] Signature names match A4 — Reviewed by is **their Program Chair**.

### K2. Designated Faculty and chairs
- [ ] First column header is **Output**.
- [ ] A Program Chair's opening reads *"Program Chairperson of the … program of the …"*.
- [ ] Sections: **I. Strategic Priorities/Support Functions (75%) · II. Core Functions (25%)**.
- [ ] Sub-section under I is **A. Administrative Functions**.
- [ ] Summary box uses **75 / 25**.
- [ ] Reviewed by is **the Dean**, per A4.

### K3. Remarks
- [ ] The note typed in G2 appears in the **Remarks** column against that target.
- [ ] Clearing it leaves the column blank, not whitespace.

### K4. Draft vs final
- [ ] Before Dean approval, a red **DRAFT** banner appears.
- [ ] After Dean approval, the banner is gone.
- [ ] A faculty who has not locked is redirected with *"No committed IPCR to print yet."*

### K5. Print settings
Press **Print / Save as PDF** → **More settings**:

- [ ] Paper **Letter 8.5 × 11**, Layout **Landscape**, Scale **100**.
- [ ] An outer **border frames the whole form** on every page.
- [ ] Toolbar buttons do **not** print.
- [ ] Text legible at 100%, no clipped columns.

> A typical form runs to **2 sheets** — targets on page 1, summary and signatures on page 2.
> That is expected; the sample IPCR runs to 3.

---

## Phase L — Admin maintenance

### L1. Faculty roster
Admin → **HR Roster**.

- [ ] **Add** a faculty profile with all fields → appears in the list.
- [ ] **Edit** their rank, department and **designation** → persists.
- [ ] **Deactivate** a profile → they no longer appear in allocation or assignment lists.
- [ ] Changing a designation from `Regular Faculty` to `Program Chair` gives that person a
      **My IPCR** item next login.

### L2. CSV import
- [ ] Import a CSV of profiles → rows are created.
- [ ] A malformed row is reported rather than silently skipped.
- [ ] Re-importing the same file does not duplicate people.

### L3. Backup
- [ ] **Backup** downloads a `.sql` file.
- [ ] The file contains `INSERT` statements for the main tables and is not empty.

### L4. Account security
Admin → **System Security**.

- [ ] **Reset password** for a user → they can log in with the new one.
- [ ] **Lock account** → that user is refused at login with a clear message.
- [ ] Unlock → they can log in again.
- [ ] **Audit log** shows the term opening, password reset and lock actions.

---

## Phase M — Permissions and security

Each of these should be **refused**. They are the checks that matter most.

### M1. Cross-role access
- [ ] A **Regular Faculty** opening `/admin/`, `/dean/`, `/prog_chair/`, `/ret_chair/` → refused.
- [ ] A **Program Chair** opening `/admin/` or `/dean/` → refused.
- [ ] **ADMIN** opening `/designated/` → refused (Admin has no IPCR).
- [ ] A **Regular Faculty** opening `/designated/` → refused (they use `/faculty/`).

### M2. Cross-user data
- [ ] Faculty A **cannot delete** Faculty B's evidence. *(fixed — was possible)*
- [ ] Faculty A **cannot view** Faculty B's evidence file via its URL.
- [ ] Faculty A **cannot save accomplishment details** against Faculty B's target.
- [ ] A Program Chair sees only **their own department's** faculty.
- [ ] A Program Chair of WST cannot review a DST faculty's IPCR.

### M3. Workflow guards
- [ ] A faculty cannot submit evidence before their IPCR is locked.
- [ ] A faculty cannot upload after submitting evidences (until something is returned).
- [ ] A locked IPCR cannot be edited.
- [ ] Extension distribution cannot be run twice.

---

## Appendix — Known gaps

1. **Rank rules reset each term** by design; redo D1 for a new term.
2. **Extension distribution is permanent** for a term — no unlock in the UI.
3. **Legacy targets** set before the duration work score as un-timed (`T = —`).
4. The **return-reason prompt** is a plain browser dialog, not a styled modal.
5. `Adjectival` efficiency type exists but nothing uses it by default.
6. **Signatory rules are unconfirmed** for two cases: who reviews the Dean's own IPCR, and
   a non-chair designated faculty's. The latter resolves to the Dean. Editable in A4.
7. **A weighted category with no targets contributes nothing**, deflating the final rating
   rather than renormalising. The case that surfaced this was a categorisation bug, since
   fixed; no gate was built.
8. **Eight tables carry a different collation** from the original schema. Harmless today;
   the repair is in `MIGRATION_group7.sql`.
9. **Export DPCR was removed** (adviser's call). Print IPCR is the only document output.
10. **Four unscoped deletes** in the submit paths remove draft targets from *earlier* terms.
    No current-term behaviour is affected and committed targets are untouched, but
    historical drafts are lost on resubmit.
11. **Co-author routes are dead** — `claim_evidence`, `unclaim_evidence`,
    `eligible_co_authors`, `unclaimed_co_authored_evidence` are reachable but no template
    references them, since co-author tagging was removed.
12. **108 evidence PDFs are tracked in git.** They are runtime uploads and will keep
    accumulating; `app/uploads/evidence/` should be gitignored and untracked.

---

## Appendix — Starting from a clean database

To run the whole script against empty data, use
[`old MDS/RESET_for_clean_test.sql`](old%20MDS/RESET_for_clean_test.sql). It clears every
term, target, evidence file, review and score, and keeps what the system cannot rebuild.

**Three things must survive a truncate:**

| Keep | Why |
|---|---|
| `tbl_employee_profiles`, `tbl_auth_credentials`, `tbl_system_access` | Registration *claims* an existing profile via a stored procedure, so clearing these locks everyone out — **unless** you then run `python bootstrap_admin.py`, which writes the first Admin directly. With that, even a fully empty database is recoverable. |
| `tbl_target_categories` | 23 places in the code match exact slugs (`instruction`, `research`, …). Rebuildable — Admin → Criteria now has a **Slug** field — but a generated slug like `a_instructions` breaks routing **silently**, so it has to be typed exactly. |

`tbl_ipcr_signatories` is now **self-healing**: opening Institution Setup recreates the five
standard blocks if they are missing, without disturbing any already configured. Only the
names need re-entering.

- [ ] After the reset, confirm config survived: target types, IPCR categories, signatories,
      departments and employee profiles all still return rows.
- [ ] Delete orphaned files in `app/uploads/evidence/` if you want a genuinely clean state.
- [ ] Phase 0 still passes — accounts were preserved.

**Starting with no accounts at all** (optional, the harshest reset):
- [ ] Truncate the three account tables as well, then run `python bootstrap_admin.py`.
- [ ] The script **refuses** if an Admin already exists, unless given `--force`.
- [ ] It rejects a weak password, a duplicate employee ID and a duplicate email.
- [ ] The created Admin can log in, and lands on the Admin dashboard.
- [ ] From there, add profiles (Phase L) so everyone else can claim theirs at `/register`.

---

## Appendix — Reset a single term (keeps other terms intact)

```sql
-- Replace 99 with the term you are resetting.
SET @t = 99;

DELETE b FROM tbl_final_score_breakdown b
  JOIN tbl_final_scores f ON b.score_id = f.score_id WHERE f.term_id = @t;
DELETE FROM tbl_final_scores               WHERE term_id = @t;
DELETE FROM tbl_ret_extension_distribution WHERE term_id = @t;  -- clears the one-time lock
DELETE FROM tbl_ret_assignments            WHERE term_id = @t;
DELETE FROM tbl_criteria_weights           WHERE term_id = @t;
DELETE FROM tbl_teaching_load_config       WHERE term_id = @t;

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

> Departments, criteria, IPCR categories, institution settings and signatories are **not**
> term-scoped, so the reset leaves them intact — that is intentional.

> Clearing the target tables also clears the chairs' own IPCRs, including their oversight
> rows. Those repopulate from `tbl_cascaded_quotas` as soon as the chair reopens My IPCR,
> so Phase B need not be redone.
