# Post-Test Implementation Plan

Derived from the annotated `TEST_SCRIPT.md` run. Groups every finding by size and
risk, and flags the one architectural defect the test surfaced.

**Test outcome:** Phases A–H passed except the items below. Not exercised:
G2 (non-Completed status disables "Completed in"), G3 (Client Satisfaction),
Phase I (Designated Faculty end-to-end) — coverage gaps, not failures.

---

## ⚠ The architectural finding

The test caught a real modeling defect. What the schema calls
`tbl_target_categories` is actually **target types** (Instruction, Research,
Extension, Support, Custom, Innovation). The real IPCR **categories** — the rows
that carry weight on the printed form — are Strategic Priorities / Core Functions /
Support Functions, and they are currently faked by the hardcoded `weight_group`
column (`instruction` / `ret` / `support` / `admin`).

That column cannot express the actual rule, because **the same target type maps to a
different category depending on designation**:

| Target type | Regular Faculty | Designated Faculty |
|---|---|---|
| Instruction | **Strategic Priorities** (50%) | **Core Functions** (25%) |
| Research / Extension | **Core Functions** (40%) | — |
| Support | **Support Functions** (10%) | — |
| Administrative *(type doesn't exist yet)* | — | **Strategic Priorities/Support Functions** (75%) |

`weight_group` is a single value per target type, so it physically cannot hold two
mappings. The Designated weights that "passed" in A4 only worked because the label
`instruction` was reusable as a bucket name — semantically it was wrong.

**Fix — promote category to a first-class, per-designation entity:**

```sql
-- The IPCR summary rows that carry weight
CREATE TABLE tbl_ipcr_categories (
  ipcr_category_id INT AUTO_INCREMENT PRIMARY KEY,
  designation_type ENUM('Regular Faculty','Designated Faculty') NOT NULL,
  category_name    VARCHAR(120) NOT NULL,      -- 'Strategic Priorities', 'Core Functions', ...
  display_order    INT NOT NULL DEFAULT 100,
  is_active        TINYINT(1) NOT NULL DEFAULT 1,
  UNIQUE KEY uq_ipcr_cat (designation_type, category_name)
);

-- Which target types fall under each category (implicitly per-designation)
CREATE TABLE tbl_ipcr_category_types (
  ipcr_category_id INT NOT NULL,
  category_id      INT NOT NULL,               -- FK -> tbl_target_categories (target TYPE)
  PRIMARY KEY (ipcr_category_id, category_id),
  FOREIGN KEY (ipcr_category_id) REFERENCES tbl_ipcr_categories(ipcr_category_id) ON DELETE CASCADE,
  FOREIGN KEY (category_id)      REFERENCES tbl_target_categories(category_id)   ON DELETE CASCADE
);
```

Then `tbl_criteria_weights.weight_group` → `ipcr_category_id`, and
`tbl_target_categories.weight_group` is retired. `tbl_final_score_breakdown` keeps
storing the category **name** as a text snapshot so historical ratings survive
later renames.

Also needed: a new **Administrative Functions** target type for Designated faculty.

---

## Group 1 — Quick UI fixes *(low risk, independent)*

| # | Finding | Fix |
|---|---|---|
| 1.1 | **A2** — "Custom Target Items (non-core)" appears in Admin's indicator category dropdown. Only Designated Faculty should create custom targets; Admin only cascades DPCR targets. | Filter the dropdown to `is_active AND is_core`. |
| 1.2 | **A3** — inactive criteria rows grey out the action buttons too, so Edit/Activate look unclickable although they work. | Move `opacity-50` off the `<tr>` onto the content cells only. |
| 1.3 | **Phase D** — RET Chair edits a rule from *Active Rules*, which throws them back to *Menu Config*. | Merge Active Rules into the Menu Config panel as one section. |
| 1.4 | **Phase G** — "Tag Co-Authors" no longer wanted in the evidence modal. | Remove the co-author section from the faculty evidence modal. |
| 1.5 | **Phase H** — evidence viewer is cramped. | Make the View Uploaded Evidence modal full-width (`modal-fullscreen` / `modal-xl`). |
| 1.6 | **A4** — Criteria panel sits below Master Indicators. | Move it next to HR Roster in the Admin sidebar. |

---

## Group 2 — Evidence verification *(closes a known gap)*

Currently `verification_status` is written as `'Pending'` and **never updated** — the
Verified/Rejected badges render but nothing sets them, so the "exclude Rejected
evidence from Q" filter is dead code. These findings together build the missing step.

- **2.1 (Phase H)** — add a **Status** column to the faculty evidence verification modal.
- **2.2 (Phase H)** — add **Approve** and **Return** actions in the evidence viewer.
  Return requires a reason (stored in `supervisor_comment`).
- **2.3 (Phase G)** — once evidence is submitted for verification, **disable further
  uploads** (viewing stays available).
- **2.4** — a **Returned** evidence item re-opens uploading for that faculty.

Together these make `verification_status` live, which in turn makes the existing
`!= 'Rejected'` quantity filter meaningful — i.e. scoring stops counting rejected
evidence.

---

## Group 3 — Missing data for scoring

- **3.1 (D1)** — research targets have **no deadline and no IPCR description**, so
  Timeliness cannot be computed for them and their accomplishment sentence has
  nothing to compose from. Add duration (value + unit) and description fields to the
  Research Menu Configuration, carried through to `tbl_draft_targets`.
- **3.2 (D3)** — rebuild Extension Distribution to mirror the Program Chair's
  allocation UX: per-target duration, description, and auto-divide across all regular
  faculty.
- **3.3 (Phase I)** — verify/complete the Designated Faculty path end-to-end so its
  targets carry durations and score against the Designated weight table.

> 3.1 is the highest-value item in this group: without it, every research target
> silently scores `T = —`, dragging the Core Functions average.

---

## Group 4 — Category Management *(the architectural item)*

- **4.1** — schema above (`tbl_ipcr_categories` + `tbl_ipcr_category_types`), seeded
  with the real names from the two sample IPCRs.
- **4.2** — new **Category Management** panel: per designation, create/order
  categories and assign which target types belong to each.
- **4.3** — rework **Weight Allocation** to key on real categories, so the matrix
  columns read *Strategic Priorities / Core Functions / Support Functions* instead of
  *instruction / ret / support*.
- **4.4** — rework the **Master Indicators** panel to group by category, with an
  **Add Target** button per category header opening the add-indicator modal
  (replacing the always-visible side form).
- **4.5** — update the roll-up (`compute_ipcr_score`) to group by `ipcr_category_id`
  and label the Summary of Ratings with real category names.

---

## Group 5 — New Admin modules

- **5.1 Department Management** — DST/WST/NST/BSDS/RET are hardcoded in
  `routes/dean.py` (quota cascade, Excel `col_map`) and in the Admin roster template.
  Add a departments table + CRUD, and drive the Dean's cascade columns from it.
- **5.2 Teaching Load Configuration** — the 21-hour (regular) and 10-hour (designated)
  loads are hardcoded in `models/faculty.py` and `models/designated.py`. Make them
  Admin-configurable using the same General-vs-per-rank-band pattern as weights, per
  designation, and default their duration to **6 months** so Timeliness computes.

---

## Group 6 — Smaller behavioural fixes

- **6.1 (Phase B)** — confirmation modal on *Cascade Institutional Targets*, and block
  submission when any target isn't assigned to at least one department.

---

## Suggested sequencing

| Order | Work | Why |
|---|---|---|
| 1 | **Group 1** (6 quick UI fixes) | Low risk, immediate polish, no schema changes |
| 2 | **Group 3.1** (research target deadline + description) | Scoring is currently wrong for research without it |
| 3 | **Group 2** (evidence verification) | Makes scoring trustworthy; activates dead filter logic |
| 4 | **Group 4** (Category Management) | Architectural; corrects naming the panel will scrutinise |
| 5 | **Group 5** (Department + Teaching Load) | Scalability; de-hardcodes institution data |
| 6 | **Groups 3.2 / 3.3 / 6.1** | Remaining UX and parallel-path work |

Group 4 is the largest and touches the scoring roll-up, so it is deliberately
sequenced after verification lands — otherwise two moving parts overlap in the same
code path.

---

## Housekeeping

There are now **two** test scripts: the annotated `TEST_SCRIPT.md` in the repo root
and the original `old MDS/TEST_SCRIPT.md`. Worth consolidating on the root one
(it has the findings) and deleting the duplicate.
