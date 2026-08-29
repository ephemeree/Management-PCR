from app import app
from app.setup import bootstrap_admin
import os

if __name__ == '__main__':
    # Create first admin account from ADMIN_EMAIL/ADMIN_PASSWORD env if none exists
    bootstrap_admin()

    debug_mode = os.getenv('FLASK_DEBUG', 'true').lower() == 'true'
    app.run(debug=debug_mode, host='0.0.0.0', port=5000)
