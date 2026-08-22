# Fix: Research target selection lost on Regular Faculty submission

## Context

Reported bug: a Regular Faculty member checks a Research target checkbox and submits their
IPCR. On reload the checkbox is unchecked, the RET Chair review stage is skipped entirely
(system behaves as if no Research target was selected), the submission proceeds straight to
the Program Chair panel, and that panel shows the faculty member with **no** mandatory
teaching-load target, no Research target, and no Extension target — i.e. their draft targets
were wiped rather than correctly saved.

Traced the whole path: `app/routes/faculty.py` `faculty_submit_ipcr()` →
`app/models/faculty.py` `submit_faculty_ipcr()` → `get_overall_ipcr_status()`
(`app/models/connection.py`). Found four compounding, verifiable bugs in
`submit_faculty_ipcr()`, all in the same function, that together produce exactly this
symptom:

1. **Term-id divergence (the trigger).** The route already validates `term_id` from the
   submitted form (`app/routes/faculty.py:186-191`) and uses it for its own locked/approved
   checks — but never passes it into `submit_faculty_ipcr()`
   (`app/routes/faculty.py:220`). The model function instead independently re-derives the
   active term via `SELECT term_id FROM tbl_academic_terms WHERE is_active = 1 LIMIT 1`
   (`app/models/faculty.py:225-227`), with no `ORDER BY` and no tie-breaker. This is a
   regression from an earlier version of the function that *did* take `term_id` as a
   parameter (see `old MDS/REFACTOR_0617.md:129`, `:162`) — the refactor that removed it
   introduced a second, independent source of truth for "the current term" inside the same
   request. `is_faculty_ret_eligible()` is re-evaluated against this independently-derived
   value (`app/models/faculty.py:238`), so it can disagree with what the dashboard showed the
   faculty when they checked the box.

2. **Research gets silently discarded when eligibility flips.** When
   `is_faculty_ret_eligible()` returns `False` at submit time, `app/models/faculty.py:336-345`
   deletes every existing Research row for the employee and never even looks at the faculty's
   selections — `target_status` is set to `'Waiting for Approval'` (the non-RET path), which
   is exactly "skips the RET Approval flow, proceeds directly to Program Chair" from the
   report. There's no message distinguishing "you aren't eligible" from "saved successfully."

3. **Extension delete isn't guarded the same way its reinsert is.** The unconditional
   `DELETE ... WHERE tc.slug = 'extension'` at `app/models/faculty.py:463-468` always runs,
   but the matching `SELECT`/`INSERT` that repopulates it is gated behind
   `if active_term_id:` (`:469-487`). Any moment where `active_term_id` is falsy wipes
   Extension targets with nothing to replace them — deterministic, not a race.

4. **No transaction around any of this.** The DB pool is `autocommit=True`
   (`app/models/connection.py:41`), documented in `CLAUDE.md` as meaning `conn.rollback()` is
   a no-op — every `cursor.execute()` in `submit_faculty_ipcr()` commits immediately and
   independently. The function's own `except: conn.rollback()`
   (`app/models/faculty.py:555-557`) does not protect anything that already executed, so a
   downstream exception after the Research/Extension deletes leaves those deletes permanently
   committed with no corresponding insert.

Fix (1) removes the trigger; (2) and (3) are real bugs regardless of (1) and get closed
directly; (4) makes the existing rollback call actually mean something so a future exception
in this function fails closed instead of leaving half-deleted state.

## Changes

**`app/routes/faculty.py`** — `faculty_submit_ipcr()` (~line 220): pass the already-validated
`term_id` through:
```python
success, msg = submit_faculty_ipcr(conn, cursor, emp_id, int(term_id), selected_ret_targets)
```

**`app/models/faculty.py`** — `submit_faculty_ipcr()` (line 215):
- New signature: `def submit_faculty_ipcr(conn, cursor, emp_id, term_id, selected_research_targets):`
- Remove the internal `SELECT term_id FROM tbl_academic_terms WHERE is_active = 1 LIMIT 1`
  re-derivation (lines 225-227); use the passed-in `term_id` as `active_term_id` everywhere
  it's currently used. Fail fast with a clear error if `term_id` is falsy, rather than
  silently proceeding with `None`.
- Wrap the extension delete (lines 463-468) inside the same `if active_term_id:` guard as its
  repopulating `SELECT`/`INSERT` (469-487), so it is never deleted without being rebuilt.
- Wrap the mutating body in an explicit transaction: set `conn.autocommit = False` on entry,
  keep the existing `conn.commit()` on success and `conn.rollback()` in the `except`, and
  restore `conn.autocommit = True` in a `finally` before the connection goes back to the pool
  (other code paths on this shared pooled connection assume `autocommit=True`, so it must not
  leak). This is scoped to this one function only — not a global pool-level change.

No other call sites of `submit_faculty_ipcr()` exist outside the route (confirmed via
project-wide search), so the signature change is safe.

## Verification

Since the DB pool's `autocommit=True` means there's no safe rollback-based dry run (per
`CLAUDE.md`), verify by re-running the actual repro from `TEST_SCRIPT.md` against the live
dev database after the fix lands:

1. Log in as a Regular Faculty member whose rank has a configured Research menu, on the
   currently active term.
2. Check one Research target checkbox and submit.
3. Confirm: checkbox stays checked/disabled as "submitted" on reload, status reads "Pending
   Review" (not skipped to Program Chair).
4. Log in as RET Chair: confirm the submission appears in their review queue with the
   Research target present.
5. Approve it; log in as Program Chair: confirm the faculty's target list includes the
   mandatory teaching-load target, the approved Research target, and any distributed
   Extension target — none missing.
6. Spot check a non-RET-eligible faculty member's submission still behaves as before (no
   Research menu shown, no Research rows created, straight to Program Chair).