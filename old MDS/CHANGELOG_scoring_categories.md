# Changelog — Scoring Engine, Evidence Verification & Category Management

Detailed record of the changeset that adds the weighted SPMS scoring pipeline,
makes uploaded evidence verifiable, and promotes the IPCR category into a
first-class per-designation entity.

Companion documents:
- [`POST_TEST_PLAN.md`](POST_TEST_PLAN.md) — the findings this work addresses
- [`DYNAMIC_CRITERIA.md`](DYNAMIC_CRITERIA.md) — the criteria/weights track
- [`RET_REDESIGN.md`](RET_REDESIGN.md) — the RET workflow redesign
- [`../TEST_SCRIPT.md`](../TEST_SCRIPT.md) — the annotated end-to-end test run

---

## 1. Scoring engine

New module: [`app/models/scoring.py`](../app/models/scoring.py)

### Structured target durations
Timeliness is `RT = 1 − (Actual T / Target T)`, which needs the target duration as
a **number plus a unit** — not the free text `target_deadline` historically held
(values like `'10'` and `'1 Semester'`, the latter being undividable).

`target_duration_value` + `target_duration_unit` now flow through every hop:

| Hop | Where |
|---|---|
| PC form → allocation | `routes/prog_chair.py`, `models/prog_chair.py` |
| allocation → draft targets | `models/faculty.py` (`submit_faculty_ipcr`) |
| draft → committed (regular) | `models/prog_chair.py` (`lock_and_commit_ipcr`) |
| designated form → draft | `routes/designated.py`, `models/designated.py` |
| draft → committed (designated) | `models/dean.py` |

`target_deadline` is still written, but now **derived** from the structured pair via
`format_duration()`, so every existing deadline display keeps working untouched.

### Actual Accomplishment composer
The printed IPCR renders the accomplishment as the target sentence with three slots
filled — quantity, duration, and (where the target names one) the efficiency rating:

> Target: "**6** report of grades … submitted **10 days** after the Final Examination."
> Actual: "**5** report of grades … submitted **8 days** after the Final Examination."

`build_actual_accomplishment()` substitutes those slots, rendering blanks for values
not yet reported (mirroring how the paper form is issued). Descriptive adverbs such
as *"accurately"* are retained; only the **rating word** is blanked, matching the
sample forms.

Best-effort by design — target descriptions are free text, so unusual phrasing leaves
a slot unsubstituted rather than guessing. Legacy targets with no structured unit fall
back to the unit written in their own sentence.

### Rating scales (per the NEUST guide)

```
Q:  RQn = actual_quantity / assigned_quantity
    ≥1.30→5 · 1.15–1.29→4 · 1.00–1.14→3 · .51–.99→2 · ≤.50→1

E:  Client Satisfaction → the reported rating (Excellent 5 … Poor 1)
    Adjectival          → 5 when the target is achieved
    otherwise           → derived from RQn (achieved→5 · .51–.99→2 · ≤.50→1)

T:  RT = 1 − (Actual T / Target T)
    ≥.30→5 · .15–.29→4 · .00–.14→3
    Partially completed at deadline→2 · Not yet begun→1

A = (Q + E + T) / 3
```

Only **Client Satisfaction** requires faculty input; the other two are derived.

### Roll-up
Per-target average → per-category average → × the category's weight →
**Final Weighted Rating** → adjectival band (4.75–5.00 Outstanding · 3.75–4.74 Very
Satisfactory · 3.00–3.74 Satisfactory · 2.01–2.99 Unsatisfactory · 1.00–2.00 Poor).

Persisted to `tbl_final_scores` + `tbl_final_score_breakdown` when the faculty submits
evidences for verification — that snapshot is what the Dean approves, and it preserves
the weights in force at the time.

### ⚠ Rounding bug fixed
Python's built-in `round()` is **banker's rounding on a binary float**:
`round(2.275, 2)` → `2.27`, where the printed form gives `2.28`. Left alone, computed
ratings would have silently disagreed with hand-computed IPCRs.

All score rounding now goes through `round2()` (Decimal, `ROUND_HALF_UP`). The guide's
own worked summary reproduces exactly: `4.55×50% + 3.89×40% + 4.60×10% = 4.30`,
Very Satisfactory — note the guide rounds **each weighted row** before summing.

Verified against all three worked examples (guide pp. 19, 21, 24) and every adjectival
band boundary (p. 27).

---

## 2. Evidence verification

### The gap
`verification_status` was written as `'Pending'` on upload and **never updated**. The
Verified/Rejected badges rendered but nothing could set them, and the
`!= 'Rejected'` filter in `recalculate_target_accomplished_quantity` was dead code —
every uploaded file counted toward Quantity permanently, unreviewed.

Worse, the vocabulary disagreed: faculty/designated templates checked `'Approved'`
while prog_chair/ret_chair checked `'Verified'`. Both branches were unreachable.

### The fix
Standardised on **Pending / Approved / Returned**, and made the transition real:

- `set_evidence_verification()` in `models/faculty.py` — validates the status,
  **requires a reason when returning** (stored in `supervisor_comment`), and
  recalculates the accomplished quantity.
- Returning **unlocks the target** (`Submitted` → `Approved`) so the faculty member
  can upload a replacement.
- Both quantity queries now exclude `Returned` evidence, which makes the previously
  dead filter meaningful.
- Endpoints for both verifiers: `POST /prog_chair/verify_evidence` and
  `POST /ret_chair/verify_evidence` (RET needs its own — research/extension evidence
  is only visible there).

### UI
- **Status** column in the Program Chair's target table, aggregating each target's
  evidence (`Approved` / `n Pending` / `n Returned` / `No evidence` / `RET Sector`).
- **Approve** / **Return** per evidence file in the viewer; the reason displays back
  on the item. Buttons hide once decided.
- Faculty uploads lock behind a notice once evidences are submitted; viewing remains.

---

## 3. Category management

### The modeling defect
What the schema called `tbl_target_categories` is actually **target types**
(Instruction, Research, Extension, Support, Custom). The real IPCR **categories** —
the rows carrying weight on the printed form — were faked by a hardcoded
`weight_group` column.

That column holds **one value per target type**, so it physically could not express
the actual rule, because the same type maps to a different category per designation:

| Target type | Regular Faculty | Designated Faculty |
|---|---|---|
| Instruction | **Strategic Priorities** (50%) | **Core Functions** (25%) |
| Research / Extension | **Core Functions** (40%) | — |
| Support | **Support Functions** (10%) | — |
| Administrative | — | **Strategic Priorities/Support Functions** (75%) |

The Designated weights that appeared to work earlier only did so because the label
`instruction` was reusable as a bucket name — semantically it was wrong.

### The fix
```sql
tbl_ipcr_categories(ipcr_category_id, designation_type, category_name,
                    display_order, is_active)
tbl_ipcr_category_types(ipcr_category_id, category_id)   -- target types per category
```

- `tbl_criteria_weights.weight_group` → `ipcr_category_id`; existing rows were
  **migrated, not cleared**.
- `tbl_target_categories.weight_group` dropped.
- `tbl_final_score_breakdown.weight_group` keeps storing the category **name** as a
  text snapshot, so historical ratings survive later renames.
- New **Administrative Functions** target type for Designated faculty.

### UI
- **Category Management** panel — per designation, create/order categories and assign
  which target types belong to each.
- **Weight Allocation** matrix columns now read *Strategic Priorities / Core Functions
  / Support Functions* instead of `instruction / ret / support`.
- **Master Indicators** regrouped to mirror the DPCR the Dean actually receives:

```
I.   Strategic Priorities  →  A. Instruction                 → indicators
II.  Core Functions        →  A. Research                    → indicators
                              B. Extension Services/Training → indicators
III. Support Functions     →  (indicators directly)
```

  **Add Target** sits on the category header, with a target-type dropdown scoped to
  that category. An *Other Target Types* section catches types outside the DPCR
  structure (currently Administrative Functions) so they remain manageable.

---

## 4. Research targets

Research targets previously carried **no description and no duration**, so Timeliness
could never be computed for them — every research target scored `T = —`, dragging the
Core Functions average.

`tbl_ret_rule_indicators` gained `target_description`, `target_duration_value` and
`target_duration_unit`. The RET Chair sets both per indicator in Menu Config, and the
submit pipeline writes them onto the draft target. Chair-**assigned** research inherits
the same values so it scores identically to a self-selected one.

---

## 5. UI fixes from the test run

| Fix | Reason |
|---|---|
| Indicator category dropdowns exclude non-core types | Only Designated faculty create custom targets; Admin cascades DPCR targets |
| Inactive criteria rows no longer grey out their action buttons | They still worked but looked disabled |
| RET Chair's Active Rules merged into Menu Config | Editing a rule bounced the user between panels |
| Co-author tagging **and** claiming removed from the evidence modal | No longer wanted |
| Evidence viewer is full-width | PDF/image evidence was unreadable while verifying |
| Criteria moved beside HR Roster in the sidebar | Logical flow |

Also fixed while in the area: the Admin indicator dropdown was hardcoded with values
that didn't match the seeded data (`B. Research` vs the real `A. Research`) — adding an
indicator through it would have created an orphan category with no slug or review lane,
silently breaking workflow routing.

---

## 6. Schema migrations

Both are already applied to the working database.

**1.** [`MIGRATION_group4.sql`](MIGRATION_group4.sql) — IPCR categories, weights
re-keyed, `weight_group` dropped, Administrative Functions added.

**2.** Research target fields (no file — recorded here):

```sql
ALTER TABLE tbl_ret_rule_indicators
  ADD COLUMN target_description    TEXT NULL AFTER target_quantity,
  ADD COLUMN target_duration_value INT NULL AFTER target_description,
  ADD COLUMN target_duration_unit  ENUM('days','weeks','months','semesters') NULL
      AFTER target_duration_value;
```

Earlier migrations in this track (structured durations on the target tables, the
accomplishment capture columns, `tbl_criteria_weights`, `tbl_final_score_breakdown`)
are documented in [`DYNAMIC_CRITERIA.md`](DYNAMIC_CRITERIA.md) and
[`RET_REDESIGN.md`](RET_REDESIGN.md).

`run_migration.py` in the repo root applies a `.sql` file using the app's own `.env`
credentials, stopping at the first error rather than half-applying.

---

## 7. Known gaps

1. **Not yet exercised:** Client Satisfaction efficiency input, the Designated Faculty
   end-to-end path, and the "non-Completed status disables Completed-in" check.
2. **Remaining plan items:** Department Management and configurable Teaching Load
   (both currently hardcoded), Extension distribution UX parity with the Program
   Chair's allocation, and the Dean cascade confirmation modal — see
   [`POST_TEST_PLAN.md`](POST_TEST_PLAN.md) Groups 5, 3.2/3.3 and 6.1.
3. **Efficiency types in use** are only `Quantity-Based` and `Output-Based`;
   `Adjectival` and `Client Satisfaction` must be set on an indicator to exercise
   those branches.
4. The **return-reason prompt** uses a browser `prompt()` rather than a styled modal.
