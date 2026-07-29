from app import app
import os

if __name__ == '__main__':
    debug_mode = os.getenv('FLASK_DEBUG', 'true').lower() == 'true'
    app.run(debug=debug_mode, port=5000)
