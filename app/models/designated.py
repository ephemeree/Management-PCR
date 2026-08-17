def get_designated_selectable_indicators(cursor, term_id):
    """
    Retrieves the standard baseline list of available Instruction and Support functions.
    """
    from app.models.connection import timed_query
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
    return timed_query(cursor, query, (term_id,), label="get_designated_selectable_indicators")


def submit_designated_ipcr(conn, cursor, emp_id, term_id, selected_targets, custom_targets):
    """
    Transactionally processes standard baseline selections and inserts custom ad-hoc targets 
    upstream before compiling all submissions securely inside tbl_draft_targets.
    Also resets any prior Dean review so the Dean can review again.
    
    selected_targets: [{'indicator_id': int, 'proposed_quantity': int, 'target_description': str, 'target_deadline': str}]
    custom_targets: [{'description': str, 'proposed_quantity': int, 'category_name': str, 'target_deadline': str}]
    """
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

        # 2. Process Standard Baseline Selected Targets
        for target in selected_targets:
            desc = target.get('target_description') or None
            dead = target.get('target_deadline') or None
            dur_value = target.get('target_duration_value')
            dur_unit = target.get('target_duration_unit')
            cursor.execute("""
                INSERT INTO tbl_draft_targets (emp_id, indicator_id, proposed_quantity, review_status, target_description, target_deadline,
                                               target_duration_value, target_duration_unit)
                VALUES (%s, %s, %s, 'Pending Review', %s, %s, %s, %s)
            """, (emp_id, target['indicator_id'], target['proposed_quantity'], desc, dead, dur_value, dur_unit))

        # Ensure mandatory default Teaching Load target (10 hours) is saved
        cursor.execute("SELECT category_id FROM tbl_target_categories WHERE slug = 'instruction'")
        cat_row = cursor.fetchone()
        cat_id = cat_row[0] if cat_row else 1
        cursor.execute("SELECT indicator_id FROM tbl_master_indicators WHERE indicator_description = '10 hours of Teaching Load' AND term_id = %s", (term_id,))
        tl_row = cursor.fetchone()
        if tl_row:
            tl_ind_id = tl_row[0]
        else:
            cursor.execute("INSERT INTO tbl_master_indicators (category_id, indicator_description, efficiency_type, term_id, is_custom) VALUES (%s, '10 hours of Teaching Load', 'Output-Based', %s, 0)", (cat_id, term_id))
            tl_ind_id = cursor.lastrowid

        cursor.execute("SELECT draft_id FROM tbl_draft_targets WHERE emp_id = %s AND indicator_id = %s", (emp_id, tl_ind_id))
        tl_draft = cursor.fetchone()
        if not tl_draft:
            cursor.execute("""
                INSERT INTO tbl_draft_targets (emp_id, indicator_id, proposed_quantity, review_status, target_description, target_deadline)
                VALUES (%s, %s, 10, 'Pending Review', '10 hours of Teaching Load', '1 Semester')
            """, (emp_id, tl_ind_id))

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

            # Step C: Downstream projection into the unified draft staging table
            cursor.execute("""
                INSERT INTO tbl_draft_targets (emp_id, indicator_id, proposed_quantity, review_status, target_description, target_deadline,
                                               target_duration_value, target_duration_unit)
                VALUES (%s, %s, %s, 'Pending Review', %s, %s, %s, %s)
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
    from app.models.connection import timed_query
    query = """
        SELECT ct.target_id, ct.indicator_id, ct.assigned_quantity, ct.actual_quantity, ct.status,
               COALESCE(ct.target_description, dt.target_description, mi.indicator_description) as indicator_description,
               COALESCE(ct.target_description, dt.target_description) as target_description,
               COALESCE(ct.target_deadline, dt.target_deadline, '1 Semester') as target_deadline,
               tc.category_name, mi.is_custom
        FROM tbl_committed_targets ct
        JOIN tbl_master_indicators mi ON ct.indicator_id = mi.indicator_id
        LEFT JOIN tbl_target_categories tc ON mi.category_id = tc.category_id
        LEFT JOIN tbl_draft_targets dt ON dt.emp_id = ct.emp_id AND dt.indicator_id = ct.indicator_id
        WHERE ct.emp_id = %s AND mi.term_id = %s
        ORDER BY tc.category_name, mi.indicator_id
    """
    return timed_query(cursor, query, (emp_id, term_id), label="get_designated_committed_targets")



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


def submit_designated_evidences(conn, cursor, emp_id, term_id):
    dpcr_targets = get_designated_committed_targets(cursor, emp_id, term_id)
    if not dpcr_targets:
        return False, "No committed targets found."

    readiness = check_designated_evidence_readiness(cursor, emp_id, term_id, dpcr_targets)
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