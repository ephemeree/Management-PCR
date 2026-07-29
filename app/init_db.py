import os
import logging
import mysql.connector

logger = logging.getLogger(__name__)


def _execute_sql_file(cursor, filepath):
    """
    Execute a SQL file that may contain DELIMITER commands.
    Handles custom delimiters ($$) used for procedures and triggers.
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    delimiter = ';'
    buffer = []

    for line in lines:
        stripped = line.strip()

        if not stripped or stripped.startswith('--'):
            buffer.append(line)
            continue

        # Handle DELIMITER changes
        if stripped.upper().startswith('DELIMITER '):
            if buffer:
                stmt = ''.join(buffer).strip()
                if stmt:
                    cursor.execute(stmt)
                buffer = []
            delimiter = stripped.split()[1]
            continue

        buffer.append(line)
        full = ''.join(buffer).strip()

        if full.endswith(delimiter) and delimiter != ';':
            stmt = full[:-len(delimiter)].strip()
            if stmt:
                cursor.execute(stmt)
            buffer = []
        elif delimiter == ';' and full.endswith(';'):
            stmt = full.rstrip(';').strip()
            if stmt:
                if stmt.upper().startswith('USE '):
                    buffer = []
                    continue
                cursor.execute(stmt)
            buffer = []

    if buffer:
        stmt = ''.join(buffer).strip()
        if stmt:
            cursor.execute(stmt)


def initialize_database():
    """Run SQL dump to create tables, procedures, and triggers if not already initialized."""
    sql_path = os.path.join(os.path.dirname(__file__), '..', 'ipcr_db_dump.sql')

    if not os.path.exists(sql_path):
        logger.warning("SQL dump not found at %s — skipping DB init.", sql_path)
        return

    try:
        conn = mysql.connector.connect(
            host=os.getenv('DB_HOST'),
            port=int(os.getenv('DB_PORT')),
            database=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            connection_timeout=10
        )
        cursor = conn.cursor()

        cursor.execute("SHOW TABLES LIKE 'tbl_employee_profiles'")
        if cursor.fetchone():
            logger.info("Database already initialized — skipping.")
            cursor.close()
            conn.close()
            return

        logger.info("Initializing database schema from %s...", sql_path)
        _execute_sql_file(cursor, sql_path)
        conn.commit()
        logger.info("Database initialized successfully.")

        cursor.close()
        conn.close()

    except mysql.connector.Error as e:
        logger.error("Failed to initialize database: %s", e)
        raise
