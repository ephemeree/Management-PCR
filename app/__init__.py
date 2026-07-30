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

# Register route blueprints
from app.routes import register_blueprints
register_blueprints(app)


@app.route('/evidence_uploads/<path:filename>')
def serve_evidence(filename):
    from flask import session, redirect, url_for, send_from_directory, abort
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response