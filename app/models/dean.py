def get_existing_cascaded_quotas(cursor, term_id):
    from app.models.connection import timed_query
    query = """
        SELECT cq.*, mi.indicator_description, tc.category_name
        FROM tbl_cascaded_quotas cq
        JOIN tbl_master_indicators mi ON cq.indicator_id = mi.indicator_id
        JOIN tbl_target_categories tc ON mi.category_id = tc.category_id
        WHERE cq.term_id = %s
        ORDER BY mi.indicator_id
    """
    return timed_query(cursor, query, (term_id,), label="get_existing_cascaded_quotas")


def get_dean_dashboard_kpis(cursor, term_id):
    """
    Consolidated KPI query — replaces 3 separate round-trips
    (get_overall_completion + get_pending_approvals_count + get_top_performing_department)
    into a single query.
    """
    query = """
        SELECT
            COALESCE(
                ROUND(
                    (SUM(CASE WHEN ts.status = 'Approved' THEN 1 ELSE 0 END) 
                     / NULLIF(COUNT(*), 0)) * 100
                ), 0
            ) AS completion_rate,
            (SELECT COUNT(*) FROM tbl_final_scores fs2
             WHERE fs2.term_id = %s AND fs2.dean_approval_status = 'Pending') AS pending_count,
            COALESCE(
                (SELECT ep2.assigned_program
                 FROM tbl_final_scores fs3
                 JOIN tbl_employee_profiles ep2 ON fs3.emp_id = ep2.emp_id
                 WHERE fs3.term_id = %s AND fs3.dean_approval_status = 'Approved'
                 GROUP BY ep2.assigned_program
                 ORDER BY AVG(fs3.final_score) DESC
                 LIMIT 1),
                'N/A'
            ) AS top_dept
        FROM tbl_committed_targets ts
        JOIN tbl_master_indicators mi ON ts.indicator_id = mi.indicator_id
        WHERE mi.term_id = %s
    """
    from app.models.connection import timed_query
    result = timed_query(cursor, query, (term_id, term_id, term_id), label="dean_dashboard_kpis")
    if result:
        return result[0]['completion_rate'], result[0]['pending_count'], result[0]['top_dept']
    return 0, 0, "N/A"


def get_pending_final_approvals(cursor, term_id):
    from app.models.connection import timed_query
    query = """
        SELECT 
            fs.score_id,
            ep.emp_id,
            CONCAT(ep.first_name, ' ', ep.last_name) as faculty_name,
            ep.assigned_program as department,
            fs.final_score,
            fs.adjectival_rating,
            fs.dean_approval_status
        FROM tbl_final_scores fs
        JOIN tbl_employee_profiles ep ON fs.emp_id = ep.emp_id
        WHERE fs.term_id = %s AND fs.dean_approval_status = 'Pending'
        ORDER BY ep.last_name ASC
    """
    return timed_query(cursor, query, (term_id,), label="get_pending_final_approvals")


def save_cascaded_quotas(cursor, connection, term_id, quotas_data):
    try:
        cursor.execute("DELETE FROM tbl_cascaded_quotas WHERE term_id = %s", (term_id,))

        for quota in quotas_data:
            cursor.execute("""
                INSERT INTO tbl_cascaded_quotas (term_id, indicator_id, total_target_value, assigned_to_role)
                VALUES (%s, %s, %s, %s)
            """, (term_id, quota['indicator_id'], quota['total_target'], quota['assigned_role']))

        connection.commit()
        return True, "Quotas cascaded successfully!"
    except Exception as e:
        connection.rollback()
        return False, f"Error saving quotas: {str(e)}"


def update_dean_approval_status(cursor, connection, score_ids, new_status):
    try:
        placeholders = ','.join(['%s'] * len(score_ids))
        cursor.execute(f"""
            UPDATE tbl_final_scores 
            SET dean_approval_status = %s 
            WHERE score_id IN ({placeholders})
        """, [new_status] + score_ids)
        connection.commit()
        return True, f"Successfully updated {cursor.rowcount} IPCR(s)"
    except Exception as e:
        connection.rollback()
        return False, f"Error updating approvals: {str(e)}"


# ──────────────────────────────────────────────
# Draft IPCR Review (Designated Faculty) — Program Chair UX style
# Requires tables:
#   tbl_ipcr_dean_review(review_id, emp_id, term_id, dean_id, overall_status, overall_remarks, reviewed_at)
#   tbl_ipcr_dean_review_items(item_id, review_id, draft_id, indicator_id, original_quantity, reviewed_quantity, item_remarks)
# ──────────────────────────────────────────────

def get_designated_draft_submissions(cursor, term_id):
    """
    Get all designated faculty who have submitted draft IPCRs,
    grouped by faculty with summary info.
    """
    from app.models.connection import timed_query
    query = """
        SELECT 
            dt.emp_id,
            CONCAT(ep.first_name, ' ', ep.last_name) AS faculty_name,
            ep.academic_rank,
            ep.assigned_program,
            ep.designation,
            COUNT(DISTINCT dt.draft_id) AS total_targets,
            COALESCE(MAX(dr.overall_status), 'Pending') AS review_status
        FROM tbl_draft_targets dt
        JOIN tbl_employee_profiles ep ON dt.emp_id = ep.emp_id
        JOIN tbl_master_indicators mi ON dt.indicator_id = mi.indicator_id
        JOIN tbl_system_access sa ON dt.emp_id = sa.emp_id
        LEFT JOIN tbl_ipcr_dean_review dr ON dr.emp_id = dt.emp_id AND dr.term_id = %s
        WHERE mi.term_id = %s
          AND sa.system_role = 'DESIGNATED_FACULTY'
          AND mi.is_custom IN (0, 1)
        GROUP BY dt.emp_id, ep.first_name, ep.last_name, ep.academic_rank, ep.assigned_program, ep.designation, dr.overall_status
        ORDER BY ep.last_name ASC
    """
    return timed_query(cursor, query, (term_id, term_id), label="get_designated_draft_submissions")


def get_or_create_dean_review(conn, cursor, emp_id, term_id, dean_id):
    """
    Fetches existing tbl_ipcr_dean_review for emp_id+term_id, or creates one
    and pre-populates items from tbl_draft_targets + all master indicators.
    Returns review_id.
    """
    cursor.execute(
        "SELECT review_id FROM tbl_ipcr_dean_review WHERE emp_id = %s AND term_id = %s",
        (emp_id, term_id)
    )
    existing = cursor.fetchone()
    if existing:
        review_id = existing[0]
        # Sync: add any new draft targets that aren't in review items yet
        cursor.execute("""
            INSERT IGNORE INTO tbl_ipcr_dean_review_items
                (review_id, draft_id, indicator_id, original_quantity, reviewed_quantity)
            SELECT %s, dt.draft_id, dt.indicator_id, dt.proposed_quantity, dt.proposed_quantity
            FROM tbl_draft_targets dt
            WHERE dt.emp_id = %s
              AND dt.draft_id NOT IN (
                  SELECT COALESCE(draft_id, 0) FROM tbl_ipcr_dean_review_items WHERE review_id = %s
              )
        """, (review_id, emp_id, review_id))
        conn.commit()
        return review_id

    # Create new review
    cursor.execute("""
        INSERT INTO tbl_ipcr_dean_review (emp_id, term_id, dean_id, overall_status)
        VALUES (%s, %s, %s, 'Pending')
    """, (emp_id, term_id, dean_id))
    review_id = cursor.lastrowid

    # Pre-populate review items from draft targets
    cursor.execute("""
        INSERT INTO tbl_ipcr_dean_review_items
            (review_id, draft_id, indicator_id, original_quantity, reviewed_quantity)
        SELECT %s, dt.draft_id, dt.indicator_id, dt.proposed_quantity, dt.proposed_quantity
        FROM tbl_draft_targets dt
        WHERE dt.emp_id = %s
    """, (review_id, emp_id))
    conn.commit()
    return review_id


def get_dean_review_items(cursor, review_id):
    """Get all review items with indicator + category details, target description, deadline, and core flags."""
    from app.models.connection import timed_query
    query = """
        SELECT
            dri.item_id,
            dri.draft_id,
            dri.indicator_id,
            dri.original_quantity,
            dri.reviewed_quantity,
            dri.item_remarks,
            mi.indicator_description,
            tc.category_name,
            mi.efficiency_type,
            mi.is_custom,
            COALESCE(dt.target_description, da.custom_description, mi.indicator_description) as target_description,
            COALESCE(dt.target_deadline, da.target_deadline, '1 Semester') as target_deadline,
            CASE WHEN da.allocation_id IS NOT NULL THEN 1 ELSE 0 END as is_cascaded
        FROM tbl_ipcr_dean_review_items dri
        JOIN tbl_ipcr_dean_review dr ON dri.review_id = dr.review_id
        JOIN tbl_master_indicators mi ON dri.indicator_id = mi.indicator_id
        LEFT JOIN tbl_target_categories tc ON mi.category_id = tc.category_id
        LEFT JOIN tbl_draft_targets dt ON dri.draft_id = dt.draft_id
        LEFT JOIN tbl_draft_allocation da ON da.emp_id = dr.emp_id AND da.indicator_id = dri.indicator_id
        WHERE dri.review_id = %s
        ORDER BY tc.category_name, mi.indicator_id
    """
    items = timed_query(cursor, query, (review_id,), label="get_dean_review_items")
    for item in items:
        if item.get('category_name') == 'Custom Target Items':
            item['category_name'] = 'Support Functions'
        is_tl = 'Teaching Load' in (item.get('indicator_description') or '')
        is_cascaded = bool(item.get('is_cascaded'))
        item['is_core'] = is_tl or is_cascaded
        item['is_cascaded'] = is_cascaded
    return items



def get_available_master_indicators(cursor, term_id):
    """Get selectable indicators relevant to designated faculty: Instructions, Support, and Custom."""
    from app.models.connection import timed_query
    query = """
        SELECT mi.indicator_id, mi.indicator_description, tc.category_name, mi.efficiency_type, mi.is_custom
        FROM tbl_master_indicators mi
        LEFT JOIN tbl_target_categories tc ON mi.category_id = tc.category_id
        WHERE mi.term_id = %s
          AND (mi.is_custom = 1 OR tc.category_name IN ('A. Instructions', 'Support Functions'))
        ORDER BY tc.category_name, mi.indicator_id
    """
    return timed_query(cursor, query, (term_id,), label="get_available_master_indicators")


def save_dean_review_items(cursor, conn, review_id, items):
    """
    Batch save all review item changes (quantities + remarks).
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
                    "SELECT emp_id, term_id FROM tbl_ipcr_dean_review WHERE review_id = %s",
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
                    INSERT INTO tbl_ipcr_dean_review_items
                        (review_id, draft_id, indicator_id, original_quantity, reviewed_quantity, item_remarks)
                    VALUES (%s, %s, %s, -1, %s, %s)
                """, (review_id, new_draft_id, indicator_id, reviewed_qty, item_remarks))
            else:
                # Existing item — update quantities and remarks
                item_id = item.get('item_id')
                if not item_id:
                    continue
                cursor.execute("""
                    UPDATE tbl_ipcr_dean_review_items
                    SET reviewed_quantity = %s, item_remarks = %s
                    WHERE item_id = %s
                """, (reviewed_qty, item_remarks, item_id))

                # Sync back to tbl_draft_targets so designated faculty sees the change
                cursor.execute("""
                    UPDATE tbl_draft_targets dt
                    JOIN tbl_ipcr_dean_review_items dri ON dt.draft_id = dri.draft_id
                    SET dt.proposed_quantity = %s
                    WHERE dri.item_id = %s
                """, (reviewed_qty, item_id))

        conn.commit()
        return True, "Review items saved successfully."
    except Exception as e:
        conn.rollback()
        return False, str(e)


def submit_dean_review_decision(cursor, conn, review_id, action, overall_remarks):
    """
    Finalize the Dean's review: approve or reject.
    Updates both tbl_ipcr_dean_review and tbl_draft_targets.
    """
    try:
        cursor.execute("""
            UPDATE tbl_ipcr_dean_review
            SET overall_status = %s, overall_remarks = %s, reviewed_at = NOW()
            WHERE review_id = %s
        """, (action, overall_remarks, review_id))

        # Sync decision to tbl_draft_targets
        cursor.execute("""
            UPDATE tbl_draft_targets dt
            JOIN tbl_ipcr_dean_review_items dri ON dt.draft_id = dri.draft_id
            JOIN tbl_ipcr_dean_review dr ON dri.review_id = dr.review_id
            SET dt.review_status = %s,
                dt.proposed_quantity = dri.reviewed_quantity
            WHERE dr.review_id = %s
        """, (action, review_id))

        # Process 6: If approved, commit to tbl_committed_targets
        if action == 'Approved':
            # Get emp_id and term_id
            cursor.execute("SELECT emp_id, term_id FROM tbl_ipcr_dean_review WHERE review_id = %s", (review_id,))
            review_info = cursor.fetchone()
            if review_info:
                emp_id, term_id = review_info[0], review_info[1]
                
                # Fetch approved items with descriptions and deadlines
                cursor.execute("""
                    SELECT dt.indicator_id, COALESCE(dri.reviewed_quantity, dt.proposed_quantity), dt.target_description, dt.target_deadline
                    FROM tbl_draft_targets dt
                    JOIN tbl_ipcr_dean_review_items dri ON dt.draft_id = dri.draft_id
                    WHERE dri.review_id = %s
                """, (review_id,))
                approved_items = cursor.fetchall()
                
                # Delete existing committed targets
                cursor.execute("""
                    DELETE FROM tbl_committed_targets 
                    WHERE emp_id = %s AND indicator_id IN (
                        SELECT indicator_id FROM tbl_master_indicators WHERE term_id = %s
                    )
                """, (emp_id, term_id))
                
                # Insert into tbl_committed_targets with target_description and target_deadline
                for indicator_id, qty, target_desc, target_dead in approved_items:
                    cursor.execute("""
                        INSERT INTO tbl_committed_targets (emp_id, indicator_id, assigned_quantity, status, actual_quantity, target_description, target_deadline)
                        VALUES (%s, %s, %s, 'Approved', 0, %s, %s)
                    """, (emp_id, indicator_id, qty, target_desc, target_dead))


        conn.commit()
        return True, f"Draft IPCR {action.lower()} successfully."
    except Exception as e:
        conn.rollback()
        return False, str(e)


# ──────────────────────────────────────────────
# College-Wide Target Assignment (Designated Faculty) Mika
# ──────────────────────────────────────────────

def get_designated_faculty_list(cursor):
    """Get all active designated faculty members via system_access role."""
    from app.models.connection import timed_query
    query = """
        SELECT ep.emp_id, ep.first_name, ep.last_name, ep.academic_rank, ep.assigned_program, ep.specialization, ep.designation
        FROM tbl_employee_profiles ep
        JOIN tbl_system_access sa ON ep.emp_id = sa.emp_id
        WHERE sa.system_role = 'DESIGNATED_FACULTY' AND ep.leave_status = 'Active'
        ORDER BY ep.last_name ASC, ep.first_name ASC
    """
    return timed_query(cursor, query, label="get_designated_faculty_list")


def get_college_wide_cascaded_quotas(cursor, term_id):
    """
    Get indicators that have College-Wide quotas set in tbl_cascaded_quotas.
    """
    from app.models.connection import timed_query
    query = """
        SELECT cq.*, mi.indicator_description, tc.category_name, mi.efficiency_type
        FROM tbl_cascaded_quotas cq
        JOIN tbl_master_indicators mi ON cq.indicator_id = mi.indicator_id
        JOIN tbl_target_categories tc ON mi.category_id = tc.category_id
        WHERE cq.term_id = %s AND cq.assigned_to_role = 'College-Wide' AND cq.total_target_value > 0
        ORDER BY tc.category_name, mi.indicator_id
    """
    return timed_query(cursor, query, (term_id,), label="get_college_wide_cascaded_quotas")


def get_designated_faculty_assignments(cursor, term_id, emp_id):
    """
    Get existing target assignments for a specific designated faculty member
    from tbl_draft_allocation.
    """
    from app.models.connection import timed_query
    query = """
        SELECT da.allocation_id, da.indicator_id, da.assigned_quantity,
               mi.indicator_description, tc.category_name
        FROM tbl_draft_allocation da
        JOIN tbl_master_indicators mi ON da.indicator_id = mi.indicator_id
        LEFT JOIN tbl_target_categories tc ON mi.category_id = tc.category_id
        WHERE mi.term_id = %s AND da.emp_id = %s
        ORDER BY tc.category_name, mi.indicator_id
    """
    return timed_query(cursor, query, (term_id, emp_id), label="get_designated_faculty_assignments")


def get_designated_faculty_assignments_batch(cursor, term_id, emp_ids):
    """
    Get target assignments for MULTIPLE designated faculty members in ONE query.
    Returns a dict: {emp_id: {indicator_id: assigned_quantity, ...}, ...}
    """
    if not emp_ids:
        return {}

    from app.models.connection import timed_query
    placeholders = ','.join(['%s'] * len(emp_ids))
    query = f"""
        SELECT da.emp_id, da.indicator_id, da.assigned_quantity
        FROM tbl_draft_allocation da
        JOIN tbl_master_indicators mi ON da.indicator_id = mi.indicator_id
        WHERE mi.term_id = %s AND da.emp_id IN ({placeholders})
    """
    rows = timed_query(cursor, query, [term_id] + emp_ids, label="get_designated_faculty_assignments_batch")

    result = {}
    for row in rows:
        emp_id = row['emp_id']
        if emp_id not in result:
            result[emp_id] = {}
        result[emp_id][row['indicator_id']] = row['assigned_quantity']
    return result


def save_designated_faculty_assignment(cursor, conn, term_id, emp_id, indicator_id, quantity):
    """Save or update a target assignment for a designated faculty member in tbl_draft_allocation."""
    try:
        # Check if an assignment already exists
        cursor.execute(
            "SELECT allocation_id FROM tbl_draft_allocation WHERE emp_id = %s AND indicator_id = %s",
            (emp_id, indicator_id)
        )
        existing = cursor.fetchone()
        if existing:
            cursor.execute(
                "UPDATE tbl_draft_allocation SET assigned_quantity = %s WHERE allocation_id = %s",
                (quantity, existing[0])
            )
        else:
            cursor.execute(
                "INSERT INTO tbl_draft_allocation (emp_id, indicator_id, assigned_quantity) VALUES (%s, %s, %s)",
                (emp_id, indicator_id, quantity)
            )
        conn.commit()
        return True, "Assignment saved successfully."
    except Exception as e:
        conn.rollback()
        return False, f"Error saving assignment: {str(e)}"


def get_college_wide_allocations_tracker(cursor, term_id):
    """
    Get actual target distributions (from tbl_draft_targets) for indicators
    that have a College-Wide quota set in tbl_cascaded_quotas.
    """
    from app.models.connection import timed_query
    query = """
        SELECT 
            dt.indicator_id,
            dt.emp_id,
            CONCAT(ep.first_name, ' ', ep.last_name) AS faculty_name,
            ep.assigned_program,
            dt.proposed_quantity,
            dt.review_status
        FROM tbl_draft_targets dt
        JOIN tbl_employee_profiles ep ON dt.emp_id = ep.emp_id
        JOIN tbl_system_access sa ON ep.emp_id = sa.emp_id
        WHERE sa.system_role = 'DESIGNATED_FACULTY'
          AND ep.leave_status = 'Active'
          AND dt.indicator_id IN (
              SELECT indicator_id 
              FROM tbl_cascaded_quotas 
              WHERE term_id = %s AND assigned_to_role = 'College-Wide' AND total_target_value > 0
          )
        ORDER BY ep.last_name, ep.first_name
    """
    return timed_query(cursor, query, (term_id,), label="get_college_wide_allocations_tracker")
