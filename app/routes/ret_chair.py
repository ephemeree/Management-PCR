from flask import Blueprint, render_template, request, redirect, session, url_for, flash, jsonify
from app.models import *
from app.decorators import role_required

ret_chair_bp = Blueprint('ret_chair', __name__, url_prefix='/ret_chair')
@ret_chair_bp.route('/')
@role_required('RET_CHAIR')
def ret_chair_dashboard():
    conn = get_db_connection()
    cursor = conn.cursor()
    from app.models.connection import timed_query

    try:
        terms = get_all_terms(cursor)
        active_term = next((t for t in terms if t['is_active'] == 1), None)

        ret_indicators = []
        ret_rules = []
        pending_ret_drafts = []
        pending_ret_count = 0

        ranks_result = timed_query(cursor,
            "SELECT DISTINCT academic_rank FROM tbl_employee_profiles WHERE academic_rank IS NOT NULL AND academic_rank != '' ORDER BY academic_rank",
            label="ret_academic_ranks")
        academic_ranks = [row['academic_rank'] for row in ranks_result]

        if active_term:
            term_id = active_term['term_id']
            ret_indicators = get_ret_indicators(cursor, term_id)
            ret_rules = get_ret_rules(cursor, term_id)
            pending_ret_drafts = get_pending_ret_draft_ipcrs(cursor, term_id)
            # Enrich each draft with dynamically computed ipcr_status
            from app.models.connection import get_overall_ipcr_status
            for draft in pending_ret_drafts:
                draft['ipcr_status'] = get_overall_ipcr_status(cursor, draft['emp_id'], term_id)
            pending_ret_count = sum(1 for d in pending_ret_drafts if d['ipcr_status'] in ('waiting_for_ret_chair_review', 'pending_ret_review'))

        return render_template('ret_chair_dashboard.html',
                               active_term=active_term,
                               ret_indicators=ret_indicators,
                               ret_rules=ret_rules,
                               academic_ranks=academic_ranks,
                               pending_ret_drafts=pending_ret_drafts,
                               pending_ret_count=pending_ret_count)
    finally:
        cursor.close()
        conn.close()


@ret_chair_bp.route('/save_rule', methods=['POST'])
@role_required('RET_CHAIR')
def ret_chair_save_rule():
    term_id = request.form.get('term_id')
    academic_rank = request.form.get('academic_rank')

    research_selections = request.form.get('research_selections', 0)
    extension_selections = request.form.get('extension_selections', 0)

    research_indicator_ids = request.form.getlist('research_indicator_ids[]')
    extension_indicator_ids = request.form.getlist('extension_indicator_ids[]')

    if not term_id or not academic_rank:
        flash("Please fill all required fields.", "warning")
        return redirect(url_for('ret_chair.ret_chair_dashboard'))

    # Parse quantities for each checked indicator
    research_indicators = []
    for r_id in research_indicator_ids:
        qty_val = request.form.get(f'research_quantity_{r_id}', 1)
        try:
            qty = int(qty_val)
            if qty < 1:
                qty = 1
        except ValueError:
            qty = 1
        research_indicators.append((int(r_id), qty))

    extension_indicators = []
    for e_id in extension_indicator_ids:
        qty_val = request.form.get(f'extension_quantity_{e_id}', 1)
        try:
            qty = int(qty_val)
            if qty < 1:
                qty = 1
        except ValueError:
            qty = 1
        extension_indicators.append((int(e_id), qty))

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        success, msg = save_ret_rule(conn, cursor, int(term_id), academic_rank,
                                     int(research_selections), int(extension_selections),
                                     research_indicators, extension_indicators)
        cursor.close()
        conn.close()

        if success:
            flash(msg, "success")
        else:
            flash(msg, "danger")
    except Exception as e:
        flash(f"Error saving rule: {str(e)}", "danger")

    return redirect(url_for('ret_chair.ret_chair_dashboard'))


@ret_chair_bp.route('/delete_rule', methods=['POST'])
@role_required('RET_CHAIR')
def ret_chair_delete_rule():
    rule_id = request.form.get('rule_id')
    category_type = request.form.get('category_type')
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        success = delete_ret_rule(conn, cursor, rule_id, category_type)
        cursor.close()
        conn.close()
        if success:
            flash("Rule deleted successfully.", "success")
        else:
            flash("Failed to delete rule.", "danger")
    except Exception as e:
        flash(f"Error deleting rule: {str(e)}", "danger")
    return redirect(url_for('ret_chair.ret_chair_dashboard'))


@ret_chair_bp.route('/review_ipcr/<int:emp_id>')
@role_required('RET_CHAIR')
def review_ipcr(emp_id):
    """
    AJAX endpoint — returns JSON payload of Research/Extension targets for RET review.
    Creates a tbl_ipcr_ret_review record if one doesn't exist.
    """
    import time
    print(f"\n[DEBUG] === Entered review_ipcr for emp_id={emp_id} ===")
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        ret_chair_emp_id = session.get('user_id')
        terms = get_all_terms(cursor)
        active_term = next((t for t in terms if t['is_active'] == 1), None)

        if not active_term:
            print("[DEBUG] No active term found.")
            return jsonify({'error': 'No active term found.'}), 400

        term_id = active_term['term_id']
        print(f"[DEBUG] Active term_id={term_id}")

        # Check overall IPCR status for sequential tracking guardrails
        from app.models.connection import get_overall_ipcr_status
        ipcr_status = get_overall_ipcr_status(cursor, emp_id, term_id)

        # Fetch overall status of review header if it exists
        cursor.execute(
            "SELECT overall_status FROM tbl_ipcr_ret_review WHERE emp_id = %s AND term_id = %s",
            (emp_id, term_id)
        )
        review_row = cursor.fetchone()
        existing_status = review_row[0] if review_row else None

        # Block if unsubmitted and not already reviewed/returned
        if ipcr_status == 'draft' and existing_status not in ('Approved', 'Rejected'):
            return jsonify({'error': 'Faculty has not submitted their choices for review yet.'}), 403

        # Fetch or create RET review record
        t0 = time.time()
        review_id = get_or_create_ret_review(conn, cursor, emp_id, term_id, ret_chair_emp_id)
        print(f"[DEBUG] get_or_create_ret_review took {time.time() - t0:.4f}s. review_id={review_id}")

        # Fetch RET review items
        t0 = time.time()
        items = get_ret_review_items(cursor, review_id)
        print(f"[DEBUG] get_ret_review_items took {time.time() - t0:.4f}s. Found {len(items)} items.")

        # Fetch overall status and remarks
        cursor.execute(
            "SELECT overall_status, overall_remarks FROM tbl_ipcr_ret_review WHERE review_id = %s",
            (review_id,)
        )
        review_row = cursor.fetchone()
        overall_status = review_row[0] if review_row else 'Pending'
        overall_remarks = review_row[1] if review_row else ''

        # Fetch faculty details
        cursor.execute(
            "SELECT CONCAT(first_name, ' ', last_name), academic_rank FROM tbl_employee_profiles WHERE emp_id = %s",
            (emp_id,)
        )
        fac_row = cursor.fetchone()
        faculty_name = fac_row[0] if fac_row else 'Unknown'
        academic_rank = fac_row[1] if fac_row else ''
        print(f"[DEBUG] Faculty: {faculty_name}, Rank: {academic_rank}")

        # Fetch available indicators for this rank and active term
        t0 = time.time()
        cursor.execute("""
            SELECT mi.indicator_id, mi.indicator_description, tc.category_name, rri.target_quantity
            FROM tbl_ret_rules r
            JOIN tbl_ret_rule_indicators rri ON r.rule_id = rri.rule_id
            JOIN tbl_master_indicators mi ON rri.indicator_id = mi.indicator_id
            JOIN tbl_target_categories tc ON mi.category_id = tc.category_id
            WHERE r.academic_rank = %s AND mi.term_id = %s
        """, (academic_rank, term_id))
        rules_indicators = cursor.fetchall()
        print(f"[DEBUG] Fetch rules indicators query took {time.time() - t0:.4f}s. Found {len(rules_indicators)} indicators.")

        all_ret_indicators = []
        for ind_id, desc, cat, qty in rules_indicators:
            all_ret_indicators.append({
                'indicator_id': ind_id,
                'indicator_description': desc,
                'category_name': cat,
                'target_quantity': qty
            })

        serializable_items = []
        selected_ids = set()
        for item in items:
            rev_qty = item['reviewed_quantity']
            if rev_qty is not None and rev_qty > 0:
                serializable_items.append({
                    'item_id': item['item_id'],
                    'draft_id': item['draft_id'],
                    'indicator_id': item['indicator_id'],
                    'indicator_description': item['indicator_description'],
                    'category_name': item['category_name'],
                    'original_quantity': item['original_quantity'],
                    'reviewed_quantity': rev_qty,
                    'item_remarks': item['item_remarks'] or '',
                })
                selected_ids.add(item['indicator_id'])

        unpicked = []
        inactive_item_ids = {item['indicator_id']: item['item_id'] for item in items if item['reviewed_quantity'] is None or item['reviewed_quantity'] <= 0}
        for ind in all_ret_indicators:
            if ind['indicator_id'] not in selected_ids:
                ind_copy = ind.copy()
                ind_copy['item_id'] = inactive_item_ids.get(ind['indicator_id'])
                unpicked.append(ind_copy)

        print(f"[DEBUG] review_ipcr returning JSON payload successfully. Review ID={review_id}")
        return jsonify({
            'review_id': review_id,
            'emp_id': emp_id,
            'faculty_name': faculty_name,
            'academic_rank': academic_rank,
            'overall_status': overall_status,
            'overall_remarks': overall_remarks or '',
            'items': serializable_items,
            'unpicked': unpicked
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@ret_chair_bp.route('/edit_review_item', methods=['POST'])
@role_required('RET_CHAIR')
def edit_review_item():
    """
    Saves an edited quantity and optional remark for one RET review item row.
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
        success, msg = update_ret_review_item(conn, cursor, int(item_id), int(reviewed_quantity), item_remarks)
        return jsonify({'success': success, 'message': msg})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@ret_chair_bp.route('/save_review_items', methods=['POST'])
@role_required('RET_CHAIR')
def save_review_items():
    data = request.get_json()
    review_id = data.get('review_id')
    items = data.get('items')

    if not review_id or items is None:
        return jsonify({'success': False, 'message': 'Missing review_id or items.'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        from app.models.ret_chair import save_ret_review_items
        success, msg = save_ret_review_items(cursor, conn, int(review_id), items)
        return jsonify({'success': success, 'message': msg})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        cursor.close()
        conn.close()


@ret_chair_bp.route('/decide_ipcr', methods=['POST'])
@role_required('RET_CHAIR')
def decide_ipcr():
    """
    Approves or rejects the RET selections.
    """
    import json
    review_id = request.form.get('review_id')
    action = request.form.get('action')           # 'approve' or 'reject'
    overall_remarks = request.form.get('overall_remarks', '').strip()
    items_json = request.form.get('items_json')

    if not review_id or action not in ('approve', 'reject'):
        flash("Invalid decision parameters.", "danger")
        return redirect(url_for('ret_chair.ret_chair_dashboard'))

    if action == 'reject' and not overall_remarks:
        flash("Remarks / Reason is required when returning the IPCR to faculty.", "danger")
        return redirect(url_for('ret_chair.ret_chair_dashboard'))

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Check overall IPCR status for sequential tracking guardrails
        cursor.execute(
            "SELECT emp_id, term_id FROM tbl_ipcr_ret_review WHERE review_id = %s",
            (review_id,)
        )
        row = cursor.fetchone()
        if row:
            emp_id, term_id = row
            from app.models.connection import get_overall_ipcr_status
            ipcr_status = get_overall_ipcr_status(cursor, emp_id, term_id)

            if ipcr_status == 'draft':
                flash("Faculty has not submitted their choices for review yet.", "danger")
                return redirect(url_for('ret_chair.ret_chair_dashboard'))

        # If items are submitted inline, save them first inside the same transaction
        if items_json:
            try:
                items = json.loads(items_json)
                from app.models.ret_chair import save_ret_review_items
                save_success, save_msg = save_ret_review_items(cursor, conn, int(review_id), items)
                if not save_success:
                    flash(f"Failed to save targets: {save_msg}", "danger")
                    return redirect(url_for('ret_chair.ret_chair_dashboard'))
            except Exception as json_err:
                flash(f"Invalid target items format: {str(json_err)}", "danger")
                return redirect(url_for('ret_chair.ret_chair_dashboard'))

        success, msg = decide_ret_review(conn, cursor, int(review_id), action, overall_remarks)
        flash(msg, "success" if success else "danger")
    except Exception as e:
        flash(f"Error processing decision: {str(e)}", "danger")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('ret_chair.ret_chair_dashboard'))
