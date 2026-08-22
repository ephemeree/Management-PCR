from flask import Flask, g, request
import os
import time
import logging
from dotenv import load_dotenv

# Ensure openpyxl is installed
try:
    import openpyxl
except ImportError:
    import subprocess
    import sys
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "openpyxl"])
    except Exception as e:
        logging.error(f"Failed to auto-install openpyxl: {str(e)}")

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Set a secret key for secure sessions (login cookies)
app.secret_key = os.getenv('SECRET_KEY', 'dipcr_version_13_secret_key')

# Configure upload settings
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'uploads', 'evidence')
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB limit

# Initialize DB connection pool at startup
from app.models.connection import init_db_pool
init_db_pool()


# Request timing middleware
@app.before_request
def start_timer():
    g.start_time = time.time()


@app.after_request
def log_request_time(response):
    if hasattr(g, 'start_time'):
        elapsed = time.time() - g.start_time
        if elapsed > 1.0:
            logger.warning(f"SLOW REQUEST: {request.method} {request.path} — took {elapsed:.2f}s")
        else:
            logger.info(f"REQUEST: {request.method} {request.path} — {elapsed:.2f}s")
    return response


@app.teardown_request
def close_db_connection(exc):
    """Safety net: return any pooled DB connection on EVERY request, even on errors.

    Prevents 'Too many connections' / pool exhaustion if a route raises before its
    manual conn.close() runs. get_db_connection() registers the connection on `g`,
    so this returns it to the pool no matter what happened in the route.
    """
    conn = getattr(g, '_db_conn', None)
    if conn is not None:
        try:
            if conn.is_connected():
                conn.close()
        except Exception:
            logger.exception("Failed to close DB connection during teardown")

# Register route blueprints
from app.routes import register_blueprints
register_blueprints(app)


@app.context_processor
def inject_own_ipcr_flag():
    """
    Exposes `has_own_ipcr` to every template so each dashboard can show a link into the
    shared Designated Faculty IPCR flow. Driven by the session's designation (job title),
    not by role — a Program Chair, RET Chair or Dean is a designated faculty member with
    an IPCR of their own.
    """
    from flask import session
    from app.models.criteria import is_designated
    from app.navigation import home_nav_for
    return {
        'has_own_ipcr': is_designated(session.get('designation')),
        # The visitor's home dashboard nav, so the shared IPCR page can show it as links
        # instead of replacing their sidebar. None when they are already home.
        'home_nav': home_nav_for(session.get('role')),
    }


@app.route('/evidence_uploads/<int:evidence_id>')
def serve_evidence(evidence_id):
    from flask import session, redirect, url_for, send_from_directory, abort
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    from app.models.connection import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT er.file_path, ct.emp_id
            FROM tbl_evidence_repo er
            JOIN tbl_committed_targets ct ON er.target_id = ct.target_id
            WHERE er.evidence_id = %s
        """, (evidence_id,))
        row = cursor.fetchone()
    finally:
        cursor.close()
        conn.close()
    if not row:
        abort(404)
    file_path, owner_emp_id = row
    current_user_id = session['user_id']
    current_role = session.get('role')
    if current_role == 'FACULTY' and current_user_id != owner_emp_id:
        abort(403)
    import os
    return send_from_directory(app.config['UPLOAD_FOLDER'], os.path.basename(file_path))

@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response