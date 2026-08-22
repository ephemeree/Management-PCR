"""
Create the first Admin account directly in the database.

Everything else in the system is reachable once an Admin exists: they add employee
profiles, and each person then *claims* their profile through the normal registration
form. But registration cannot create the very first account, because it claims a profile
that an Admin has to have created — so an empty database has no way in.

This script is that way in. It is the only thing in the project that writes an account
without going through the application.

    python bootstrap_admin.py

The password is typed at a prompt, never passed on the command line, so it does not end
up in shell history. It must satisfy the same policy the registration form enforces.

If an Admin already exists the script stops. Pass --force only when you deliberately want
a second one.
"""

import argparse
import getpass
import sys

from app.auth import hash_pass, validate_password_policy
from app.models.connection import get_db_connection

ADMIN_ROLE = 'Admin'          # tbl_system_access.system_role — login upper-cases it
ADMIN_DESIGNATION = 'Admin'   # marks the profile as a system account with no IPCR


def existing_admins(cursor):
    cursor.execute("""
        SELECT ep.employee_id_number, ac.corporate_email
        FROM tbl_system_access sa
        JOIN tbl_employee_profiles ep ON sa.emp_id = ep.emp_id
        LEFT JOIN tbl_auth_credentials ac ON ac.emp_id = ep.emp_id
        WHERE UPPER(sa.system_role) = 'ADMIN'
    """)
    return cursor.fetchall()


def prompt(label, default=None, required=True):
    suffix = f" [{default}]" if default else ""
    while True:
        value = input(f"{label}{suffix}: ").strip()
        if not value and default:
            return default
        if value or not required:
            return value
        print("  This field is required.")


def prompt_password():
    while True:
        pw = getpass.getpass("Password: ")
        ok, msg = validate_password_policy(pw)
        if not ok:
            print(f"  {msg}")
            continue
        if pw != getpass.getpass("Confirm password: "):
            print("  Passwords do not match.")
            continue
        return pw


def main():
    parser = argparse.ArgumentParser(description="Create the first Admin account.")
    parser.add_argument('--force', action='store_true',
                        help="create another Admin even though one already exists")
    args = parser.parse_args()

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        admins = existing_admins(cursor)
        if admins and not args.force:
            print("An Admin account already exists:")
            for emp_no, email in admins:
                print(f"  {emp_no}  {email or '(no login yet)'}")
            print("\nNothing to do. Re-run with --force to add another.")
            return 0

        print("Creating an Admin account.\n")
        employee_id_number = prompt("Employee ID number")

        cursor.execute(
            "SELECT emp_id FROM tbl_employee_profiles WHERE employee_id_number = %s",
            (employee_id_number,))
        row = cursor.fetchone()
        if row:
            print(f"  A profile with that employee ID already exists (emp_id {row[0]}).")
            print("  Choose a different ID, or grant that person Admin from the roster.")
            return 1

        first_name = prompt("First name")
        last_name = prompt("Last name")
        email = prompt("Corporate email").lower()

        cursor.execute(
            "SELECT emp_id FROM tbl_auth_credentials WHERE corporate_email = %s", (email,))
        if cursor.fetchone():
            print("  That email is already registered.")
            return 1

        college = prompt("College code", default="CICT")
        # academic_rank and assigned_program are NOT NULL on the profile table even though
        # an Admin is a system account rather than teaching staff, so they get placeholders.
        academic_rank = prompt("Academic rank", default="N/A")
        assigned_program = prompt("Assigned program", default="N/A")
        password = prompt_password()

        # The three rows an account is made of: who they are, what they may do, how they
        # sign in. Written together so a half-created account is impossible.
        cursor.execute("""
            INSERT INTO tbl_employee_profiles
                (employee_id_number, first_name, last_name, college, assigned_program,
                 academic_rank, employment_status, designation, leave_status)
            VALUES (%s, %s, %s, %s, %s, %s, 'Permanent', %s, 'Active')
        """, (employee_id_number, first_name, last_name, college, assigned_program,
              academic_rank, ADMIN_DESIGNATION))
        emp_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO tbl_system_access (emp_id, system_role, account_status)
            VALUES (%s, %s, 'Active')
        """, (emp_id, ADMIN_ROLE))

        cursor.execute("""
            INSERT INTO tbl_auth_credentials
                (emp_id, corporate_email, password_hash, verification_status)
            VALUES (%s, %s, %s, 'APPROVED')
        """, (emp_id, email, hash_pass(password)))

        conn.commit()
        print(f"\nAdmin created — emp_id {emp_id}, sign in as {email}")
        print("Next: log in and add employee profiles so everyone else can claim theirs.")
        return 0

    except Exception as e:
        conn.rollback()
        print(f"\nFailed, nothing was written: {e}")
        return 1
    finally:
        cursor.close()
        conn.close()


if __name__ == '__main__':
    sys.exit(main())
