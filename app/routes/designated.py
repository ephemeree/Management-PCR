from flask import Blueprint, render_template, session, request, jsonify, redirect, url_for, flash
from app.models import *
from app.decorators import role_required
from app.models.designated import get_designated_selectable_indicators, submit_designated_ipcr

designated_bp = Blueprint('designated', __name__, url_prefix='/designated')


@designated_bp.route('/')
@role_required('DESIGNATED_FACULTY')
def designated_dashboard():
    conn = get_db_connection()
    cursor = conn.cursor()
    from app.models.connection import timed_query

    emp_id = session.get('user_id')

    emp_result = timed_query(cursor, """
        SELECT academic_rank, specialization, designation, first_name, last_name, assigned_program 
        FROM tbl_employee_profiles 
        WHERE emp_id = %s
    """, (emp_id,), label="designated_profile")
    
    academic_rank = emp_result[0]['academic_rank'] if emp_result else ''
    specialization = emp_result[0]['specialization'] if emp_result else ''
    designation = emp_result[0]['designation'] if emp_result else ''
    first_name = emp_result[0]['first_name'] if emp_result else ''
    last_name = emp_result[0]['last_name'] if emp_result else ''
    assigned_program = emp_result[0]['assigned_program'] if emp_result else ''

    terms = get_all_terms(cursor)
    active_term = next((t for t in terms if t['is_active'] == 1), None)

    dpcr_targets = []
    has_submitted = False
    can_edit = True
    dean_review = None

    if active_term:
        term_id = active_term['term_id']
        
        # Check if committed targets exist for evidence gathering
        cursor.execute("""
            SELECT COUNT(*) FROM tbl_committed_targets ct
            JOIN tbl_master_indicators mi ON ct.indicator_id = mi.indicator_id
            WHERE ct.emp_id = %s AND mi.term_id = %s
        """, (emp_id, term_id))
        is_committed = cursor.fetchone()[0] > 0

        # Check if the user has already submitted
        sub_result = timed_query(cursor, """
            SELECT COUNT(*) as cnt FROM tbl_draft_targets dt
            JOIN tbl_master_indicators mi ON dt.indicator_id = mi.indicator_id
            WHERE dt.emp_id = %s AND mi.term_id = %s
        """, (emp_id, term_id), label="designated_submit_check")
        has_submitted = sub_result[0]['cnt'] > 0 if sub_result else False

        # Fetch Dean's overall review status & remarks
        dr_result = timed_query(cursor, """
            SELECT overall_status, overall_remarks
            FROM tbl_ipcr_dean_review
            WHERE emp_id = %s AND term_id = %s
            ORDER BY reviewed_at DESC LIMIT 1
        """, (emp_id, term_id), label="designated_dean_review")
        if dr_result:
            dean_review = dr_result[0]

        # Determine editability: allowed if not submitted, or if returned/rejected by Dean
        if not has_submitted:
            can_edit = True
        else:
            if dean_review and dean_review['overall_status'] == 'Rejected':
                can_edit = True
            else:
                can_edit = False

        if is_committed:
            can_edit = False
            has_submitted = True
            from app.models.designated import get_designated_committed_targets
            from app.models.faculty import get_evidence_by_target
            dpcr_targets = get_designated_committed_targets(cursor, emp_id, term_id)
            for t in dpcr_targets:
                t['is_selected'] = True
                t['total_target_value'] = t['assigned_quantity']
                t['evidence_list'] = get_evidence_by_target(cursor, t['target_id'], emp_id, t['indicator_id'])
        elif can_edit:
            # Load standard selectable indicators
            standard_targets = get_designated_selectable_indicators(cursor, term_id)
            
            draft_targets = timed_query(cursor, """
                SELECT dt.draft_id as target_id, dt.indicator_id, dt.proposed_quantity as total_target_value, dt.review_status as status,
                       mi.indicator_description, tc.category_name, mi.is_custom,
                       dri.item_remarks as dean_remarks, dri.original_quantity, dri.reviewed_quantity
                FROM tbl_draft_targets dt
                JOIN tbl_master_indicators mi ON dt.indicator_id = mi.indicator_id
                LEFT JOIN tbl_target_categories tc ON mi.category_id = tc.category_id
                LEFT JOIN tbl_ipcr_dean_review_items dri ON dt.draft_id = dri.draft_id
                WHERE dt.emp_id = %s AND mi.term_id = %s
                ORDER BY tc.category_name, mi.indicator_id
            """, (emp_id, term_id), label="designated_load_drafts")
            
            for d in draft_targets:
                if d['category_name'] == 'Custom Target Items':
                    d['category_name'] = 'Support Functions'
            
            draft_map = {d['indicator_id']: d for d in draft_targets}
            
            dpcr_targets = []
            for t in standard_targets:
                ind_id = t['indicator_id']
                if ind_id in draft_map:
                    t['total_target_value'] = draft_map[ind_id]['total_target_value']
                    t['status'] = draft_map[ind_id]['status']
                    t['dean_remarks'] = draft_map[ind_id]['dean_remarks']
                    t['original_quantity'] = draft_map[ind_id]['original_quantity']
                    t['reviewed_quantity'] = draft_map[ind_id]['reviewed_quantity']
                    t['is_selected'] = True
                else:
                    t['total_target_value'] = 0
                    t['status'] = None
                    t['dean_remarks'] = None
                    t['original_quantity'] = None
                    t['reviewed_quantity'] = None
                    t['is_selected'] = False
                dpcr_targets.append(t)
                
            # Add custom targets from drafts
            for d in draft_targets:
                if d['is_custom']:
                    d['is_selected'] = True
                    dpcr_targets.append(d)
        else:
            # If they cannot edit, we just load their submitted drafts (as before)
            dpcr_targets = timed_query(cursor, """
                SELECT dt.draft_id as target_id, dt.indicator_id, dt.proposed_quantity as total_target_value, dt.review_status as status,
                       mi.indicator_description, tc.category_name, mi.is_custom,
                       dri.item_remarks as dean_remarks, dri.original_quantity, dri.reviewed_quantity
                FROM tbl_draft_targets dt
                JOIN tbl_master_indicators mi ON dt.indicator_id = mi.indicator_id
                LEFT JOIN tbl_target_categories tc ON mi.category_id = tc.category_id
                LEFT JOIN tbl_ipcr_dean_review_items dri ON dt.draft_id = dri.draft_id
                WHERE dt.emp_id = %s AND mi.term_id = %s
                ORDER BY tc.category_name, mi.indicator_id
            """, (emp_id, term_id), label="designated_load_drafts")
            for t in dpcr_targets:
                t['is_selected'] = True
                if t['category_name'] == 'Custom Target Items':
                    t['category_name'] = 'Support Functions'

    cursor.close()
    conn.close()

    return render_template('designated_dashboard.html',
                           emp_name=f"{first_name} {last_name}",
                           academic_rank=academic_rank,
                           designation=designation,
                           assigned_program=assigned_program,
                           active_term=active_term,
                           dpcr_targets=dpcr_targets,
                           has_submitted=has_submitted,
                           can_edit=can_edit,
                           dean_review=dean_review)


@designated_bp.route('/submit', methods=['POST'])
@role_required('DESIGNATED_FACULTY')
def submit_designated_ipcr_route():
    emp_id = session.get('user_id')
    term_id = request.form.get('term_id')
    
    if not term_id:
        flash("No active academic term found.", "danger")
        return redirect(url_for('designated.designated_dashboard'))

    # Parse baseline target checkboxes
    selected_ids = request.form.getlist('selected_indicators[]')
    selected_targets = []
    for ind_id in selected_ids:
        qty_val = request.form.get(f'target_qty_{ind_id}', '0')
        selected_targets.append({
            'indicator_id': int(ind_id),
            'proposed_quantity': int(qty_val) if qty_val.isdigit() else 1
        })
        
    # Parse custom targets added on the frontend
    custom_descriptions = request.form.getlist('custom_descriptions[]')
    custom_quantities = request.form.getlist('custom_quantities[]')
    custom_categories = request.form.getlist('custom_categories[]')
    
    custom_targets = []
    for desc, qty, cat in zip(custom_descriptions, custom_quantities, custom_categories):
        if desc.strip():
            custom_targets.append({
                'description': desc.strip(),
                'proposed_quantity': int(qty) if str(qty).isdigit() else 1,
                'category_name': cat.strip()
            })

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        success, msg = submit_designated_ipcr(conn, cursor, emp_id, int(term_id), selected_targets, custom_targets)
        if success:
            flash(msg, "success")
        else:
            flash(msg, "danger")
    except Exception as e:
        flash(f"Error submitting IPCR: {str(e)}", "danger")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('designated.designated_dashboard'))


# ──────────────────────────────────────────────
# Process 6: Evidence Management Routes
# ──────────────────────────────────────────────

from flask import current_app
import uuid
import os
from werkzeug.utils import secure_filename

@designated_bp.route('/target_evidence/<int:target_id>/<int:indicator_id>')
@role_required('DESIGNATED_FACULTY')
def designated_target_evidence(target_id, indicator_id):
    emp_id = session.get('user_id')
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        from app.models.faculty import get_evidence_by_target
        evidence_list = get_evidence_by_target(cursor, target_id, emp_id, indicator_id)
        return jsonify({'success': True, 'evidence_list': evidence_list})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@designated_bp.route('/upload_evidence', methods=['POST'])
@role_required('DESIGNATED_FACULTY')
def designated_upload_evidence():
    emp_id = session.get('user_id')
    target_id = request.form.get('target_id')
    quantity = request.form.get('quantity', '1')
    
    if not target_id:
        flash("Invalid target ID.", "danger")
        return redirect(url_for('designated.designated_dashboard'))
        
    try:
        qty_val = int(quantity)
    except ValueError:
        qty_val = 1

    file = request.files.get('file')
    if not file or file.filename == '':
        flash("Please select a file to upload.", "danger")
        return redirect(url_for('designated.designated_dashboard'))

    # Check file extension
    allowed_extensions = {'pdf', 'png', 'jpg', 'jpeg', 'docx'}
    filename = file.filename
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    if ext not in allowed_extensions:
        flash(f"Unsupported file format. Allowed formats: {', '.join(allowed_extensions)}", "danger")
        return redirect(url_for('designated.designated_dashboard'))

    # Save the file
    upload_dir = current_app.config['UPLOAD_FOLDER']
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir, exist_ok=True)

    unique_filename = f"{uuid.uuid4().hex}_{secure_filename(filename)}"
    file_path = os.path.join(upload_dir, unique_filename)
    file.save(file_path)

    # Save path relative to static
    relative_path = f"uploads/evidence/{unique_filename}"

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        from app.models.faculty import upload_evidence_item
        upload_evidence_item(cursor, int(target_id), relative_path, qty_val)
        conn.commit()
        flash("Evidence uploaded successfully!", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error uploading evidence: {str(e)}", "danger")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('designated.designated_dashboard'))


@designated_bp.route('/delete_evidence', methods=['POST'])
@role_required('DESIGNATED_FACULTY')
def designated_delete_evidence():
    evidence_id = request.form.get('evidence_id')
    if not evidence_id:
        flash("Invalid evidence ID.", "danger")
        return redirect(url_for('designated.designated_dashboard'))

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        from app.models.faculty import delete_evidence_item
        success = delete_evidence_item(cursor, int(evidence_id))
        if success:
            conn.commit()
            flash("Evidence removed successfully.", "success")
        else:
            flash("Evidence item not found.", "danger")
    except Exception as e:
        conn.rollback()
        flash(f"Error deleting evidence: {str(e)}", "danger")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('designated.designated_dashboard'))