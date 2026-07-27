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
        SELECT emp_id, first_name, last_name, academic_rank, leave_status
        FROM tbl_employee_profiles
        WHERE specialization = %s AND leave_status = 'Active' AND designation = 'Regular Faculty'
    """
    return timed_query(cursor, query, (specialization,), label="get_specialization_faculty")


def get_assigned_quantity_batch(cursor, term_id, indicator_ids, faculty_ids):
    """
    Get assigned quantities for MULTIPLE indicators in ONE query.
    Returns dict: {indicator_id: assigned_quantity}
    Replaces N+1 get_assigned_quantity() calls.
    """
    if not faculty_ids or not indicator_ids:
        return {}
    from app.models.connection import timed_query
    fac_placeholders = ','.join(['%s'] * len(faculty_ids))
    ind_placeholders = ','.join(['%s'] * len(indicator_ids))
    query = f"""
        SELECT da.indicator_id, da.assigned_quantity
        FROM tbl_draft_allocation da
        JOIN tbl_master_indicators mi ON da.indicator_id = mi.indicator_id
        WHERE mi.term_id = %s 
          AND da.indicator_id IN ({ind_placeholders})
          AND da.emp_id IN ({fac_placeholders})
        GROUP BY da.indicator_id, da.assigned_quantity
    """
    rows = timed_query(cursor, query, [term_id] + indicator_ids + faculty_ids, label="get_assigned_quantity_batch")
    result = {}
    for row in rows:
        result[row['indicator_id']] = row['assigned_quantity']
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

        for indicator_id, assigned_quantity in allocations:
            for emp_id in faculty_ids:
                # Check if an allocation record already exists in the draft staging table
                check_query = """
                    SELECT allocation_id 
                    FROM tbl_draft_allocation
                    WHERE emp_id = %s AND indicator_id = %s
                """
                cursor.execute(check_query, (emp_id, indicator_id))
                existing = cursor.fetchall()

                if existing:
                    update_query = "UPDATE tbl_draft_allocation SET assigned_quantity = %s WHERE allocation_id = %s"
                    cursor.execute(update_query, (assigned_quantity, existing[0][0]))
                else:
                    insert_query = """
                        INSERT INTO tbl_draft_allocation (emp_id, indicator_id, assigned_quantity)
                        VALUES (%s, %s, %s)
                    """
                    cursor.execute(insert_query, (emp_id, indicator_id, assigned_quantity))

        conn.commit()
        return True, "Targets distributed successfully to all faculty draft worklists."
    except Exception as e:
        conn.rollback()
        return False, str(e)


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
        JOIN tbl_employee_profiles ep ON dt.emp_id = ep.emp_id
        LEFT JOIN tbl_ipcr_chair_review cr
            ON cr.emp_id = dt.emp_id AND cr.term_id = %s
        WHERE mi.term_id = %s
          AND ep.specialization = %s
          AND ep.designation = 'Regular Faculty'
          AND dt.review_status = 'Pending Review'
          AND (cr.overall_status IS NULL OR cr.overall_status = 'Pending' OR cr.overall_status = 'Waiting for Approval')
    """
    cursor.execute(query, (term_id, term_id, specialization))
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
            COUNT(dt.draft_id)                          AS target_count,
            CASE 
                WHEN (SELECT COUNT(*) FROM tbl_committed_targets ct 
                      JOIN tbl_master_indicators mi2 ON ct.indicator_id = mi2.indicator_id 
                      WHERE ct.emp_id = ep.emp_id AND mi2.term_id = %s) > 0 THEN 'Locked'
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
              WHERE ct.emp_id = ep.emp_id AND mi2.term_id = %s
          )
        GROUP BY ep.emp_id, ep.first_name, ep.last_name,
                 ep.academic_rank, ep.specialization,
                 cr.review_id, cr.overall_status, cr.overall_remarks, cr.reviewed_at
        ORDER BY ep.last_name, ep.first_name
    """
    cursor.execute(query, (term_id, term_id, specialization, term_id))
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
             WHERE ct.emp_id = ep.emp_id AND mi2.term_id = %s) AS target_count,
            CASE
                WHEN (SELECT COUNT(*) FROM tbl_committed_targets ct 
                      JOIN tbl_master_indicators mi2 ON ct.indicator_id = mi2.indicator_id 
                      WHERE ct.emp_id = ep.emp_id AND mi2.term_id = %s) > 0
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
            mi.indicator_description,
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
            SELECT dt.indicator_id, COALESCE(ri.reviewed_quantity, dt.proposed_quantity)
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

        for indicator_id, qty in drafts:
            if qty > 0:
                cursor.execute(
                    """
                    INSERT INTO tbl_committed_targets (emp_id, indicator_id, assigned_quantity, status)
                    VALUES (%s, %s, %s, 'Approved')
                    """,
                    (emp_id, indicator_id, qty)
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
