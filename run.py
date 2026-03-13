from app import app

if __name__ == '__main__':
    # Runs the app in debug mode so it auto-reloads when you save changes
    app.run(debug=True, port=5000)