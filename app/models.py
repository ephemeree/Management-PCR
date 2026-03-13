import mysql.connector
from mysql.connector import Error

def get_db_connection():
    """Establishes and returns a connection to the XAMPP MySQL database."""
    try:
        connection = mysql.connector.connect(
            host='localhost',
            database='ipcr_db',    # The name of the Version 13 database we built
            user='root',           # Default XAMPP username
            password=''            # Default XAMPP password is empty
        )
        if connection.is_connected():
            return connection
    except Error as e:
        print(f"Error while connecting to MySQL: {e}")
        return None