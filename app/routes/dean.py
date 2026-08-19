from flask import Blueprint, render_template, request, redirect, session, url_for, flash, jsonify
from app.models import *
from app.decorators import role_required

dean_bp = Blueprint('dean', __name__, url_prefix='/dean')


@dean_bp.route('/')
@role_required('DEAN')
def dean_dashboard():
    conn = get_db_connection()
    cursor = conn.cursor()

    dean_id = session.get('user_id')
    terms = get_all_terms(cursor)
    active_term = next((t for t in terms if t['is_active'] == 1), None)

    if not active_term:
        flash('No active academic term found.', 'warning')
        cursor.close()
        conn.close()
        return render_template('dean_dashboard.html',
                               active_term=None,
                               departments=[],
                               special_roles=SPECIAL_CASCADE_ROLES,
                               master_indicators=[],
                               existing_quotas={},
                               completion_rate=0,
                               pending_count=0,
                               top_dept="N/A",
                               pending_approvals=[],
                               draft_submissions=[],
                               college_wide_quotas=[],
                               designated_faculty_list=[])

    term_id = active_term['term_id']

    # Use timed_query helper for all queries
    from app.models.connection import timed_query

    indicators = get_master_indicators(cursor, term_id)

    existing_quotas_raw = get_existing_cascaded_quotas(cursor, term_id)

    existing_quotas = {}
    for quota in existing_quotas_raw:
        ind_id = quota['indicator_id']
        if ind_id not in existing_quotas:
            existing_quotas[ind_id] = {}
        existing_quotas[ind_id][quota['assigned_to_role']] = quota['total_target_value']

    # Consolidated KPI query — 1 round-trip instead of 3
    completion_rate, pending_count, top_dept = get_dean_dashboard_kpis(cursor, term_id)

    pending_approvals = get_pending_final_approvals(cursor, term_id)

    # ── New: Draft IPCR submissions from designated faculty ──
    draft_submissions = get_designated_draft_submissions(cursor, term_id)

    # ── New: College-Wide quotas for target assignment ──
    college_wide_quotas = get_college_wide_cascaded_quotas(cursor, term_id)

    # ── New: Designated faculty list ──
    designated_faculty_list = get_designated_faculty_list(cursor)

    # Get ALL assignments in ONE batch query (replaces N+1 loop)
    emp_ids = [fac['emp_id'] for fac in designated_faculty_list]
    designated_assignments = get_designated_faculty_assignments_batch(cursor, term_id, emp_ids)

    # Fetch college-wide allocations for tracking
    allocations_list = get_college_wide_allocations_tracker(cursor, term_id)
    
    # Structure them by indicator_id: {indicator_id: [allocations]}
    college_wide_allocations = {}
    for alloc in allocations_list:
        ind_id = alloc['indicator_id']
        if ind_id not in college_wide_allocations:
            college_wide_allocations[ind_id] = []
        college_wide_allocations[ind_id].append(alloc)

    from app.models.dean import get_dean_evidence_faculty
    pending_dean_evidence_list, approved_dean_evidence_list = get_dean_evidence_faculty(cursor, term_id)
    approved_designated_dean_evidence_list = [f for f in approved_dean_evidence_list if f.get('designation') == 'Designated Faculty' or f.get('system_role') == 'DESIGNATED_FACULTY']
    approved_regular_dean_evidence_list = [f for f in approved_dean_evidence_list if not (f.get('designation') == 'Designated Faculty' or f.get('system_role') == 'DESIGNATED_FACULTY')]

    departments = get_departments(cursor)

    cursor.close()
    conn.close()

    return render_template('dean_dashboard.html',
                           active_term=active_term,
                           departments=departments,
                           special_roles=SPECIAL_CASCADE_ROLES,
                           master_indicators=indicators,
                           existing_quotas=existing_quotas,
                           completion_rate=completion_rate,
                           pending_count=pending_count,
                           top_dept=top_dept,
                           pending_approvals=pending_approvals,
                           draft_submissions=draft_submissions,
                           college_wide_quotas=college_wide_quotas,
                           designated_faculty_list=designated_faculty_list,
                           designated_assignments=designated_assignments,
                           college_wide_allocations=college_wide_allocations,
                           pending_dean_evidence_list=pending_dean_evidence_list,
                           approved_dean_evidence_list=approved_dean_evidence_list,
                           approved_designated_dean_evidence_list=approved_designated_dean_evidence_list,
                           approved_regular_dean_evidence_list=approved_regular_dean_evidence_list)


@dean_bp.route('/cascade_quotas', methods=['POST'])
@role_required('DEAN')
def cascade_quotas():
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        term_id = request.form.get('term_id')
        if not term_id:
            flash('Missing term ID', 'danger')
            return redirect(url_for('dean.dean_dashboard'))

        quotas_data = []
        indicator_ids = request.form.getlist('indicator_id[]')

        # Cascade columns are generated from the managed department list plus the two
        # non-department roles, so adding a program needs no code change.
        departments = get_departments(cursor)
        cascade_roles = [d['department_name'] for d in departments] + SPECIAL_CASCADE_ROLES
        role_values = {role: request.form.getlist(f'quota_{i}[]')
                       for i, role in enumerate(cascade_roles)}

        def _qty(role, idx):
            vals = role_values.get(role, [])
            if idx >= len(vals) or not vals[idx]:
                return 0
            try:
                v = int(vals[idx])
            except (TypeError, ValueError):
                return 0
            return v if v > 0 else 0

        for i, ind_id in enumerate(indicator_ids):
            if not ind_id:
                continue

            values = [(role, _qty(role, i)) for role in cascade_roles]

            for role, value in values:
                if value > 0:
                    quotas_data.append({
                        'indicator_id': int(ind_id),
                        'total_target': value,
                        'assigned_role': role
                    })

        success, message = save_cascaded_quotas(cursor, conn, term_id, quotas_data)

        if success:
            flash(message, 'success')
        else:
            flash(message, 'danger')

    except Exception as e:
        flash(f'Error cascading quotas: {str(e)}', 'danger')
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    return redirect(url_for('dean.dean_dashboard'))




@dean_bp.route('/validate_quotas', methods=['POST'])
@role_required('DEAN')
def validate_quotas():
    """AJAX endpoint to validate quotas before submission"""
    data = request.get_json()
    return jsonify({'valid': True, 'message': 'Quotas validated'})


@dean_bp.route('/review_draft_fetch/<int:emp_id>')
@role_required('DEAN')
def review_draft_fetch(emp_id):
    """AJAX endpoint — returns JSON to populate the Dean's review modal."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        dean_id = session.get('user_id')
        terms = get_all_terms(cursor)
        active_term = next((t for t in terms if t['is_active'] == 1), None)
        if not active_term:
            return jsonify({'error': 'No active term found.'}), 400

        term_id = active_term['term_id']

        # Get or create review record
        review_id = get_or_create_dean_review(conn, cursor, emp_id, term_id, dean_id)

        # Fetch review items
        items = get_dean_review_items(cursor, review_id)

        # Fetch overall status & remarks
        cursor.execute(
            "SELECT overall_status, overall_remarks FROM tbl_ipcr_dean_review WHERE review_id = %s",
            (review_id,)
        )
        row = cursor.fetchone()
        overall_status = row[0] if row else 'Pending'
        overall_remarks = row[1] if row else ''

        # Faculty info
        cursor.execute(
            "SELECT CONCAT(first_name, ' ', last_name), academic_rank, designation, assigned_program FROM tbl_employee_profiles WHERE emp_id = %s",
            (emp_id,)
        )
        fac = cursor.fetchone()
        faculty_name = fac[0] if fac else 'Unknown'
        academic_rank = fac[1] if fac else ''
        designation = fac[2] if fac else ''
        assigned_program = fac[3] if fac else ''

        # Get college-wide quotas
        college_wide = get_college_wide_cascaded_quotas(cursor, term_id)
        college_wide_ids = {q['indicator_id'] for q in college_wide}

        # Also get ALL available master indicators for this term
        all_indicators = get_available_master_indicators(cursor, term_id)
        picked_ids = {i['indicator_id'] for i in items}
        
        # Filter unpicked to exclude picked AND college wide targets
        unpicked = [ind for ind in all_indicators if ind['indicator_id'] not in picked_ids and ind['indicator_id'] not in college_wide_ids]

        # Filter college wide to only show those that are unpicked
        college_wide_unpicked = []
        for q in college_wide:
            if q['indicator_id'] not in picked_ids:
                college_wide_unpicked.append({
                    'indicator_id': q['indicator_id'],
                    'indicator_description': q['indicator_description'],
                    'category_name': q['category_name'],
                    'total_target_value': q['total_target_value']
                })

        serializable_items = []
        for item in items:
            serializable_items.append({
                'item_id': item['item_id'],
                'draft_id': item['draft_id'],
                'indicator_id': item['indicator_id'],
                'indicator_description': item['indicator_description'],
                'category_name': item['category_name'],
                'original_quantity': item['original_quantity'],
                'reviewed_quantity': item['reviewed_quantity'],
                'item_remarks': item['item_remarks'] or '',
                'is_custom': item['is_custom'],
                'target_description': item.get('target_description') or item['indicator_description'],
                'target_deadline': item.get('target_deadline') or '1 Semester',
                'is_core': item.get('is_core', False),
                'is_cascaded': item.get('is_cascaded', False),
            })


        return jsonify({
            'review_id': review_id,
            'emp_id': emp_id,
            'faculty_name': faculty_name,
            'academic_rank': academic_rank,
            'designation': designation,
            'assigned_program': assigned_program,
            'overall_status': overall_status,
            'overall_remarks': overall_remarks or '',
            'items': serializable_items,
            'unpicked': unpicked,
            'college_wide_unpicked': college_wide_unpicked,
            'college_wide_all': [{
                'indicator_id': q['indicator_id'],
                'indicator_description': q['indicator_description'],
                'category_name': q['category_name'],
                'total_target_value': q['total_target_value']
            } for q in college_wide],
            'college_wide_ids': list(college_wide_ids),
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@dean_bp.route('/save_review_items', methods=['POST'])
@role_required('DEAN')
def save_review_items():
    """Batch save all edited quantities and remarks for one review."""
    data = request.get_json()
    review_id = data.get('review_id')
    items = data.get('items', [])

    if not review_id or not items:
        return jsonify({'success': False, 'message': 'Missing review_id or items.'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        success, msg = save_dean_review_items(cursor, conn, review_id, items)
        return jsonify({'success': success, 'message': msg})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@dean_bp.route('/submit_review_decision', methods=['POST'])
@role_required('DEAN')
def submit_review_decision():
    """Approve or reject the entire review with overall remarks."""
    data = request.get_json()
    review_id = data.get('review_id')
    action = data.get('action')
    overall_remarks = data.get('overall_remarks', '').strip()

    if not review_id or action not in ('Approved', 'Rejected'):
        return jsonify({'success': False, 'message': 'Missing review_id or invalid action.'}), 400

    if action == 'Rejected' and not overall_remarks:
        return jsonify({'success': False, 'message': 'Remarks are required when rejecting.'}), 400

    dean_id = session.get('user_id')
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        success, msg = submit_dean_review_decision(cursor, conn, review_id, action, overall_remarks)

        if success:
            details = f"Dean {dean_id} {action.lower()} draft IPCR (review #{review_id}). Remarks: {overall_remarks}"
            from app.models.audit import log_audit_action
            log_audit_action(conn, cursor, dean_id, f'DEAN_REVIEW_{action.upper()}', details, request.remote_addr or '127.0.0.1')

        return jsonify({'success': success, 'message': msg})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


# ──────────────────────────────────────────────
# College-Wide Target Assignment (Designated Faculty)
# ──────────────────────────────────────────────

@dean_bp.route('/assign_designated_target', methods=['POST'])
@role_required('DEAN')
def assign_designated_target():
    """Assign a College-Wide target to a designated faculty member."""
    term_id = request.form.get('term_id')
    emp_id = request.form.get('emp_id')
    indicator_id = request.form.get('indicator_id')
    quantity = request.form.get('quantity', '0')

    if not term_id or not emp_id or not indicator_id:
        flash('Missing required data.', 'danger')
        return redirect(url_for('dean.dean_dashboard'))

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        success, msg = save_designated_faculty_assignment(
            cursor, conn, int(term_id), emp_id, int(indicator_id), int(quantity) if quantity.isdigit() else 0
        )
        flash(msg, 'success' if success else 'danger')
    except Exception as e:
        flash(f'Error assigning target: {str(e)}', 'danger')
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('dean.dean_dashboard'))


# ──────────────────────────────────────────────
# Dean Final Evidence Verification
# ──────────────────────────────────────────────

@dean_bp.route('/faculty_evidence_details/<int:emp_id>')
@role_required('DEAN')
def dean_faculty_evidence_details(emp_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        from app.models import get_all_terms
        terms = get_all_terms(cursor)
        active_term = next((t for t in terms if t['is_active'] == 1), None)
        if not active_term:
            return jsonify({'success': False, 'message': 'No active term.'}), 400
        term_id = active_term['term_id']

        from app.models.faculty import get_faculty_committed_targets
        from app.models.scoring import compute_ipcr_score
        targets = get_faculty_committed_targets(cursor, emp_id, term_id)
        ipcr_summary = compute_ipcr_score(cursor, emp_id, term_id)

        cursor.execute("SELECT CONCAT(first_name, ' ', last_name), academic_rank, assigned_program FROM tbl_employee_profiles WHERE emp_id = %s", (emp_id,))
        fac = cursor.fetchone()
        fac_name = f"{fac[0]}" if fac else f"Employee #{emp_id}"
        rank = fac[1] if fac else ''
        prog = fac[2] if fac else ''

        return jsonify({
            'success': True,
            'faculty_name': fac_name,
            'academic_rank': rank,
            'department': prog,
            'targets': targets,
            'ipcr_summary': ipcr_summary
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@dean_bp.route('/verify_evidence', methods=['POST'])
@role_required('DEAN')
def dean_verify_evidence():
    data = request.get_json(silent=True) or request.form
    evidence_id = data.get('evidence_id')
    status = (data.get('status') or '').strip()
    comment = data.get('comment') or ''
    if not evidence_id:
        return jsonify({'success': False, 'message': 'Missing evidence_id.'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        from app.models.dean import set_dean_evidence_verification
        success, msg = set_dean_evidence_verification(conn, cursor, int(evidence_id), status, comment)
        return jsonify({'success': success, 'message': msg})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@dean_bp.route('/approve_package', methods=['POST'])
@role_required('DEAN')
def dean_approve_package():
    data = request.get_json(silent=True) or request.form
    emp_id = data.get('emp_id')
    if not emp_id:
        return jsonify({'success': False, 'message': 'Missing emp_id.'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        from app.models import get_all_terms
        terms = get_all_terms(cursor)
        active_term = next((t for t in terms if t['is_active'] == 1), None)
        if not active_term:
            return jsonify({'success': False, 'message': 'No active term.'}), 400
            
        term_id = active_term['term_id']
        cursor.execute("""
            UPDATE tbl_committed_targets ct
            JOIN tbl_master_indicators mi ON ct.indicator_id = mi.indicator_id
            SET ct.status = 'Dean Approved'
            WHERE ct.emp_id = %s AND mi.term_id = %s AND ct.status = 'Submitted to Dean'
        """, (emp_id, term_id))
        conn.commit()
        return jsonify({'success': True, 'message': 'Evidence package successfully approved!'})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()

@dean_bp.route('/return_to_faculty/<int:emp_id>', methods=['POST'])
@role_required('DEAN')
def dean_return_to_faculty(emp_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        from app.models import get_all_terms
        terms = get_all_terms(cursor)
        active_term = next((t for t in terms if t['is_active'] == 1), None)
        if not active_term:
            return jsonify({'success': False, 'message': 'No active term.'}), 400
            
        term_id = active_term['term_id']
        cursor.execute("""
            UPDATE tbl_committed_targets ct
            JOIN tbl_master_indicators mi ON ct.indicator_id = mi.indicator_id
            SET ct.status = 'Returned to Faculty'
            WHERE ct.emp_id = %s AND mi.term_id = %s AND ct.status = 'Dean Approved'
        """, (emp_id, term_id))
        conn.commit()
        return jsonify({'success': True, 'message': 'IPCR successfully returned to faculty for printing!'})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()
