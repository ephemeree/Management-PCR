import os
import logging
from flask import render_template
from app.services.mail_service import send_async_email

logger = logging.getLogger(__name__)


def _ensure_notification_table(cursor):
    """Safely checks or ignores DDL if user has only DML permissions."""
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tbl_ipcr_approval_notifications (
                notification_id  INT NOT NULL AUTO_INCREMENT,
                emp_id           INT NOT NULL,
                term_id          INT NOT NULL,
                tier             ENUM('TIER_1', 'TIER_2') NOT NULL,
                event_type       VARCHAR(60) NOT NULL,
                recipient_emails TEXT NOT NULL,
                sent_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                status           ENUM('SENT', 'FAILED', 'DEV_LOGGED') NOT NULL DEFAULT 'SENT',
                error_message    TEXT NULL,
                PRIMARY KEY (notification_id),
                UNIQUE KEY uq_emp_term_tier (emp_id, term_id, tier),
                KEY idx_emp_term (emp_id, term_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
        """)
    except Exception:
        pass


def _get_base_url(custom_base_url: str = None) -> str:
    if custom_base_url and custom_base_url.strip():
        return custom_base_url.rstrip('/')
    env_url = os.getenv('APP_BASE_URL', '').strip()
    if env_url:
        return env_url.rstrip('/')
    try:
        from flask import request
        if request and request.host_url:
            return request.host_url.rstrip('/')
    except Exception:
        pass
    return "http://127.0.0.1:5000"


def _format_term_period(term_row: dict) -> str:
    if not term_row:
        return "Current Academic Term"
    ay = term_row.get('academic_year', '')
    sem = term_row.get('semester', '')
    p_start = term_row.get('period_start')
    p_end = term_row.get('period_end')
    
    parts = []
    if ay:
        parts.append(f"A.Y. {ay}")
    if sem:
        parts.append(f"({sem})")
    if p_start and p_end:
        try:
            parts.append(f"[{p_start.strftime('%b %Y')} - {p_end.strftime('%b %Y')}]")
        except Exception:
            pass
    return " ".join(parts) if parts else "Current Academic Term"


def check_and_trigger_tier1_notification(conn, cursor, emp_id: int, term_id: int, base_url: str = None) -> tuple[bool, str]:
    """
    Checks if both Program Chair and RET Chair have approved the faculty member's IPCR targets.
    If so, sends Tier 1 notifications asynchronously to:
      1. Dean (ready for final approval)
      2. Faculty Member (passed first level)
    Ensures idempotency using tbl_ipcr_approval_notifications.
    """
    try:
        _ensure_notification_table(cursor)

        # 1. Idempotency Check: Don't send if already sent for this term
        cursor.execute("""
            SELECT notification_id FROM tbl_ipcr_approval_notifications
            WHERE emp_id = %s AND term_id = %s AND tier = 'TIER_1'
        """, (emp_id, term_id))
        if cursor.fetchone():
            return False, "Tier 1 notification already sent."

        # 2. Check Faculty Profile
        cursor.execute("""
            SELECT ep.first_name, ep.last_name, ep.academic_rank, ep.designation,
                   ep.assigned_program, ep.specialization, ac.corporate_email
            FROM tbl_employee_profiles ep
            LEFT JOIN tbl_auth_credentials ac ON ep.emp_id = ac.emp_id
            WHERE ep.emp_id = %s
        """, (emp_id,))
        fac_row = cursor.fetchone()
        if not fac_row:
            return False, f"Faculty member #{emp_id} not found."

        first_name, last_name, academic_rank, designation, assigned_prog, spec, faculty_email = fac_row
        faculty_name = f"{first_name} {last_name}".strip()
        department = spec or assigned_prog or "CICT"

        # 3. Check Program Chair Approval Status
        cursor.execute("""
            SELECT overall_status FROM tbl_ipcr_chair_review
            WHERE emp_id = %s AND term_id = %s
        """, (emp_id, term_id))
        chair_row = cursor.fetchone()
        if not chair_row or chair_row[0] != 'Approved':
            return False, "Program Chair has not approved yet."

        # 4. Check Research Targets & RET Chair Approval Status
        cursor.execute("""
            SELECT COUNT(*)
            FROM tbl_draft_targets dt
            JOIN tbl_master_indicators mi ON dt.indicator_id = mi.indicator_id
            JOIN tbl_target_categories tc ON mi.category_id = tc.category_id
            WHERE dt.emp_id = %s AND mi.term_id = %s
              AND tc.slug = 'research' AND dt.proposed_quantity > 0
        """, (emp_id, term_id))
        has_research = cursor.fetchone()[0] > 0

        if has_research:
            cursor.execute("""
                SELECT overall_status FROM tbl_ipcr_ret_review
                WHERE emp_id = %s AND term_id = %s
            """, (emp_id, term_id))
            ret_row = cursor.fetchone()
            if not ret_row or ret_row[0] != 'Approved':
                return False, "RET Chair has not approved yet."

        # 5. Fetch Term info
        cursor.execute("""
            SELECT academic_year, semester, period_start, period_end
            FROM tbl_academic_terms WHERE term_id = %s
        """, (term_id,))
        term_data = cursor.fetchone()
        term_dict = {
            'academic_year': term_data[0] if term_data else '',
            'semester': term_data[1] if term_data else '',
            'period_start': term_data[2] if term_data else None,
            'period_end': term_data[3] if term_data else None
        } if term_data else {}
        period_display = _format_term_period(term_dict)

        resolved_base_url = _get_base_url(base_url)

        recipients_logged = []
        if faculty_email:
            recipients_logged.append(f"Faculty: {faculty_email}")

        # 7. Record Notification in DB first (idempotency barrier)
        cursor.execute("""
            INSERT INTO tbl_ipcr_approval_notifications
                (emp_id, term_id, tier, event_type, recipient_emails, status)
            VALUES (%s, %s, 'TIER_1', 'TIER_1_APPROVED', %s, 'SENT')
        """, (emp_id, term_id, ", ".join(recipients_logged) if recipients_logged else "No email registered"))
        conn.commit()

        # 8. (Dean email dispatch disabled for now per user request)

        # 9. Render & Dispatch Email to Faculty Member
        if faculty_email:
            faculty_action_url = f"{resolved_base_url}/faculty"
            html_fac = render_template('emails/tier1_faculty.html',
                faculty_name=faculty_name,
                academic_rank=academic_rank,
                department=department,
                period_display=period_display,
                action_url=faculty_action_url
            )
            text_fac = (
                f"Dear {faculty_name},\n\n"
                f"Your IPCR targets for {period_display} have been approved by both the Program Chair and the RET Chair.\n\n"
                f"View your dashboard at: {faculty_action_url}\n"
            )
            send_async_email(
                subject=f"[D-IPCR] IPCR Targets Approved by Program Chair and RET Chair - {period_display}",
                recipients=[faculty_email],
                html_body=html_fac,
                text_body=text_fac
            )

        logger.info(f"[TIER 1 NOTIFICATION TRIGGERED] emp_id={emp_id}, term_id={term_id}")
        return True, "Tier 1 notifications dispatched successfully."

    except Exception as e:
        logger.error(f"Error triggering Tier 1 notification: {e}")
        return False, str(e)


def check_and_trigger_tier2_notification(conn, cursor, emp_id: int, term_id: int, base_url: str = None) -> tuple[bool, str]:
    """
    Checks if the Dean has granted final approval on the faculty member's IPCR.
    If so, sends Tier 2 (Final) notifications asynchronously to:
      1. Faculty Member
      2. Program Chair
      3. RET Chair
    Ensures idempotency using tbl_ipcr_approval_notifications.
    """
    try:
        _ensure_notification_table(cursor)

        # 1. Idempotency Check
        cursor.execute("""
            SELECT notification_id FROM tbl_ipcr_approval_notifications
            WHERE emp_id = %s AND term_id = %s AND tier = 'TIER_2'
        """, (emp_id, term_id))
        if cursor.fetchone():
            return False, "Tier 2 notification already sent."

        # 2. Check Faculty Profile
        cursor.execute("""
            SELECT ep.first_name, ep.last_name, ep.academic_rank, ep.designation,
                   ep.assigned_program, ep.specialization, ac.corporate_email
            FROM tbl_employee_profiles ep
            LEFT JOIN tbl_auth_credentials ac ON ep.emp_id = ac.emp_id
            WHERE ep.emp_id = %s
        """, (emp_id,))
        fac_row = cursor.fetchone()
        if not fac_row:
            return False, f"Faculty member #{emp_id} not found."

        first_name, last_name, academic_rank, designation, assigned_prog, spec, faculty_email = fac_row
        faculty_name = f"{first_name} {last_name}".strip()
        department = spec or assigned_prog or "CICT"

        # 3. Check Dean Approval Status on committed targets
        cursor.execute("""
            SELECT COUNT(*) FROM tbl_committed_targets ct
            JOIN tbl_master_indicators mi ON ct.indicator_id = mi.indicator_id
            WHERE ct.emp_id = %s AND mi.term_id = %s AND ct.status = 'Dean Approved'
        """, (emp_id, term_id))
        approved_count = cursor.fetchone()[0]
        if approved_count == 0:
            return False, "IPCR is not Dean Approved yet."

        # 4. Fetch Scores if available
        cursor.execute("""
            SELECT final_score, adjectival_rating
            FROM tbl_final_scores
            WHERE emp_id = %s AND term_id = %s
        """, (emp_id, term_id))
        score_row = cursor.fetchone()
        final_score = f"{score_row[0]:.4f}" if (score_row and score_row[0] is not None) else None
        adjectival_rating = score_row[1] if score_row else None

        # 5. Fetch Term info
        cursor.execute("""
            SELECT academic_year, semester, period_start, period_end
            FROM tbl_academic_terms WHERE term_id = %s
        """, (term_id,))
        term_data = cursor.fetchone()
        term_dict = {
            'academic_year': term_data[0] if term_data else '',
            'semester': term_data[1] if term_data else '',
            'period_start': term_data[2] if term_data else None,
            'period_end': term_data[3] if term_data else None
        } if term_data else {}
        period_display = _format_term_period(term_dict)

        # 6. Fetch Program Chair Email
        cursor.execute("""
            SELECT ep.first_name, ep.last_name, ac.corporate_email
            FROM tbl_system_access sa
            JOIN tbl_employee_profiles ep ON sa.emp_id = ep.emp_id
            LEFT JOIN tbl_auth_credentials ac ON ac.emp_id = ep.emp_id
            WHERE UPPER(sa.system_role) = 'PROGRAM_CHAIR'
              AND (ep.specialization = %s OR ep.assigned_program = %s)
              AND sa.account_status = 'Active'
            LIMIT 1
        """, (department, department))
        chair_row = cursor.fetchone()
        chair_email = chair_row[2] if chair_row and chair_row[2] else None
        chair_name = f"{chair_row[0]} {chair_row[1]}".strip() if chair_row else "Program Chair"

        # 7. Fetch RET Chair Email
        cursor.execute("""
            SELECT ep.first_name, ep.last_name, ac.corporate_email
            FROM tbl_system_access sa
            JOIN tbl_employee_profiles ep ON sa.emp_id = ep.emp_id
            LEFT JOIN tbl_auth_credentials ac ON ac.emp_id = ep.emp_id
            WHERE UPPER(sa.system_role) = 'RET_CHAIR' AND sa.account_status = 'Active'
            LIMIT 1
        """)
        ret_row = cursor.fetchone()
        ret_email = ret_row[2] if ret_row and ret_row[2] else None
        ret_name = f"{ret_row[0]} {ret_row[1]}".strip() if ret_row else "RET Chair"

        resolved_base_url = _get_base_url(base_url)
        action_url = f"{resolved_base_url}/faculty/ipcr_preview"

        recipients_logged = []
        if faculty_email:
            recipients_logged.append(f"Faculty: {faculty_email}")
        if chair_email:
            recipients_logged.append(f"Chair: {chair_email}")
        if ret_email:
            recipients_logged.append(f"RET: {ret_email}")

        # 8. Record Notification in DB first (idempotency barrier)
        cursor.execute("""
            INSERT INTO tbl_ipcr_approval_notifications
                (emp_id, term_id, tier, event_type, recipient_emails, status)
            VALUES (%s, %s, 'TIER_2', 'TIER_2_APPROVED', %s, 'SENT')
        """, (emp_id, term_id, ", ".join(recipients_logged) if recipients_logged else "No email registered"))
        conn.commit()

        # 9. Send to Faculty Member
        if faculty_email:
            html_fac = render_template('emails/tier2_final.html',
                recipient_name=faculty_name,
                faculty_name=faculty_name,
                academic_rank=academic_rank,
                department=department,
                period_display=period_display,
                final_score=final_score,
                adjectival_rating=adjectival_rating,
                action_url=action_url
            )
            text_fac = (
                f"Dear {faculty_name},\n\n"
                f"Your IPCR for {period_display} is approved by the College Dean and is ready for print.\n"
                f"Final Score: {final_score or 'N/A'} ({adjectival_rating or 'N/A'})\n\n"
                f"View your finalized IPCR at: {action_url}\n"
            )
            send_async_email(
                subject=f"[D-IPCR] IPCR is approved by Dean and is ready for print - {faculty_name} ({period_display})",
                recipients=[faculty_email],
                html_body=html_fac,
                text_body=text_fac
            )

        # 10. Send to Program Chair
        if chair_email:
            chair_view_url = f"{resolved_base_url}/dean/preview_ipcr/{emp_id}"
            html_chair = render_template('emails/tier2_final.html',
                recipient_name=chair_name,
                faculty_name=faculty_name,
                academic_rank=academic_rank,
                department=department,
                period_display=period_display,
                final_score=final_score,
                adjectival_rating=adjectival_rating,
                action_url=chair_view_url
            )
            text_chair = (
                f"Dear {chair_name},\n\n"
                f"The IPCR for {faculty_name} ({department}) for {period_display} is approved by the College Dean and is ready for print.\n"
                f"Final Score: {final_score or 'N/A'} ({adjectival_rating or 'N/A'})\n\n"
                f"View finalized document at: {chair_view_url}\n"
            )
            send_async_email(
                subject=f"[D-IPCR] IPCR is approved by Dean and is ready for print: {faculty_name} ({period_display})",
                recipients=[chair_email],
                html_body=html_chair,
                text_body=text_chair
            )

        # 11. Send to RET Chair
        if ret_email:
            ret_view_url = f"{resolved_base_url}/dean/preview_ipcr/{emp_id}"
            html_ret = render_template('emails/tier2_final.html',
                recipient_name=ret_name,
                faculty_name=faculty_name,
                academic_rank=academic_rank,
                department=department,
                period_display=period_display,
                final_score=final_score,
                adjectival_rating=adjectival_rating,
                action_url=ret_view_url
            )
            text_ret = (
                f"Dear {ret_name},\n\n"
                f"The IPCR for {faculty_name} ({department}) for {period_display} is approved by the College Dean and is ready for print.\n"
                f"Final Score: {final_score or 'N/A'} ({adjectival_rating or 'N/A'})\n\n"
                f"View finalized document at: {ret_view_url}\n"
            )
            send_async_email(
                subject=f"[D-IPCR] IPCR is approved by Dean and is ready for print: {faculty_name} ({period_display})",
                recipients=[ret_email],
                html_body=html_ret,
                text_body=text_ret
            )

        logger.info(f"[TIER 2 NOTIFICATION TRIGGERED] emp_id={emp_id}, term_id={term_id}")
        return True, "Tier 2 notifications dispatched successfully."

    except Exception as e:
        logger.error(f"Error triggering Tier 2 notification: {e}")
        return False, str(e)


def send_return_notification(conn, cursor, reviewer_role: str, review_id: int, emp_id: int, term_id: int, overall_remarks: str = "", base_url: str = None) -> tuple[bool, str]:
    """
    Sends an immediate notification to the regular faculty member when their draft IPCR
    targets are returned by either the Program Chair or the RET Chair, including any
    modified quantities and item-level remarks.
    """
    try:
        # 1. Fetch Faculty Profile & Email
        cursor.execute("""
            SELECT ep.first_name, ep.last_name, ep.academic_rank, ep.designation,
                   ep.assigned_program, ep.specialization, ac.corporate_email
            FROM tbl_employee_profiles ep
            LEFT JOIN tbl_auth_credentials ac ON ep.emp_id = ac.emp_id
            WHERE ep.emp_id = %s
        """, (emp_id,))
        fac_row = cursor.fetchone()
        if not fac_row:
            return False, f"Faculty member #{emp_id} not found."

        first_name, last_name, academic_rank, designation, assigned_prog, spec, faculty_email = fac_row
        if not faculty_email:
            return False, f"No email found for faculty member #{emp_id}."

        faculty_name = f"{first_name} {last_name}".strip()
        department = spec or assigned_prog or "CICT"

        # 2. Fetch Term Period
        cursor.execute("""
            SELECT academic_year, semester, period_start, period_end
            FROM tbl_academic_terms WHERE term_id = %s
        """, (term_id,))
        term_data = cursor.fetchone()
        term_dict = {
            'academic_year': term_data[0] if term_data else '',
            'semester': term_data[1] if term_data else '',
            'period_start': term_data[2] if term_data else None,
            'period_end': term_data[3] if term_data else None
        } if term_data else {}
        period_display = _format_term_period(term_dict)

        # 3. Query Modified Targets & Item Remarks
        modified_items = []
        if 'RET' in reviewer_role.upper():
            cursor.execute("""
                SELECT mi.indicator_description, ri.original_quantity, ri.reviewed_quantity, ri.item_remarks
                FROM tbl_ipcr_ret_review_items ri
                JOIN tbl_master_indicators mi ON ri.indicator_id = mi.indicator_id
                WHERE ri.review_id = %s
            """, (review_id,))
        else:
            cursor.execute("""
                SELECT mi.indicator_description, ri.original_quantity, ri.reviewed_quantity, ri.item_remarks
                FROM tbl_ipcr_chair_review_items ri
                JOIN tbl_master_indicators mi ON ri.indicator_id = mi.indicator_id
                WHERE ri.review_id = %s
            """, (review_id,))

        for row in cursor.fetchall():
            desc, orig_q, rev_q, remarks = row
            is_qty_changed = (orig_q != rev_q)
            has_remarks = bool(remarks and remarks.strip())
            if is_qty_changed or has_remarks:
                modified_items.append({
                    'indicator_description': desc,
                    'original_quantity': orig_q,
                    'reviewed_quantity': rev_q,
                    'is_qty_changed': is_qty_changed,
                    'item_remarks': remarks.strip() if remarks else None
                })

        resolved_base_url = _get_base_url(base_url)
        action_url = f"{resolved_base_url}/faculty"

        html_body = render_template('emails/ipcr_returned.html',
            faculty_name=faculty_name,
            department=department,
            period_display=period_display,
            reviewer_role=reviewer_role,
            overall_remarks=overall_remarks,
            modified_items=modified_items,
            action_url=action_url
        )

        text_items = ""
        if modified_items:
            text_items = "\nModified Targets:\n" + "\n".join([
                f"- {item['indicator_description']}: Proposed {item['original_quantity']} -> Adjusted {item['reviewed_quantity']}" +
                (f" (Remark: {item['item_remarks']})" if item['item_remarks'] else "")
                for item in modified_items
            ])

        text_body = (
            f"Dear {faculty_name},\n\n"
            f"Your draft IPCR targets for {period_display} were returned by the {reviewer_role}.\n"
            f"Overall Remarks: {overall_remarks or 'None'}\n"
            f"{text_items}\n\n"
            f"Please update your draft and resubmit at: {action_url}\n"
        )

        send_async_email(
            subject=f"[D-IPCR] Action Required: IPCR Targets Returned by {reviewer_role} - {period_display}",
            recipients=[faculty_email],
            html_body=html_body,
            text_body=text_body
        )

        logger.info(f"[RETURN NOTIFICATION TRIGGERED] emp_id={emp_id}, term_id={term_id}, reviewer={reviewer_role}")
        return True, "Return notification dispatched successfully."

    except Exception as e:
        logger.error(f"Error triggering return notification: {e}")
        return False, str(e)

