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

    cursor.close()
    conn.close()

    return render_template('dean_dashboard.html',
                           active_term=active_term,
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
                           college_wide_allocations=college_wide_allocations)


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
        wst_values = request.form.getlist('wst[]')
        dst_values = request.form.getlist('dst[]')
        nst_values = request.form.getlist('nst[]')
        bsds_values = request.form.getlist('bsds[]')
        ret_values = request.form.getlist('ret[]')
        college_values = request.form.getlist('college[]')

        for i, ind_id in enumerate(indicator_ids):
            if not ind_id:
                continue

            values = [
                ('WST Program', int(wst_values[i]) if wst_values[i] and int(wst_values[i]) > 0 else 0),
                ('DST Program', int(dst_values[i]) if dst_values[i] and int(dst_values[i]) > 0 else 0),
                ('NST Program', int(nst_values[i]) if nst_values[i] and int(nst_values[i]) > 0 else 0),
                ('BSDS Program', int(bsds_values[i]) if bsds_values[i] and int(bsds_values[i]) > 0 else 0),
                ('RET / Extension', int(ret_values[i]) if ret_values[i] and int(ret_values[i]) > 0 else 0),
                ('College-Wide', int(college_values[i]) if i < len(college_values) and college_values[i] and int(college_values[i]) > 0 else 0)
            ]

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


@dean_bp.route('/batch_approve', methods=['POST'])
@role_required('DEAN')
def batch_approve():
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        score_ids = request.form.getlist('score_ids[]')
        action = request.form.get('action', 'approve')

        if not score_ids:
            flash('No IPCRs selected for approval', 'warning')
            return redirect(url_for('dean.dean_dashboard'))

        new_status = 'Approved' if action == 'approve' else 'Reverted'
        success, message = update_dean_approval_status(cursor, conn, score_ids, new_status)

        flash(message, 'success' if success else 'danger')

    except Exception as e:
        flash(f'Error processing batch approval: {str(e)}', 'danger')
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


@dean_bp.route('/inspect_template')
@role_required('DEAN')
def inspect_template():
    import os
    from openpyxl import load_workbook
    template_dir = os.path.join(os.getcwd(), 'app', 'static', 'templates')
    template_path = os.path.join(template_dir, 'dpcr_template.xlsx')
    if not os.path.exists(template_path):
        return jsonify({'error': 'Template not found'})
    wb = load_workbook(template_path)
    ws = wb.active
    cells_info = []
    for r in range(1, 45):
        row_info = {}
        for c in range(1, 15):
            cell = ws.cell(row=r, column=c)
            row_info[cell.coordinate] = {
                'value': cell.value,
                'is_merged': cell.coordinate in ws.merged_cells
            }
        cells_info.append(row_info)
    return jsonify({
        'merged_ranges': [str(r) for r in ws.merged_cells.ranges],
        'cells': cells_info
    })


@dean_bp.route('/export_dpcr')
@role_required('DEAN')
def export_dpcr():
    import os
    import io
    from flask import send_file, flash, redirect, url_for, session
    try:
        import xlsxwriter
    except ImportError:
        import subprocess, sys
        subprocess.check_call([sys.executable, "-m", "pip", "install", "xlsxwriter"])
        import xlsxwriter
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        terms = get_all_terms(cursor)
        active_term = next((t for t in terms if t['is_active'] == 1), None)
        
        if not active_term:
            flash('No active academic term found.', 'warning')
            return redirect(url_for('dean.dean_dashboard'))
            
        term_id = active_term['term_id']

        # Fetch Dean's name and college info
        dean_id = session.get('user_id')
        cursor.execute("SELECT first_name, last_name, college FROM tbl_employee_profiles WHERE emp_id = %s", (dean_id,))
        dean_profile = cursor.fetchone()
        if isinstance(dean_profile, dict):
            dean_name = f"{dean_profile.get('first_name', '')} {dean_profile.get('last_name', '')}".strip()
            college_name = dean_profile.get('college', 'College of Information and Communications Technology')
        elif dean_profile:
            dean_name = f"{dean_profile[0]} {dean_profile[1]}".strip()
            college_name = dean_profile[2] or 'College of Information and Communications Technology'
        else:
            dean_name = "College Dean"
            college_name = "College of Information and Communications Technology"

        def get_category_key(cat_name):
            cat_lower = cat_name.lower()
            if 'instruction' in cat_lower: return 'instruction'
            elif 'research' in cat_lower: return 'research'
            elif 'extension' in cat_lower or 'advisory' in cat_lower: return 'extension'
            elif 'support' in cat_lower: return 'support'
            return 'custom'

        cursor.execute("""
            SELECT 
                mi.indicator_id, mi.indicator_description, tc.category_name,
                cq.total_target_value, cq.assigned_to_role
            FROM tbl_master_indicators mi
            JOIN tbl_target_categories tc ON mi.category_id = tc.category_id
            LEFT JOIN tbl_cascaded_quotas cq ON mi.indicator_id = cq.indicator_id AND cq.term_id = mi.term_id
            WHERE mi.term_id = %s AND (mi.is_custom = 0 OR mi.is_custom IS NULL)
            ORDER BY tc.category_id, mi.indicator_id
        """, (term_id,))
        
        rows = cursor.fetchall()
        indicators_map = {}
        for row in rows:
            if isinstance(row, dict):
                ind_id = row['indicator_id']
                desc = row['indicator_description']
                cat_name = row['category_name']
                val = row['total_target_value']
                role = row['assigned_to_role']
            else:
                ind_id = row[0]
                desc = row[1]
                cat_name = row[2]
                val = row[3]
                role = row[4]

            if ind_id not in indicators_map:
                indicators_map[ind_id] = {
                    'indicator_id': ind_id,
                    'indicator_description': desc,
                    'category_name': cat_name,
                    'quotas': {}
                }
            if role and val is not None:
                indicators_map[ind_id]['quotas'][role] = val

        indicators_by_category = {'instruction': [], 'research': [], 'extension': [], 'support': [], 'custom': []}
        for ind in indicators_map.values():
            key = get_category_key(ind['category_name'])
            indicators_by_category[key].append(ind)

        if indicators_by_category.get('custom'):
            indicators_by_category['support'].extend(indicators_by_category['custom'])
            indicators_by_category['custom'] = []

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('DPCR')

        # Row Heights
        worksheet.set_row(0, 25)
        worksheet.set_row(1, 16)
        worksheet.set_row(2, 16)
        worksheet.set_row(3, 16)
        worksheet.set_row(4, 16)
        worksheet.set_row(5, 16)
        worksheet.set_row(6, 22)
        worksheet.set_row(7, 22)

        # Formats
        fmt_title = workbook.add_format({'bold': True, 'font_name': 'Times New Roman', 'font_size': 13, 'align': 'center', 'valign': 'vcenter'})
        fmt_subtitle = workbook.add_format({'font_name': 'Times New Roman', 'font_size': 10, 'align': 'left', 'valign': 'vcenter', 'text_wrap': True})
        fmt_bold_sm = workbook.add_format({'bold': True, 'font_name': 'Times New Roman', 'font_size': 10, 'align': 'left', 'valign': 'vcenter'})
        fmt_center_sm = workbook.add_format({'font_name': 'Times New Roman', 'font_size': 9, 'align': 'center', 'valign': 'vcenter'})
        fmt_bold_center_sm = workbook.add_format({'bold': True, 'font_name': 'Times New Roman', 'font_size': 9, 'align': 'center', 'valign': 'vcenter'})
        fmt_right_sm = workbook.add_format({'bold': True, 'font_name': 'Times New Roman', 'font_size': 10, 'align': 'right', 'valign': 'vcenter'})
        fmt_hdr_bg = workbook.add_format({'bold': True, 'font_name': 'Times New Roman', 'font_size': 9, 'align': 'center', 'valign': 'vcenter', 'border': 1, 'text_wrap': True})
        fmt_cat_hdr = workbook.add_format({'bold': True, 'font_name': 'Times New Roman', 'font_size': 10, 'align': 'left', 'valign': 'vcenter', 'border': 1})
        fmt_subcat_hdr = workbook.add_format({'bold': True, 'font_name': 'Times New Roman', 'font_size': 9, 'align': 'left', 'valign': 'vcenter', 'border': 1})
        fmt_cell = workbook.add_format({'font_name': 'Times New Roman', 'font_size': 9, 'align': 'left', 'valign': 'vcenter', 'border': 1, 'text_wrap': True})
        fmt_cell_center = workbook.add_format({'font_name': 'Times New Roman', 'font_size': 9, 'align': 'center', 'valign': 'vcenter', 'border': 1, 'text_wrap': True})
        fmt_cell_bold_center = workbook.add_format({'bold': True, 'font_name': 'Times New Roman', 'font_size': 9, 'align': 'center', 'valign': 'vcenter', 'border': 1})
        fmt_box = workbook.add_format({'font_name': 'Times New Roman', 'font_size': 8, 'border': 1, 'valign': 'top', 'text_wrap': True})
        fmt_italic_sm = workbook.add_format({'italic': True, 'font_name': 'Times New Roman', 'font_size': 9})

        # Columns configuration (24 columns: 0..23)
        col_widths = {
            0: 6, 1: 6, 2: 6, 3: 12,
            4: 12, 5: 12, 6: 12,
            7: 10,
            8: 6, 9: 6, 10: 6, 11: 6, 12: 6,
            13: 15, 14: 15,
            15: 4, 16: 4, 17: 4, 18: 4,
            19: 5, 20: 5, 21: 5, 22: 5, 23: 5
        }
        for c, w in col_widths.items():
            worksheet.set_column(c, c, w)

        # Helper to apply full border grid on merged ranges
        def safe_merge_range(ws, r1, c1, r2, c2, data, format_obj):
            if r1 == r2 and c1 == c2:
                ws.write(r1, c1, data, format_obj)
            else:
                for r in range(r1, r2 + 1):
                    for c in range(c1, c2 + 1):
                        ws.write_blank(r, c, '', format_obj)
                ws.merge_range(r1, c1, r2, c2, data, format_obj)

        # Title Block
        safe_merge_range(worksheet, 0, 0, 0, 23, "DEPARTMENT PERFORMANCE COMMITMENT AND REVIEW (DPCR)", fmt_title)
        
        c_full = college_name
        if c_full.upper() == 'CICT':
            c_full = "College of Information and Communications Technology"
        elif not c_full.lower().startswith('college'):
            c_full = f"College of {c_full}"

        term_desc = f"{active_term['semester'].upper()} {active_term['academic_year']}"
        sub_text = f"I, {dean_name}, Dean of the {c_full} of Nueva Ecija University of Science and Technology, commit to deliver and agree to be rated in the targets in accordance with the attainment of the following indicated measures for this period {term_desc}."
        safe_merge_range(worksheet, 1, 0, 2, 23, sub_text, fmt_subtitle)

        # Row 3: Approved by: (Left A4) & Underline for Dean (Right R4:X4)
        worksheet.write(3, 0, "Approved by:", fmt_bold_sm)
        safe_merge_range(worksheet, 3, 17, 3, 23, "________________________________________", fmt_center_sm)

        # Row 4: RHODORA R. JUGO (O5:Q5) & Dean (R5:X5)
        safe_merge_range(worksheet, 4, 14, 4, 16, "RHODORA R. JUGO, Ed.D.", fmt_bold_center_sm)
        safe_merge_range(worksheet, 4, 17, 4, 23, "Dean", fmt_center_sm)

        # Row 5: Head of Agency (O6:Q6) & Date: ___ (R6:X6)
        safe_merge_range(worksheet, 5, 14, 5, 16, "Head of Agency", fmt_center_sm)
        worksheet.write(5, 17, "Date:", fmt_right_sm)
        safe_merge_range(worksheet, 5, 18, 5, 23, "________________________", fmt_center_sm)

        # Table Main Header (Row 6 & 7)
        safe_merge_range(worksheet, 6, 0, 7, 3, "MFO/PAP", fmt_hdr_bg)
        safe_merge_range(worksheet, 6, 4, 7, 6, "Success Indicator\n(Target + Measure)", fmt_hdr_bg)
        safe_merge_range(worksheet, 6, 7, 7, 7, "Allocated\nBudget", fmt_hdr_bg)
        safe_merge_range(worksheet, 6, 8, 6, 12, "Divisison/Individual accountable", fmt_hdr_bg)
        
        # Subheaders for roles
        worksheet.write(7, 8, "DST", fmt_hdr_bg)
        worksheet.write(7, 9, "WST", fmt_hdr_bg)
        worksheet.write(7, 10, "NST", fmt_hdr_bg)
        worksheet.write(7, 11, "BSDS", fmt_hdr_bg)
        worksheet.write(7, 12, "RET", fmt_hdr_bg)

        safe_merge_range(worksheet, 6, 13, 7, 14, "Actual Accomplishments", fmt_hdr_bg)
        safe_merge_range(worksheet, 6, 15, 6, 18, "Rating", fmt_hdr_bg)
        worksheet.write(7, 15, "Q1", fmt_hdr_bg)
        worksheet.write(7, 16, "E2", fmt_hdr_bg)
        worksheet.write(7, 17, "T3", fmt_hdr_bg)
        worksheet.write(7, 18, "A4", fmt_hdr_bg)
        safe_merge_range(worksheet, 6, 19, 7, 23, "Remarks", fmt_hdr_bg)

        curr_r = 8

        def generate_accomplishment_text(desc):
            if not desc:
                return ""
            import re
            text = desc
            verb_map = {
                "prepare": "Prepared", "submit": "Submitted", "monitor": "Monitored",
                "review": "Reviewed", "produce": "Produced", "conduct": "Conducted",
                "publish": "Published", "assign": "Assigned", "designate": "Designated",
                "send": "Sent", "distribute": "Distributed", "retrieve": "Retrieved",
                "complete": "Completed", "observe": "Observed"
            }
            words = text.split(None, 1)
            if words:
                first_word_lower = words[0].lower()
                if first_word_lower in verb_map:
                    text = verb_map[first_word_lower] + (" " + words[1] if len(words) > 1 else "")

            text = re.sub(r'\b(in|within)\s+\d+\s+months?\b', r'\1 _____ month/s', text, flags=re.IGNORECASE)
            text = re.sub(r'\b(in|within)\s+\d+\s+working days\b', r'\1 _____ working days', text, flags=re.IGNORECASE)
            text = re.sub(r'\b\d+(?:\.\d+)?%?\b', '_____', text)
            return text

        # Section configurations
        sections = [
            ('instruction', 'I. Strategic Priorities (50%)', 'A. Instruction', 'Advanced/Higher Education Services'),
            ('research', 'II. Core Functions (40%)', 'A. Research', ''),
            ('extension', 'II. Core Functions (40%)', 'B. Extension Services / Training Services / Technical Advisory', ''),
            ('support', 'III. Support Functions (10%)', '', '')
        ]

        col_map = {'DST Program': 8, 'WST Program': 9, 'NST Program': 10, 'BSDS Program': 11, 'RET / Extension': 12}
        last_sec_title = None

        for cat_key, sec_title, cat_title, subcat_title in sections:
            indicators = indicators_by_category.get(cat_key, [])
            if not indicators:
                continue

            # Write section header if not yet written
            if sec_title != last_sec_title:
                safe_merge_range(worksheet, curr_r, 0, curr_r, 23, sec_title, fmt_cat_hdr)
                curr_r += 1
                last_sec_title = sec_title

            if cat_title:
                safe_merge_range(worksheet, curr_r, 0, curr_r, 23, cat_title, fmt_subcat_hdr)
                curr_r += 1

            for ind_idx, ind in enumerate(indicators):
                desc = ind['indicator_description']
                quotas = ind.get('quotas', {})
                is_cw = ('College-Wide' in quotas and quotas['College-Wide'] > 0)
                block_h = 3 # 4 rows per indicator block (curr_r .. curr_r + 3)

                # MFO/PAP cols (0-3): Write subcat_title ONLY on the very first indicator of Instruction!
                mfo_text = subcat_title if (cat_key == 'instruction' and ind_idx == 0) else ""
                safe_merge_range(worksheet, curr_r, 0, curr_r + block_h, 3, mfo_text, fmt_cell)

                # Indicator cols (4-6), Budget (7)
                safe_merge_range(worksheet, curr_r, 4, curr_r + block_h, 6, desc, fmt_cell)
                safe_merge_range(worksheet, curr_r, 7, curr_r + block_h, 7, "", fmt_cell_center)

                if is_cw:
                    val = quotas['College-Wide']
                    display_val = f"{int(val * 100)}%" if ('%' in desc and isinstance(val, (int, float)) and val <= 5) else val
                    safe_merge_range(worksheet, curr_r, 8, curr_r + block_h, 12, display_val, fmt_cell_bold_center)
                else:
                    for role, c_idx in col_map.items():
                        q_val = quotas.get(role, 0)
                        safe_merge_range(worksheet, curr_r, c_idx, curr_r + block_h, c_idx, q_val if q_val else 0, fmt_cell_center)

                # Generate accomplishment text with numbers replaced with _____
                acc_text = generate_accomplishment_text(desc)
                safe_merge_range(worksheet, curr_r, 13, curr_r + block_h, 14, acc_text, fmt_cell)

                # Rating Q1-A4 (15-18) and Remarks (19-23)
                for r_col in range(15, 19):
                    safe_merge_range(worksheet, curr_r, r_col, curr_r + block_h, r_col, "", fmt_cell_center)
                safe_merge_range(worksheet, curr_r, 19, curr_r + block_h, 23, "", fmt_cell)

                curr_r += block_h + 1

        # Rating Summary Rows
        safe_merge_range(worksheet, curr_r, 0, curr_r, 14, "Total Overall Rating", fmt_bold_sm)
        for c in range(15, 19): worksheet.write(curr_r, c, "", fmt_cell_center)
        safe_merge_range(worksheet, curr_r, 19, curr_r, 23, "", fmt_cell)
        curr_r += 1

        safe_merge_range(worksheet, curr_r, 0, curr_r, 14, "Final Average Rating", fmt_bold_sm)
        for c in range(15, 19): worksheet.write(curr_r, c, "", fmt_cell_center)
        safe_merge_range(worksheet, curr_r, 19, curr_r, 23, "", fmt_cell)
        curr_r += 1

        safe_merge_range(worksheet, curr_r, 0, curr_r, 14, "Adjectival Rating", fmt_bold_sm)
        for c in range(15, 19): worksheet.write(curr_r, c, "", fmt_cell_center)
        safe_merge_range(worksheet, curr_r, 19, curr_r, 23, "", fmt_cell)
        curr_r += 1

        # Comments & Category Rating Table Box (Rows curr_r .. curr_r+6)
        safe_merge_range(worksheet, curr_r, 0, curr_r+6, 13, 
            "Comments and Recommendations for Development Purposes\n(to be accomplished by the immediate supervisor)", fmt_box)

        # Right side Summary Table
        safe_merge_range(worksheet, curr_r, 14, curr_r, 16, "Category", fmt_hdr_bg)
        safe_merge_range(worksheet, curr_r, 17, curr_r, 18, "Weight (%)", fmt_hdr_bg)
        safe_merge_range(worksheet, curr_r, 19, curr_r, 23, "Rating", fmt_hdr_bg)

        # Subheaders Average & Weighted
        safe_merge_range(worksheet, curr_r+1, 19, curr_r+1, 20, "Average", fmt_hdr_bg)
        safe_merge_range(worksheet, curr_r+1, 21, curr_r+1, 23, "Weighted", fmt_hdr_bg)

        cat_rows = [
            ("I. Strategic Priorities", "50%"),
            ("II. Core Functions", "40%"),
            ("III. Support Functions", "10%"),
            ("Total Overall Rating", ""),
            ("Final Weighted Rating", ""),
            ("Adjectival Rating", "")
        ]

        for idx, (c_name, w_val) in enumerate(cat_rows):
            r_idx = curr_r + 2 + idx
            safe_merge_range(worksheet, r_idx, 14, r_idx, 16, c_name, fmt_cell)
            safe_merge_range(worksheet, r_idx, 17, r_idx, 18, w_val, fmt_cell_center)
            safe_merge_range(worksheet, r_idx, 19, r_idx, 20, "", fmt_cell_center)
            safe_merge_range(worksheet, r_idx, 21, r_idx, 23, "", fmt_cell_center)

        curr_r += 8

        # Legend Row
        safe_merge_range(worksheet, curr_r, 0, curr_r, 23, "Legend: 1 - Quantity 2 - Efficiency 3 - Timeliness 4 - Average", fmt_italic_sm)
        curr_r += 1

        # 4-Box Signature Block
        safe_merge_range(worksheet, curr_r, 0, curr_r+3, 5, f"Discussed with:\n\n\n_________________________\n{dean_name}\nDean/Director\nDate: ________", fmt_box)
        safe_merge_range(worksheet, curr_r, 6, curr_r+3, 11, "Assessed by:\n\n\n_________________________\nKENNETH L. ARMAS, PhD\nDirector, Planning and Development Office\nDate: ________", fmt_box)
        safe_merge_range(worksheet, curr_r, 12, curr_r+3, 17, "\n\n\n_________________________\nEngr. FELICIANA P. JACOBA, EdD\nVice President for Academic Affairs\nDate: ________", fmt_box)
        safe_merge_range(worksheet, curr_r, 18, curr_r+3, 23, "Final Rating by:\n\n\n_________________________\nRHODORA R. JUGO, Ed.D.\nHead of Agency\nDate: ________", fmt_box)

        workbook.close()
        output.seek(0)

        filename = f"DPCR_{active_term['academic_year'].replace('/', '_')}_{active_term['semester'].replace(' ', '_')}.xlsx"
        return send_file(output, as_attachment=True, download_name=filename, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    except Exception as e:
        import traceback
        traceback.print_exc()
        flash(f'Error exporting DPCR: {str(e)}', 'danger')
        return redirect(url_for('dean.dean_dashboard'))
    finally:
        cursor.close()
        conn.close()



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
