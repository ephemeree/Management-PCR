# Automated & Synchronized IPCR Target Description Generation

## Overview
During academic performance planning (IPCR cascading and drafting), managers (**Program Chair**, **RET Chair**, **Dean**) and **Designated Faculty** input IPCR target descriptions for cascaded indicators.

Manual entry of target descriptions is prone to human errors (typos, inconsistent phrasing across faculty, missing deadlines, or mismatched quantities). The proposal is to **automate the generation of IPCR target descriptions**:
- By default, the IPCR description dynamically **mirrors the master indicator**, automatically incorporating the **assigned quantity** and **deadline duration** (e.g. `2 Preparation and submission of syllabus for assigned courses within 1 semester`).
- The manager/faculty member **retains full freedom to customize or edit** the description at any time.
- If the user modifies the quantity or deadline, untampered descriptions update automatically in real time, with an instant "Reset to Auto" option available if customized.
- On the backend, if an IPCR description is submitted empty, the system automatically builds the standardized description instead of failing validation or storing empty strings.

---

## Feasibility Assessment

### Verdict: **Feasible — schema change required, cleaning scoped down from the original draft**
1. **Data Availability**: All required data points (`indicator_description`, `quantity`, `target_duration_value`, `target_duration_unit`) are already present in forms, modals, and database schemas (`tbl_draft_allocation`, `tbl_ret_rule_indicators`, `tbl_ret_assignments`, `tbl_ret_extension_distribution`, `tbl_draft_targets`, `tbl_committed_targets`).
2. **Compatibility with Timeliness & Accomplishment Engine**: `app/models/scoring.py` already uses regex (`_LEADING_QTY`, `_DURATION_PHRASE`) to compose actual accomplishment sentences from `target_description`. Standardizing the generated text format ensures compatibility with automated accomplishment sentence generation and IPCR printouts — **but see Risk 2 below**: this engine substitutes on the *first* regex match, so the cleaning step must leave no other quantity- or duration-shaped text in the string, not just look right.
3. **Schema change required** (revised from the original "no schema changes" claim): tracking "is this description still auto-generated" reliably across page reloads and across the multi-role cascade needs a persisted flag, not a runtime guess — see Decision 1 below. This needs one new `MIGRATION_groupN.sql` file per CLAUDE.md's schema-change process, coordinated before applying it to the shared dev database.
4. **User Experience Improvement**: Eliminates repetitive typing of identical sentences across dozens of indicators while preserving full manual control.

---

## Decisions (resolved 2026-08-30)

These three forks were identified during review and settled before implementation:

1. **Auto-state tracking: persisted flag, not a heuristic.**
   Add a `is_auto_description TINYINT(1) NOT NULL DEFAULT 1` column to every table that stores a manager/faculty-editable description: `tbl_draft_allocation`, `tbl_ret_rule_indicators`, `tbl_ret_assignments`, `tbl_ret_extension_distribution`, `tbl_draft_targets`, `tbl_committed_targets`.
   - Rejected alternative: recomputing the auto-text from current quantity/duration and string-comparing against the saved description on load. This breaks as soon as quantity/duration changes after the description was saved by a *different* role in the cascade (e.g. Program Chair adjusts `assigned_quantity` after a Dean already saved the row) — the stored text goes stale with no way to tell "stale auto text" apart from "deliberately customized text that happens to differ."
   - With the flag: on any save, if `is_auto_description = 1`, the backend always recomputes the description from the row's current quantity/duration (ignoring whatever text was submitted for that field); if `0`, the submitted text is stored verbatim. The flag flips to `0` the moment a user types into the field (detected client-side) and flips back to `1` only via the explicit "Reset to Auto" action.

2. **Cleaning: conservative, but asymmetric between the leading quantity and the trailing duration.** Implemented and verified in [ipcr_description.py](file:///c:/Users/chest/Management-PCR/app/models/ipcr_description.py) against `build_actual_accomplishment()` — this asymmetry was *discovered* while writing that verification, not decided up front:
   - **Leading quantity**: stripped only on an **exact duplicate** of the quantity about to be inserted (e.g. indicator text literally starts with `"2 "` and the assigned quantity is also `2`). A mismatch (indicator says `"1 Research paper..."`, assigned quantity is `2`) is left as `"2 1 Research paper..."` rather than guessed at — cosmetically odd but harmless, because `build_actual_accomplishment()`'s quantity regex is anchored to the start of the string and can't land on the leftover token.
   - **Trailing duration clause** (`"...within/in <N> <unit>"` at the very end of the text): **always** stripped before appending the current duration, whether or not it matches. Leaving a stale one in place (e.g. legacy text already says `"...within 6 months"` and the newly-assigned duration is 3 months) would produce two duration-shaped phrases in one string. `build_actual_accomplishment()` substitutes on the *first* duration match it finds — confirmed by test to be the stale leftover, not the freshly-appended clause — silently corrupting the printed accomplishment sentence with the wrong number in the wrong place. Exact-duplicate-only cleaning, as originally decided, is unsafe specifically for this half of the string.
   - **Safety net**: after cleaning, if a duration-shaped phrase still exists anywhere in the text (a mid-sentence mention, e.g. `"...every 6 months as part of ongoing output"`, that the trailing-clause strip doesn't catch because it isn't at the end), the generator does **not** append its own duration clause — it falls back to `"[Quantity] [Indicator Description]"` rather than risk a second match. In this rare case the auto-generated text won't visibly show the currently-assigned duration; `build_actual_accomplishment()` still works safely off the one duration phrase that is present.
   - Rejected alternative: unconditionally stripping *any* leading number or *any* `\d+ (day|week|month|semester)s?` phrase found anywhere in the indicator text, as in the original draft. `_LEADING_QTY`-style matching is not word-bounded, so this would have corrupted indicator text like `"3rd Year students' thesis mentoring"` → `"rd Year students'..."`.
   - Recommend flagging to Admins as a data-hygiene note: new master indicators should be entered without an embedded quantity/duration, since that's the only case fully free of the cosmetic leading-quantity mismatch.

3. **Retroactivity: forward-only.**
   The `is_auto_description` flag defaults to `1` for new rows, but existing rows (already in the DB before this ships) are backfilled to `is_auto_description = 0` and their `custom_description`/`target_description` left exactly as-is. Auto-generation only kicks in for rows created or edited after this feature ships. Already-committed/locked/printed IPCRs render identically to how they do today — no historical printed record changes text on next view. The backfill migration must set this explicitly; don't rely on a column default alone once historical rows exist.

---

## Proposed Formatting Template

The standardized IPCR target description follows the Civil Service / SPMS convention:
```
[Quantity] [Indicator Description, conservatively cleaned] within [Duration Value] [Duration Unit]
```

### Formatting Rules:
1. **Quantity Prefix**: Automatically prepended as integer/number (e.g. `1`, `2`, `100%`). Confirm with Admin/RET Chair whether any current indicators use a percentage-based quantity convention distinct from a plain integer `assigned_quantity` — if `assigned_quantity` is always stored as a bare integer, the `%` suffix (if needed at all) has to come from somewhere else (e.g. `efficiency_type`), not from the quantity value itself.
2. **Indicator Text Cleaning (conservative — see Decision 2)**: Only strips a leading/trailing fragment from the indicator text when it exactly duplicates the quantity/duration being inserted. No cleaning is attempted otherwise.
3. **Pluralization / Unit Handling**: Reuse the existing `normalize_duration_unit()` / `format_duration()` helpers in `app/models/scoring.py` (already implement this — `1`+`months`→`1 month`, `6`+`months`→`6 months`, `1`+`semesters`→`1 semester`, `15`+`days`→`15 days`) rather than reimplementing the rule.
4. **Fallback Handling**: If duration is not yet specified, format as `[Quantity] [Indicator Description]`.

---

## User Review Required

> [!IMPORTANT]
> **Behavior Alignment**:
> 1. **Live Mirroring with Edit Detection**: When a user changes the Quantity or Deadline inputs, the IPCR Description field will automatically update in real time **unless** `is_auto_description` for that row has been flipped to `0` (i.e. the user has manually typed custom text into the description field this session or a prior one).
> 2. **"Reset to Standard" Action**: A small sync/wand icon button next to the description immediately regenerates the standard auto-format and flips `is_auto_description` back to `1`.
> 3. **Backend Fallback**: If a user submits a form with a blank description, the backend auto-generates the standard description rather than blocking submission with validation errors — this requires changing five existing hard-fail validation gates (see Component list below), which today `flash()` an error and reject the whole submission on a blank description.

---

## Proposed Changes

### Component 0: Schema Migration [NEW]

#### [NEW] `old MDS/MIGRATION_group<N>.sql`
- `ALTER TABLE` to add `is_auto_description TINYINT(1) NOT NULL DEFAULT 1` to: `tbl_draft_allocation`, `tbl_ret_rule_indicators`, `tbl_ret_assignments`, `tbl_ret_extension_distribution`, `tbl_draft_targets`, `tbl_committed_targets`.
- Explicit backfill `UPDATE ... SET is_auto_description = 0` for all pre-existing rows in each table (per Decision 3 — forward-only), run *before* the default takes effect for new inserts.
- Note `tbl_ret_extension_distribution` is a one-time-lock-per-term table (per `SETUP.md`) — once distributed, rows are frozen for the term, so any bug in this table's auto-generation path can't be corrected without a fresh term. Test this path with extra care before real use.

---

### Component 1: Shared Core Logic & Helpers

#### [NEW] [ipcr_description.py](file:///c:/Users/chest/Management-PCR/app/models/ipcr_description.py) (or addition to [scoring.py](file:///c:/Users/chest/Management-PCR/app/models/scoring.py))
- Implement `format_ipcr_target_description(indicator_description, quantity, duration_value, duration_unit)`:
  - Conservatively strips only exact-duplicate leading quantity / trailing duration (Decision 2).
  - Delegates pluralization to `normalize_duration_unit()` / `format_duration()` (already in `scoring.py`) instead of reimplementing.
  - Returns the clean, standardized target description string.
- **Regression test — done**: ran the function's output through `build_actual_accomplishment()` across 10 cases including the exact corruption scenario from Risk 2 (a legacy trailing duration mention that doesn't match the newly-assigned duration). Confirmed the original conservative design *would* have corrupted the accomplishment sentence in that case, and fixed it — see Decision 2's revised, asymmetric cleaning rule above. This should still be turned into a permanent unit test file rather than living only as an ad hoc verification run.

#### [MODIFY] [base.html](file:///c:/Users/chest/Management-PCR/app/templates/base.html) (or shared JS utility)
- Add shared client-side helper function `generateIpcrDescription(indicatorText, quantity, durationVal, durationUnit)`:
  - Mirrors backend formatting logic in JavaScript — **keep this deliberately minimal** (concatenation + the same conservative exact-duplicate check) so the two implementations don't drift; any rule beyond simple concatenation should be considered for a small JSON-serializable ruleset shared by both, or a fetch-based preview, rather than a second hand-maintained regex set.
  - Attaches real-time listeners (`input`, `change`) to quantity and duration inputs.
  - Manages a client-side "customized" state and sends it to the backend as the field's `is_auto_description` value on submit (a new hidden input per row, not just a `data-` attribute, since the backend needs this to make the always-recompute-if-auto decision from Decision 1).

---

### Component 2: Program Chair Dashboard

#### [MODIFY] [prog_chair_dashboard.html](file:///c:/Users/chest/Management-PCR/app/templates/prog_chair_dashboard.html)
- Enhance Instructions & Support Functions tables:
  - Add real-time synchronization between `assigned_quantities`, `target_duration_values`, `target_duration_units`, and `custom_descriptions`.
  - Add "Auto" badge / reset button for each description field, driven by the row's `is_auto_description` value.
  - Pre-populate blank description fields on initial load with the auto-generated format if empty.

#### [DONE] [prog_chair.py](file:///c:/Users/chest/Management-PCR/app/routes/prog_chair.py) & [models/prog_chair.py](file:///c:/Users/chest/Management-PCR/app/models/prog_chair.py)
- Replaced the blank-description hard-fail at `prog_chair.py:299` — blank now flows through to `save_chair_allocations_batch`, which auto-generates via `format_ipcr_target_description` and persists `is_auto_description` alongside `custom_description`/duration fields.
- Also carried `is_auto_description` forward in `lock_and_commit_ipcr` ([models/prog_chair.py](file:///c:/Users/chest/Management-PCR/app/models/prog_chair.py)) so the flag survives the draft→`tbl_committed_targets` copy at lock time — not explicitly called out in the original component list, added while wiring since the migration's backfill comment promised it.
- Not yet done: recompute-when-flagged-auto regardless of submitted text (full Decision 1 behavior) needs the frontend to send the flag explicitly — currently "blank submitted → auto" is the only signal, which is correct until Component 1's JS half exists.

---

### Component 3: RET Chair Dashboard

#### [MODIFY] [ret_chair_dashboard.html](file:///c:/Users/chest/Management-PCR/app/templates/ret_chair_dashboard.html)
- **Research Menu Rules**: live auto-generation of `research_description_<id>` when quantity or duration is adjusted.
- **Direct Assignment Modal (`openAssignmentEditor`)**: auto-generate `assign_description_<id>` dynamically when selecting indicators and updating quantity/duration.
- **Extension Distribution to All Faculty**: live auto-generation of `ext_description_<id>` from quantity and duration. Recall this flow is one-time-lock-per-term — verify the generated text before the RET Chair submits, since it cannot be edited afterward this term.

#### [DONE] [ret_chair.py](file:///c:/Users/chest/Management-PCR/app/routes/ret_chair.py) & [models/ret_chair.py](file:///c:/Users/chest/Management-PCR/app/models/ret_chair.py)
- All three hard-fail validation gates removed and wired to auto-fill-on-blank: `save_extension_distribution` (Extension), `save_assignments` (Direct Assignment), `ret_chair_save_rule` (Research Menu). Each corresponding model function (`save_ret_extension_distribution`, `save_ret_assignments`, `save_ret_rule`) now auto-generates via `format_ipcr_target_description` and persists `is_auto_description` in `tbl_ret_extension_distribution`, `tbl_ret_assignments`, and `tbl_ret_rule_indicators` respectively.
- Added a shared `get_indicator_description(cursor, indicator_id)` lookup to [ipcr_description.py](file:///c:/Users/chest/Management-PCR/app/models/ipcr_description.py) rather than a private per-file copy, since Dean and Designated Faculty need the identical lookup.

---

### Component 4: College Dean Dashboard

#### [MODIFY] [dean_dashboard.html](file:///c:/Users/chest/Management-PCR/app/templates/dean_dashboard.html)
- **Assign College-Wide Targets Modal (`openDesignatedAssignmentEditor`)**: live auto-generation of `assign_description_<id>` when assigning targets to Designated Faculty / Chairs.
- **IPCR Review / Add Target Modal**: automatically fill `review-desc` when Dean adds unpicked target items or adjusts quantity/duration. This path writes directly to `tbl_draft_targets` ([dean.py:389-398](file:///c:/Users/chest/Management-PCR/app/models/dean.py#L389-L398)), separate from the cascaded-quota path — confirm both need `is_auto_description` handled independently since they're different code paths into the same table.

#### [DONE] [dean.py](file:///c:/Users/chest/Management-PCR/app/routes/dean.py) & [models/dean.py](file:///c:/Users/chest/Management-PCR/app/models/dean.py)
- Removed the blank-description hard-fail at `dean.py:500`. `save_designated_faculty_assignments` auto-generates and persists `is_auto_description` in `tbl_draft_allocation`.
- `save_dean_review_items` (the review/add-target path) auto-generates and persists `is_auto_description` in `tbl_draft_targets`, in both the new-item-insert branch and the existing-item description/duration-edit branch.
- Also carried `is_auto_description` forward in the Designated Faculty lock function ([models/designated.py](file:///c:/Users/chest/Management-PCR/app/models/designated.py)) — same draft→committed carry-forward as Program Chair's lock path, added while wiring.

---

### Component 5: Designated Faculty Dashboard

#### [MODIFY] [designated_dashboard.html](file:///c:/Users/chest/Management-PCR/app/templates/designated_dashboard.html)
- Table 2 (Strategic Priorities & Support Functions):
  - When user modifies `target_qty_<id>`, `target_dur_value_<id>`, or `target_dur_unit_<id>`, auto-update `target_desc_<id>` if `is_auto_description = 1` for that row.
  - Provide a quick reset button to revert to auto-generated wording and flip the flag back to `1`.

#### [DONE] [designated.py](file:///c:/Users/chest/Management-PCR/app/routes/designated.py) & [models/designated.py](file:///c:/Users/chest/Management-PCR/app/models/designated.py)
- `submit_designated_ipcr`'s Table 2 (Strategic Priorities & Support Functions) loop now auto-generates via `format_ipcr_target_description` when `target_desc_<id>` is blank, and persists `is_auto_description` in `tbl_draft_targets`. Confirmed no route-level blank-description validation exists here to remove (consistent with the "Out of scope" note below — Designated Faculty never had a hard-fail gate).
- Left untouched, deliberately: the oversight-cascade loop (quantity/description are never taken from the form there, per the function's own docstring) and the custom ad-hoc target loop (user-authored free text with no master indicator to mirror).

---

## Out of scope (confirmed, not an oversight)

**Regular Faculty dashboard** (`app/routes/faculty.py` / `app/models/faculty.py`) has no blank-description validation today and none is proposed here — Regular Faculty inherit their descriptions from allocations/RET assignments set upstream by Program Chair/RET Chair via existing `COALESCE` fallback chains, and don't independently author target descriptions the way managers and Designated Faculty do.

---

## Verification Plan

### Automated Tests
1. Unit tests for `format_ipcr_target_description`:
   - Singular vs plural duration units (`1 month`, `6 months`, `1 semester`, `2 semesters`).
   - Exact-duplicate cleaning only (indicator text starting with the *same* quantity, or ending with the *same* duration phrase, gets cleaned; a mismatched embedded quantity/duration does not).
   - Various input combinations (missing duration, large quantities, percentages).
2. **Accomplishment-engine interaction tests** (new — not in the original plan): feed generated descriptions through `build_actual_accomplishment()` and assert the actual quantity/duration substitute into the appended clause only, per Risk 2.
3. Integration tests for submission routes, covering all five validation-gate call sites listed above:
   - Saving with blank descriptions → verify DB receives standardized formatted text and `is_auto_description = 1`.
   - Saving with custom descriptions → verify custom text is preserved untouched and `is_auto_description = 0`.
   - Saving an auto row after changing quantity/duration → verify the description recomputes even if stale text was submitted for that field.

### Manual UI Verification
1. **Program Chair**: Change quantity to 3 and duration to 1 semester → check description mirrors instantly → type custom text → change quantity → verify custom text stays → click Reset button → verify it reverts to 3 ... 1 semester.
2. **RET Chair**: Configure Research Menu rules, Direct Assignment, and Extension distribution → verify auto-description in each of the three sub-flows independently.
3. **Dean**: Open both the College-Wide Assignment modal and the IPCR Review/Add Target modal → verify auto-generation in each.
4. **Designated Faculty**: Select targets on draft IPCR → verify auto-description updates on quantity change.
5. **Printed IPCR**: Verify generated descriptions, and the accomplishment sentences built from them, render correctly on the printable IPCR form (`ipcr_print.html`) — including at least one case where actual quantity/duration differ from the target's.
6. **Cross-role staleness check**: have a Dean cascade a quota, let a Program Chair save the row with an auto description, then have the Program Chair change the assigned quantity again in a later save — verify the description updates to match rather than going stale.

---

## Redesign (2026-08-30): Placeholder-based generation

Everything above shipped and was verified working as designed. Reviewing it against a **real
DPCR document** (the actual indicator library this college uses) surfaced a problem serious
enough to require a design change before this feature is usable in production — not a bug fix,
a different generation strategy for the common case.

### Why the prepend/append model doesn't fit this college's real indicators

The whole design above assumes master indicators are bare activity names with no embedded
number — its own example was `"Preparation and submission of syllabus for assigned courses"`.
That assumption is wrong for this college. Real indicators, copied from the source DPCR:

```
Submit 51 accurate report of grades within 10 working days after the final examination period
Monitor/Observe 30 face to face classes in 6 months
Assign 15 Faculty Members as advisers of thesis writing/student organizations in 6 months
Distribute and Retrieve 50 Client Satisfaction Survey Forms in 6 months with satisfactory rating
Complete 5 Research outputs in 6 months
Prepare 1 tracer studies of different programs within 6 months showing that 34.27% of
  graduates from 2 years prior are employed
```

Of the ~24 indicators sampled from the real document, **~75% embed their quantity right after
an introductory verb** ("Submit", "Monitor/Observe", "Assign", "Complete", "Prepare", ...), not
at position 0. `format_ipcr_target_description`'s leading-quantity cleaning only strips an
*exact* match anchored at the very start of the string (Decision 2, deliberately, to avoid
guessing at arbitrary embedded numbers). Since the quantity in these real indicators is never
at position 0, that check never fires, and every one of them gets a second, redundant number
blindly prepended — e.g. assigning `2` to the tracer-study indicator produces
`"2 Prepare 1 tracer studies of different programs within 6 months..."`, not the intended
`"Prepare 2 tracer studies..."`.

**This is structural, not cosmetic.** The same master indicator is reused at multiple levels of
the cascade with a *different* quantity at each level — `"Submit 51 accurate report of
grades..."` is the Dean-level DPCR total (15+15+15+6+0 across departments); when a Program Chair
distributes a smaller share (say `15`) to a department, or further to one faculty member (say
`3`), the embedded `51` needs to be **replaced**, not left in place while a new number is glued
onto the front. Prepending can never do this correctly, no matter how the cleaning rule is
tuned — the fix has to substitute *at the position the number belongs*, and free-text regex
can't reliably find that position without the guessing this feature's whole design has
deliberately avoided.

### A second, pre-existing bug this surfaced

Testing the real indicator against the *existing* (pre-dates-this-feature) accomplishment-sentence
engine turned up an independent bug in `scoring.py`'s `build_actual_accomplishment()`:

```python
build_actual_accomplishment(
    "Submit 51 accurate report of grades within 10 working days after the final examination period",
    actual_quantity=15, actual_duration_value=8, duration_unit='days', ...)
# -> "Submit 51 accurate report of grades within 10 working days after the final examination period"
#    (unchanged — neither the actual quantity nor the actual duration got substituted at all)
```

`_LEADING_QTY` is anchored to the start of the string (`^`), same limitation as the generator
above. For the ~75% of real indicators where quantity isn't the first word, the printed "Actual
Accomplishment" column would always show the *target* text verbatim, never what was actually
reported — silently, with no error. This bug predates this feature entirely, but fixing target
descriptions without also fixing this would leave the printed IPCR still wrong for most targets,
so it's now in scope.

### The fix: explicit placeholders, not position-guessing

Master indicators may contain two literal tokens, typed by whoever authors them:

- `{qty}` — where the quantity goes
- `{duration}` — where the formatted duration phrase goes (`"6 months"`, `"1 semester"`, ...)

```
Submit {qty} accurate report of grades within {duration} after the final examination period
Prepare {qty} tracer studies of different programs within {duration} showing that 34.27% of
  graduates from 2 years prior are employed
```

This is a direct match for how the source DPCR is *already* structured — its "Success
Indicator" column is a fill-in-the-blank template (`"Submitted ___ report of grades ___ working
days..."`) that gets the blanks filled in per cascade level. `{qty}`/`{duration}` are that same
idea, just typed once by the Admin instead of literal underscores — named tokens instead of a
bare blank because a sentence can have more than one blank and a plain `___` can't say which one
is the quantity and which is the duration.

**Why this beats trying to detect the number's position automatically**: it requires zero
guessing. The Admin marks the spot once, when authoring the indicator; the system reads it back
deterministically forever after, at every cascade level, with no regex fragility and no risk of
the false positives (`"3rd Year students"`, a year number, an ID) that ruled out a more automatic
approach earlier in this document.

**Percentage/qualitative blanks stay untouched.** `34.27%`, `"with satisfactory rating"` etc. are
not modeled as placeholders — nothing in the schema tracks them as structured per-target data
(unlike quantity and duration), and in the source document they don't vary by cascade level the
way quantity does. They stay literal text in the indicator description, typed once at authoring
time, exactly as today.

### Decisions for this redesign (please confirm before implementation starts)

1. **Dual-mode formatter, not a replacement.** `format_ipcr_target_description` gains a
   placeholder path but keeps the existing prepend/append path unchanged as a fallback for
   indicators authored without `{qty}`/`{duration}` — including every indicator already in the
   database today. No forced migration: an indicator only opts into the new behavior when its
   text contains one of the tokens.
2. **No schema change.** `is_auto_description` (added in `MIGRATION_group11.sql`) already covers
   what's needed; placeholders live inside the existing `indicator_description` text column.
3. **Retrofit is manual, one-time, per indicator — not automatic.** Converting an existing
   indicator like `"Submit 51 accurate report of grades..."` to
   `"Submit {qty} accurate report of grades..."` means an Admin edits it once in Master
   Indicators. The system will not attempt to auto-detect where to insert tokens into existing
   text — that's exactly the guessing this design avoids. Since Admin's "Import from Previous
   Term" carries indicator text forward as-is, a retrofitted indicator keeps its placeholders in
   every future term without re-editing.
4. **Custom unit vocabulary (e.g. "10 working days" vs. the system's "10 days") is out of
   scope.** `{duration}` always renders using the existing `DURATION_UNITS`
   (days/weeks/months/semesters) via `format_duration()`. An indicator needing different unit
   wording either accepts the closest standard unit or is typed manually per recipient (Auto
   turned off) — documented as a known limitation, not solved by this redesign.
5. **The accomplishment-engine fix only fully applies to auto (mirrored) rows.** A row still on
   Auto has a live link back to its master indicator's template, so its actual-accomplishment
   sentence can be rebuilt by re-running the *same* placeholder substitution with the actual
   values — deterministic, no regex. A row the manager customized has no template to fall back
   to; it keeps using today's regex-based best-effort extraction (`_LEADING_QTY`/
   `_DURATION_PHRASE`), with the same position-dependent limitation as before. This is an
   accepted, pre-existing constraint of free-text customization, not something this redesign
   claims to fix.

### Proposed components — all implemented and verified 2026-08-30

#### [DONE] Component 1 — Core formatter (`app/models/ipcr_description.py`)
- `has_placeholders()` detects `{qty}`/`{duration}` tokens; `format_ipcr_target_description`
  dispatches to `_format_placeholders` (direct substitution, `____` fallback for an unset
  `{duration}`) or `_format_legacy` (the original prepend/append + conservative cleaning,
  unchanged) accordingly.
- Verified against the real DPCR examples: `"Submit {qty} accurate report of grades within
  {duration} after the final examination period"` correctly re-substitutes `51 → 15 → 3` at
  each cascade level with no leftover stale number; legacy cases (`"Preparation and submission
  of syllabus..."`, `"1 Research paper..."`, `"Conduct of extension activity within 6
  months"`) reproduce byte-identical output to before this redesign.

#### [DONE] Component 2 — Fixed `build_actual_accomplishment()` (`app/models/scoring.py`) and its two call sites
- New optional params `raw_indicator_description` / `is_auto_description`. When the row is
  still Auto and its indicator uses placeholders, the actual quantity/duration are substituted
  directly into the raw template (deterministic); every other case (customized text, or an auto
  row without placeholders) falls through to the original regex logic, byte-for-byte unchanged —
  confirmed both by a legacy call with no new args at all, and by a customized-row case that
  still exhibits the same pre-existing position-dependent limitation as before (not a
  regression: the fix is scoped to Auto rows only, per Decision 5).
- Wired into `get_faculty_committed_targets` (`app/models/faculty.py`) and
  `get_designated_committed_targets` (`app/models/designated.py`) — both now select
  `mi.indicator_description AS raw_indicator_description` and `ct.is_auto_description`
  alongside their existing joins (no new columns needed).
- Verified end-to-end: an Auto row reporting actual qty `12`/duration `8 days` against a target
  of `15`/`10 days` now correctly prints `"...12 accurate report of grades within 8 days..."` —
  previously (pre-redesign) this exact shape silently printed the *target* text unchanged, with
  neither actual value appearing anywhere in the printed IPCR.

#### [DONE] Component 3 — Shared JS mirror (`app/templates/base.html`)
- `generateIpcrDescription()` now checks for `{qty}`/`{duration}` first and substitutes
  directly before falling through to the existing legacy-mode logic. Verified via Node against
  the identical test matrix used for the Python formatter — output matches exactly, including
  the multi-level cascade reuse case and the `____` blank fallback.

#### [DONE] Component 4 — Admin UI guidance (`app/templates/admin_dashboard.html`)
- Both the Add Target and Edit Master Indicator modals now carry inline help text explaining
  `{qty}`/`{duration}` with a worked example drawn directly from the real indicator library
  (the report-of-grades case), and the Add modal's placeholder text was updated to demonstrate
  the syntax instead of a plain bare-activity example.
- Not done (explicitly deferred, per the original component list): a live preview inside the
  modal itself — not required to ship the fix.

#### [DONE] Component 5 — Verification
- Full regression matrix re-run covering: multi-level cascade reuse, duration-blank fallback,
  legacy-mode non-regression, the fixed accomplishment path (auto+placeholder), the unchanged
  accomplishment path (customized text), and the unchanged legacy call-site signature. All
  passed — see the verification run in this session for exact inputs/outputs.
- Not yet done: a from-the-browser click-through of the live JS mirror on an actual dashboard
  page (the Node-level JS verification confirms the *function* is correct, not that the DOM
  wiring calls it correctly end-to-end in a real page load) — recommend doing this once real
  placeholder-authored indicators exist in a test term.

#### [DONE] Component 6 — Documentation
- This section. `TEST_SCRIPT.md` updated: Phase A8 gained placeholder-authoring steps, Phase N
  gained placeholder-mode verification cases, and a new Known Gap entry documents the
  custom-unit-vocabulary limitation (Decision 4).

### Addendum (2026-08-30): click-to-tag helper, and an embedded-default syntax refinement

Raised concern: hand-typing `{qty}`/`{duration}` is itself a manual step, and once typed, the
indicator's *raw text* shows bare brace syntax everywhere it's displayed (the Admin's indicator
list, the edit form) instead of a readable sentence with a real number in it — a legitimate
"didn't we just move the manual work, not remove it" question worth taking seriously for a
panel presentation.

**Fix — two parts:**

1. **Click-to-tag helper** (`app/templates/admin_dashboard.html`): as an Admin types a
   description, every number-like token is shown as a clickable pill with Qty/Dur buttons.
   Clicking one rewrites just that character range — no hand-typing braces at all.
2. **Syntax extended to carry a display-only default**: a tag now writes `{qty:1}` or
   `{duration:6:months}` instead of the bare `{qty}`/`{duration}` from the first version of this
   redesign. The embedded value is cosmetic only — `render_indicator_preview()`
   (`ipcr_description.py`), exposed as the `ipcr_preview` Jinja filter, renders it back into a
   normal sentence for the Admin's indicator list; **actual generation still always substitutes
   the real assigned quantity/duration**, never the embedded default (verified: tagging `1`/`6
   months` then generating with `3`/`8 months` correctly produces the `3`/`8 months` version,
   not the embedded default). Bare `{qty}`/`{duration}` (typed by hand, or from before this
   syntax existed) still works identically — the colon-suffix is optional everywhere it's parsed.

**Three bugs caught and fixed while implementing this, all verified against real inputs before
shipping:**
- The Duration tag button naively targeting only the bare number (not a following unit word)
  would have produced `"...within 6 months months"` once `{duration}` rendered its own complete
  `"6 months"` on top of the leftover literal `"months"` — fixed by extending the Duration tag's
  replaced span to swallow an adjacent unit word; the Quantity tag never does this.
- The JS mirror's placeholder detection (`generateIpcrDescription` in `base.html`) used
  `.test()` on a global-flagged regex, which is stateful (`lastIndex` persists across calls) —
  confirmed it flips between true/false on identical input across repeated calls, which would
  have intermittently broken the live preview on every other keystroke. Fixed with separate
  non-global instances for existence checks and global instances (safe, self-resetting) for
  `.replace()`.
- The number-detector re-scanned digits *inside* an already-tagged token (e.g. the `1` inside
  `{qty:1}`) as if untagged, offering a pill that would have nested a new token inside the
  existing braces if clicked. Fixed by excluding any match that falls inside an existing
  `{qty:...}`/`{duration:...}` span before rendering pills.

### Explicitly out of scope for this redesign
- Auto-detecting or auto-inserting placeholders into existing indicator text.
- A structured field for the percentage/qualitative blank (`34.27%`, `"satisfactory rating"`).
- Fixing the customized-text (non-auto) accomplishment-sentence fallback's position-dependent
  limitation — pre-existing, unrelated to whether an indicator uses placeholders.
- Supporting duration unit vocabulary beyond days/weeks/months/semesters.

----

DEPARTMENTAL OVERSIGHT TARGETS FOR PROGRAM CHAIRS (targets that program chairs get when dean cascades to their specific dept, should also have its own target description--auto edited qty(based on the qty assigned by dean) )

**[DONE 2026-08-30]** `get_oversight_targets()` (`app/models/designated.py`) was falling back to
the raw `mi.indicator_description` whenever no draft had been saved yet — for a placeholder-
tagged indicator (e.g. `"Prepare {qty:1} tracer studies..."`), this showed the indicator's own
embedded example number (`1`) instead of the department's actual cascaded quota (e.g. `5`),
both on the Program Chair's own dashboard and in whatever got saved to `tbl_draft_targets` on
submit. Fixed in two places:
- `get_oversight_targets()` now always calls `format_ipcr_target_description()` with
  `total_target_value` (the fixed, non-editable department quota — never the row's own stray
  value) and the chair's current duration input, instead of the naive `or` fallback.
- `submit_designated_ipcr()`'s oversight-row insert regenerates the description again at save
  time using the *actual* duration values being submitted this request (not a possibly-stale
  one read earlier), and now sets `is_auto_description = 1`.
- `designated_dashboard.html`'s oversight-row label was also showing the raw indicator text
  unconditionally; changed to show the generated `target_description` for oversight rows
  specifically (they have no editable description field of their own, so this label is the
  only place their description is ever shown), and suppressed the redundant second copy that
  used to render right below it.
- Verified: a placeholder indicator authored with `{qty:1}` cascaded at quota `5` now correctly
  shows/saves `"Prepare 5 tracer studies..."`, not `"...1 tracer studies..."`.

----

### Addendum (2026-09-01): custom ad-hoc targets — three-branch composition

**The problem.** Combining the Add Custom Target modal's three fields into one sentence
(description + quantity + duration) was correct for the bare activity phrase the field's
placeholder asks for (`"Number of workshops conducted"`), but wrong when the person typed a
complete sentence that already stated its own numbers: `"Report 3 activities within 6 months"`
with Quantity `1` produced **`"1 Report 3 activities within 6 months"`**. The duration half was
fine (legacy mode always strips a trailing duration before appending); only the quantity half
prepended unconditionally, per Decision 2's exact-match-at-position-0 rule.

**Why no detection rule fixes it.** Given `"Report 3 activities"` and Quantity `1`, the system
cannot know whether `3` is the tracked quantity (and `1` was mistyped) or `1` is correct and `3`
describes something else. Both produce identical input. Widening the regex to "any number
anywhere" only trades one wrong answer for another — `"Grade 12 students"`, `"ISO 9001"`,
`"Section 3"` all contain numbers that are not the quantity. This is not a detection problem.

**The fix: binding, not detection.** Custom targets are a one-shot entry — the same person types
the description *and* the quantity, in the same form, at the same moment — so they can simply
say which number is which, in one click. `wirePlaceholderTagger` (built for Admin's Master
Indicator form) moved from `admin_dashboard.html` to `base.html` as `window.wirePlaceholderTagger`,
gaining an `options` argument, and is now wired to the Add Custom Target modal. Tagging a number
writes `{qty:3}`/`{duration:6:months}` into the text **and** syncs the matching field, which then
goes read-only — the sentence and the field cannot drift apart, because they are one value.

`submit_designated_ipcr()` and the modal's `composeCustomTargetDescription()` implement the same
three branches, verified to produce byte-identical output on the same inputs:

| Typed | Branch | Stored |
|---|---|---|
| `Report {qty:3} activities within {duration:6:months}` | tagged → substitute | `Report 3 activities within 6 months` |
| `Report 3 activities within 6 months` | untagged, has digits → **verbatim** | `Report 3 activities within 6 months` |
| `Number of workshops conducted` (qty 5, 6 months) | no digits → combine | `5 Number of workshops conducted within 6 months` |

No branch guesses. The ambiguous case degrades to trusting exactly what was typed rather than
mangling it; quantity and duration still reach scoring through their own columns either way.

**Bonus — the mid-sentence accomplishment gap closes for custom targets too.** A tagged custom
item stores its *raw* placeholder text in `tbl_master_indicators` and carries
`is_auto_description = 1`, so it behaves like an Admin-authored indicator: regeneration on read
is exact and idempotent, and `build_actual_accomplishment()` takes its placeholder fast path
instead of the regex anchored at character 0. Verified: target `3 in 6 months`, actual
`2 in 4 months` → `"Report 2 activities within 4 months"`. Untagged items keep
`is_auto_description = 0` (nothing to re-substitute), preserving the earlier corruption fix.

Two limitations recorded as Known Gaps 17 and 18 in `TEST_SCRIPT.md`: an untagged numeric
description is not woven into the sentence at all, and `{qty:80%}` substitutes as `80` (write
`{qty}%` instead). Manual coverage is Phase N5.

EXTENSION DISTRIBUTION REFACTOR: SAME AS MENU CONFIG FOR RESEARCH, but with auto divide, and instead of the selected targets (by RET Chair) showing as checked (suggested) on the Faculty's list, it should show their locked targets for Extension. So the flow for Research and Extension will be:  RET Chair configures the Research Menu Choices for each Academic Rank Band > that configuration will then be displayed for each faculty as their optional research target selection. RET Chair fonfigures the "Extension Menu Targets" for each Academic Rank Band > that configuration will then be displayed as their LOCKED extension targets (based on the faculty's acad rank)


SUPPORT DISTRIBUTION: REFACTOR