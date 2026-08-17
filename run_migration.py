"""
Apply a .sql migration file to the configured database.

Usage:
    python run_migration.py "old MDS/MIGRATION_group4.sql"

Reads connection settings from .env (same ones the app uses), splits the file into
statements, and runs them in order — stopping at the first error so a partially
applied migration is obvious rather than silent.
"""
import os
import sys

import mysql.connector
from dotenv import load_dotenv

load_dotenv()


def split_statements(sql_text):
    """Split on semicolons at end-of-line, ignoring comment-only lines."""
    cleaned = []
    for line in sql_text.splitlines():
        stripped = line.strip()
        if stripped.startswith('--') or not stripped:
            continue
        cleaned.append(line)
    joined = '\n'.join(cleaned)
    return [s.strip() for s in joined.split(';') if s.strip()]


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    path = sys.argv[1]
    if not os.path.exists(path):
        print(f"File not found: {path}")
        sys.exit(1)

    with open(path, encoding='utf-8') as f:
        statements = split_statements(f.read())

    conn = mysql.connector.connect(
        host=os.getenv('DB_HOST'),
        port=int(os.getenv('DB_PORT')),
        database=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
    )
    cursor = conn.cursor()

    print(f"Applying {len(statements)} statement(s) from {path}\n")
    for i, stmt in enumerate(statements, 1):
        preview = ' '.join(stmt.split())[:90]
        try:
            cursor.execute(stmt)
            # Drain any result set so the connection stays usable.
            try:
                cursor.fetchall()
            except mysql.connector.Error:
                pass
            print(f"  [{i}/{len(statements)}] OK   {preview}")
        except mysql.connector.Error as e:
            conn.rollback()
            print(f"  [{i}/{len(statements)}] FAIL {preview}")
            print(f"\n  Error: {e}")
            print("\n  Stopped. Nothing after this statement was applied.")
            cursor.close()
            conn.close()
            sys.exit(1)

    conn.commit()
    cursor.close()
    conn.close()
    print("\nMigration applied successfully.")


if __name__ == '__main__':
    main()
