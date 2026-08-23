def get_designated_selectable_indicators(cursor, term_id, exclude_claimed=True, emp_id=None):
    """
    The pool a designated faculty / chair member can add targets from.
    - If RET Chair: only Research and Extension (review_lane = 'RET').
    - If Program Chair / Designated Faculty: Instruction and Support (review_lane = 'CHAIR' AND is_core = 1).
    """
    from app.models.connection import timed_query
    
    is_ret = False
    if emp_id:
        cursor.execute("SELECT designation FROM tbl_employee_profiles WHERE emp_id = %s", (emp_id,))
        row = cursor.fetchone()
        if row and (row[0] or '').strip() == 'RET Chair':
            is_ret = True

    if is_ret:
        query = """
            SELECT mi.indicator_id, mi.indicator_description, tc.category_name
            FROM tbl_master_indicators mi
            JOIN tbl_target_categories tc ON mi.category_id = tc.category_id
            WHERE mi.term_id = %s
              AND mi.is_custom = 0
              AND tc.review_lane = 'RET'
            ORDER BY tc.category_name, mi.indicator_id
        """
        rows = timed_query(cursor, query, (term_id,), label="get_designated_selectable_indicators_ret")
        if exclude_claimed:
            # An indicator the Dean cascades to "RET / Extension" is already carried whole
            # as the RET Chair's oversight target (get_oversight_targets) — unlike Instruction,
            # there is no personal-allocation table for RET, so there's no legitimate reason
            # for it to also appear as a free pick here. Leaving it in let the same indicator
            # be selected twice under two different categories (see submit_designated_ipcr).
            claimed = get_claimed_indicator_ids(cursor, term_id)
            rows = [r for r in rows if r['indicator_id'] not in claimed]
        return rows

    query = """
        SELECT mi.indicator_id, mi.indicator_description, tc.category_name
        FROM tbl_master_indicators mi
        JOIN tbl_target_categories tc ON mi.category_id = tc.category_id
        WHERE mi.term_id = %s
          AND mi.is_custom = 0
          AND mi.indicator_description NOT LIKE '%%Teaching Load%%'
          AND tc.review_lane = 'CHAIR' AND tc.is_core = 1
        ORDER BY tc.category_name, mi.indicator_id
    """
    rows = timed_query(cursor, query, (term_id,), label="get_designated_selectable_indicators")
    if exclude_claimed:
        claimed = get_claimed_indicator_ids(cursor, term_id)

        # An indicator the Program Chair explicitly allocated to *this* person stays in the
        # list even though the department also holds it. The claimed rule exists to stop
        # someone picking up work that already has an owner — but for their own allocated
        # share they are the owner. Dropping it left the allocation with no row to attach
        # to, so a chair's Core Functions showed only the teaching load.
        allocated = set()
        if emp_id:
            cursor.execute(
                "SELECT da.indicator_id "
                "FROM tbl_draft_allocation da "
                "JOIN tbl_master_indicators mi ON da.indicator_id = mi.indicator_id "
                "WHERE da.emp_id = %s AND mi.term_id = %s "
                "  AND COALESCE(da.assigned_quantity, 0) > 0",
                (emp_id, term_id))
            allocated = {r[0] for r in cursor.fetchall()}

        rows = [r for r in rows
                if r['indicator_id'] not in claimed or r['indicator_id'] in allocated]
    return rows


def get_oversight_cascade_role(cursor, emp_id):
    """
    Which cascade bucket this person is accountable for overseeing, or None.

    A Program Chair oversees everything the Dean cascaded to their department; the RET Chair
    oversees the RET / Extension bucket. Other designated faculty (and the Dean, pending a
    decision on what the Dean's own oversight set should be) oversee nothing.
    """
    from app.models.institution import ROLE_RET
    cursor.execute(
        "SELECT designation, specialization FROM tbl_employee_profiles WHERE emp_id = %s",
        (emp_id,))
    row = cursor.fetchone()
    if not row:
        return None
    designation, specialization = (row[0] or '').strip(), (row[1] or '').strip()

    if designation == 'RET Chair':
        return ROLE_RET
    if designation == 'Program Chair' and specialization:
        return specialization
    return None


def get_claimed_indicator_ids(cursor, term_id):
    """
    Indicators already spoken for by a chair's oversight accountability.

    Anything the Dean cascaded to a department or to RET is automatically carried by that
    chair, so it must not also be offered in the pool other designated faculty pick from.
    College-Wide quotas are not claimed — the Dean assigns those explicitly.
    """
    from app.models.institution import ROLE_RET, get_departments

    # Department names are read separately rather than joined: tbl_departments was created
    # with a different collation from tbl_cascaded_quotas, so comparing the two columns
    # directly raises "Illegal mix of collations". Binding them as parameters sidesteps it.
    owners = [d['department_name'] for d in get_departments(cursor, active_only=False)]
    owners.append(ROLE_RET)
    if not owners:
        return set()

    placeholders = ','.join(['%s'] * len(owners))
    cursor.execute(f"""
        SELECT DISTINCT cq.indicator_id
        FROM tbl_cascaded_quotas cq
        JOIN tbl_master_indicators mi ON cq.indicator_id = mi.indicator_id
        WHERE cq.term_id = %s
          AND mi.term_id = %s
          AND cq.total_target_value > 0
          AND cq.assigned_to_role IN ({placeholders})
    """, tuple([term_id, term_id] + owners))
    return {r[0] for r in cursor.fetchall()}


def get_oversight_targets(cursor, emp_id, term_id):
    """
    The cascaded quotas a chair carries on their own IPCR as an administrative function.

    These are their department's (or RET's) numbers taken *whole*, not a share: the Dean
    cascades 5 of "Instruction 1" to WST, the WST chair divides that 5 among their faculty,
    and separately answers for the full 5 themselves. They rate under Strategic Priorities/
    Support Functions rather than by target type, which is what is_admin_function records.

    A chair may also hold the same indicator as their own allocated teaching work; that is a
    separate row with the flag clear, rating under Core Functions.
    """
    from app.models.connection import timed_query
    role = get_oversight_cascade_role(cursor, emp_id)
    if not role:
        return []

    query = """
        SELECT cq.indicator_id,
               cq.total_target_value,
               mi.indicator_description,
               mi.efficiency_type,
               tc.category_name,
               tc.slug,
               dt.draft_id,
               dt.proposed_quantity,
               dt.target_description,
               dt.target_deadline,
               dt.target_duration_value,
               dt.target_duration_unit,
               dt.review_status
        FROM tbl_cascaded_quotas cq
        JOIN tbl_master_indicators mi ON cq.indicator_id = mi.indicator_id
        JOIN tbl_target_categories tc ON mi.category_id = tc.category_id
        LEFT JOIN tbl_draft_targets dt
               ON dt.emp_id = %s AND dt.indicator_id = cq.indicator_id
              AND dt.is_admin_function = 1
        WHERE cq.term_id = %s
          AND mi.term_id = %s
          AND cq.assigned_to_role = %s
          AND cq.total_target_value > 0
        ORDER BY tc.display_order, mi.indicator_id
    """
    rows = timed_query(cursor, query, (emp_id, term_id, term_id, role),
                       label="get_oversight_targets")

    for r in rows:
        # Pre-filled from the cascade; a saved draft value wins so an edit survives a reload.
        r['total_target_value'] = r.get('proposed_quantity') or r['total_target_value']
        r['target_description'] = r.get('target_description') or r['indicator_description']
        r['target_deadline'] = r.get('target_deadline') or ''
        r['status'] = r.get('review_status') or 'Draft'
        r['is_admin_function'] = True
        # Narrower than is_admin_function: this row is specifically a chair's departmental
        # oversight quota (not just "not Core Function" — a freely-picked pool item is also
        # is_admin_function=1 after submission). The template uses this one for anything
        # UI-specific to the oversight row: the badge, locking the quantity, and picking the
        # `_adm`-suffixed deadline field name that avoids colliding with a personal Core
        # Function row that happens to share this indicator_id.
        r['is_oversight_cascade'] = True
        r['is_cascaded'] = True
        r['is_selected'] = True
        r['is_core'] = False
        # The quantity is fixed (the department's/RET's whole cascaded quota, not a share
        # the chair can adjust), but the deadline is real chair-provided input the Timeliness
        # score needs — see the duration handling in submit_designated_ipcr.
        r['is_locked'] = False
        r['is_custom'] = False
    return rows


def submit_designated_ipcr(conn, cursor, emp_id, term_id, selected_targets, custom_targets, oversight_durations=None):
    """
    Transactionally processes standard baseline selections and inserts custom ad-hoc targets
    upstream before compiling all submissions securely inside tbl_draft_targets.
    Also resets any prior Dean review so the Dean can review again.

    selected_targets: [{'indicator_id': int, 'proposed_quantity': int, 'target_description': str, 'target_deadline': str}]
    custom_targets: [{'description': str, 'proposed_quantity': int, 'category_name': str, 'target_deadline': str}]
    oversight_durations: {indicator_id: {'target_duration_value', 'target_duration_unit', 'target_deadline'}} —
        the chair's deadline input for their departmental oversight targets (see get_oversight_targets).
        Quantity/description for those targets is never taken from the form, only the deadline.
    """
    oversight_durations = oversight_durations or {}
    try:
        # 0. Clear any prior Dean review so Dean can re-review fresh
        cursor.execute(
            "SELECT review_id FROM tbl_ipcr_dean_review WHERE emp_id = %s AND term_id = %s",
            (emp_id, term_id)
        )
        old_review = cursor.fetchone()
        if old_review:
            old_review_id = old_review[0]
            cursor.execute("DELETE FROM tbl_ipcr_dean_review_items WHERE review_id = %s", (old_review_id,))
            cursor.execute("DELETE FROM tbl_ipcr_dean_review WHERE review_id = %s", (old_review_id,))

        # 1. Clear any prior unverified submissions for this profile to prevent key errors
        cursor.execute("DELETE FROM tbl_draft_targets WHERE emp_id = %s", (emp_id,))

        # A designated faculty's Core Functions are only their personal teaching work: the
        # mandatory teaching load plus whatever instruction the Program Chair allocated to
        # them (departmental CHAIR instruction, not College-Wide Dean assignments). Everything
        # else they carry — College-Wide targets, targets picked from the pool, custom items, and
        # a chair's oversight cascades — is a Strategic Priorities/Support Function.
        #
        # Derived here rather than taken from the form so the category cannot be spoofed or
        # drift out of step with what the dashboard displayed.
        cursor.execute("""
            SELECT da.indicator_id
            FROM tbl_draft_allocation da
            JOIN tbl_master_indicators mi ON da.indicator_id = mi.indicator_id
            JOIN tbl_target_categories tc ON mi.category_id = tc.category_id
            JOIN tbl_cascaded_quotas cq ON mi.indicator_id = cq.indicator_id AND cq.term_id = mi.term_id
            WHERE da.emp_id = %s AND mi.term_id = %s 
              AND tc.slug = 'instruction'
              AND tc.review_lane = 'CHAIR'
              AND cq.assigned_to_role != 'College-Wide'
              AND COALESCE(da.assigned_quantity, 0) > 0
        """, (emp_id, term_id))
        core_indicator_ids = {r[0] for r in cursor.fetchall()}

        # A chair's/RET chair's departmental oversight quota (see get_oversight_targets) can
        # be the *same indicator* as their personal Core Function allocation above — e.g. the
        # Dean cascades "Instruction 1" to WST, the WST chair keeps a personal teaching share
        # of it (Core Function, in core_indicator_ids) and separately answers for the
        # department's full quota (Strategic Priorities, inserted below from oversight_rows,
        # never trusted from the form). An indicator with *no* personal allocation — Support/
        # Admin/Innovation quotas, or any RET/Extension quota — only ever appears here as a
        # stray, data-less submission (the template renders no qty/duration fields for a pure
        # oversight row), so it's dropped; one *with* a personal allocation is real Core
        # Function input and must still be processed normally below.
        oversight_rows = get_oversight_targets(cursor, emp_id, term_id)
        oversight_indicator_ids = {r['indicator_id'] for r in oversight_rows}
        pure_oversight_ids = oversight_indicator_ids - core_indicator_ids

        # 2. Process Standard Baseline Selected Targets
        for target in selected_targets:
            if target['indicator_id'] in pure_oversight_ids:
                # A stray submission for an oversight-only row (see above) — the real
                # oversight target is inserted separately below.
                continue
            desc = target.get('target_description') or None
            dead = target.get('target_deadline') or None
            dur_value = target.get('target_duration_value')
            dur_unit = target.get('target_duration_unit')
            is_teaching_load = 'Teaching Load' in str(target.get('target_description') or '')
            is_core = is_teaching_load or target['indicator_id'] in core_indicator_ids
            is_admin = 0 if is_core else 1
            cursor.execute("""
                INSERT INTO tbl_draft_targets (emp_id, indicator_id, proposed_quantity, review_status, target_description, target_deadline,
                                               target_duration_value, target_duration_unit, is_admin_function)
                VALUES (%s, %s, %s, 'Pending Review', %s, %s, %s, %s, %s)
            """, (emp_id, target['indicator_id'], target['proposed_quantity'], desc, dead, dur_value, dur_unit, is_admin))

        from app.models.institution import resolve_teaching_load, teaching_load_description
        from app.models.scoring import format_duration

        # 2b. Insert the chair's/RET chair's departmental oversight targets. Quantity and
        # description come from get_oversight_targets (the cascade total — never the form, see
        # the note above); the deadline is real chair input, submitted separately in
        # oversight_durations (the `_adm`-suffixed fields) precisely because it can't be
        # derived from anywhere else and Timeliness scoring needs it.
        for r in oversight_rows:
            ov_input = oversight_durations.get(r['indicator_id'], {})
            ov_dur_value = (ov_input.get('target_duration_value') or r.get('target_duration_value') or 1)
            ov_dur_unit = (ov_input.get('target_duration_unit') or r.get('target_duration_unit') or 'semesters')
            ov_deadline = (ov_input.get('target_deadline') or r.get('target_deadline')
                           or format_duration(ov_dur_value, ov_dur_unit))
            cursor.execute("""
                INSERT INTO tbl_draft_targets (emp_id, indicator_id, proposed_quantity, review_status, target_description, target_deadline,
                                               target_duration_value, target_duration_unit, is_admin_function)
                VALUES (%s, %s, %s, 'Pending Review', %s, %s, %s, %s, 1)
            """, (emp_id, r['indicator_id'], r['total_target_value'], r['target_description'], ov_deadline, ov_dur_value, ov_dur_unit))

        # Ensure the mandatory Teaching Load target is saved, using the Admin's configured
        # hours and duration for Designated faculty (previously hardcoded at 10 hours).
        cursor.execute("SELECT academic_rank FROM tbl_employee_profiles WHERE emp_id = %s", (emp_id,))
        tl_rank_row = cursor.fetchone()
        tl_hours, tl_dur_value, tl_dur_unit = resolve_teaching_load(
            cursor, term_id, 'Designated Faculty', tl_rank_row[0] if tl_rank_row else None)
        tl_desc = teaching_load_description(tl_hours)
        tl_deadline = format_duration(tl_dur_value, tl_dur_unit)

        cursor.execute("SELECT category_id FROM tbl_target_categories WHERE slug = 'instruction'")
        cat_row = cursor.fetchone()
        cat_id = cat_row[0] if cat_row else 1
        cursor.execute("SELECT indicator_id FROM tbl_master_indicators WHERE indicator_description = %s AND term_id = %s",
                       (tl_desc, term_id))
        tl_row = cursor.fetchone()
        if tl_row:
            tl_ind_id = tl_row[0]
        else:
            cursor.execute("INSERT INTO tbl_master_indicators (category_id, indicator_description, efficiency_type, term_id, is_custom) VALUES (%s, %s, 'Output-Based', %s, 0)",
                           (cat_id, tl_desc, term_id))
            tl_ind_id = cursor.lastrowid

        cursor.execute("SELECT draft_id FROM tbl_draft_targets WHERE emp_id = %s AND indicator_id = %s", (emp_id, tl_ind_id))
        tl_draft = cursor.fetchone()
        if not tl_draft:
            cursor.execute("""
                INSERT INTO tbl_draft_targets (emp_id, indicator_id, proposed_quantity, review_status,
                                               target_description, target_deadline,
                                               target_duration_value, target_duration_unit)
                VALUES (%s, %s, %s, 'Pending Review', %s, %s, %s, %s)
            """, (emp_id, tl_ind_id, tl_hours, tl_desc, tl_deadline, tl_dur_value, tl_dur_unit))

        # 3. Process Custom Ad-Hoc Target Items
        for custom in custom_targets:
            text_clean = custom['description'].strip()
            qty = custom['proposed_quantity']
            dead = custom.get('target_deadline') or None
            cust_dur_value = custom.get('target_duration_value')
            cust_dur_unit = custom.get('target_duration_unit')
            if not text_clean:
                continue

            # Step A: Identify or provision the specific category block dynamically
            cat_name = custom.get('category_name', 'Support Functions')
            cursor.execute("SELECT category_id FROM tbl_target_categories WHERE category_name = %s", (cat_name,))
            cat_row = cursor.fetchone()
            if cat_row:
                category_id = cat_row[0]
            else:
                cursor.execute("INSERT INTO tbl_target_categories (category_name) VALUES (%s)", (cat_name,))
                category_id = cursor.lastrowid

            # Step B: Upstream runtime injection into master indicators (Explicitly flagged as is_custom = 1)
            cursor.execute("""
                SELECT indicator_id FROM tbl_master_indicators 
                WHERE indicator_description = %s AND term_id = %s AND category_id = %s AND is_custom = 1
            """, (text_clean, term_id, category_id))
            existing_ind = cursor.fetchone()
            if existing_ind:
                new_indicator_id = existing_ind[0]
            else:
                cursor.execute("""
                    INSERT INTO tbl_master_indicators (category_id, indicator_description, efficiency_type, term_id, is_custom)
                    VALUES (%s, %s, 'Output-Based', %s, 1)
                """, (category_id, text_clean, term_id))
                new_indicator_id = cursor.lastrowid

            # Step C: Downstream projection into the unified draft staging table.
            # Custom ad-hoc items are never personal teaching work, so they always rate
            # under Strategic Priorities/Support Functions.
            cursor.execute("""
                INSERT INTO tbl_draft_targets (emp_id, indicator_id, proposed_quantity, review_status, target_description, target_deadline,
                                               target_duration_value, target_duration_unit, is_admin_function)
                VALUES (%s, %s, %s, 'Pending Review', %s, %s, %s, %s, 1)
            """, (emp_id, new_indicator_id, qty, text_clean, dead, cust_dur_value, cust_dur_unit))

        conn.commit()
        return True, "Designated IPCR successfully compiled and submitted to Draft Targets for verification review."
    except Exception as e:
        conn.rollback()
        return False, str(e)


# ──────────────────────────────────────────────
# Process 6: Evidence Gathering Helpers
# ──────────────────────────────────────────────

def get_designated_committed_targets(cursor, emp_id, term_id):
    """
    Designated faculty's committed targets, including the fields the scoring engine
    needs (durations, reported accomplishment, efficiency type) so their IPCR rates
    the same way a regular faculty's does.
    """
    from app.models.connection import timed_query
    from app.models.scoring import build_actual_accomplishment, client_satisfaction_label, compute_target_rating
    query = """
        SELECT ct.target_id, ct.indicator_id, ct.assigned_quantity, ct.actual_quantity, ct.status,
               COALESCE(ct.target_description, dt.target_description, mi.indicator_description) as indicator_description,
               COALESCE(ct.target_description, dt.target_description) as target_description,
               COALESCE(ct.target_deadline, dt.target_deadline) as target_deadline,
               COALESCE(ct.target_duration_value, dt.target_duration_value) as target_duration_value,
               COALESCE(ct.target_duration_unit, dt.target_duration_unit) as target_duration_unit,
               ct.actual_duration_value, ct.completion_status, ct.efficiency_rating_E,
               ct.is_admin_function, ct.print_remarks,
               mi.efficiency_type,
               tc.category_name, tc.category_id, mi.is_custom
        FROM tbl_committed_targets ct
        JOIN tbl_master_indicators mi ON ct.indicator_id = mi.indicator_id
        LEFT JOIN tbl_target_categories tc ON mi.category_id = tc.category_id
        LEFT JOIN tbl_draft_targets dt ON dt.emp_id = ct.emp_id AND dt.indicator_id = ct.indicator_id
              AND dt.is_admin_function = ct.is_admin_function
        WHERE ct.emp_id = %s AND mi.term_id = %s
        ORDER BY tc.category_name, mi.indicator_id
    """
    rows = timed_query(cursor, query, (emp_id, term_id), label="get_designated_committed_targets")
    for r in rows:
        r['actual_accomplishment'] = build_actual_accomplishment(
            r.get('indicator_description'),
            r.get('actual_quantity'),
            r.get('actual_duration_value'),
            r.get('target_duration_unit'),
            client_satisfaction_label(r.get('efficiency_rating_E')),
        )
        r['rating'] = compute_target_rating(r)
    return rows



def check_designated_evidence_readiness(cursor, emp_id, term_id, dpcr_targets):
    if not dpcr_targets:
        return {
            'all_evidence_ready': False,
            'evidence_submitted': False,
            'total_targets': 0,
            'targets_with_evidence': 0,
            'targets_met_qty': 0
        }

    from app.models.faculty import get_evidence_by_target

    total_targets = len(dpcr_targets)
    targets_with_evidence = 0
    targets_met_qty = 0
    submitted_count = 0

    for t in dpcr_targets:
        ev_list = t.get('evidence_list')
        if ev_list is None:
            ev_list = get_evidence_by_target(cursor, t['target_id'], emp_id, t['indicator_id'])
            t['evidence_list'] = ev_list

        if len(ev_list) > 0:
            targets_with_evidence += 1

        actual_q = t.get('actual_quantity') or 0
        assigned_q = t.get('assigned_quantity') or t.get('total_target_value') or 0
        if actual_q >= assigned_q and assigned_q > 0:
            targets_met_qty += 1

        if t.get('status') in ('Submitted', 'Pending Verification', 'Verified', 'Submitted to Dean', 'Dean Approved'):
            submitted_count += 1

    all_ready = (total_targets > 0) and (targets_with_evidence == total_targets) and (targets_met_qty == total_targets)
    evidence_submitted = (submitted_count == total_targets) and (total_targets > 0)

    return {
        'all_evidence_ready': all_ready,
        'evidence_submitted': evidence_submitted,
        'total_targets': total_targets,
        'targets_with_evidence': targets_with_evidence,
        'targets_met_qty': targets_met_qty
    }


def submit_designated_evidences(conn, cursor, emp_id, term_id):
    dpcr_targets = get_designated_committed_targets(cursor, emp_id, term_id)
    if not dpcr_targets:
        return False, "No committed targets found."

    readiness = check_designated_evidence_readiness(cursor, emp_id, term_id, dpcr_targets)
    if readiness['evidence_submitted']:
        return False, "Evidences have already been submitted for verification."

    if not readiness['all_evidence_ready']:
        return False, "All targets must have uploaded evidence and meet target quantities before submitting."

    # A plain Designated Faculty member reports to a Program Chair, same as Regular Faculty —
    # their evidence must go through that Program Chair's review (get_program_chair_evidence_
    # faculty already lists them there) before it reaches the Dean. A Program Chair/RET Chair/
    # Dean has no one else positioned to review their own evidence, so theirs goes straight to
    # the Dean, same as before.
    cursor.execute("SELECT designation FROM tbl_employee_profiles WHERE emp_id = %s", (emp_id,))
    row = cursor.fetchone()
    designation = (row[0] or '').strip() if row else ''
    is_chair = designation in ('Program Chair', 'RET Chair', 'Dean')
    new_status = 'Submitted to Dean' if is_chair else 'Submitted'
    success_msg = ("Evidences successfully submitted to Dean for verification." if is_chair
                   else "Evidences successfully submitted to the Program Chair for verification.")

    try:
        target_ids = [t['target_id'] for t in dpcr_targets if t.get('target_id')]
        if target_ids:
            placeholders = ','.join(['%s'] * len(target_ids))
            update_sql = f"UPDATE tbl_committed_targets SET status = %s WHERE emp_id = %s AND target_id IN ({placeholders})"
            cursor.execute(update_sql, [new_status, emp_id] + target_ids)
            conn.commit()
            return True, success_msg
    except Exception as e:
        conn.rollback()
        return False, f"Error submitting evidences: {str(e)}"


def lock_and_commit_designated_ipcr(conn, cursor, emp_id, term_id):
    """
    Locks the designated faculty / chair IPCR after Dean approval.
    Commits approved draft targets into tbl_committed_targets and locks them for evidence gathering.
    """
    try:
        cursor.execute(
            "SELECT overall_status, review_id FROM tbl_ipcr_dean_review WHERE emp_id = %s AND term_id = %s",
            (emp_id, term_id)
        )
        review_row = cursor.fetchone()
        if not review_row or review_row[0] != 'Approved':
            return False, "Your IPCR must be approved by the Dean before locking."

        review_id = review_row[1]

        # Fetch approved draft items
        cursor.execute("""
            SELECT dt.indicator_id,
                   COALESCE(dri.reviewed_quantity, dt.proposed_quantity),
                   dt.target_description,
                   dt.target_deadline,
                   dt.target_duration_value,
                   dt.target_duration_unit,
                   dt.is_admin_function
            FROM tbl_draft_targets dt
            JOIN tbl_master_indicators mi ON dt.indicator_id = mi.indicator_id
            LEFT JOIN tbl_ipcr_dean_review_items dri ON dt.draft_id = dri.draft_id AND dri.review_id = %s
            WHERE dt.emp_id = %s AND mi.term_id = %s
        """, (review_id, emp_id, term_id))
        draft_items = cursor.fetchall()

        if not draft_items:
            return False, "No draft targets found to commit."

        # Delete any existing committed targets for this term
        cursor.execute("""
            DELETE ct FROM tbl_committed_targets ct
            JOIN tbl_master_indicators mi ON ct.indicator_id = mi.indicator_id
            WHERE ct.emp_id = %s AND mi.term_id = %s
        """, (emp_id, term_id))

        # Insert approved items into tbl_committed_targets
        for indicator_id, qty, target_desc, target_dead, dur_value, dur_unit, is_admin in draft_items:
            if qty > 0:
                cursor.execute("""
                    INSERT INTO tbl_committed_targets (emp_id, indicator_id, assigned_quantity, status, actual_quantity,
                                                       target_description, target_deadline,
                                                       target_duration_value, target_duration_unit, is_admin_function)
                    VALUES (%s, %s, %s, 'Approved', 0, %s, %s, %s, %s, %s)
                """, (emp_id, indicator_id, qty, target_desc, target_dead, dur_value, dur_unit, is_admin or 0))

        conn.commit()
        return True, "IPCR locked successfully and committed to evaluation targets."
    except Exception as e:
        conn.rollback()
        return False, str(e)
