from flask import Blueprint, render_template, request, redirect, session, url_for, flash
from app.auth import hash_pass, verify_pass, validate_password_policy
from app.models import get_db_connection, get_user_by_email, register_user
from app.decorators import role_required
import mysql.connector, time

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/')
def login():
    return render_template('login.html')


@auth_bp.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('auth.login'))


@auth_bp.route('/authenticate', methods=['POST'])
def authenticate():
    email = request.form.get('email', '').lower().strip()
    password = request.form.get('password', '')

    conn = get_db_connection()
    cursor = conn.cursor()

    result = get_user_by_email(cursor, email)

    if not result:
        cursor.close()
        conn.close()
        time.sleep(0.5)
        flash("Invalid Credentials.", "danger")
        return redirect(url_for('auth.login'))

    emp_id, stored_hash, verification, role = result[0]

    # Check if account has been soft-deleted/deactivated
    cursor.execute("SELECT account_status FROM tbl_system_access WHERE emp_id = %s", (emp_id,))
    acc_status_row = cursor.fetchone()

    cursor.execute("SELECT specialization FROM tbl_employee_profiles WHERE emp_id = %s", (emp_id,))
    spec_rows = cursor.fetchall()
    specialization = spec_rows[0][0] if spec_rows else ''

    cursor.close()
    conn.close()

    if acc_status_row and acc_status_row[0] == 'Inactive':
        flash("Your account has been deactivated. Please contact the administrator.", "danger")
        return redirect(url_for('auth.login'))

    # Normalize role for matching
    role = role.upper() if role else ""

    if verification != "APPROVED":
        flash("Account not approved. Please contact the administrator.", "danger")
        return redirect(url_for('auth.login'))

    if not verify_pass(password, stored_hash):
        time.sleep(0.5)
        flash("Invalid Credentials.", "danger")
        return redirect(url_for('auth.login'))

    session['user_id'] = emp_id
    session['role'] = role
    session['specialization'] = specialization

    if role == "ADMIN":
        return redirect(url_for('admin.admin_dashboard'))
    elif role == "DEAN":
        return redirect(url_for('dean.dean_dashboard'))
    elif role == "FACULTY":
        return redirect(url_for('faculty.faculty_dashboard'))
    elif role == "PROGRAM_CHAIR":
        return redirect(url_for('prog_chair.prog_chair_dashboard'))
    elif role == "RET_CHAIR":
        return redirect(url_for('ret_chair.ret_chair_dashboard'))
    elif role == "DESIGNATED_FACULTY":
        return redirect(url_for('designated.designated_dashboard'))
    else:
        flash(f"No system role assigned to this account (Role: {role}).", "danger")
        return redirect(url_for('auth.login'))


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        employee_id_number = request.form.get('employee_id_number')
        email = request.form.get('email', ' ').lower().strip()
        password = request.form.get('password', '')

        if not employee_id_number or not email or not password:
            flash("All fields are required.", "danger")
            return redirect(url_for('auth.register'))

        is_valid, msg = validate_password_policy(password)
        if not is_valid:
            flash(msg, "danger")
            return redirect(url_for('auth.register'))

        hashed_pw = hash_pass(password)

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            register_user(conn, cursor, employee_id_number, email, hashed_pw)

            cursor.close()
            conn.close()

            flash("Account claimed successfully! You have been auto-approved and may now log in.", "success")
            return redirect(url_for('auth.login'))

        except mysql.connector.Error as e:
            flash(str(e), "danger")
            return redirect(url_for('auth.register'))
        except Exception as e:
            flash(f"An unexpected error occurred: {str(e)}", "danger")
            return redirect(url_for('auth.register'))

    return render_template('register.html')
