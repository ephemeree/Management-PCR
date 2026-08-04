from datetime import datetime


# ─────────────────────────────────────────────
# Existing functions (unchanged)
# ─────────────────────────────────────────────

def get_chair_indicators(cursor, term_id, specialization):
    from app.models.connection import timed_query
    query = """
        SELECT mi.indicator_id, mi.indicator_description, mi.efficiency_type, tc.category_name, cq.total_target_value as dept_quota
        FROM tbl_master_indicators mi
        JOIN tbl_target_categories tc ON mi.category_id = tc.category_id
        JOIN tbl_cascaded_quotas cq ON mi.indicator_id = cq.indicator_id AND cq.term_id = mi.term_id
        WHERE mi.term_id = %s
          AND tc.category_name IN ('A. Instructions', 'Support Functions')
          AND cq.assigned_to_role = %s
        ORDER BY tc.category_name, mi.indicator_id
    """
    return timed_query(cursor, query, (term_id, specialization), label="get_chair_indicators")


def get_specialization_faculty(cursor, specialization):
    from app.models.connection import timed_query
    query = """
        SELECT emp_id, first_name, last_name, academic_rank, leave_status, designation
        FROM tbl_employee_profiles
        WHERE (specialization = %s OR assigned_program = %s)
          AND leave_status = 'Active'
          AND designation IN ('Regular Faculty', 'Designated Faculty')
    """
    return timed_query(cursor, query, (specialization, specialization), label="get_specialization_faculty")


def get_assigned_quantity_batch(cursor, term_id, indicator_ids, faculty_ids):
    """
    Get assigned quantities, custom descriptions, and deadlines for MULTIPLE indicators in ONE query.
    Returns dict: {indicator_id: {'assigned_quantity': qty, 'custom_description': desc, 'target_deadline': deadline}}
    Replaces N+1 get_assigned_quantity() calls.
    """
    if not faculty_ids or not indicator_ids:
        return {}
    from app.models.connection import timed_query
    fac_placeholders = ','.join(['%s'] * len(faculty_ids))
    ind_placeholders = ','.join(['%s'] * len(indicator_ids))
    query = f"""
        SELECT da.indicator_id, da.assigned_quantity, da.custom_description, da.target_deadline
        FROM tbl_draft_allocation da
        JOIN tbl_master_indicators mi ON da.indicator_id = mi.indicator_id
        WHERE mi.term_id = %s 
          AND da.indicator_id IN ({ind_placeholders})
          AND da.emp_id IN ({fac_placeholders})
        GROUP BY da.indicator_id, da.assigned_quantity, da.custom_description, da.target_deadline
    """
    rows = timed_query(cursor, query, [term_id] + indicator_ids + faculty_ids, label="get_assigned_quantity_batch")
    result = {}
    for row in rows:
        result[row['indicator_id']] = {
            'assigned_quantity': row['assigned_quantity'],
            'custom_description': row.get('custom_description'),
            'target_deadline': row.get('target_deadline')
        }
    return result


def get_assigned_quantity(cursor, term_id, indicator_id, faculty_ids):
    if not faculty_ids:
        return 0
    format_strings = ','.join(['%s'] * len(faculty_ids))
    query = f"""
        SELECT da.assigned_quantity
        FROM tbl_draft_allocation da
        JOIN tbl_master_indicators mi ON da.indicator_id = mi.indicator_id
        WHERE mi.term_id = %s AND da.indicator_id = %s AND da.emp_id IN ({format_strings})
        LIMIT 1
    """
    cursor.execute(query, [term_id, indicator_id] + faculty_ids)
    res = cursor.fetchall()
    return res[0][0] if res else 0


def save_chair_allocations_batch(conn, cursor, term_id, allocations, faculty_ids):
    try:
        if not faculty_ids:
            return False, "No active faculty found for this specialization."

        for item in allocations:
            if len(item) == 4:
                indicator_id, assigned_quantity, custom_description, target_deadline = item
            else:
                indicator_id, assigned_quantity = item[0], item[1]
                custom_description, target_deadline = None, None

            # Determine category of the indicator
            cursor.execute("""
                SELECT tc.category_name
                FROM tbl_master_indicators mi
                JOIN tbl_target_categories tc ON mi.category_id = tc.category_id
                WHERE mi.indicator_id = %s
            """, (indicator_id,))
            cat_row = cursor.fetchone()
            cat_name = cat_row[0] if cat_row else ''

            if 'Instruction' in cat_name:
                # Instruction targets are cascaded to both Regular and Designated Faculty
                target_emp_ids = faculty_ids
            else:
                # Support targets are cascaded to Regular Faculty ONLY
                format_strings = ','.join(['%s'] * len(faculty_ids))
                cursor.execute(f"""
                    SELECT emp_id FROM tbl_employee_profiles
                    WHERE emp_id IN ({format_strings}) AND designation = 'Regular Faculty'
                """, faculty_ids)
                target_emp_ids = [r[0] for r in cursor.fetchall()]

            for emp_id in target_emp_ids:
                # Check if an allocation record already exists in the draft staging table
                check_query = """
                    SELECT allocation_id 
                    FROM tbl_draft_allocation
                    WHERE emp_id = %s AND indicator_id = %s
                """
                cursor.execute(check_query, (emp_id, indicator_id))
                existing = cursor.fetchall()

                if existing:
                    update_query = """
                        UPDATE tbl_draft_allocation 
                        SET assigned_quantity = %s, custom_description = %s, target_deadline = %s 
                        WHERE allocation_id = %s
                    """
                    cursor.execute(update_query, (assigned_quantity, custom_description, target_deadline, existing[0][0]))
                else:
                    insert_query = """
                        INSERT INTO tbl_draft_allocation (emp_id, indicator_id, assigned_quantity, custom_description, target_deadline)
                        VALUES (%s, %s, %s, %s, %s)
                    """
                    cursor.execute(insert_query, (emp_id, indicator_id, assigned_quantity, custom_description, target_deadline))

        conn.commit()
        return True, "Targets distributed successfully to all faculty draft worklists."
    except Exception as e:
        conn.rollback()
        return False, str(e)


def check_chair_targets_saved(cursor, term_id, specialization):
    """
    Returns True if target allocations have already been saved in tbl_draft_allocation
    for faculty members under `specialization` for `term_id`.
    """
    if not term_id or not specialization:
        return False
    query = """
        SELECT COUNT(*) 
        FROM tbl_draft_allocation da
        JOIN tbl_master_indicators mi ON da.indicator_id = mi.indicator_id
        JOIN tbl_employee_profiles ep ON da.emp_id = ep.emp_id
        WHERE mi.term_id = %s AND ep.specialization = %s
    """
    cursor.execute(query, (term_id, specialization))
    res = cursor.fetchone()
    return res[0] > 0 if res else False


# ─────────────────────────────────────────────
# New functions — Commitments & IPCR Review
# ─────────────────────────────────────────────

def get_pending_drafts_count(cursor, specialization, term_id):
    """
    Returns the count of faculty members under `specialization` who have
    submitted a draft IPCR (tbl_draft_targets) for the term that still
    have an overall_status of 'Pending' (or 'Waiting for Approval' or no review record yet).
    """
    query = """
        SELECT COUNT(DISTINCT dt.emp_id)
        FROM tbl_draft_targets dt
        JOIN tbl_master_indicators mi ON dt.indicator_id = mi.indicator_id
        JOIN tbl_target_categories tc ON mi.category_id = tc.category_id
        JOIN tbl_employee_profiles ep ON dt.emp_id = ep.emp_id
        LEFT JOIN tbl_ipcr_chair_review cr ON cr.emp_id = dt.emp_id AND cr.term_id = mi.term_id
        LEFT JOIN tbl_ipcr_chair_review_items ri ON ri.review_id = cr.review_id AND ri.draft_id = dt.draft_id
        LEFT JOIN tbl_ipcr_ret_review rr ON rr.emp_id = dt.emp_id AND rr.term_id = mi.term_id
        LEFT JOIN tbl_ipcr_ret_review_items rri ON rri.review_id = rr.review_id AND rri.indicator_id = dt.indicator_id
        WHERE mi.term_id = %s
          AND ep.specialization = %s
          AND ep.designation = 'Regular Faculty'
          AND dt.review_status IN ('Pending Review', 'Waiting for Approval')
          AND (
              (tc.category_name IN ('A. Instructions', 'Support Functions') AND COALESCE(ri.reviewed_quantity, dt.proposed_quantity) > 0)
              OR (tc.category_name IN ('A. Research', 'B. Extension Services / Training / Advisory') AND COALESCE(rri.reviewed_quantity, dt.proposed_quantity) > 0)
              OR (tc.category_name NOT IN ('A. Instructions', 'Support Functions', 'A. Research', 'B. Extension Services / Training / Advisory') AND dt.proposed_quantity > 0)
          )
          AND (cr.overall_status IS NULL OR cr.overall_status = 'Pending' OR cr.overall_status = 'Waiting for Approval')
    """
    cursor.execute(query, (term_id, specialization))
    result = cursor.fetchone()
    return result[0] if result else 0


def get_pending_draft_ipcrs(cursor, specialization, term_id):
    """
    Returns all faculty members under `specialization` who have submitted
    a Draft IPCR for the active term, along with their current review status.
    Faculty with no review record yet are treated as 'Pending Review'.
    Approved or Locked IPCRs are excluded from this list.
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
                LEFT JOIN tbl_ipcr_chair_review cr2 ON cr2.emp_id = ep.emp_id AND cr2.term_id = mi2.term_id
                LEFT JOIN tbl_ipcr_chair_review_items ri2 ON ri2.review_id = cr2.review_id AND ri2.draft_id = dt2.draft_id
                LEFT JOIN tbl_ipcr_ret_review rr2 ON rr2.emp_id = ep.emp_id AND rr2.term_id = mi2.term_id
                LEFT JOIN tbl_ipcr_ret_review_items rri2 ON rri2.review_id = rr2.review_id AND rri2.indicator_id = dt2.indicator_id
                WHERE dt2.emp_id = ep.emp_id AND mi2.term_id = %s
                  AND (
                      (tc2.category_name IN ('A. Instructions', 'Support Functions') AND COALESCE(ri2.reviewed_quantity, dt2.proposed_quantity) > 0)
                      OR (tc2.category_name IN ('A. Research', 'B. Extension Services / Training / Advisory') AND COALESCE(rri2.reviewed_quantity, dt2.proposed_quantity) > 0)
                      OR (tc2.category_name NOT IN ('A. Instructions', 'Support Functions', 'A. Research', 'B. Extension Services / Training / Advisory') AND dt2.proposed_quantity > 0)
                  )
            ) AS target_count,
            CASE 
                WHEN (SELECT COUNT(*) FROM tbl_committed_targets ct 
                      JOIN tbl_master_indicators mi2 ON ct.indicator_id = mi2.indicator_id 
                      WHERE ct.emp_id = ep.emp_id AND mi2.term_id = %s AND ct.assigned_quantity > 0) > 0 THEN 'Locked'
                ELSE MAX(dt.review_status)
            END AS review_status,
            cr.review_id,
            cr.overall_remarks,
            cr.reviewed_at
        FROM tbl_draft_targets dt
        JOIN tbl_master_indicators mi ON dt.indicator_id = mi.indicator_id
        JOIN tbl_employee_profiles ep ON dt.emp_id = ep.emp_id
        LEFT JOIN tbl_ipcr_chair_review cr
            ON cr.emp_id = dt.emp_id AND cr.term_id = mi.term_id
        WHERE mi.term_id = %s
          AND ep.specialization = %s
          AND ep.designation = 'Regular Faculty'
          AND dt.review_status IN ('Pending Review', 'Waiting for Approval', 'Approved', 'Returned')
          AND (cr.overall_status IS NULL OR cr.overall_status IN ('Pending', 'Rejected'))
          AND NOT EXISTS (
              SELECT 1 FROM tbl_committed_targets ct 
              JOIN tbl_master_indicators mi2 ON ct.indicator_id = mi2.indicator_id 
              WHERE ct.emp_id = ep.emp_id AND mi2.term_id = %s AND ct.assigned_quantity > 0
          )
        GROUP BY ep.emp_id, ep.first_name, ep.last_name,
                 ep.academic_rank, ep.specialization,
                 cr.review_id, cr.overall_status, cr.overall_remarks, cr.reviewed_at
        ORDER BY ep.last_name, ep.first_name
    """
    cursor.execute(query, (term_id, term_id, term_id, specialization, term_id))
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def get_locked_faculty_ipcrs(cursor, specialization, term_id):
    """
    Returns all faculty members under `specialization` who have either:
    - Locked/committed their IPCR (tbl_committed_targets rows exist), OR
    - Been approved by the Program Chair but not yet locked.
    """
    query = """
        SELECT
            ep.emp_id,
            CONCAT(ep.first_name, ' ', ep.last_name) AS faculty_name,
            ep.academic_rank,
            ep.specialization,
            (SELECT COUNT(*) FROM tbl_committed_targets ct 
             JOIN tbl_master_indicators mi2 ON ct.indicator_id = mi2.indicator_id 
             WHERE ct.emp_id = ep.emp_id AND mi2.term_id = %s AND ct.assigned_quantity > 0) AS target_count,
            CASE
                WHEN (SELECT COUNT(*) FROM tbl_committed_targets ct 
                      JOIN tbl_master_indicators mi2 ON ct.indicator_id = mi2.indicator_id 
                      WHERE ct.emp_id = ep.emp_id AND mi2.term_id = %s AND ct.assigned_quantity > 0) > 0
                THEN 'Locked'
                ELSE 'Approved'
            END AS review_status,
            cr.review_id,
            cr.overall_remarks,
            cr.reviewed_at
        FROM tbl_employee_profiles ep
        LEFT JOIN tbl_ipcr_chair_review cr
            ON cr.emp_id = ep.emp_id AND cr.term_id = %s
        WHERE ep.specialization = %s
          AND ep.designation = 'Regular Faculty'
          AND cr.overall_status = 'Approved'
        GROUP BY ep.emp_id, ep.first_name, ep.last_name,
                 ep.academic_rank, ep.specialization,
                 cr.review_id, cr.overall_remarks, cr.reviewed_at
        ORDER BY ep.last_name, ep.first_name
    """
    cursor.execute(query, (term_id, term_id, term_id, specialization))
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def get_or_create_chair_review(conn, cursor, emp_id, term_id, chair_emp_id):
    """
    Fetches an existing review record for emp_id + term_id, or creates one
    and pre-populates tbl_ipcr_chair_review_items by copying from tbl_draft_targets.
    Returns the review_id.
    """
    # Check for existing review
    cursor.execute(
        "SELECT review_id FROM tbl_ipcr_chair_review WHERE emp_id = %s AND term_id = %s",
        (emp_id, term_id)
    )
    existing = cursor.fetchone()
    if existing:
        review_id = existing[0]
        # Sync: Insert any draft targets that are missing from review items
        cursor.execute(
            """
            INSERT INTO tbl_ipcr_chair_review_items
                (review_id, draft_id, indicator_id, original_quantity, reviewed_quantity)
            SELECT %s, dt.draft_id, dt.indicator_id, dt.proposed_quantity, dt.proposed_quantity
            FROM tbl_draft_targets dt
            JOIN tbl_master_indicators mi ON dt.indicator_id = mi.indicator_id
            LEFT JOIN tbl_ipcr_chair_review_items ri ON ri.review_id = %s AND ri.draft_id = dt.draft_id
            WHERE dt.emp_id = %s AND mi.term_id = %s AND dt.review_status IN ('Pending Review', 'Waiting for Approval', 'Approved') AND ri.item_id IS NULL
            """,
            (review_id, review_id, emp_id, term_id)
        )
        # Sync RET target quantities to match the finalized RET-approved quantities
        cursor.execute(
            """
            UPDATE tbl_ipcr_chair_review_items ri
            JOIN tbl_draft_targets dt ON ri.draft_id = dt.draft_id
            JOIN tbl_master_indicators mi ON dt.indicator_id = mi.indicator_id
            JOIN tbl_target_categories tc ON mi.category_id = tc.category_id
            SET ri.original_quantity = dt.proposed_quantity,
                ri.reviewed_quantity = dt.proposed_quantity
            WHERE ri.review_id = %s
              AND tc.category_name IN ('A. Research', 'B. Extension Services / Training / Advisory')
            """,
            (review_id,)
        )
        conn.commit()
        return review_id

    # Create the review header
    cursor.execute(
        """
        INSERT INTO tbl_ipcr_chair_review (emp_id, term_id, chair_emp_id, overall_status)
        VALUES (%s, %s, %s, 'Pending')
        """,
        (emp_id, term_id, chair_emp_id)
    )
    review_id = cursor.lastrowid

    # Pre-populate items from tbl_draft_targets
    cursor.execute(
        """
        SELECT dt.draft_id, dt.indicator_id, dt.proposed_quantity
        FROM tbl_draft_targets dt
        JOIN tbl_master_indicators mi ON dt.indicator_id = mi.indicator_id
        WHERE dt.emp_id = %s AND mi.term_id = %s AND dt.review_status IN ('Pending Review', 'Waiting for Approval', 'Approved')
        """,
        (emp_id, term_id)
    )
    draft_rows = cursor.fetchall()

    for draft_id, indicator_id, proposed_qty in draft_rows:
        cursor.execute(
            """
            INSERT INTO tbl_ipcr_chair_review_items
                (review_id, draft_id, indicator_id, original_quantity, reviewed_quantity)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (review_id, draft_id, indicator_id, proposed_qty, proposed_qty)
        )

    conn.commit()
    return review_id


def get_review_items(cursor, review_id):
    """
    Returns all items for a given review_id, joined with indicator descriptions,
    category names, and draft review statuses.
    """
    query = """
        SELECT
            ri.item_id,
            ri.draft_id,
            ri.indicator_id,
            ri.original_quantity,
            ri.reviewed_quantity,
            ri.item_remarks,
            COALESCE(dt.target_description, mi.indicator_description) AS indicator_description,
            dt.target_deadline,
            tc.category_name,
            dt.review_status AS draft_status
        FROM tbl_ipcr_chair_review_items ri
        JOIN tbl_master_indicators mi ON ri.indicator_id = mi.indicator_id
        JOIN tbl_target_categories tc ON mi.category_id = tc.category_id
        JOIN tbl_draft_targets dt ON ri.draft_id = dt.draft_id
        WHERE ri.review_id = %s
          AND (
              tc.category_name NOT IN ('A. Research', 'B. Extension Services / Training / Advisory')
              OR (tc.category_name IN ('A. Research', 'B. Extension Services / Training / Advisory') AND dt.proposed_quantity > 0)
          )
        ORDER BY tc.category_name, mi.indicator_id
    """
    cursor.execute(query, (review_id,))
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def update_review_item(conn, cursor, item_id, reviewed_quantity, item_remarks):
    """
    Updates a single review item's reviewed quantity and optional remark.
    The original tbl_draft_targets row is never modified.
    """
    try:
        cursor.execute(
            """
            UPDATE tbl_ipcr_chair_review_items
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


def save_chair_review_items(cursor, conn, review_id, items):
    """
    Batch save all Program Chair review item changes (quantities + remarks).
    """
    try:
        for item in items:
            item_id = item.get('item_id')
            reviewed_qty = item.get('reviewed_quantity', 0)
            item_remarks = item.get('item_remarks', '')

            cursor.execute(
                """
                UPDATE tbl_ipcr_chair_review_items
                SET reviewed_quantity = %s, item_remarks = %s
                WHERE item_id = %s
                """,
                (reviewed_qty, item_remarks if item_remarks else None, item_id)
            )
        conn.commit()
        return True, "Review items saved successfully."
    except Exception as e:
        conn.rollback()
        return False, str(e)


def decide_chair_review(conn, cursor, review_id, action, overall_remarks):
    """
    Sets overall_status to 'Approved' or 'Rejected' on the review header.
    If rejected, flips the related tbl_draft_targets rows back to 'Returned'
    so the faculty member can see the returned status and re-submit.
    """
    try:
        new_status = 'Approved' if action == 'approve' else 'Rejected'

        cursor.execute(
            """
            UPDATE tbl_ipcr_chair_review
            SET overall_status = %s,
                overall_remarks = %s,
                reviewed_at = %s
            WHERE review_id = %s
            """,
            (new_status, overall_remarks, datetime.now(), review_id)
        )

        # Get the emp_id and term_id for this review
        cursor.execute(
            "SELECT emp_id, term_id FROM tbl_ipcr_chair_review WHERE review_id = %s",
            (review_id,)
        )
        row = cursor.fetchone()
        if row:
            emp_id, term_id = row
            if action == 'reject':
                cursor.execute(
                    """
                    UPDATE tbl_draft_targets dt
                    JOIN tbl_master_indicators mi ON dt.indicator_id = mi.indicator_id
                    JOIN tbl_target_categories tc ON mi.category_id = tc.category_id
                    SET dt.review_status = 'Returned'
                    WHERE dt.emp_id = %s 
                      AND mi.term_id = %s
                      AND tc.category_name IN ('A. Instructions', 'Support Functions')
                    """,
                    (emp_id, term_id)
                )
            elif action == 'approve':
                cursor.execute(
                    """
                    UPDATE tbl_draft_targets dt
                    JOIN tbl_master_indicators mi ON dt.indicator_id = mi.indicator_id
                    JOIN tbl_ipcr_chair_review cr ON dt.emp_id = cr.emp_id AND cr.term_id = mi.term_id
                    JOIN tbl_ipcr_chair_review_items ri ON ri.review_id = cr.review_id AND ri.draft_id = dt.draft_id
                    SET dt.proposed_quantity = ri.reviewed_quantity
                    WHERE dt.emp_id = %s AND mi.term_id = %s
                    """,
                    (emp_id, term_id)
                )

        conn.commit()
        msg = "IPCR successfully approved." if action == 'approve' else "IPCR successfully returned to faculty."
        return True, msg
    except Exception as e:
        conn.rollback()
        return False, str(e)


def lock_and_commit_ipcr(conn, cursor, emp_id, term_id):
    try:
        cursor.execute(
            "SELECT overall_status FROM tbl_ipcr_chair_review WHERE emp_id = %s AND term_id = %s",
            (emp_id, term_id)
        )
        review_row = cursor.fetchone()
        if not review_row or review_row[0] != 'Approved':
            return False, "Your IPCR must be approved by the Program Chair before locking."

        cursor.execute(
            """
            SELECT dt.indicator_id, COALESCE(ri.reviewed_quantity, dt.proposed_quantity), dt.target_description, dt.target_deadline
            FROM tbl_draft_targets dt
            JOIN tbl_master_indicators mi ON dt.indicator_id = mi.indicator_id
            LEFT JOIN tbl_ipcr_chair_review cr ON cr.emp_id = dt.emp_id AND cr.term_id = mi.term_id
            LEFT JOIN tbl_ipcr_chair_review_items ri ON ri.review_id = cr.review_id AND ri.draft_id = dt.draft_id
            WHERE dt.emp_id = %s AND mi.term_id = %s
            """,
            (emp_id, term_id)
        )
        drafts = cursor.fetchall()

        if not drafts:
            return False, "No draft targets found to commit."

        cursor.execute(
            """
            DELETE ct FROM tbl_committed_targets ct
            JOIN tbl_master_indicators mi ON ct.indicator_id = mi.indicator_id
            WHERE ct.emp_id = %s AND mi.term_id = %s
            """,
            (emp_id, term_id)
        )

        for indicator_id, qty, target_desc, target_dead in drafts:
            if qty > 0:
                cursor.execute(
                    """
                    INSERT INTO tbl_committed_targets (emp_id, indicator_id, assigned_quantity, status, target_description, target_deadline)
                    VALUES (%s, %s, %s, 'Approved', %s, %s)
                    """,
                    (emp_id, indicator_id, qty, target_desc, target_dead)
                )

        cursor.execute(
            """
            UPDATE tbl_draft_targets dt
            JOIN tbl_master_indicators mi ON dt.indicator_id = mi.indicator_id
            SET dt.review_status = 'Approved'
            WHERE dt.emp_id = %s AND mi.term_id = %s
            """,
            (emp_id, term_id)
        )

        conn.commit()
        return True, "IPCR successfully locked and committed to evaluation targets."
    except Exception as e:
        conn.rollback()
        return False, str(e)


def get_program_chair_evidence_faculty(cursor, specialization, term_id):
    from app.models.connection import timed_query
    query = """
        SELECT ep.emp_id, ep.first_name, ep.last_name, ep.academic_rank, ep.specialization,
               COUNT(DISTINCT ct.target_id) as total_targets,
               SUM(CASE WHEN ct.actual_quantity >= ct.assigned_quantity AND ct.assigned_quantity > 0 THEN 1 ELSE 0 END) as met_targets,
               MAX(CASE WHEN ct.status IN ('Submitted', 'Pending Verification', 'Verified') THEN 1 ELSE 0 END) as has_submitted
        FROM tbl_employee_profiles ep
        JOIN tbl_committed_targets ct ON ep.emp_id = ct.emp_id
        JOIN tbl_master_indicators mi ON ct.indicator_id = mi.indicator_id
        WHERE ep.specialization = %s AND mi.term_id = %s
        GROUP BY ep.emp_id, ep.first_name, ep.last_name, ep.academic_rank, ep.specialization
        HAVING MAX(CASE WHEN ct.status IN ('Submitted', 'Pending Verification', 'Verified') THEN 1 ELSE 0 END) = 1
        ORDER BY ep.last_name, ep.first_name
    """
    rows = timed_query(cursor, query, (specialization, term_id), label="get_program_chair_evidence_faculty")
    for r in rows:
        r['evidence_status'] = 'Submitted'
    return rows

