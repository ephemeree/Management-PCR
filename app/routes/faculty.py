from flask import Blueprint, render_template, request, redirect, session, url_for, flash
from app.models import *
from app.decorators import role_required

faculty_bp = Blueprint('faculty', __name__, url_prefix='/faculty')


@faculty_bp.route('/')
@role_required('FACULTY')
def faculty_dashboard():
    conn = get_db_connection()
    cursor = conn.cursor()
    from app.models.connection import timed_query

    emp_id = session.get('user_id')

    emp_result = timed_query(cursor, "SELECT academic_rank, specialization FROM tbl_employee_profiles WHERE emp_id = %s", (emp_id,), label="faculty_profile")
    academic_rank = emp_result[0]['academic_rank'] if emp_result else ''
    specialization = emp_result[0]['specialization'] if emp_result else ''

    terms = get_all_terms(cursor)
    active_term = next((t for t in terms if t['is_active'] == 1), None)

    assigned_targets = []
    ret_menu = {'required_selections': 0, 'indicators': []}
    has_submitted = False
    is_locked = False
    chair_review = None

    if active_term:
        term_id = active_term['term_id']
        assigned_targets = get_faculty_assigned_targets(cursor, emp_id, term_id)
        if academic_rank:
            ret_menu = get_faculty_ret_menu(cursor, academic_rank, term_id)

        # Check if the faculty member has submitted
        sub_result = timed_query(cursor, """
            SELECT COUNT(*) as cnt
            FROM tbl_draft_targets dt
            JOIN tbl_master_indicators mi ON dt.indicator_id = mi.indicator_id
            WHERE dt.emp_id = %s AND mi.term_id = %s AND dt.review_status IN ('Pending Review', 'Waiting for Approval')
        """, (emp_id, term_id), label="faculty_submit_check")
        has_submitted = sub_result[0]['cnt'] > 0 if sub_result else False
        # Fetch the Program Chair's review decision (if any)
        chair_review = get_faculty_chair_review_status(cursor, emp_id, term_id)
        # Fetch the RET Chair's review decision (if any)
        ret_review = get_faculty_ret_review_status(cursor, emp_id, term_id)
        # Fetch the overall IPCR status (dynamically computed)
        from app.models.connection import get_overall_ipcr_status
        ipcr_status = get_overall_ipcr_status(cursor, emp_id, term_id)

        # Check if locked
        cursor.execute("""
            SELECT COUNT(*) FROM tbl_committed_targets ct
            JOIN tbl_master_indicators mi ON ct.indicator_id = mi.indicator_id
            WHERE ct.emp_id = %s AND mi.term_id = %s
        """, (emp_id, term_id))
        is_locked = cursor.fetchone()[0] > 0

        # Determine submission state based on overall status
        if ipcr_status == 'draft':
            has_submitted = False
        else:
            has_submitted = True

        if is_locked:
            has_submitted = True
            from app.models.faculty import get_faculty_committed_targets, get_evidence_by_target
            assigned_targets = get_faculty_committed_targets(cursor, emp_id, term_id)
            # Fetch evidence for each target
            for target in assigned_targets:
                target['evidence_list'] = get_evidence_by_target(cursor, target['target_id'], emp_id, target['indicator_id'])

    cursor.close()
    conn.close()

    return render_template('faculty_dashboard.html',
                           active_term=active_term,
                           assigned_targets=assigned_targets,
                           ret_menu=ret_menu,
                           academic_rank=academic_rank,
                           specialization=specialization,
                           has_submitted=has_submitted,
                           is_locked=is_locked,
                           chair_review=chair_review,
                           ret_review=ret_review,
                           ipcr_status=ipcr_status)
@faculty_bp.route('/submit_ipcr', methods=['POST'])
@role_required('FACULTY')
def faculty_submit_ipcr():
    emp_id = session.get('user_id')
    term_id = request.form.get('term_id')
    selected_indicators = request.form.getlist('ret_indicators[]')

    if not term_id:
        flash("No active term.", "danger")
        return redirect(url_for('faculty.faculty_dashboard'))

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Check if already locked or approved
        cursor.execute("""
            SELECT COUNT(*) FROM tbl_committed_targets ct
            JOIN tbl_master_indicators mi ON ct.indicator_id = mi.indicator_id
            WHERE ct.emp_id = %s AND mi.term_id = %s
        """, (emp_id, term_id))
        is_locked = cursor.fetchone()[0] > 0

        cursor.execute("""
            SELECT overall_status FROM tbl_ipcr_chair_review
            WHERE emp_id = %s AND term_id = %s
        """, (emp_id, term_id))
        review_row = cursor.fetchone()
        is_approved = review_row and review_row[0] == 'Approved'

        if is_locked or is_approved:
            flash("Your IPCR has already been approved/locked and cannot be re-submitted.", "danger")
            return redirect(url_for('faculty.faculty_dashboard'))

        # Construct research targets payload (proposed_quantity=1 per selection)
        selected_ret_targets = [{'indicator_id': int(x), 'proposed_quantity': 1} for x in selected_indicators]

        # Call submit pipeline (handles writing both chair allocations and RET selections to tbl_draft_targets)
        success, msg = submit_faculty_ipcr(conn, cursor, emp_id, selected_ret_targets)

        if success:
            flash(msg, "success")
        else:
            flash(msg, "danger")

    except Exception as e:
        flash(f"Error submitting IPCR: {str(e)}", "danger")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('faculty.faculty_dashboard'))


@faculty_bp.route('/lock_ipcr', methods=['POST'])
@role_required('FACULTY')
def faculty_lock_ipcr():
    emp_id = session.get('user_id')
    term_id = request.form.get('term_id')

    if not term_id:
        flash("No active term.", "danger")
        return redirect(url_for('faculty.faculty_dashboard'))

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Check if already locked
        cursor.execute("""
            SELECT COUNT(*) FROM tbl_committed_targets ct
            JOIN tbl_master_indicators mi ON ct.indicator_id = mi.indicator_id
            WHERE ct.emp_id = %s AND mi.term_id = %s
        """, (emp_id, term_id))
        is_locked = cursor.fetchone()[0] > 0
        if is_locked:
            flash("Your IPCR is already locked.", "warning")
            return redirect(url_for('faculty.faculty_dashboard'))

        # Verify it is approved by chair before locking
        cursor.execute("""
            SELECT overall_status FROM tbl_ipcr_chair_review
            WHERE emp_id = %s AND term_id = %s
        """, (emp_id, term_id))
        row = cursor.fetchone()
        is_approved = row and row[0] == 'Approved'
        if not is_approved:
            flash("Your IPCR must be approved by the Program Chair before locking.", "danger")
            return redirect(url_for('faculty.faculty_dashboard'))

        success, msg = lock_and_commit_ipcr(conn, cursor, emp_id, int(term_id))
        if success:
            flash("IPCR locked successfully and committed to evaluation targets.", "success")
        else:
            flash(msg, "danger")
    except Exception as e:
        flash(f"Error locking IPCR: {str(e)}", "danger")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('faculty.faculty_dashboard'))


# ──────────────────────────────────────────────
# Process 6: Evidence Management Routes
# ──────────────────────────────────────────────

from flask import current_app, jsonify
import uuid
import os
from werkzeug.utils import secure_filename

@faculty_bp.route('/upload_evidence', methods=['POST'])
@role_required('FACULTY')
def faculty_upload_evidence():
    emp_id = session.get('user_id')
    target_id = request.form.get('target_id')
    quantity = request.form.get('quantity', '1')
    co_authors_raw = request.form.getlist('co_authors[]')
    
    if not target_id:
        flash("Invalid target ID.", "danger")
        return redirect(url_for('faculty.faculty_dashboard'))
        
    try:
        qty_val = int(quantity)
    except ValueError:
        qty_val = 1

    file = request.files.get('file')
    if not file or file.filename == '':
        flash("Please select a file to upload.", "danger")
        return redirect(url_for('faculty.faculty_dashboard'))

    # Check file extension
    allowed_extensions = {'pdf', 'png', 'jpg', 'jpeg', 'docx'}
    filename = file.filename
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    if ext not in allowed_extensions:
        flash(f"Unsupported file format. Allowed formats: {', '.join(allowed_extensions)}", "danger")
        return redirect(url_for('faculty.faculty_dashboard'))

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
        from app.models.faculty import upload_evidence_item, add_co_authors_to_evidence
        evidence_id = upload_evidence_item(cursor, int(target_id), relative_path, qty_val)
        
        # Parse co-authors list
        co_author_ids = []
        for x in co_authors_raw:
            if x.isdigit():
                co_author_ids.append(int(x))
                
        if co_author_ids:
            add_co_authors_to_evidence(cursor, evidence_id, co_author_ids)
            
        conn.commit()
        flash("Evidence uploaded successfully!", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error uploading evidence: {str(e)}", "danger")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('faculty.faculty_dashboard'))


@faculty_bp.route('/delete_evidence', methods=['POST'])
@role_required('FACULTY')
def faculty_delete_evidence():
    evidence_id = request.form.get('evidence_id')
    if not evidence_id:
        flash("Invalid evidence ID.", "danger")
        return redirect(url_for('faculty.faculty_dashboard'))

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

    return redirect(url_for('faculty.faculty_dashboard'))


@faculty_bp.route('/target_evidence/<int:target_id>/<int:indicator_id>')
@role_required('FACULTY')
def faculty_target_evidence(target_id, indicator_id):
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


@faculty_bp.route('/eligible_co_authors/<int:indicator_id>')
@role_required('FACULTY')
def faculty_eligible_co_authors(indicator_id):
    emp_id = session.get('user_id')
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        from app.models.faculty import get_eligible_co_authors_for_indicator
        faculty_list = get_eligible_co_authors_for_indicator(cursor, indicator_id, emp_id)
        return jsonify({'success': True, 'co_authors': faculty_list})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@faculty_bp.route('/unclaimed_co_authored_evidence/<int:indicator_id>')
@role_required('FACULTY')
def faculty_unclaimed_co_authored_evidence(indicator_id):
    emp_id = session.get('user_id')
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        from app.models.faculty import get_unclaimed_co_authored_evidence
        evidence_list = get_unclaimed_co_authored_evidence(cursor, emp_id, indicator_id)
        return jsonify({'success': True, 'evidence_list': evidence_list})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@faculty_bp.route('/claim_evidence', methods=['POST'])
@role_required('FACULTY')
def faculty_claim_evidence():
    co_author_id = request.form.get('co_author_id')
    target_id = request.form.get('target_id')
    if not co_author_id or not target_id:
        flash("Invalid claim payload.", "danger")
        return redirect(url_for('faculty.faculty_dashboard'))

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        from app.models.faculty import claim_co_authored_evidence
        claim_co_authored_evidence(cursor, int(co_author_id), int(target_id))
        conn.commit()
        flash("Co-authored evidence linked successfully!", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error linking co-authored evidence: {str(e)}", "danger")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('faculty.faculty_dashboard'))


@faculty_bp.route('/unclaim_evidence', methods=['POST'])
@role_required('FACULTY')
def faculty_unclaim_evidence():
    co_author_id = request.form.get('co_author_id')
    target_id = request.form.get('target_id')
    if not co_author_id or not target_id:
        flash("Invalid claim payload.", "danger")
        return redirect(url_for('faculty.faculty_dashboard'))

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        from app.models.faculty import unclaim_co_authored_evidence
        unclaim_co_authored_evidence(cursor, int(co_author_id), int(target_id))
        conn.commit()
        flash("Co-authored evidence unlinked successfully.", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error unlinking co-authored evidence: {str(e)}", "danger")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('faculty.faculty_dashboard'))
