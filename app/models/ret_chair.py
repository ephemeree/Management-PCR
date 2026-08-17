def get_ret_indicators(cursor, term_id):
    from app.models.connection import timed_query
    query = """
        SELECT 
            mi.indicator_id, 
            mi.indicator_description, 
            mi.efficiency_type, 
            tc.category_name, 
            cq.total_target_value AS dean_quota,
            COALESCE(SUM(dt.proposed_quantity), 0) AS total_distributed
        FROM tbl_cascaded_quotas cq
        JOIN tbl_master_indicators mi ON cq.indicator_id = mi.indicator_id
        JOIN tbl_target_categories tc ON mi.category_id = tc.category_id
        
        -- Pull targets submitted by the faculty
        LEFT JOIN tbl_draft_targets dt ON mi.indicator_id = dt.indicator_id
        
        WHERE cq.term_id = %s
          AND cq.assigned_to_role = 'RET / Extension'
        GROUP BY 
            mi.indicator_id, 
            mi.indicator_description, 
            mi.efficiency_type, 
            tc.category_name, 
            cq.total_target_value
        ORDER BY tc.category_name, mi.indicator_id
    """
    return timed_query(cursor, query, (term_id,), label="get_ret_indicators")


def save_ret_rule(conn, cursor, term_id, academic_rank, research_selections, extension_selections, research_indicators, extension_indicators):
    try:
        # 1. Clean up existing rules for this academic rank to avoid conflicts
        cursor.execute("SELECT rule_id FROM tbl_ret_rules WHERE academic_rank = %s", (academic_rank,))
        rule_ids = [row[0] for row in cursor.fetchall()]
        if rule_ids:
            format_strings = ','.join(['%s'] * len(rule_ids))
            cursor.execute(f"DELETE FROM tbl_ret_rule_indicators WHERE rule_id IN ({format_strings})", tuple(rule_ids))
            cursor.execute(f"DELETE FROM tbl_ret_rules WHERE rule_id IN ({format_strings})", tuple(rule_ids))

        # 2. Save Research rule (if indicators are selected).
        # Each research indicator carries its own IPCR description and target duration so
        # Timeliness can be scored and the accomplishment sentence can be composed.
        if research_indicators and int(research_selections) > 0:
            cursor.execute("INSERT INTO tbl_ret_rules (academic_rank, required_selections) VALUES (%s, %s)",
                           (academic_rank, int(research_selections)))
            res_rule_id = cursor.lastrowid
            for item in research_indicators:
                if len(item) == 5:
                    ind_id, qty, desc, dur_value, dur_unit = item
                else:
                    ind_id, qty = item[0], item[1]
                    desc, dur_value, dur_unit = None, None, None
                cursor.execute("""
                    INSERT INTO tbl_ret_rule_indicators
                        (rule_id, indicator_id, target_quantity, target_description, target_duration_value, target_duration_unit)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (res_rule_id, ind_id, qty, desc, dur_value, dur_unit))

        # 3. Save Extension rule (if indicators are selected)
        if extension_indicators and int(extension_selections) > 0:
            cursor.execute("INSERT INTO tbl_ret_rules (academic_rank, required_selections) VALUES (%s, %s)", 
                           (academic_rank, int(extension_selections)))
            ext_rule_id = cursor.lastrowid
            for item in extension_indicators:
                ind_id, qty = item[0], item[1]
                cursor.execute("INSERT INTO tbl_ret_rule_indicators (rule_id, indicator_id, target_quantity) VALUES (%s, %s, %s)",
                               (ext_rule_id, ind_id, qty))

        conn.commit()
        return True, "Menu configuration saved successfully to structural rules templates."
    except Exception as e:
        conn.rollback()
        return False, str(e)


def get_ret_rules(cursor, term_id):
    from app.models.connection import timed_query
    # Filters by mi.term_id so rules effectively reset each term — intentional design.
    # When a new term is opened, new indicator IDs are created and old rule-indicator
    # references no longer match the current term's indicators, making the table appear
    # empty and prompting the RET Chair to reconfigure for the new term.
    query = """
        SELECT r.rule_id, r.academic_rank, r.required_selections, mi.indicator_id, mi.indicator_description, tc.category_name,
               rri.target_quantity, rri.target_description, rri.target_duration_value, rri.target_duration_unit
        FROM tbl_ret_rules r
        JOIN tbl_ret_rule_indicators rri ON r.rule_id = rri.rule_id
        JOIN tbl_master_indicators mi ON rri.indicator_id = mi.indicator_id
        JOIN tbl_target_categories tc ON mi.category_id = tc.category_id
        WHERE mi.term_id = %s
        ORDER BY r.academic_rank, tc.category_name
    """
    # BUGFIX: timed_query() internally calls cursor.fetchall() and returns the rows.
    # The old code discarded the return value and called cursor.fetchall() again,
    # which always returned [] because the cursor was already exhausted.
    rows = timed_query(cursor, query, (term_id,), label="get_ret_rules")
    rules_dict = {}

    for r in rows:
        rule_id = r['rule_id']
        rank    = r['academic_rank']
        required = r['required_selections']
        ind_id   = r['indicator_id']
        desc     = r['indicator_description']
        category = r['category_name']
        qty      = r['target_quantity']

        if rank not in rules_dict:
            rules_dict[rank] = {
                'rule_id': rank,  # Use rank string as rule_id for frontend delete forms
                'academic_rank': rank,
                'research_required': 0,
                'extension_required': 0,
                'research_indicators': [],
                'extension_indicators': []
            }

        # Safe matching using 'in' in case formatting contains letters like A. or B.
        if 'Research' in category:
            rules_dict[rank]['research_required'] = required
            rules_dict[rank]['research_indicators'].append({
                'id': ind_id, 'desc': desc, 'qty': qty,
                'target_description': r.get('target_description') or '',
                'duration_value': r.get('target_duration_value'),
                'duration_unit': r.get('target_duration_unit'),
            })
        elif 'Extension' in category or 'Training' in category or 'Advisory' in category:
            rules_dict[rank]['extension_required'] = required
            rules_dict[rank]['extension_indicators'].append({'id': ind_id, 'desc': desc, 'qty': qty})

    return list(rules_dict.values())


def delete_ret_rule(conn, cursor, rule_id, category_type=None):
    try:
        # Note: rule_id is passed as the academic_rank string from the frontend delete form
        academic_rank = rule_id
        cursor.execute("SELECT rule_id FROM tbl_ret_rules WHERE academic_rank = %s", (academic_rank,))
        rule_ids = [row[0] for row in cursor.fetchall()]
        if rule_ids:
            format_strings = ','.join(['%s'] * len(rule_ids))
            cursor.execute(f"DELETE FROM tbl_ret_rule_indicators WHERE rule_id IN ({format_strings})", tuple(rule_ids))
            cursor.execute(f"DELETE FROM tbl_ret_rules WHERE rule_id IN ({format_strings})", tuple(rule_ids))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        return False


def get_ret_assignment_faculty(cursor, term_id):
    """
    Returns all regular faculty (across specializations) with their current Research
    assignment count, for the RET Chair's Target Assignment list. Option B: there is
    no per-faculty access gate — every regular faculty may take Research targets.
    """
    query = """
        SELECT
            ep.emp_id,
            CONCAT(ep.first_name, ' ', ep.last_name) AS faculty_name,
            ep.first_name,
            ep.last_name,
            ep.academic_rank,
            ep.specialization,
            ep.college,
            (SELECT COUNT(*) FROM tbl_ret_assignments ra
             WHERE ra.emp_id = ep.emp_id AND ra.term_id = %s) AS assignment_count
        FROM tbl_employee_profiles ep
        WHERE ep.designation = 'Regular Faculty'
        ORDER BY ep.specialization, ep.last_name, ep.first_name
    """
    cursor.execute(query, (term_id,))
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def get_ret_extension_distribution(cursor, term_id):
    """
    Returns every Extension indicator for the term with the per-faculty quantity currently
    distributed to all regular faculty (0 if not distributed) — for the RET Chair's
    Extension distribution editor.
    """
    query = """
        SELECT
            mi.indicator_id,
            mi.indicator_description,
            COALESCE(red.target_quantity, 0) AS distributed_quantity,
            CASE WHEN red.dist_id IS NOT NULL THEN 1 ELSE 0 END AS is_distributed,
            (SELECT cq.total_target_value FROM tbl_cascaded_quotas cq
             WHERE cq.indicator_id = mi.indicator_id AND cq.term_id = %s LIMIT 1) AS dean_quota
        FROM tbl_master_indicators mi
        JOIN tbl_target_categories tc ON mi.category_id = tc.category_id
        LEFT JOIN tbl_ret_extension_distribution red
               ON red.indicator_id = mi.indicator_id AND red.term_id = %s
        WHERE mi.term_id = %s AND tc.slug = 'extension'
        ORDER BY mi.indicator_id
    """
    cursor.execute(query, (term_id, term_id, term_id))
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def get_distributed_extension_targets(cursor, term_id):
    """Extension targets distributed to all regular faculty — for the faculty read-only view."""
    query = """
        SELECT red.indicator_id, mi.indicator_description, red.target_quantity
        FROM tbl_ret_extension_distribution red
        JOIN tbl_master_indicators mi ON red.indicator_id = mi.indicator_id
        WHERE red.term_id = %s
        ORDER BY mi.indicator_id
    """
    cursor.execute(query, (term_id,))
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def is_extension_distributed(cursor, term_id):
    """True once Extension has been distributed for the term (distribution is one-time / locked)."""
    cursor.execute("SELECT COUNT(*) FROM tbl_ret_extension_distribution WHERE term_id = %s", (term_id,))
    return cursor.fetchone()[0] > 0


def save_ret_extension_distribution(conn, cursor, term_id, distributions, distributed_by):
    """
    Replaces the term's Extension distribution set. `distributions` is a list of
    (indicator_id, per_faculty_quantity). Only Extension indicators for the term are
    accepted. Extension is uniform across all regular faculty and is materialized per
    faculty at submit. This is a one-time action per term: once distributed it is locked
    and cannot be changed.
    """
    try:
        # One-time lock: refuse if Extension has already been distributed for this term.
        if is_extension_distributed(cursor, term_id):
            return False, "Extension targets have already been distributed for this term and are locked."

        cursor.execute("""
            SELECT mi.indicator_id
            FROM tbl_master_indicators mi
            JOIN tbl_target_categories tc ON mi.category_id = tc.category_id
            WHERE mi.term_id = %s AND tc.slug = 'extension'
        """, (term_id,))
        allowed = {r[0] for r in cursor.fetchall()}

        cursor.execute("DELETE FROM tbl_ret_extension_distribution WHERE term_id = %s", (term_id,))

        saved = 0
        skipped = 0
        for indicator_id, qty in distributions:
            if indicator_id not in allowed:
                skipped += 1
                continue
            qty = qty if qty and int(qty) > 0 else 1
            cursor.execute("""
                INSERT INTO tbl_ret_extension_distribution (term_id, indicator_id, target_quantity, distributed_by)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE target_quantity = VALUES(target_quantity), distributed_by = VALUES(distributed_by)
            """, (term_id, indicator_id, int(qty), distributed_by))
            saved += 1

        conn.commit()
        msg = f"Distributed {saved} Extension target(s) to all regular faculty."
        if skipped:
            msg += f" {skipped} skipped (not an Extension indicator for this term)."
        return True, msg
    except Exception as e:
        conn.rollback()
        return False, str(e)


def get_ret_faculty_assignments(cursor, term_id, emp_id):
    """
    Returns the RET Chair's authored assignments for one faculty member in a term,
    joined with indicator descriptions and category names.
    """
    query = """
        SELECT ra.indicator_id, ra.target_quantity,
               mi.indicator_description, tc.category_name, tc.slug
        FROM tbl_ret_assignments ra
        JOIN tbl_master_indicators mi ON ra.indicator_id = mi.indicator_id
        JOIN tbl_target_categories tc ON mi.category_id = tc.category_id
        WHERE ra.term_id = %s AND ra.emp_id = %s
        ORDER BY tc.display_order, mi.indicator_id
    """
    cursor.execute(query, (term_id, emp_id))
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def save_ret_assignments(conn, cursor, term_id, emp_id, assignments, assigned_by):
    """
    Replaces the RET Chair's assignments for a faculty member in a term.

    `assignments` is a list of (indicator_id, target_quantity) tuples. Only
    indicators that belong to the faculty member's rank menu (tbl_ret_rules) are
    accepted — assignments are restricted to the rank-eligible pool.
    """
    try:
        # Resolve the faculty member's rank to bound the allowed indicator pool
        cursor.execute("SELECT academic_rank FROM tbl_employee_profiles WHERE emp_id = %s", (emp_id,))
        rank_row = cursor.fetchone()
        academic_rank = rank_row[0] if rank_row else None

        allowed_ids = set()
        if academic_rank:
            from app.models.faculty import get_faculty_ret_menu
            menu = get_faculty_ret_menu(cursor, academic_rank, term_id)
            for ind in menu['research_indicators'] + menu['extension_indicators']:
                allowed_ids.add(ind['indicator_id'])

        # Replace the full set for this faculty/term
        cursor.execute(
            "DELETE FROM tbl_ret_assignments WHERE term_id = %s AND emp_id = %s",
            (term_id, emp_id)
        )

        saved = 0
        skipped = 0
        for indicator_id, qty in assignments:
            if indicator_id not in allowed_ids:
                skipped += 1
                continue
            qty = qty if qty and int(qty) > 0 else 1
            cursor.execute("""
                INSERT INTO tbl_ret_assignments (term_id, emp_id, indicator_id, target_quantity, assigned_by)
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE target_quantity = VALUES(target_quantity), assigned_by = VALUES(assigned_by)
            """, (term_id, emp_id, indicator_id, int(qty), assigned_by))
            saved += 1

        conn.commit()
        msg = f"Saved {saved} assigned target(s)."
        if skipped:
            msg += f" {skipped} skipped (outside the faculty member's rank menu)."
        return True, msg
    except Exception as e:
        conn.rollback()
        return False, str(e)


def get_pending_ret_draft_ipcrs(cursor, term_id):
    """
    Returns all regular faculty members enabled for RET targets who have submitted their IPCR draft (i.e. tbl_draft_targets has entries for the term),
    with their RET review status from tbl_ipcr_ret_review.
    """
    query = """
        SELECT
            ep.emp_id,
            CONCAT(ep.first_name, ' ', ep.last_name) AS faculty_name,
            ep.academic_rank,
            ep.specialization,
            (
                SELECT COUNT(dt2.draft_id)
                FROM tbl_draft_targets dt2
                JOIN tbl_master_indicators mi2 ON dt2.indicator_id = mi2.indicator_id
                JOIN tbl_target_categories tc2 ON mi2.category_id = tc2.category_id
                LEFT JOIN tbl_ipcr_ret_review rr2 ON rr2.emp_id = ep.emp_id AND rr2.term_id = mi2.term_id
                LEFT JOIN tbl_ipcr_ret_review_items ri2 ON ri2.review_id = rr2.review_id AND ri2.draft_id = dt2.draft_id
                WHERE dt2.emp_id = ep.emp_id AND mi2.term_id = %s
                  AND tc2.slug = 'research'
                  AND COALESCE(ri2.reviewed_quantity, dt2.proposed_quantity) > 0
            ) AS target_count,
            COALESCE(rr.overall_status, 'Pending Review') AS review_status,
            rr.review_id,
            rr.overall_remarks,
            rr.reviewed_at
        FROM tbl_employee_profiles ep
        -- Only check employees who have draft targets for the active term
        JOIN (
            SELECT DISTINCT dt3.emp_id
            FROM tbl_draft_targets dt3
            JOIN tbl_master_indicators mi3 ON dt3.indicator_id = mi3.indicator_id
            JOIN tbl_target_categories tc3 ON mi3.category_id = tc3.category_id
            LEFT JOIN tbl_ipcr_ret_review rr3 ON rr3.emp_id = dt3.emp_id AND rr3.term_id = mi3.term_id
            LEFT JOIN tbl_ipcr_ret_review_items ri3 ON ri3.review_id = rr3.review_id AND ri3.draft_id = dt3.draft_id
            WHERE mi3.term_id = %s
              AND tc3.slug = 'research'
              AND COALESCE(ri3.reviewed_quantity, dt3.proposed_quantity) > 0
        ) dt_sub ON ep.emp_id = dt_sub.emp_id
        LEFT JOIN tbl_ipcr_ret_review rr ON rr.emp_id = ep.emp_id AND rr.term_id = %s
        WHERE ep.designation = 'Regular Faculty'
        ORDER BY ep.last_name, ep.first_name
    """
    cursor.execute(query, (term_id, term_id, term_id))
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def get_ret_target_assignments(cursor, term_id):
    """
    Returns individual RET target assignments with quantities.
    Used for the new task assignment tracking.
    """
    query = """
        SELECT
            ep.emp_id,
            CONCAT(ep.first_name, ' ', ep.last_name) AS faculty_name,
            ep.academic_rank,
            ep.specialization,
            dt.indicator_id,
            mi.indicator_description,
            tc.category_name,
            dt.proposed_quantity AS target_quantity,
            dt.review_status
        FROM tbl_draft_targets dt
        JOIN tbl_employee_profiles ep ON dt.emp_id = ep.emp_id
        JOIN tbl_master_indicators mi ON dt.indicator_id = mi.indicator_id
        JOIN tbl_target_categories tc ON mi.category_id = tc.category_id
        WHERE mi.term_id = %s
          AND ep.designation = 'Regular Faculty'
          AND (tc.category_name LIKE '%%Research%%' OR tc.category_name LIKE '%%Extension%%' OR tc.category_name LIKE '%%Training%%' OR tc.category_name LIKE '%%Advisory%%')
        ORDER BY
            ep.last_name,
            ep.first_name,
            tc.category_name,
            mi.indicator_id
    """

    cursor.execute(query, (term_id,))
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def get_or_create_ret_review(conn, cursor, emp_id, term_id, ret_chair_emp_id):
    """
    Gets or creates the RET review record, pre-populating items from tbl_draft_targets
    for Research and Extension targets.
    """
    # Check for existing review
    cursor.execute(
        "SELECT review_id FROM tbl_ipcr_ret_review WHERE emp_id = %s AND term_id = %s",
        (emp_id, term_id)
    )
    existing = cursor.fetchone()
    if existing:
        review_id = existing[0]
        # Sync: Insert any draft targets that are missing from review items
        cursor.execute(
            """
            INSERT INTO tbl_ipcr_ret_review_items
                (review_id, draft_id, indicator_id, original_quantity, reviewed_quantity)
            SELECT %s, dt.draft_id, dt.indicator_id, dt.proposed_quantity, dt.proposed_quantity
            FROM tbl_draft_targets dt
            JOIN tbl_master_indicators mi ON dt.indicator_id = mi.indicator_id
            JOIN tbl_target_categories tc ON mi.category_id = tc.category_id
            LEFT JOIN tbl_ipcr_ret_review_items ri ON ri.review_id = %s AND ri.draft_id = dt.draft_id
            WHERE dt.emp_id = %s AND mi.term_id = %s
              AND tc.slug = 'research'
              AND ri.item_id IS NULL
            """,
            (review_id, review_id, emp_id, term_id)
        )
        conn.commit()
        return review_id

    # Create the review header
    cursor.execute(
        """
        INSERT INTO tbl_ipcr_ret_review (emp_id, term_id, ret_chair_emp_id, overall_status)
        VALUES (%s, %s, %s, 'Pending')
        """,
        (emp_id, term_id, ret_chair_emp_id)
    )
    review_id = cursor.lastrowid

    # Pre-populate items from tbl_draft_targets
    cursor.execute(
        """
        SELECT dt.draft_id, dt.indicator_id, dt.proposed_quantity
        FROM tbl_draft_targets dt
        JOIN tbl_master_indicators mi ON dt.indicator_id = mi.indicator_id
        JOIN tbl_target_categories tc ON mi.category_id = tc.category_id
        WHERE dt.emp_id = %s AND mi.term_id = %s
          AND tc.slug = 'research'
        """,
        (emp_id, term_id)
    )
    draft_rows = cursor.fetchall()

    for draft_id, indicator_id, proposed_qty in draft_rows:
        cursor.execute(
            """
            INSERT INTO tbl_ipcr_ret_review_items
                (review_id, draft_id, indicator_id, original_quantity, reviewed_quantity)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (review_id, draft_id, indicator_id, proposed_qty, proposed_qty)
        )

    conn.commit()
    return review_id


def get_ret_review_items(cursor, review_id):
    """
    Returns all items for a given RET review_id, joined with indicator descriptions
    and category names.
    """
    query = """
        SELECT
            ri.item_id,
            ri.draft_id,
            ri.indicator_id,
            ri.original_quantity,
            ri.reviewed_quantity,
            ri.item_remarks,
            mi.indicator_description,
            tc.category_name
        FROM tbl_ipcr_ret_review_items ri
        JOIN tbl_master_indicators mi ON ri.indicator_id = mi.indicator_id
        JOIN tbl_target_categories tc ON mi.category_id = tc.category_id
        WHERE ri.review_id = %s
        ORDER BY tc.category_name, mi.indicator_id
    """
    cursor.execute(query, (review_id,))
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def update_ret_review_item(conn, cursor, item_id, reviewed_quantity, item_remarks):
    """
    Updates a single RET review item's reviewed quantity and optional remark.
    """
    try:
        cursor.execute(
            """
            UPDATE tbl_ipcr_ret_review_items
            SET reviewed_quantity = %s, item_remarks = %s
            WHERE item_id = %s
            """,
            (reviewed_quantity, item_remarks if item_remarks else None, item_id)
        )
        conn.commit()
        return True, "Change saved."
    except Exception as e:
        conn.rollback()
        return False, str(e)


def decide_ret_review(conn, cursor, review_id, action, overall_remarks):
    """
    Sets overall_status to 'Approved' or 'Rejected' on the RET review header.
    On rejection, sets the related RET draft targets to 'Returned'.
    On approval, updates the draft targets with finalized quantities and sets status to 'Approved'.
    """
    from datetime import datetime
    try:
        new_status = 'Approved' if action == 'approve' else 'Rejected'

        cursor.execute(
            """
            UPDATE tbl_ipcr_ret_review
            SET overall_status = %s,
                overall_remarks = %s,
                reviewed_at = %s
            WHERE review_id = %s
            """,
            (new_status, overall_remarks, datetime.now(), review_id)
        )

        # Get the emp_id and term_id for this review
        cursor.execute(
            "SELECT emp_id, term_id FROM tbl_ipcr_ret_review WHERE review_id = %s",
            (review_id,)
        )
        row = cursor.fetchone()
        if row:
            emp_id, term_id = row
            if action == 'reject':
                # Set RET draft targets review status to 'Returned'
                cursor.execute(
                    """
                    UPDATE tbl_draft_targets dt
                    JOIN tbl_master_indicators mi ON dt.indicator_id = mi.indicator_id
                    JOIN tbl_target_categories tc ON mi.category_id = tc.category_id
                    SET dt.review_status = 'Returned'
                    WHERE dt.emp_id = %s AND mi.term_id = %s
                      AND tc.slug = 'research'
                    """,
                    (emp_id, term_id)
                )
            elif action == 'approve':
                # Finalize proposed quantities in tbl_draft_targets to match RET reviewed quantities
                cursor.execute(
                    """
                    UPDATE tbl_draft_targets dt
                    JOIN tbl_master_indicators mi ON dt.indicator_id = mi.indicator_id
                    JOIN tbl_ipcr_ret_review rr ON dt.emp_id = rr.emp_id AND rr.term_id = mi.term_id
                    JOIN tbl_ipcr_ret_review_items ri ON ri.review_id = rr.review_id AND ri.draft_id = dt.draft_id
                    SET dt.proposed_quantity = ri.reviewed_quantity,
                        dt.review_status = 'Approved'
                    WHERE dt.emp_id = %s AND mi.term_id = %s
                    """,
                    (emp_id, term_id)
                )

        conn.commit()
        return True, f"RET Choices successfully {new_status.lower()}."
    except Exception as e:
        conn.rollback()
        return False, str(e)


def get_faculty_ret_review_status(cursor, emp_id, term_id):
    """
    Returns the RET Chair's current review record for this faculty member,
    or None if no review has been started yet.
    """
    cursor.execute("""
        SELECT review_id, overall_status, overall_remarks, reviewed_at
        FROM tbl_ipcr_ret_review
        WHERE emp_id = %s AND term_id = %s
    """, (emp_id, term_id))
    row = cursor.fetchone()
    if row:
        return {
            'review_id':      row[0],
            'overall_status': row[1],
            'overall_remarks': row[2],
            'reviewed_at':    row[3],
        }
    return None


def save_ret_review_items(cursor, conn, review_id, items):
    """
    Batch save all RET review item changes (quantities + remarks).
    Items: [{'item_id': int, 'reviewed_quantity': int, 'item_remarks': str}, ...]
    For new items (is_new=True, no item_id), creates draft target + review item.
    Also syncs changes back to tbl_draft_targets so faculty see the update.
    """
    try:
        for item in items:
            reviewed_qty = item.get('reviewed_quantity', 0)
            item_remarks = item.get('item_remarks', '')

            if item.get('is_new') and not item.get('item_id'):
                # New item from unpicked indicators — insert draft target + review item
                indicator_id = item.get('indicator_id')
                if not indicator_id:
                    continue
                # Get emp_id from review
                cursor.execute(
                    "SELECT emp_id, term_id FROM tbl_ipcr_ret_review WHERE review_id = %s",
                    (review_id,)
                )
                r = cursor.fetchone()
                if not r:
                    continue
                emp_id, term_id = r
                # Insert draft target
                cursor.execute("""
                    INSERT INTO tbl_draft_targets (emp_id, indicator_id, proposed_quantity, review_status)
                    VALUES (%s, %s, %s, 'Pending Review')
                """, (emp_id, indicator_id, reviewed_qty))
                new_draft_id = cursor.lastrowid
                # Insert review item linked to new draft
                cursor.execute("""
                    INSERT INTO tbl_ipcr_ret_review_items
                        (review_id, draft_id, indicator_id, original_quantity, reviewed_quantity, item_remarks)
                    VALUES (%s, %s, %s, -1, %s, %s)
                """, (review_id, new_draft_id, indicator_id, reviewed_qty, item_remarks))
            else:
                # Existing item — update quantities and remarks
                item_id = item.get('item_id')
                if not item_id:
                    continue
                cursor.execute("""
                    UPDATE tbl_ipcr_ret_review_items
                    SET reviewed_quantity = %s, item_remarks = %s
                    WHERE item_id = %s
                """, (reviewed_qty, item_remarks, item_id))

                # Sync back to tbl_draft_targets so faculty member sees the change
                cursor.execute("""
                    UPDATE tbl_draft_targets dt
                    JOIN tbl_ipcr_ret_review_items ri ON dt.draft_id = ri.draft_id
                    SET dt.proposed_quantity = %s
                    WHERE ri.item_id = %s
                """, (reviewed_qty, item_id))

        conn.commit()
        return True, "Review items saved successfully."
    except Exception as e:
        conn.rollback()
        return False, str(e)


def get_ret_chair_evidence_faculty(cursor, term_id):
    from app.models.connection import timed_query
    query = """
        SELECT ep.emp_id, ep.first_name, ep.last_name, ep.academic_rank, ep.specialization,
               COUNT(DISTINCT ct.target_id) as total_targets,
               SUM(CASE WHEN ct.actual_quantity >= ct.assigned_quantity AND ct.assigned_quantity > 0 THEN 1 ELSE 0 END) as met_targets,
               MAX(CASE WHEN ct.status IN ('Submitted', 'Pending Verification', 'Verified') THEN 1 ELSE 0 END) as has_submitted
        FROM tbl_employee_profiles ep
        JOIN tbl_committed_targets ct ON ep.emp_id = ct.emp_id
        JOIN tbl_master_indicators mi ON ct.indicator_id = mi.indicator_id
        JOIN tbl_target_categories tc ON mi.category_id = tc.category_id
        WHERE mi.term_id = %s AND (tc.category_name LIKE '%%Research%%' OR tc.category_name LIKE '%%Extension%%')
        GROUP BY ep.emp_id, ep.first_name, ep.last_name, ep.academic_rank, ep.specialization
        HAVING MAX(CASE WHEN ct.status IN ('Submitted', 'Pending Verification', 'Verified') THEN 1 ELSE 0 END) = 1
        ORDER BY ep.last_name, ep.first_name
    """
    rows = timed_query(cursor, query, (term_id,), label="get_ret_chair_evidence_faculty")
    for r in rows:
        r['evidence_status'] = 'Submitted'
    return rows