from flask import session, redirect, url_for

def role_required(required_role):
    def decorator(func):
        def wrapper(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('auth.login'))
            if session.get('role') != required_role:
                return "Unauthorised", 403
            return func(*args, **kwargs)

        wrapper.__name__ = func.__name__
        return wrapper
    return decorator


def designated_ipcr_required(func):
    """
    Guards the shared Designated Faculty IPCR flow.

    Access is decided by the employee's *designation* (their accountability role), not by
    session['role'] (which dashboard they logged into). A Program Chair, RET Chair or Dean
    is a designated faculty member with an IPCR of their own, so they reach this flow from
    their own dashboard while keeping their chair/dean role.

    Regular Faculty are excluded — they have their own flow under /faculty/ — as are system
    accounts with no IPCR at all.
    """
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))

        from app.models.connection import get_db_connection
        from app.models.criteria import is_designated

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT designation FROM tbl_employee_profiles WHERE emp_id = %s",
                (session.get('user_id'),))
            row = cursor.fetchone()
        finally:
            cursor.close()
            conn.close()

        if not row or not is_designated(row[0]):
            return "Unauthorised", 403
        return func(*args, **kwargs)

    wrapper.__name__ = func.__name__
    return wrapper
