from flask import Blueprint, render_template, request, redirect, session, url_for, flash, jsonify
from app.models import *
from app.decorators import role_required

prog_chair_bp = Blueprint('prog_chair', __name__, url_prefix='/prog_chair')


# ─────────────────────────────────────────────
# Dashboard
# ─────────────────────────────────────────────

@prog_chair_bp.route('/')
@role_required('PROGRAM_CHAIR')
def prog_chair_dashboard():
    conn = get_db_connection()
    cursor = conn.cursor()

    specialization = session.get('specialization')
    if not specialization:
        cursor.execute(
            "SELECT specialization FROM tbl_employee_profiles WHERE emp_id = %s",
            (session.get('user_id'),)
        )
        spec_rows = cursor.fetchall()
        specialization = spec_rows[0][0] if spec_rows else ''
        session['specialization'] = specialization

    if not specialization:
        flash("Your account does not have a designated specialization. Please contact HR/Admin.", "warning")

    try:
        terms = get_all_terms(cursor)
        active_term = next((t for t in terms if t['is_active'] == 1), None)

        indicators = []
        faculty_count = 0
        pending_drafts = []
        pending_drafts_count = 0
        locked_drafts = []

        if active_term and specialization:
            term_id = active_term['term_id']

            # Phase 1: Target allocation indicators
            indicators = get_chair_indicators(cursor, term_id, specialization)
            faculty_list = get_specialization_faculty(cursor, specialization)
            faculty_count = len(faculty_list)
            faculty_ids = [f['emp_id'] for f in faculty_list]

            # Batch: get ALL assigned quantities in ONE query (replaces N+1 loop)
            indicator_ids = [ind['indicator_id'] for ind in indicators]
            assigned_quantities = get_assigned_quantity_batch(cursor, active_term['term_id'], indicator_ids, faculty_ids)

            for ind in indicators:
                assigned_qty = assigned_quantities.get(ind['indicator_id'], 0)
                ind['assigned_per_faculty'] = assigned_qty
                ind['total_distributed'] = assigned_qty * faculty_count

            # Phase 2: Commitments — live draft IPCR submissions scoped by specialization
            pending_drafts = get_pending_draft_ipcrs(cursor, specialization, term_id)
            # Enrich each draft with dynamically computed ipcr_status
            from app.models.connection import get_overall_ipcr_status
            for draft in pending_drafts:
                draft['ipcr_status'] = get_overall_ipcr_status(cursor, draft['emp_id'], term_id)
            pending_drafts_count = get_pending_drafts_count(cursor, specialization, term_id)
            locked_drafts = get_locked_faculty_ipcrs(cursor, specialization, term_id)

        return render_template(
            'prog_chair_dashboard.html',
            active_term=active_term,
            specialization=specialization,
            indicators=indicators,
            faculty_count=faculty_count,
            pending_drafts=pending_drafts,
            pending_drafts_count=pending_drafts_count,
            locked_drafts=locked_drafts,
        )
    finally:
        cursor.close()
        conn.close()


# ─────────────────────────────────────────────
# Phase 1: Target allocation
# ─────────────────────────────────────────────

@prog_chair_bp.route('/assign_target', methods=['POST'])
@role_required('PROGRAM_CHAIR')
def assign_chair_target():
    specialization = session.get('specialization')
    term_id = request.form.get('term_id')
    indicator_ids = request.form.getlist('indicator_ids')
    assigned_quantities = request.form.getlist('assigned_quantities')

    if not specialization or not term_id or not indicator_ids or not assigned_quantities:
        flash("Missing required data for assignment.", "danger")
        return redirect(url_for('prog_chair.prog_chair_dashboard'))

    if len(indicator_ids) != len(assigned_quantities):
        flash("Mismatch between indicators and quantities.", "danger")
        return redirect(url_for('prog_chair.prog_chair_dashboard'))

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        faculty_list = get_specialization_faculty(cursor, specialization)
        faculty_ids = [f['emp_id'] for f in faculty_list]

        allocations = []
        for ind_id, qty in zip(indicator_ids, assigned_quantities):
            try:
                allocations.append((int(ind_id), int(qty)))
            except ValueError:
                continue

        if not allocations:
            flash("No valid allocations to save.", "warning")
            return redirect(url_for('prog_chair.prog_chair_dashboard'))

        success, msg = save_chair_allocations_batch(
            conn, cursor, int(term_id), allocations, faculty_ids
        )
        flash(msg, "success" if success else "danger")
    except Exception as e:
        flash(f"Error saving allocations: {str(e)}", "danger")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('prog_chair.prog_chair_dashboard'))


# ─────────────────────────────────────────────
# Phase 2: IPCR Review — AJAX fetch for modal
# ─────────────────────────────────────────────

@prog_chair_bp.route('/review_ipcr/<int:emp_id>')
@role_required('PROGRAM_CHAIR')
def review_ipcr(emp_id):
    """
    AJAX endpoint — returns JSON payload used to populate the review modal.
    Creates a tbl_ipcr_chair_review record (and pre-populates items) if one
    doesn't exist yet for this faculty + active term.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        chair_emp_id = session.get('user_id')
        terms = get_all_terms(cursor)
        active_term = next((t for t in terms if t['is_active'] == 1), None)

        if not active_term:
            return jsonify({'error': 'No active term found.'}), 400

        term_id = active_term['term_id']

        # Check overall IPCR status for sequential tracking guardrails
        from app.models.connection import get_overall_ipcr_status
        ipcr_status = get_overall_ipcr_status(cursor, emp_id, term_id)

        if ipcr_status not in ('waiting_for_program_chair_review', 'approved_by_program_chair', 'completed'):
            return jsonify({'error': 'RET Chair approval is required before Program Chair verification.'}), 403

        # Fetch or create the review record
        review_id = get_or_create_chair_review(conn, cursor, emp_id, term_id, chair_emp_id)

        # Fetch review items with indicator details
        items = get_review_items(cursor, review_id)

        # Fetch current overall status and remarks
        cursor.execute(
            "SELECT overall_status, overall_remarks FROM tbl_ipcr_chair_review WHERE review_id = %s",
            (review_id,)
        )
        review_row = cursor.fetchone()
        overall_status = review_row[0] if review_row else 'Pending'
        overall_remarks = review_row[1] if review_row else ''

        # Check draft status to see if it is Waiting for Approval
        cursor.execute("""
            SELECT MAX(review_status) FROM tbl_draft_targets dt
            JOIN tbl_master_indicators mi ON dt.indicator_id = mi.indicator_id
            WHERE dt.emp_id = %s AND mi.term_id = %s
        """, (emp_id, term_id))
        draft_status_row = cursor.fetchone()
        draft_status = draft_status_row[0] if draft_status_row else 'Pending Review'

        # If Pending overall review but resubmitted, elevate overall_status to Waiting for Approval
        if overall_status == 'Pending' and draft_status == 'Waiting for Approval':
            overall_status = 'Waiting for Approval'

        # Check if locked
        cursor.execute(
            """
            SELECT COUNT(*) FROM tbl_committed_targets ct
            JOIN tbl_master_indicators mi ON ct.indicator_id = mi.indicator_id
            WHERE ct.emp_id = %s AND mi.term_id = %s
            """,
            (emp_id, term_id)
        )
        is_locked = cursor.fetchone()[0] > 0
        if is_locked:
            overall_status = 'Locked'

        # Fetch faculty name for the modal header
        cursor.execute(
            "SELECT CONCAT(first_name, ' ', last_name), academic_rank FROM tbl_employee_profiles WHERE emp_id = %s",
            (emp_id,)
        )
        fac_row = cursor.fetchone()
        faculty_name = fac_row[0] if fac_row else 'Unknown'
        academic_rank = fac_row[1] if fac_row else ''

        # Serialize datetime fields or load committed/approved targets
        serializable_items = []
        if is_locked:
            cursor.execute("""
                SELECT 
                    ct.target_id AS item_id,
                    0 AS draft_id,
                    ct.indicator_id,
                    mi.indicator_description,
                    tc.category_name,
                    COALESCE(
                        CASE WHEN tc.category_name IN ('A. Instructions', 'Support Functions') THEN ri.original_quantity ELSE NULL END,
                        CASE WHEN tc.category_name IN ('A. Research', 'B. Extension Services / Training / Advisory') THEN rri.original_quantity ELSE NULL END,
                        ct.assigned_quantity
                    ) AS original_quantity,
                    ct.assigned_quantity AS reviewed_quantity,
                    COALESCE(ri.item_remarks, rri.item_remarks, '') AS item_remarks,
                    'Locked' AS draft_status
                FROM tbl_committed_targets ct
                JOIN tbl_master_indicators mi ON ct.indicator_id = mi.indicator_id
                JOIN tbl_target_categories tc ON mi.category_id = tc.category_id
                LEFT JOIN tbl_ipcr_chair_review cr ON cr.emp_id = ct.emp_id AND cr.term_id = mi.term_id
                LEFT JOIN tbl_ipcr_chair_review_items ri ON ri.review_id = cr.review_id AND ri.indicator_id = ct.indicator_id
                LEFT JOIN tbl_ipcr_ret_review rr ON rr.emp_id = ct.emp_id AND rr.term_id = mi.term_id
                LEFT JOIN tbl_ipcr_ret_review_items rri ON rri.review_id = rr.review_id AND rri.indicator_id = ct.indicator_id
                WHERE ct.emp_id = %s AND mi.term_id = %s
            """, (emp_id, term_id))
            rows = cursor.fetchall()
            for row in rows:
                serializable_items.append({
                    'item_id': row[0],
                    'draft_id': row[1],
                    'indicator_id': row[2],
                    'indicator_description': row[3],
                    'category_name': row[4],
                    'original_quantity': max(0, row[5]) if row[5] is not None else 0,
                    'reviewed_quantity': row[6],
                    'item_remarks': row[7],
                    'draft_status': row[8],
                })
        elif overall_status == 'Approved':
            cursor.execute("""
                SELECT 
                    dt.draft_id AS item_id,
                    dt.draft_id,
                    dt.indicator_id,
                    mi.indicator_description,
                    tc.category_name,
                    COALESCE(
                        CASE WHEN tc.category_name IN ('A. Instructions', 'Support Functions') THEN ri.original_quantity ELSE NULL END,
                        CASE WHEN tc.category_name IN ('A. Research', 'B. Extension Services / Training / Advisory') THEN rri.original_quantity ELSE NULL END,
                        dt.proposed_quantity
                    ) AS original_quantity,
                    COALESCE(
                        CASE WHEN tc.category_name IN ('A. Instructions', 'Support Functions') THEN ri.reviewed_quantity ELSE NULL END,
                        CASE WHEN tc.category_name IN ('A. Research', 'B. Extension Services / Training / Advisory') THEN rri.reviewed_quantity ELSE NULL END,
                        dt.proposed_quantity
                    ) AS reviewed_quantity,
                    COALESCE(ri.item_remarks, rri.item_remarks, '') AS item_remarks,
                    dt.review_status AS draft_status
                FROM tbl_draft_targets dt
                JOIN tbl_master_indicators mi ON dt.indicator_id = mi.indicator_id
                JOIN tbl_target_categories tc ON mi.category_id = tc.category_id
                LEFT JOIN tbl_ipcr_chair_review cr ON cr.emp_id = dt.emp_id AND cr.term_id = mi.term_id
                LEFT JOIN tbl_ipcr_chair_review_items ri ON ri.review_id = cr.review_id AND ri.draft_id = dt.draft_id
                LEFT JOIN tbl_ipcr_ret_review rr ON rr.emp_id = dt.emp_id AND rr.term_id = mi.term_id
                LEFT JOIN tbl_ipcr_ret_review_items rri ON rri.review_id = rr.review_id AND rri.indicator_id = dt.indicator_id
                WHERE dt.emp_id = %s AND mi.term_id = %s
                  AND (
                      (tc.category_name IN ('A. Instructions', 'Support Functions') AND dt.proposed_quantity > 0)
                      OR (tc.category_name IN ('A. Research', 'B. Extension Services / Training / Advisory') AND rri.reviewed_quantity > 0)
                  )
            """, (emp_id, term_id))
            rows = cursor.fetchall()
            for row in rows:
                serializable_items.append({
                    'item_id': row[0],
                    'draft_id': row[1],
                    'indicator_id': row[2],
                    'indicator_description': row[3],
                    'category_name': row[4],
                    'original_quantity': max(0, row[5]) if row[5] is not None else 0,
                    'reviewed_quantity': row[6],
                    'item_remarks': row[7],
                    'draft_status': row[8],
                })
        else:
            for item in items:
                serializable_items.append({
                    'item_id': item['item_id'],
                    'draft_id': item['draft_id'],
                    'indicator_id': item['indicator_id'],
                    'indicator_description': item['indicator_description'],
                    'category_name': item['category_name'],
                    'original_quantity': max(0, item['original_quantity']) if item['original_quantity'] is not None else 0,
                    'reviewed_quantity': item['reviewed_quantity'],
                    'item_remarks': item['item_remarks'] or '',
                    'draft_status': item['draft_status'],
                })

        return jsonify({
            'review_id': review_id,
            'emp_id': emp_id,
            'faculty_name': faculty_name,
            'academic_rank': academic_rank,
            'overall_status': overall_status,
            'overall_remarks': overall_remarks or '',
            'items': serializable_items,
        })

    except Exception as e:
        import traceback
        with open("error_log.txt", "w") as f:
            traceback.print_exc(file=f)
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


# ─────────────────────────────────────────────
# Phase 2: Edit a single review item
# ─────────────────────────────────────────────

@prog_chair_bp.route('/edit_review_item', methods=['POST'])
@role_required('PROGRAM_CHAIR')
def edit_review_item():
    """
    Saves an edited quantity and optional remark for one review item row.
    Returns JSON so the modal can update inline without a page reload.
    """
    data = request.get_json()
    item_id = data.get('item_id')
    reviewed_quantity = data.get('reviewed_quantity')
    item_remarks = data.get('item_remarks', '').strip()

    if item_id is None or reviewed_quantity is None:
        return jsonify({'success': False, 'message': 'Missing item_id or reviewed_quantity.'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Check if locked
        cursor.execute(
            "SELECT review_id FROM tbl_ipcr_chair_review_items WHERE item_id = %s",
            (item_id,)
        )
        review_row = cursor.fetchone()
        if review_row:
            review_id = review_row[0]
            cursor.execute(
                "SELECT emp_id, term_id FROM tbl_ipcr_chair_review WHERE review_id = %s",
                (review_id,)
            )
            row = cursor.fetchone()
            if row:
                emp_id, term_id = row
                cursor.execute(
                    """
                    SELECT COUNT(*) FROM tbl_committed_targets ct
                    JOIN tbl_master_indicators mi ON ct.indicator_id = mi.indicator_id
                    WHERE ct.emp_id = %s AND mi.term_id = %s
                    """,
                    (emp_id, term_id)
                )
                if cursor.fetchone()[0] > 0:
                    return jsonify({'success': False, 'message': 'This IPCR is locked and cannot be edited.'}), 403

        success, msg = update_review_item(conn, cursor, int(item_id), int(reviewed_quantity), item_remarks)
        return jsonify({'success': success, 'message': msg})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


# ─────────────────────────────────────────────
# Phase 2: Approve or Reject a draft IPCR
# ─────────────────────────────────────────────

@prog_chair_bp.route('/decide_ipcr', methods=['POST'])
@role_required('PROGRAM_CHAIR')
def decide_ipcr():
    """
    Approves or rejects the full draft IPCR for a faculty member.
    On rejection, the faculty's tbl_draft_targets rows are set to 'Returned'
    so they can re-submit after making corrections.
    """
    import json
    review_id = request.form.get('review_id')
    action = request.form.get('action')           # 'approve' or 'reject'
    overall_remarks = request.form.get('overall_remarks', '').strip()
    items_json = request.form.get('items_json')

    if not review_id or action not in ('approve', 'reject'):
        flash("Invalid decision parameters.", "danger")
        return redirect(url_for('prog_chair.prog_chair_dashboard'))

    if action == 'reject' and not overall_remarks:
        flash("Remarks / Reason is required when returning the IPCR to faculty.", "danger")
        return redirect(url_for('prog_chair.prog_chair_dashboard'))

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Check if locked
        cursor.execute(
            "SELECT emp_id, term_id FROM tbl_ipcr_chair_review WHERE review_id = %s",
            (review_id,)
        )
        row = cursor.fetchone()
        if row:
            emp_id, term_id = row

            # Check overall IPCR status for sequential tracking guardrails
            from app.models.connection import get_overall_ipcr_status
            ipcr_status = get_overall_ipcr_status(cursor, emp_id, term_id)

            if ipcr_status not in ('waiting_for_program_chair_review', 'approved_by_program_chair', 'completed'):
                flash("RET Chair approval is required before Program Chair verification.", "danger")
                return redirect(url_for('prog_chair.prog_chair_dashboard'))

            cursor.execute(
                """
                SELECT COUNT(*) FROM tbl_committed_targets ct
                JOIN tbl_master_indicators mi ON ct.indicator_id = mi.indicator_id
                WHERE ct.emp_id = %s AND mi.term_id = %s
                """,
                (emp_id, term_id)
            )
            if cursor.fetchone()[0] > 0:
                flash("This IPCR is locked and cannot be modified.", "warning")
                return redirect(url_for('prog_chair.prog_chair_dashboard'))

        # If items are submitted inline, save them first inside the same transaction
        if items_json:
            try:
                items = json.loads(items_json)
                from app.models.prog_chair import save_chair_review_items
                save_success, save_msg = save_chair_review_items(cursor, conn, int(review_id), items)
                if not save_success:
                    flash(f"Failed to save targets: {save_msg}", "danger")
                    return redirect(url_for('prog_chair.prog_chair_dashboard'))
            except Exception as json_err:
                flash(f"Invalid target items format: {str(json_err)}", "danger")
                return redirect(url_for('prog_chair.prog_chair_dashboard'))

        success, msg = decide_chair_review(conn, cursor, int(review_id), action, overall_remarks)
        flash(msg, "success" if success else "danger")
    except Exception as e:
        flash(f"Error processing decision: {str(e)}", "danger")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('prog_chair.prog_chair_dashboard'))



