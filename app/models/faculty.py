# Trigger reload 19
def get_faculty_assigned_targets(cursor, emp_id, term_id):
    from app.models.connection import timed_query
    
    # Sync reviewed quantities from the Program Chair review back to draft targets
    cursor.execute("""
        UPDATE tbl_draft_targets dt
        JOIN tbl_master_indicators mi ON dt.indicator_id = mi.indicator_id
        JOIN tbl_ipcr_chair_review cr ON dt.emp_id = cr.emp_id AND cr.term_id = mi.term_id
        JOIN tbl_ipcr_chair_review_items ri ON ri.review_id = cr.review_id AND ri.draft_id = dt.draft_id
        SET dt.proposed_quantity = ri.reviewed_quantity
        WHERE dt.emp_id = %s
    """, (emp_id,))
    
    # Check if this user has already submitted their targets to the review registry
    count_result = timed_query(cursor, """
        SELECT COUNT(*) as cnt FROM tbl_draft_targets dt
        JOIN tbl_master_indicators mi ON dt.indicator_id = mi.indicator_id
        WHERE dt.emp_id = %s AND mi.term_id = %s
    """, (emp_id, term_id), label="get_faculty_assigned_targets_check")
    has_submitted = count_result[0]['cnt'] > 0 if count_result else False

    if has_submitted:
        query = """
            SELECT dt.draft_id as target_id, dt.indicator_id,
                   COALESCE(
                       CASE WHEN cr.overall_status IN ('Approved', 'Rejected') THEN ri.reviewed_quantity ELSE NULL END,
                       CASE WHEN rr.overall_status IN ('Approved', 'Rejected', 'Pending') THEN rri.reviewed_quantity ELSE NULL END,
                       dt.proposed_quantity
                   ) as assigned_quantity,
                   dt.review_status as status,
                   COALESCE(dt.target_description, da.custom_description, mi.indicator_description) as indicator_description,
                   COALESCE(dt.target_deadline, da.target_deadline) as target_deadline,
                   tc.category_name,
                   ri.item_remarks as chair_item_remarks,
                   ri.reviewed_quantity as chair_reviewed_quantity,
                   rri.item_remarks as ret_item_remarks,
                   rri.reviewed_quantity as ret_reviewed_quantity
            FROM tbl_draft_targets dt
            JOIN tbl_master_indicators mi ON dt.indicator_id = mi.indicator_id
            LEFT JOIN tbl_target_categories tc ON mi.category_id = tc.category_id
            LEFT JOIN tbl_draft_allocation da ON da.emp_id = dt.emp_id AND da.indicator_id = dt.indicator_id
            LEFT JOIN tbl_ipcr_chair_review cr
                ON cr.emp_id = dt.emp_id AND cr.term_id = mi.term_id
            LEFT JOIN tbl_ipcr_chair_review_items ri
                ON ri.review_id = cr.review_id AND ri.draft_id = dt.draft_id
            LEFT JOIN tbl_ipcr_ret_review rr
                ON rr.emp_id = dt.emp_id AND rr.term_id = mi.term_id
            LEFT JOIN tbl_ipcr_ret_review_items rri
                ON rri.review_id = rr.review_id AND rri.draft_id = dt.draft_id
            WHERE dt.emp_id = %s AND mi.term_id = %s
            ORDER BY tc.category_name, mi.indicator_id
        """
    else:
        query = """
            SELECT MIN(da.allocation_id) as target_id, da.indicator_id, MAX(da.assigned_quantity) as assigned_quantity, 'Draft' as status,
                   COALESCE(MAX(da.custom_description), mi.indicator_description) as indicator_description,
                   MAX(da.target_deadline) as target_deadline,
                   tc.category_name,
                   NULL as chair_item_remarks, NULL as chair_reviewed_quantity
            FROM tbl_draft_allocation da
            JOIN tbl_master_indicators mi ON da.indicator_id = mi.indicator_id
            LEFT JOIN tbl_target_categories tc ON mi.category_id = tc.category_id
            JOIN tbl_employee_profiles ep ON da.emp_id = ep.emp_id
            WHERE ep.specialization = (SELECT specialization FROM tbl_employee_profiles WHERE emp_id = %s)
              AND mi.term_id = %s
            GROUP BY da.indicator_id, mi.indicator_description, tc.category_name
            ORDER BY tc.category_name, da.indicator_id
        """
    targets = timed_query(cursor, query, (emp_id, term_id), label="get_faculty_assigned_targets_load")
    # Filter out designated 10 hours teaching load target for Regular Faculty
    targets = [t for t in targets if '10 hours' not in str(t.get('indicator_description', '')) and '10 hrs' not in str(t.get('indicator_description', ''))]

    # Ensure mandatory default Teaching Load target (21 hours) is present
    has_teaching_load = any(
        t.get('category_name') == 'A. Instructions' and 'Teaching Load' in str(t.get('indicator_description', ''))
        for t in targets
    )
    if not has_teaching_load:
        cursor.execute("SELECT category_id FROM tbl_target_categories WHERE category_name = 'A. Instructions'")
        cat_row = cursor.fetchone()
        cat_id = cat_row[0] if cat_row else 1
        cursor.execute("""
            SELECT indicator_id FROM tbl_master_indicators
            WHERE indicator_description = '21 hours of Teaching Load' AND term_id = %s
        """, (term_id,))
        ind_row = cursor.fetchone()
        if ind_row:
            tl_ind_id = ind_row[0]
        else:
            cursor.execute("""
                INSERT INTO tbl_master_indicators (category_id, indicator_description, efficiency_type, term_id, is_custom)
                VALUES (%s, '21 hours of Teaching Load', 'Output-Based', %s, 0)
            """, (cat_id, term_id))
            tl_ind_id = cursor.lastrowid

        mandatory_target = {
            'target_id': f'tl_{tl_ind_id}',
            'indicator_id': tl_ind_id,
            'assigned_quantity': 21,
            'status': 'Draft',
            'indicator_description': '21 hours of Teaching Load',
            'target_deadline': '1 Semester',
            'category_name': 'A. Instructions',
            'chair_item_remarks': None,
            'chair_reviewed_quantity': None,
            'is_mandatory': True
        }
        targets.insert(0, mandatory_target)
    else:
        for t in targets:
            if t.get('category_name') == 'A. Instructions' and 'Teaching Load' in str(t.get('indicator_description', '')):
                t['is_mandatory'] = True
                if not t.get('assigned_quantity'):
                    t['assigned_quantity'] = 21

    return targets


def get_faculty_chair_review_status(cursor, emp_id, term_id):
    """
    Returns the Program Chair's current review record for this faculty member,
    or None if no review has been started yet.
    Used by the faculty dashboard to display the 'Returned' alert with remarks.
    """
    cursor.execute("""
        SELECT review_id, overall_status, overall_remarks, reviewed_at
        FROM tbl_ipcr_chair_review
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


def get_faculty_ret_menu(cursor, academic_rank, term_id):
    from app.models.connection import timed_query
    query = """
        SELECT r.required_selections, mi.indicator_id, mi.indicator_description, tc.category_name, rri.target_quantity
        FROM tbl_ret_rules r
        JOIN tbl_ret_rule_indicators rri ON r.rule_id = rri.rule_id
        JOIN tbl_master_indicators mi ON rri.indicator_id = mi.indicator_id
        JOIN tbl_target_categories tc ON mi.category_id = tc.category_id
        WHERE r.academic_rank = %s AND mi.term_id = %s
    """
    results = timed_query(cursor, query, (academic_rank, term_id), label="get_faculty_ret_menu")

    ret_menu = {
        'research_required': 0,
        'extension_required': 0,
        'research_indicators': [],
        'extension_indicators': []
    }

    for r in results:
        if r['category_name'] == 'A. Research':
            ret_menu['research_required'] = int(r['required_selections'])
            ret_menu['research_indicators'].append(r)
        elif r['category_name'] == 'B. Extension Services / Training / Advisory':
            ret_menu['extension_required'] = int(r['required_selections'])
            ret_menu['extension_indicators'].append(r)

    return ret_menu


def save_faculty_ret_selections(conn, cursor, emp_id, term_id, selected_indicator_ids):
    # This helper is deprecated as RET selections are processed inside the submit pipeline,
    # but we keep a dummy return for backward compatibility.
    return True, "RET selections processed."


def is_faculty_ret_eligible(cursor, emp_id, term_id):
    """
    Returns True if the faculty member is checked/enabled for RET target access in tbl_ret_faculty_access for term_id.
    """
    if not term_id:
        return False
    cursor.execute(
        "SELECT is_enabled FROM tbl_ret_faculty_access WHERE emp_id = %s AND term_id = %s",
        (emp_id, term_id)
    )
    row = cursor.fetchone()
    return bool(row and row[0] == 1)


def submit_faculty_ipcr(conn, cursor, emp_id, selected_research_targets):
    """
    selected_research_targets parameter format:
    [
        {'indicator_id': 12, 'proposed_quantity': 1},
        ...
    ]
    """
    try:
        # Check if they are resubmitting (meaning a review record already exists for the active term)
        cursor.execute("SELECT term_id FROM tbl_academic_terms WHERE is_active = 1 LIMIT 1")
        term_row = cursor.fetchone()
        active_term_id = term_row[0] if term_row else None

        is_resubmission = False
        if active_term_id:
            cursor.execute("""
                SELECT 1 FROM tbl_ipcr_chair_review 
                WHERE emp_id = %s AND term_id = %s
                LIMIT 1
            """, (emp_id, active_term_id))
            is_resubmission = cursor.fetchone() is not None

        ret_eligible = is_faculty_ret_eligible(cursor, emp_id, active_term_id)
        ret_editable = False
        if not ret_eligible:
            # Non-RET faculty bypass RET review stage completely -> target_status is immediately 'Waiting for Approval' (for Program Chair)
            target_status = 'Waiting for Approval'
        else:
            target_status = 'Waiting for Approval' if is_resubmission else 'Pending Review'
            ret_editable = True


        # 1. Sync any reviewed quantities from the chair's decision back into tbl_draft_targets FIRST
        # to preserve any adjustments made by the Program Chair on standard workloads.
        cursor.execute("""
            UPDATE tbl_draft_targets dt
            JOIN tbl_master_indicators mi ON dt.indicator_id = mi.indicator_id
            JOIN tbl_ipcr_chair_review cr ON dt.emp_id = cr.emp_id AND cr.term_id = mi.term_id
            JOIN tbl_ipcr_chair_review_items ri ON ri.review_id = cr.review_id AND ri.draft_id = dt.draft_id
            SET dt.proposed_quantity = ri.reviewed_quantity
            WHERE dt.emp_id = %s
        """, (emp_id,))

        # 2. Gather all assigned regular workloads distributed by the Program Chair for this specialization (if any)
        cursor.execute("""
            SELECT da.indicator_id, MAX(da.assigned_quantity), MAX(da.custom_description), MAX(da.target_deadline)
            FROM tbl_draft_allocation da
            JOIN tbl_employee_profiles ep ON da.emp_id = ep.emp_id
            WHERE ep.specialization = (SELECT specialization FROM tbl_employee_profiles WHERE emp_id = %s)
            GROUP BY da.indicator_id
        """, (emp_id,))
        chair_allocations = cursor.fetchall()

        # 3. Process and migrate standard workloads into tbl_draft_targets
        for ind_id, qty, cust_desc, t_dead in chair_allocations:
            cursor.execute("""
                SELECT draft_id FROM tbl_draft_targets 
                WHERE emp_id = %s AND indicator_id = %s
            """, (emp_id, ind_id))
            existing_draft = cursor.fetchone()

            if existing_draft:
                cursor.execute("""
                    UPDATE tbl_draft_targets 
                    SET proposed_quantity = %s, review_status = %s, target_description = %s, target_deadline = %s 
                    WHERE draft_id = %s
                """, (qty, target_status, cust_desc, t_dead, existing_draft[0]))
            else:
                cursor.execute("""
                    INSERT INTO tbl_draft_targets (emp_id, indicator_id, proposed_quantity, review_status, target_description, target_deadline)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (emp_id, ind_id, qty, target_status, cust_desc, t_dead))

        # Ensure mandatory default Teaching Load target (21 hours) is saved
        cursor.execute("SELECT category_id FROM tbl_target_categories WHERE category_name = 'A. Instructions'")
        cat_row = cursor.fetchone()
        cat_id = cat_row[0] if cat_row else 1
        cursor.execute("SELECT indicator_id FROM tbl_master_indicators WHERE indicator_description = '21 hours of Teaching Load' AND term_id = %s", (active_term_id,))
        tl_row = cursor.fetchone()
        if tl_row:
            tl_ind_id = tl_row[0]
        else:
            cursor.execute("INSERT INTO tbl_master_indicators (category_id, indicator_description, efficiency_type, term_id, is_custom) VALUES (%s, '21 hours of Teaching Load', 'Output-Based', %s, 0)", (cat_id, active_term_id))
            tl_ind_id = cursor.lastrowid


        cursor.execute("SELECT draft_id FROM tbl_draft_targets WHERE emp_id = %s AND indicator_id = %s", (emp_id, tl_ind_id))
        tl_draft = cursor.fetchone()
        if not tl_draft:
            cursor.execute("""
                INSERT INTO tbl_draft_targets (emp_id, indicator_id, proposed_quantity, review_status, target_description, target_deadline)
                VALUES (%s, %s, 21, %s, '21 hours of Teaching Load', '1 Semester')
            """, (emp_id, tl_ind_id, target_status))

        # 4. If this is a re-submission or non-RET submission, update status of existing standard workloads to target_status
        cursor.execute("""
            UPDATE tbl_draft_targets dt
            JOIN tbl_master_indicators mi ON dt.indicator_id = mi.indicator_id
            JOIN tbl_target_categories tc ON mi.category_id = tc.category_id
            SET dt.review_status = %s
            WHERE dt.emp_id = %s
              AND tc.category_name NOT IN ('A. Research', 'B. Extension Services / Training / Advisory')
        """, (target_status, emp_id))

        if not ret_eligible:
            # Non-RET faculty: delete any existing Research and Extension targets
            cursor.execute("""
                DELETE dt FROM tbl_draft_targets dt
                JOIN tbl_master_indicators mi ON dt.indicator_id = mi.indicator_id
                JOIN tbl_target_categories tc ON mi.category_id = tc.category_id
                WHERE dt.emp_id = %s
                  AND tc.category_name IN ('A. Research', 'B. Extension Services / Training / Advisory')
            """, (emp_id,))
        else:
            # RET-eligible faculty: check if Research & Extension targets are editable
            ret_editable = True
            if active_term_id:
                cursor.execute(
                    """
                    SELECT overall_status FROM tbl_ipcr_ret_review 
                    WHERE emp_id = %s AND term_id = %s
                    """,
                    (emp_id, active_term_id)
                )
                ret_row = cursor.fetchone()
                if ret_row:
                    ret_status = ret_row[0]
                    if ret_status in ('Approved', 'Rejected'):
                        ret_editable = False

            if ret_editable:
                # Delete existing Research and Extension targets to rewrite selections
                cursor.execute("""
                    DELETE dt FROM tbl_draft_targets dt
                    JOIN tbl_master_indicators mi ON dt.indicator_id = mi.indicator_id
                    JOIN tbl_target_categories tc ON mi.category_id = tc.category_id
                    WHERE dt.emp_id = %s
                      AND tc.category_name IN ('A. Research', 'B. Extension Services / Training / Advisory')
                """, (emp_id,))

                # Process and write selected Research/Extension targets
                for target in selected_research_targets:
                    res_ind_id = target['indicator_id']
                    
                    cursor.execute("""
                        SELECT rri.target_quantity 
                        FROM tbl_ret_rule_indicators rri
                        JOIN tbl_ret_rules r ON rri.rule_id = r.rule_id
                        JOIN tbl_employee_profiles ep ON ep.academic_rank = r.academic_rank
                        WHERE ep.emp_id = %s AND rri.indicator_id = %s
                        LIMIT 1
                    """, (emp_id, res_ind_id))
                    row = cursor.fetchone()
                    res_qty = row[0] if (row and row[0] is not None) else 1

                    cursor.execute("""
                        INSERT INTO tbl_draft_targets (emp_id, indicator_id, proposed_quantity, review_status)
                        VALUES (%s, %s, %s, %s)
                    """, (emp_id, res_ind_id, res_qty, target_status))
            else:
                if ret_status == 'Rejected':
                    cursor.execute("""
                        UPDATE tbl_draft_targets dt
                        JOIN tbl_master_indicators mi ON dt.indicator_id = mi.indicator_id
                        JOIN tbl_target_categories tc ON mi.category_id = tc.category_id
                        SET dt.review_status = %s
                        WHERE dt.emp_id = %s
                          AND tc.category_name IN ('A. Research', 'B. Extension Services / Training / Advisory')
                    """, (target_status, emp_id))

                cursor.execute("""
                    UPDATE tbl_draft_targets dt
                    JOIN tbl_master_indicators mi ON dt.indicator_id = mi.indicator_id
                    JOIN tbl_target_categories tc ON mi.category_id = tc.category_id
                    SET dt.review_status = %s
                    WHERE dt.emp_id = %s
                      AND tc.category_name IN ('A. Research', 'B. Extension Services / Training / Advisory')
                """, (target_status, emp_id))

        # 8. Update existing Program Chair review records for active term to 'Pending' and clear items/remarks
        if active_term_id and is_resubmission:
            cursor.execute("""
                SELECT review_id FROM tbl_ipcr_chair_review 
                WHERE emp_id = %s AND term_id = %s
            """, (emp_id, active_term_id))
            existing_review = cursor.fetchone()
            if existing_review:
                review_id = existing_review[0]
                # Delete ONLY Research and Extension review items to preserve standard workload adjustments
                cursor.execute("""
                    DELETE ri FROM tbl_ipcr_chair_review_items ri
                    JOIN tbl_master_indicators mi ON ri.indicator_id = mi.indicator_id
                    JOIN tbl_target_categories tc ON mi.category_id = tc.category_id
                    WHERE ri.review_id = %s
                      AND tc.category_name IN ('A. Research', 'B. Extension Services / Training / Advisory')
                """, (review_id,))

                # Sync/update the standard workload review items to match the new draft proposed quantities.
                # We conditionally update reviewed_quantity: if it matches original_quantity (meaning
                # it was not custom edited by the Program Chair), we sync it. Otherwise, we preserve
                # the custom edited value.
                cursor.execute("""
                    UPDATE tbl_ipcr_chair_review_items ri
                    JOIN tbl_draft_targets dt ON ri.draft_id = dt.draft_id
                    JOIN tbl_master_indicators mi ON dt.indicator_id = mi.indicator_id
                    JOIN tbl_target_categories tc ON mi.category_id = tc.category_id
                    SET ri.reviewed_quantity = CASE 
                            WHEN ri.reviewed_quantity = ri.original_quantity THEN dt.proposed_quantity 
                            ELSE ri.reviewed_quantity 
                        END,
                        ri.original_quantity = dt.proposed_quantity
                    WHERE ri.review_id = %s
                      AND tc.category_name IN ('A. Instructions', 'Support Functions')
                """, (review_id,))

                cursor.execute("""
                    UPDATE tbl_ipcr_chair_review
                    SET overall_status = 'Pending',
                        overall_remarks = NULL,
                        reviewed_at = NULL
                    WHERE review_id = %s
                """, (review_id,))

        # 8b. Reset RET Chair review record status if it exists for active term
        if active_term_id:
            cursor.execute("""
                SELECT review_id, overall_status FROM tbl_ipcr_ret_review
                WHERE emp_id = %s AND term_id = %s
            """, (emp_id, active_term_id))
            existing_ret_review = cursor.fetchone()
            if existing_ret_review:
                ret_review_id = existing_ret_review[0]
                ret_status = existing_ret_review[1]
                if ret_editable or ret_status == 'Rejected':
                    if ret_editable:
                        # If editable, delete items so they rebuild from scratch
                        cursor.execute("DELETE FROM tbl_ipcr_ret_review_items WHERE review_id = %s", (ret_review_id,))
                    
                    # Reset review header status to Pending so RET Chair can review it again
                    cursor.execute("""
                        UPDATE tbl_ipcr_ret_review
                        SET overall_status = 'Pending',
                            overall_remarks = NULL,
                            reviewed_at = NULL
                        WHERE review_id = %s
                    """, (ret_review_id,))

        conn.commit()
        if not ret_editable or is_resubmission:
            return True, "IPCR successfully submitted for approval."
        return True, "IPCR successfully submitted for review."
    except Exception as e:
        conn.rollback()
        return False, str(e)


# ──────────────────────────────────────────────
# Process 6: Evidence Gathering Helpers
# ──────────────────────────────────────────────

def get_faculty_committed_targets(cursor, emp_id, term_id):
    from app.models.connection import timed_query
    query = """
        SELECT ct.target_id, ct.indicator_id, ct.assigned_quantity, ct.actual_quantity, ct.status,
               COALESCE(ct.target_description, mi.indicator_description) as indicator_description,
               ct.target_deadline,
               tc.category_name
        FROM tbl_committed_targets ct
        JOIN tbl_master_indicators mi ON ct.indicator_id = mi.indicator_id
        LEFT JOIN tbl_target_categories tc ON mi.category_id = tc.category_id
        WHERE ct.emp_id = %s AND mi.term_id = %s AND ct.assigned_quantity > 0
        ORDER BY tc.category_name, mi.indicator_id
    """
    return timed_query(cursor, query, (emp_id, term_id), label="get_faculty_committed_targets")


def recalculate_target_accomplished_quantity(cursor, target_id):
    # 1. Get emp_id and indicator_id of this target
    cursor.execute("SELECT emp_id, indicator_id FROM tbl_committed_targets WHERE target_id = %s", (target_id,))
    row = cursor.fetchone()
    if not row:
        return
    emp_id, indicator_id = row[0], row[1]
    
    # 2. Sum direct uploads (exclude Rejected evidence)
    cursor.execute("""
        SELECT COALESCE(SUM(actual_qty_Q), 0) FROM tbl_evidence_repo
        WHERE target_id = %s AND verification_status != 'Rejected'
    """, (target_id,))
    direct_sum = cursor.fetchone()[0]
    
    # 3. Sum claimed co-authored uploads (exclude Rejected evidence)
    cursor.execute("""
        SELECT COALESCE(SUM(er.actual_qty_Q), 0) FROM tbl_co_authors ca
        JOIN tbl_evidence_repo er ON ca.evidence_id = er.evidence_id
        WHERE ca.emp_id = %s 
          AND ca.claimed = 1 
          AND er.verification_status != 'Rejected'
          AND (SELECT indicator_id FROM tbl_committed_targets WHERE target_id = er.target_id) = %s
    """, (emp_id, indicator_id))
    co_author_sum = cursor.fetchone()[0]
    
    # 4. Update the target's actual_quantity
    total = direct_sum + co_author_sum
    cursor.execute("""
        UPDATE tbl_committed_targets
        SET actual_quantity = %s
        WHERE target_id = %s
    """, (total, target_id))


def upload_evidence_item(cursor, target_id, file_path, quantity):
    cursor.execute("""
        INSERT INTO tbl_evidence_repo (target_id, file_path, actual_qty_Q, verification_status)
        VALUES (%s, %s, %s, 'Pending')
    """, (target_id, file_path, quantity))
    evidence_id = cursor.lastrowid
    recalculate_target_accomplished_quantity(cursor, target_id)
    return evidence_id


def delete_evidence_item(cursor, evidence_id):
    # Find target_id first
    cursor.execute("SELECT target_id FROM tbl_evidence_repo WHERE evidence_id = %s", (evidence_id,))
    row = cursor.fetchone()
    if not row:
        return False
    target_id = row[0]
    
    # Delete co-author relationships
    cursor.execute("DELETE FROM tbl_co_authors WHERE evidence_id = %s", (evidence_id,))
    # Delete evidence item
    cursor.execute("DELETE FROM tbl_evidence_repo WHERE evidence_id = %s", (evidence_id,))
    
    recalculate_target_accomplished_quantity(cursor, target_id)
    return True


def get_eligible_co_authors_for_indicator(cursor, indicator_id, current_emp_id):
    from app.models.connection import timed_query
    query = """
        SELECT ep.emp_id, CONCAT(ep.first_name, ' ', ep.last_name) as name
        FROM tbl_employee_profiles ep
        JOIN tbl_committed_targets ct ON ep.emp_id = ct.emp_id
        WHERE ct.indicator_id = %s AND ep.emp_id != %s
    """
    return timed_query(cursor, query, (indicator_id, current_emp_id), label="get_eligible_co_authors")


def add_co_authors_to_evidence(cursor, evidence_id, co_author_emp_ids):
    for emp_id in co_author_emp_ids:
        cursor.execute("""
            INSERT INTO tbl_co_authors (evidence_id, emp_id, claimed)
            VALUES (%s, %s, 0)
        """, (evidence_id, emp_id))


def get_unclaimed_co_authored_evidence(cursor, emp_id, indicator_id):
    from app.models.connection import timed_query
    query = """
        SELECT ca.co_author_id, er.evidence_id, er.file_path, er.actual_qty_Q,
               CONCAT(ep_owner.first_name, ' ', ep_owner.last_name) as uploaded_by
        FROM tbl_co_authors ca
        JOIN tbl_evidence_repo er ON ca.evidence_id = er.evidence_id
        JOIN tbl_committed_targets ct_owner ON er.target_id = ct_owner.target_id
        JOIN tbl_employee_profiles ep_owner ON ct_owner.emp_id = ep_owner.emp_id
        WHERE ca.emp_id = %s 
          AND ca.claimed = 0
          AND ct_owner.indicator_id = %s
    """
    return timed_query(cursor, query, (emp_id, indicator_id), label="get_unclaimed_co_authored_evidence")


def claim_co_authored_evidence(cursor, co_author_id, target_id):
    cursor.execute("UPDATE tbl_co_authors SET claimed = 1 WHERE co_author_id = %s", (co_author_id,))
    recalculate_target_accomplished_quantity(cursor, target_id)


def unclaim_co_authored_evidence(cursor, co_author_id, target_id):
    cursor.execute("UPDATE tbl_co_authors SET claimed = 0 WHERE co_author_id = %s", (co_author_id,))
    recalculate_target_accomplished_quantity(cursor, target_id)


def get_evidence_by_target(cursor, target_id, emp_id, indicator_id):
    from app.models.connection import timed_query
    # 1. Fetch direct uploads
    query1 = """
        SELECT er.evidence_id, NULL as co_author_id, er.file_path, er.actual_qty_Q, 
               er.verification_status, er.supervisor_comment, 0 as is_co_authored, NULL as uploaded_by
        FROM tbl_evidence_repo er
        WHERE er.target_id = %s
    """
    direct = timed_query(cursor, query1, (target_id,), label="get_direct_evidence")
    
    # 2. Fetch claimed co-authored uploads
    query2 = """
        SELECT er.evidence_id, ca.co_author_id, er.file_path, er.actual_qty_Q, 
               er.verification_status, er.supervisor_comment, 1 as is_co_authored, 
               CONCAT(ep.first_name, ' ', ep.last_name) as uploaded_by
        FROM tbl_co_authors ca
        JOIN tbl_evidence_repo er ON ca.evidence_id = er.evidence_id
        JOIN tbl_committed_targets ct ON er.target_id = ct.target_id
        JOIN tbl_employee_profiles ep ON ct.emp_id = ep.emp_id
        WHERE ca.emp_id = %s AND ca.claimed = 1 AND ct.indicator_id = %s
    """
    co_authored = timed_query(cursor, query2, (emp_id, indicator_id), label="get_co_authored_evidence")
    
    return direct + co_authored


def get_tagged_co_authors(cursor, evidence_id):
    from app.models.connection import timed_query
    query = """
        SELECT ca.co_author_id, ca.emp_id, ca.claimed,
               CONCAT(ep.first_name, ' ', ep.last_name) as name
        FROM tbl_co_authors ca
        JOIN tbl_employee_profiles ep ON ca.emp_id = ep.emp_id
        WHERE ca.evidence_id = %s
    """
    return timed_query(cursor, query, (evidence_id,), label="get_tagged_co_authors")



def check_faculty_evidence_readiness(cursor, emp_id, term_id, assigned_targets):
    if not assigned_targets:
        return {
            'all_evidence_ready': False,
            'evidence_submitted': False,
            'total_targets': 0,
            'targets_with_evidence': 0,
            'targets_met_qty': 0
        }

    total_targets = len(assigned_targets)
    targets_with_evidence = 0
    targets_met_qty = 0
    submitted_count = 0

    for t in assigned_targets:
        ev_list = t.get('evidence_list')
        if ev_list is None:
            ev_list = get_evidence_by_target(cursor, t['target_id'], emp_id, t['indicator_id'])
            t['evidence_list'] = ev_list

        if len(ev_list) > 0:
            targets_with_evidence += 1

        actual_q = t.get('actual_quantity') or 0
        assigned_q = t.get('assigned_quantity') or 0
        if actual_q >= assigned_q and assigned_q > 0:
            targets_met_qty += 1

        if t.get('status') in ('Submitted', 'Pending Verification', 'Verified'):
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


def submit_faculty_evidences(conn, cursor, emp_id, term_id):
    targets = get_faculty_committed_targets(cursor, emp_id, term_id)
    if not targets:
        return False, "No committed targets found."

    readiness = check_faculty_evidence_readiness(cursor, emp_id, term_id, targets)
    if readiness['evidence_submitted']:
        return False, "Evidences have already been submitted for verification."

    if not readiness['all_evidence_ready']:
        return False, "All targets must have uploaded evidence and meet target quantities before submitting."

    try:
        update_sql = "UPDATE tbl_committed_targets ct JOIN tbl_master_indicators mi ON ct.indicator_id = mi.indicator_id SET ct.status = 'Submitted' WHERE ct.emp_id = %s AND mi.term_id = %s"
        cursor.execute(update_sql, (emp_id, term_id))
        conn.commit()
        return True, "Evidences submitted successfully for verification."
    except Exception as e:
        conn.rollback()
        return False, f"Error submitting evidences: {str(e)}"


