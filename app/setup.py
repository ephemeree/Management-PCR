import os
import logging
import mysql.connector
from mysql.connector import Error
from app.auth import hash_pass

logger = logging.getLogger(__name__)


def bootstrap_admin():
    """Create the first admin account if none exists."""
    admin_email = os.getenv('ADMIN_EMAIL')
    admin_password = os.getenv('ADMIN_PASSWORD')

    if not admin_email or not admin_password:
        logger.warning("ADMIN_EMAIL or ADMIN_PASSWORD not set — skipping bootstrap.")
        return

    try:
        conn = mysql.connector.connect(
            host=os.getenv('DB_HOST'),
            port=int(os.getenv('DB_PORT')),
            database=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            connection_timeout=5
        )
        cursor = conn.cursor()

        # Check if any admin already exists
        cursor.execute("SELECT COUNT(*) FROM tbl_system_access WHERE system_role = 'Admin' AND account_status = 'Active'")
        count = cursor.fetchone()[0]

        if count > 0:
            logger.info("Admin account already exists — skipping bootstrap.")
            cursor.close()
            conn.close()
            return

        logger.info("No admin found. Bootstrapping first admin...")

        # Create the employee profile
        cursor.execute("""
            INSERT INTO tbl_employee_profiles 
                (employee_id_number, first_name, last_name, college, assigned_program,
                 academic_rank, employment_status, designation, leave_status, specialization)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, ('ADMIN-001', 'System', 'Admin', 'CICT', 'BSIT',
              'Admin', 'Regular', 'Admin', 'Active', 'System Administration'))

        emp_id = cursor.lastrowid

        # Create auth credentials
        hashed = hash_pass(admin_password)
        cursor.execute("""
            INSERT INTO tbl_auth_credentials (emp_id, corporate_email, password_hash, verification_status)
            VALUES (%s, %s, %s, 'APPROVED')
        """, (emp_id, admin_email, hashed))

        # Grant system access
        cursor.execute("""
            INSERT INTO tbl_system_access (emp_id, system_role, account_status)
            VALUES (%s, 'Admin', 'Active')
        """, (emp_id,))

        conn.commit()
        logger.info(f"Admin account created: {admin_email}")

        cursor.close()
        conn.close()

    except Error as e:
        logger.error(f"Failed to bootstrap admin: {e}")