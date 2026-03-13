from flask import render_template, request, redirect, url_for, flash
from app import app
from app.models import get_db_connection

@app.route('/')
def login():
    # Test the database connection
    conn = get_db_connection()
    db_status = "Connected successfully to Version 13 Database!" if conn else "Database connection failed."
    
    if conn:
        conn.close()

    # Renders the login page HTML and passes the DB status to it
    return render_template('login.html', status=db_status)

# Example placeholder for when the user submits the login form
@app.route('/authenticate', methods=['POST'])
def authenticate():
    email = request.form.get('email')
    password = request.form.get('password')
    
    # Sprint 1 Goal: Check tbl_auth_credentials and route to the correct dashboard
    # For now, just redirect back to login
    return redirect(url_for('login'))