# Dynamic Criteria & Scalability

Consolidated record of the "Add Custom Criteria" + "Dynamic Weight Allocation"
capstone-adviser requirement. Turns the four hardcoded IPCR criteria
(Instruction, Research, Extension, Support) into data — new criteria, and their
per-rank weights, are now Admin-configurable without a code change.

> Status legend: ✅ done · 🔨 planned/not started

---

## 1. The original problem

Before this work, "criteria" were baked in three separate ways:
1. **~40 SQL sites** hardcoded `category_name IN ('A. Instructions', 'Support Functions')` /
   `('A. Research', 'B. Extension...')` to decide which review lane (Program Chair vs
   RET Chair) a target went through.
2. **`tbl_final_scores`** had fixed columns — `instruction_weighted`, `ret_weighted`,
   `support_weighted`, `admin_weighted` — one per criterion, baked into the schema.
3. The **Admin's "Add Master Indicator" category dropdown was hardcoded** with option
   values that didn't even match the seeded category names (`B. Research` vs. the real
   `A. Research`) — picking it would have silently created an orphan category with no
   lane/slug, breaking the workflow.

None of this could support a genuinely new criterion (e.g. *Innovation*) without editing
code in several files.

---

## 2. Phases

### Phase 0 — Schema ✅
`tbl_target_categories` gained the columns that let a category describe its own behaviour:

```sql
ALTER TABLE tbl_target_categories
  ADD COLUMN slug          VARCHAR(40)  NULL,          -- stable machine key
  ADD COLUMN review_lane   ENUM('CHAIR','RET') NOT NULL DEFAULT 'CHAIR',
  ADD COLUMN is_core       TINYINT(1)   NOT NULL DEFAULT 1,
  ADD COLUMN weight_group  VARCHAR(40)  NULL,          -- scoring bucket
  ADD COLUMN display_order INT          NOT NULL DEFAULT 100,
  ADD COLUMN is_active     TINYINT(1)   NOT NULL DEFAULT 1;
```

New tables:
```sql
CREATE TABLE tbl_criteria_weights (
  weight_id    INT AUTO_INCREMENT PRIMARY KEY,
  term_id      INT NOT NULL,
  weight_group VARCHAR(40) NOT NULL,   -- e.g. 'instruction', 'ret', 'support', 'admin'
  rank_band    VARCHAR(50) NOT NULL,   -- 'Instructor', 'Assistant Professor', ...
  weight_pct   DECIMAL(5,2) NOT NULL,
  UNIQUE KEY uq_weight (term_id, weight_group, rank_band),
  FOREIGN KEY (term_id) REFERENCES tbl_academic_terms(term_id)
);

CREATE TABLE tbl_final_score_breakdown (
  breakdown_id   INT AUTO_INCREMENT PRIMARY KEY,
  score_id       INT NOT NULL,
  category_id    INT NOT NULL,
  raw_avg        DECIMAL(6,3) NULL,
  weight_pct     DECIMAL(5,2) NULL,
  weighted_value DECIMAL(6,3) NULL,
  FOREIGN KEY (score_id) REFERENCES tbl_final_scores(score_id) ON DELETE CASCADE,
  FOREIGN KEY (category_id) REFERENCES tbl_target_categories(category_id)
);
```
`tbl_final_scores` had its four fixed weighted columns dropped — the per-criterion
breakdown moved to `tbl_final_score_breakdown` (one row per criterion instead of one
column per criterion, so adding a criterion never means an `ALTER TABLE`).

Backfill: the five original categories were tagged (`instruction`→CHAIR/core,
`research`→RET/core, `extension`→RET/core, `support`→CHAIR/core, `custom`→CHAIR/non-core),
and Research + Extension were both mapped to `weight_group='ret'` — Research and Extension
stay **separate criteria** but are weighted as **one bucket** (matches the old
`ret_weighted` column's intent).

### Phase 1a — De-hardcode the lane routing ✅
Replaced every `category_name IN (...)` lane check with data-driven predicates:

| Old | New |
|---|---|
| `category_name IN ('A. Instructions','Support Functions')` | `review_lane='CHAIR' AND is_core=1` |
| `category_name IN ('A. Research','B. Extension...')` | `review_lane='RET'` |
| `category_name NOT IN (...four canonical...)` | `is_core=0` |

New module [`app/models/criteria.py`](../app/models/criteria.py) centralizes the
constants (`LANE_CHAIR`, `LANE_RET`, `GROUP_*`, `SLUG_*`) and helpers
(`get_category_by_slug`, `rank_band`). ~30 sites across `faculty.py`, `prog_chair.py`
(model + route), `designated.py` (model + route), `dean.py` were converted. Behavior-
preserving on existing data — the payoff is a new *core* criterion now auto-routes
through the correct review lane instead of falling into the "custom" catch-all.

### Phase 2 — Admin Criteria CRUD ✅
Criteria became a first-class, Admin-managed list instead of an implicit side-effect of
adding an indicator.

- **Model**: `get_all_criteria`, `add_criteria` (auto-slugifies the name, enforces slug
  uniqueness), `update_criteria` (slug is **immutable** after creation — code and future
  data reference it), `set_criteria_active` (soft delete only; hard delete stays blocked
  by the FK from indicators/targets).
- **UI**: Admin → **Criteria** — add form + table (name, slug, lane, core, weight group,
  order, active) with Edit / Activate-Deactivate.
- **Bug fix along the way**: the Master Indicator add/edit category dropdowns were
  hardcoded and mismatched the real seed data (see §1.3) — both now populate from active
  managed criteria.

### Phase 3 — Weight Allocation by Rank ✅
Admin → Criteria → **Weight Allocation by Rank**: a matrix, rows = `RANK_BANDS`
(`Instructor` / `Assistant Professor` / `Associate Professor` / `Professor`), columns =
whichever `weight_group`s are actually in use (dynamic — reading a new criterion's group
adds a column automatically). Live client-side row-total badges (green=100%,
red=off, gray=unconfigured). "Copy from Previous Term" seeds a new term from the most
recent one that has weights.

Server-side validation (`save_criteria_weights`): any rank whose entered percentages sum
to a **nonzero** total must sum to **exactly 100**; an all-zero rank is treated as "not
yet configured" and its rows are simply cleared — so the matrix can be filled in
incrementally without one incomplete row blocking the rest.

---

## 3. Rank-band normalization

Full academic ranks (`Instructor I`, `Associate Professor V`, ...) collapse to one of
four bands via `criteria.rank_band()`:

```python
def rank_band(rank):
    r = (rank or '').strip().lower()
    if r.startswith('assistant professor'): return 'Assistant Professor'
    if r.startswith('associate professor'): return 'Associate Professor'
    if r.startswith('instructor'):          return 'Instructor'
    if r.startswith('professor'):           return 'Professor'
    return 'Unclassified'
```
(Assistant/Associate are checked before the bare `professor` prefix since they contain it.)
`rank_band()` is defined but **not yet wired into the scoring path** — that lands with
Phase 4.

---

## 4. What adding a new criterion looks like now

1. Admin → Criteria → **Add Criterion**: name (e.g. *Innovation*), review lane
   (`CHAIR` or `RET`), optional weight group, display order, core toggle. Slug
   auto-generates (`innovation`) and is fixed from then on.
2. It immediately appears as an option when adding a Master Indicator under it.
3. If it's `review_lane=CHAIR, is_core=1`, its targets auto-route through the Program
   Chair review lane — no code change.
4. If it has a `weight_group`, it gets its own column in the Weight Allocation matrix.

---

## 5. Not built yet — Phase 4: weighted scoring

Deliberately deferred — the priority was finishing the data/approval flow first. The
schema is staged for it (`tbl_criteria_weights`, `tbl_final_score_breakdown`, the four
fixed columns already dropped from `tbl_final_scores`), and `rank_band()` exists — but nothing
yet reads a faculty's achievement, rolls it up by `weight_group`, multiplies by
`tbl_criteria_weights`, and writes `tbl_final_scores.final_score` /
`adjectival_rating`. That's the next major piece.

---

## 6. Component map

| Area | File |
|---|---|
| Constants, lane/slug helpers, rank bands | `app/models/criteria.py` |
| Lane-routing de-hardcode | `app/models/{faculty,prog_chair,designated,dean}.py`, `app/routes/{prog_chair,designated}.py` |
| Criteria CRUD | `app/models/criteria.py` (CRUD fns), `app/routes/admin.py` (`/criteria/add|edit|toggle_active`) |
| Weight matrix | `app/models/criteria.py` (weight fns), `app/routes/admin.py` (`/criteria/save_weights`, `/criteria/copy_weights`) |
| UI | `app/templates/admin_dashboard.html` (`#nav-criteria`) |
