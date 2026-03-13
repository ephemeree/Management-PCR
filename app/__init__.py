from flask import Flask

# Initialize the Flask application
app = Flask(__name__)

# Set a secret key for secure sessions (login cookies)
app.secret_key = 'accrual_version_13_secret_key'

# Import the routes so the app knows what URLs exist
from app import routes