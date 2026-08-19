def open_new_term(conn, cursor, academic_year, semester, deadline_date,
                  period_start=None, period_end=None):
    """
    Open a term and make it the active one.

    period_start/period_end are the rating period printed on the IPCR header
    ("...for the period JANUARY to JUNE 2026"); academic_year and semester cannot
    express that on their own.
    """
    try:
        # Deactivate all current terms
        cursor.execute("UPDATE tbl_academic_terms SET is_active = FALSE")

        # Insert and activate the new term
        query_open = """
            INSERT INTO tbl_academic_terms
                (academic_year, semester, deadline_date, period_start, period_end, is_active)
            VALUES (%s, %s, %s, %s, %s, TRUE)
        """
        cursor.execute(query_open, (academic_year, semester, deadline_date,
                                    period_start or None, period_end or None))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e


def get_all_terms(cursor):
    from app.models.connection import timed_query
    query = """
        SELECT term_id, academic_year, semester, deadline_date,
               period_start, period_end, is_active
        FROM tbl_academic_terms ORDER BY term_id DESC
    """
    return timed_query(cursor, query, label="get_all_terms")
