"""
Institution-level configuration that used to be hardcoded in the application:

  * Departments / programs — previously fixed columns (WST/DST/NST/BSDS) in the
    Dean's cascade form and a hardcoded col_map in the Excel export.
  * Teaching load — previously the literals '21 hours of Teaching Load' (regular)
    and '10 hours of Teaching Load' (designated) scattered across the submit paths,
    with a free-text '1 Semester' deadline that could not be scored for Timeliness.

Both are now data, so the system scales to new programs and to a change in the
mandated teaching load without a code edit.
"""

from app.models.criteria import DESIGNATION_TYPES, GENERAL_BAND, RANK_BANDS, rank_band

# Cascade targets that are not departments. The Dean assigns quotas to these
# alongside the real programs.
ROLE_RET = 'RET / Extension'
ROLE_COLLEGE_WIDE = 'College-Wide'
SPECIAL_CASCADE_ROLES = [ROLE_RET, ROLE_COLLEGE_WIDE]


# ─────────────────────────────────────────────
# Departments
# ─────────────────────────────────────────────

def get_departments(cursor, active_only=True):
    """Departments/programs in display order. `department_name` is the value stored on
    tbl_employee_profiles.specialization and tbl_cascaded_quotas.assigned_to_role."""
    query = """
        SELECT department_id, department_name, department_code, display_order, is_active
        FROM tbl_departments
    """
    if active_only:
        query += " WHERE is_active = 1"
    query += " ORDER BY display_order, department_name"
    cursor.execute(query)
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def save_department(conn, cursor, name, code, display_order, department_id=None):
    """Create or rename a department. The name is what targets are routed by, so
    renaming one also updates the rows that reference it."""
    name = (name or '').strip()
    if not name:
        return False, "Department name is required."
    try:
        if department_id:
            cursor.execute("SELECT department_name FROM tbl_departments WHERE department_id = %s",
                           (department_id,))
            row = cursor.fetchone()
            old_name = row[0] if row else None

            cursor.execute("""
                UPDATE tbl_departments
                SET department_name = %s, department_code = %s, display_order = %s
                WHERE department_id = %s
            """, (name, (code or '').strip() or None, int(display_order or 100), department_id))

            # Keep the rows that route by name in step with the rename.
            if old_name and old_name != name:
                cursor.execute(
                    "UPDATE tbl_employee_profiles SET specialization = %s WHERE specialization = %s",
                    (name, old_name))
                cursor.execute(
                    "UPDATE tbl_cascaded_quotas SET assigned_to_role = %s WHERE assigned_to_role = %s",
                    (name, old_name))
        else:
            cursor.execute("""
                INSERT INTO tbl_departments (department_name, department_code, display_order)
                VALUES (%s, %s, %s)
            """, (name, (code or '').strip() or None, int(display_order or 100)))

        conn.commit()
        return True, f"Department '{name}' saved."
    except Exception as e:
        conn.rollback()
        return False, str(e)


def set_department_active(conn, cursor, department_id, is_active):
    """Soft-delete / restore a department. Existing faculty and quotas keep their
    routing value; the department simply stops appearing in new cascades."""
    try:
        cursor.execute("UPDATE tbl_departments SET is_active = %s WHERE department_id = %s",
                       (1 if is_active else 0, department_id))
        conn.commit()
        return True, ("Department activated." if is_active else "Department deactivated.")
    except Exception as e:
        conn.rollback()
        return False, str(e)


# ─────────────────────────────────────────────
# Teaching load
# ─────────────────────────────────────────────

# Fallbacks used only when a term has no configuration yet, matching the values that
# were previously hardcoded.
DEFAULT_TEACHING_LOAD = {
    'Regular Faculty': 21,
    'Designated Faculty': 10,
}
DEFAULT_LOAD_DURATION = (6, 'months')


def get_teaching_load_config(cursor, term_id, designation_type=None):
    """Raw teaching-load rows for a term (optionally one designation type)."""
    query = """
        SELECT config_id, term_id, designation_type, rank_band, hours,
               duration_value, duration_unit
        FROM tbl_teaching_load_config
        WHERE term_id = %s
    """
    params = [term_id]
    if designation_type:
        query += " AND designation_type = %s"
        params.append(designation_type)
    query += " ORDER BY designation_type, rank_band"
    cursor.execute(query, tuple(params))
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def get_teaching_load_grid(cursor, term_id, designation_type):
    """{rank_band: {hours, duration_value, duration_unit}} including the General row."""
    grid = {}
    for row in get_teaching_load_config(cursor, term_id, designation_type):
        grid[row['rank_band']] = {
            'hours': row['hours'],
            'duration_value': row['duration_value'],
            'duration_unit': row['duration_unit'],
        }
    return grid


def get_teaching_load_mode(cursor, term_id, designation_type):
    """'SPECIFIC' when per-rank rows exist, otherwise 'GENERAL'."""
    cursor.execute("""
        SELECT COUNT(*) FROM tbl_teaching_load_config
        WHERE term_id = %s AND designation_type = %s AND rank_band <> %s
    """, (term_id, designation_type, GENERAL_BAND))
    return 'SPECIFIC' if cursor.fetchone()[0] > 0 else 'GENERAL'


def resolve_teaching_load(cursor, term_id, designation_type, academic_rank=None):
    """
    The teaching load that applies to one employee: (hours, duration_value, duration_unit).

    A General row wins for every rank; otherwise the employee's rank band is used.
    Falls back to the previously hardcoded values when a term has no configuration,
    so the mandatory teaching-load target is never missing.
    """
    designation_type = designation_type if designation_type in DESIGNATION_TYPES else 'Regular Faculty'

    cursor.execute("""
        SELECT hours, duration_value, duration_unit FROM tbl_teaching_load_config
        WHERE term_id = %s AND designation_type = %s AND rank_band = %s
    """, (term_id, designation_type, GENERAL_BAND))
    row = cursor.fetchone()
    if not row:
        cursor.execute("""
            SELECT hours, duration_value, duration_unit FROM tbl_teaching_load_config
            WHERE term_id = %s AND designation_type = %s AND rank_band = %s
        """, (term_id, designation_type, rank_band(academic_rank)))
        row = cursor.fetchone()

    if row:
        return int(row[0]), int(row[1]), row[2]
    hours = DEFAULT_TEACHING_LOAD.get(designation_type, 21)
    return hours, DEFAULT_LOAD_DURATION[0], DEFAULT_LOAD_DURATION[1]


def teaching_load_description(hours):
    """The indicator description for a teaching load target — the text the rest of the
    system matches on when detecting the mandatory target."""
    return f"{hours} hours of Teaching Load"


def save_teaching_load(conn, cursor, term_id, designation_type, mode, rows):
    """
    Replace a term + designation type's teaching load configuration.

    `rows` is a list of (rank_band, hours, duration_value, duration_unit). As with the
    weight matrix, the two modes are mutually exclusive: all existing rows for the pair
    are cleared first so a configuration is never half General and half per-rank.
    """
    if designation_type not in DESIGNATION_TYPES:
        return False, "Invalid designation type."
    if mode not in ('GENERAL', 'SPECIFIC'):
        return False, "Invalid teaching load mode."
    try:
        cursor.execute(
            "DELETE FROM tbl_teaching_load_config WHERE term_id = %s AND designation_type = %s",
            (term_id, designation_type))

        saved = 0
        for band, hours, dur_value, dur_unit in rows:
            if not hours or int(hours) <= 0:
                continue
            cursor.execute("""
                INSERT INTO tbl_teaching_load_config
                    (term_id, designation_type, rank_band, hours, duration_value, duration_unit)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (term_id, designation_type, band, int(hours),
                  int(dur_value or 6), dur_unit or 'months'))
            saved += 1

        conn.commit()
        label = "all ranks" if mode == 'GENERAL' else "per academic rank"
        return True, f"Teaching load saved for {designation_type} ({label})."
    except Exception as e:
        conn.rollback()
        return False, str(e)
