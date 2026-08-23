import os
import unittest
from unittest.mock import MagicMock, patch
from app import app
from app.services.mail_service import _send_email_sync, send_async_email, get_mail_config
from app.services.notification_service import (
    check_and_trigger_tier1_notification,
    check_and_trigger_tier2_notification,
    _format_term_period
)

class TestNotificationWorkflow(unittest.TestCase):

    def setUp(self):
        self.app = app
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self):
        self.app_context.pop()

    def test_term_period_formatting(self):
        term = {
            'academic_year': '2025-2026',
            'semester': '1st Semester',
            'period_start': None,
            'period_end': None
        }
        res = _format_term_period(term)
        self.assertIn('2025-2026', res)
        self.assertIn('1st Semester', res)

    def test_mail_dev_logging_fallback(self):
        # When SMTP_HOST is not set or suppress_send is true, it logs without throwing
        with patch.dict(os.environ, {'SMTP_HOST': '', 'MAIL_SUPPRESS_SEND': 'true'}):
            success, msg = _send_email_sync(
                subject="Test Subject",
                recipients=["faculty@cict.edu.ph"],
                html_body="<p>Test Body</p>",
                text_body="Test Body"
            )
            self.assertTrue(success)
            self.assertEqual(msg, "DEV_LOGGED")

    def test_tier1_notification_trigger_with_research(self):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # 1. Idempotency check: not sent yet (None)
        # 2. Faculty profile: emp_id=5
        # 3. Chair review: 'Approved'
        # 4. Research count: 1
        # 5. RET review: 'Approved'
        # 6. Term info
        # 7. Dean info
        mock_cursor.fetchone.side_effect = [
            None,  # No existing notification
            ('Juan', 'Dela Cruz', 'Assistant Professor I', 'Regular Faculty', 'BSIT', 'BSIT', 'juan@cict.edu.ph'), # Faculty profile
            ('Approved',), # Chair review
            (1,), # Research count
            ('Approved',), # RET review
            ('2025-2026', '1st Semester', None, None), # Term info
            ('Dean', 'Officer', 'dean@cict.edu.ph') # Dean info
        ]

        with patch('app.services.notification_service.send_async_email') as mock_send_email:
            success, msg = check_and_trigger_tier1_notification(mock_conn, mock_cursor, 5, 1)
            self.assertTrue(success)
            self.assertEqual(mock_send_email.call_count, 2)  # Dean + Faculty

    def test_tier1_notification_trigger_without_research(self):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # 1. Idempotency check: not sent yet
        # 2. Faculty profile: emp_id=6
        # 3. Chair review: 'Approved'
        # 4. Research count: 0 (No RET review required)
        # 5. Term info
        # 6. Dean info
        mock_cursor.fetchone.side_effect = [
            None,  # No existing notification
            ('Maria', 'Santos', 'Instructor I', 'Regular Faculty', 'BSCS', 'BSCS', 'maria@cict.edu.ph'), # Faculty profile
            ('Approved',), # Chair review
            (0,), # Research count = 0
            ('2025-2026', '2nd Semester', None, None), # Term info
            ('Dean', 'Officer', 'dean@cict.edu.ph') # Dean info
        ]

        with patch('app.services.notification_service.send_async_email') as mock_send_email:
            success, msg = check_and_trigger_tier1_notification(mock_conn, mock_cursor, 6, 2)
            self.assertTrue(success)
            self.assertEqual(mock_send_email.call_count, 2)  # Dean + Faculty

    def test_tier1_idempotency_prevents_duplicate(self):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # Existing notification found in DB
        mock_cursor.fetchone.return_value = (101,)

        with patch('app.services.notification_service.send_async_email') as mock_send_email:
            success, msg = check_and_trigger_tier1_notification(mock_conn, mock_cursor, 5, 1)
            self.assertFalse(success)
            self.assertIn("already sent", msg)
            self.assertEqual(mock_send_email.call_count, 0)

    def test_tier2_notification_trigger(self):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # 1. Idempotency check: not sent yet
        # 2. Faculty profile: emp_id=5
        # 3. Dean approved count: 5
        # 4. Final score: (4.8500, 'Outstanding')
        # 5. Term info
        # 6. Program Chair info
        # 7. RET Chair info
        mock_cursor.fetchone.side_effect = [
            None,  # No existing notification
            ('Juan', 'Dela Cruz', 'Assistant Professor I', 'Regular Faculty', 'BSIT', 'BSIT', 'juan@cict.edu.ph'), # Faculty profile
            (5,),  # Dean approved target count
            (4.8500, 'Outstanding'), # Score
            ('2025-2026', '1st Semester', None, None), # Term info
            ('Chair', 'Person', 'chair@cict.edu.ph'), # Chair info
            ('RET', 'Lead', 'ret@cict.edu.ph') # RET Chair info
        ]

        with patch('app.services.notification_service.send_async_email') as mock_send_email:
            success, msg = check_and_trigger_tier2_notification(mock_conn, mock_cursor, 5, 1)
            self.assertTrue(success)
            self.assertEqual(mock_send_email.call_count, 3)  # Faculty + Chair + RET Chair

    def test_tier2_idempotency_prevents_duplicate(self):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # Existing notification found in DB
        mock_cursor.fetchone.return_value = (102,)

        with patch('app.services.notification_service.send_async_email') as mock_send_email:
            success, msg = check_and_trigger_tier2_notification(mock_conn, mock_cursor, 5, 1)
            self.assertFalse(success)
            self.assertIn("already sent", msg)
            self.assertEqual(mock_send_email.call_count, 0)


if __name__ == '__main__':
    unittest.main()
