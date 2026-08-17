"""Central semantics for target criteria (categories).

Replaces the category-name string literals formerly hardcoded across the
faculty / prog_chair / designated / dean modules. A criterion's behaviour is
now driven by data columns on tbl_target_categories:

    review_lane   -> which review pipeline it routes through (CHAIR vs RET)
    is_core       -> participates in weighting / structured review items
    slug          -> stable machine key, independent of display name

Which weighted IPCR category a target type belongs to lives in tbl_ipcr_category_types,
because that mapping differs per designation type (Instruction is Strategic Priorities
for Regular faculty but Core Functions for Designated faculty).
"""
import re

# review_lane — which review pipeline a criterion routes through
LANE_CHAIR = 'CHAIR'   # Program Chair reviews (Instruction, Support, + future core)
LANE_RET = 'RET'       # RET Chair reviews (Research, Extension)

# stable category slugs backfilled in Phase 0
SLUG_INSTRUCTION = 'instruction'
SLUG_RESEARCH = 'research'
SLUG_EXTENSION = 'extension'
SLUG_SUPPORT = 'support'
SLUG_CUSTOM = 'custom'


def get_category_by_slug(cursor, slug):
    """Return the category row for a slug as a dict, or None."""
    cursor.execute(
        "SELECT category_id, category_name, slug, review_lane, is_core "
        "FROM tbl_target_categories WHERE slug = %s",
        (slug,),
    )
    row = cursor.fetchone()
    if not row:
        return None
    keys = ('category_id', 'category_name', 'slug', 'review_lane', 'is_core')
    return dict(zip(keys, row))


def get_category_id(cursor, slug, default=None):
    """Return the category_id for a slug, or `default` if not found."""
    cat = get_category_by_slug(cursor, slug)
    return cat['category_id'] if cat else default


RANK_BANDS = ['Instructor', 'Assistant Professor', 'Associate Professor', 'Professor']


def rank_band(rank):
    """Normalise a full academic rank string to its band.

    'Instructor I' / 'Instructor II' -> 'Instructor', etc. Assistant/Associate
    are checked before the bare 'professor' prefix since they also contain it.
    """
    r = (rank or '').strip().lower()
    if r.startswith('assistant professor'):
        return 'Assistant Professor'
    if r.startswith('associate professor'):
        return 'Associate Professor'
    if r.startswith('instructor'):
        return 'Instructor'
    if r.startswith('professor'):
        return 'Professor'
    return 'Unclassified'


# ─────────────────────────────────────────────
# Admin Criteria CRUD (Phase 2)
# ─────────────────────────────────────────────

def _slugify(name):
    """Turn a display name into a stable machine slug: lowercase, alnum + underscores."""
    slug = re.sub(r'[^a-z0-9]+', '_', (name or '').strip().lower()).strip('_')
    return slug or 'criterion'


def get_all_criteria(cursor, active_only=False):
    """All target criteria (categories) with every column, ordered by display_order."""
    query = """
        SELECT category_id, category_name, slug, review_lane, is_core,
               display_order, is_active
        FROM tbl_target_categories
    """
    if active_only:
        query += " WHERE is_active = 1"
    query += " ORDER BY display_order, category_name"
    cursor.execute(query)
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _unique_slug(cursor, base, exclude_id=None):
    """Return a slug unique across tbl_target_categories, suffixing _2, _3, ... on collision."""
    slug = base
    n = 1
    while True:
        if exclude_id is None:
            cursor.execute("SELECT category_id FROM tbl_target_categories WHERE slug = %s", (slug,))
        else:
            cursor.execute(
                "SELECT category_id FROM tbl_target_categories WHERE slug = %s AND category_id <> %s",
                (slug, exclude_id))
        if not cursor.fetchone():
            return slug
        n += 1
        slug = f"{base}_{n}"


def add_criteria(conn, cursor, name, slug, review_lane, is_core, display_order):
    """Create a new criterion. Slug auto-derives from name when blank; kept unique."""
    name = (name or '').strip()
    if not name:
        return False, "Criterion name is required."
    if review_lane not in ('CHAIR', 'RET'):
        return False, "Review lane must be CHAIR or RET."
    try:
        base = _slugify(slug) if (slug and slug.strip()) else _slugify(name)
        final_slug = _unique_slug(cursor, base)
        cursor.execute("""
            INSERT INTO tbl_target_categories
                (category_name, slug, review_lane, is_core, display_order, is_active)
            VALUES (%s, %s, %s, %s, %s, 1)
        """, (name, final_slug, review_lane, 1 if is_core else 0, int(display_order or 100)))
        conn.commit()
        return True, f"Criterion '{name}' added (slug: {final_slug})."
    except Exception as e:
        conn.rollback()
        return False, str(e)


def update_criteria(conn, cursor, category_id, name, review_lane, is_core, display_order):
    """Update a criterion. Slug is immutable (code/data reference it)."""
    name = (name or '').strip()
    if not name:
        return False, "Criterion name is required."
    if review_lane not in ('CHAIR', 'RET'):
        return False, "Review lane must be CHAIR or RET."
    try:
        cursor.execute("""
            UPDATE tbl_target_categories
            SET category_name = %s, review_lane = %s, is_core = %s, display_order = %s
            WHERE category_id = %s
        """, (name, review_lane, 1 if is_core else 0, int(display_order or 100), category_id))
        conn.commit()
        return True, "Criterion updated."
    except Exception as e:
        conn.rollback()
        return False, str(e)


def set_criteria_active(conn, cursor, category_id, is_active):
    """Soft-delete / restore a criterion (hard delete stays blocked by FKs)."""
    try:
        cursor.execute(
            "UPDATE tbl_target_categories SET is_active = %s WHERE category_id = %s",
            (1 if is_active else 0, category_id))
        conn.commit()
        return True, ("Criterion activated." if is_active else "Criterion deactivated.")
    except Exception as e:
        conn.rollback()
        return False, str(e)


# ─────────────────────────────────────────────
# Weight Allocation by Rank (Phase 3)
# ─────────────────────────────────────────────

# Regular vs Designated faculty get independently configured weight tables — the same
# indicator "type" can sit under a differently-weighted bucket for each (e.g. Instruction
# is weighted under 'Strategic Priorities' at 50% for Regular, but under 'Core Functions'
# at 25% for Designated) — see old MDS/DYNAMIC_CRITERIA.md for the source IPCR forms.
# Values match tbl_employee_profiles.designation used elsewhere in the codebase.
DESIGNATION_TYPES = ['Regular Faculty', 'Designated Faculty']

# Weights can be allocated one of two ways per (term, designation type):
#   GENERAL  — one set of percentages applying to every academic rank. Stored as rows with
#              rank_band = GENERAL_BAND (a sentinel; rank_band has no FK, so no migration).
#   SPECIFIC — a separate set of percentages per rank band (RANK_BANDS).
# The two modes are mutually exclusive: saving either mode clears all existing rows for that
# (term, designation type) first, so a configuration is never ambiguously half in each mode.
# Unconfigured defaults to GENERAL — notably for Designated Faculty, whose weights are driven
# by the designation rather than academic rank.
GENERAL_BAND = 'General'
MODE_GENERAL = 'GENERAL'
MODE_SPECIFIC = 'SPECIFIC'


def get_weights_mode(cursor, term_id, designation_type):
    """Which mode this (term, designation type) is configured in. Unconfigured -> GENERAL."""
    cursor.execute("""
        SELECT COUNT(*) FROM tbl_criteria_weights
        WHERE term_id = %s AND designation_type = %s AND rank_band <> %s
    """, (term_id, designation_type, GENERAL_BAND))
    return MODE_SPECIFIC if cursor.fetchone()[0] > 0 else MODE_GENERAL


# ─────────────────────────────────────────────
# IPCR Categories (Group 4) — the rows that carry weight on the printed form
# ─────────────────────────────────────────────

def get_ipcr_categories(cursor, designation_type=None, active_only=True):
    """
    IPCR categories (Strategic Priorities / Core Functions / …) for a designation type.
    These are the weight-bearing rows; the target *types* under each come from
    tbl_ipcr_category_types.
    """
    query = """
        SELECT ipcr_category_id, designation_type, category_name, display_order, is_active
        FROM tbl_ipcr_categories
    """
    conds, params = [], []
    if designation_type:
        conds.append("designation_type = %s")
        params.append(designation_type)
    if active_only:
        conds.append("is_active = 1")
    if conds:
        query += " WHERE " + " AND ".join(conds)
    query += " ORDER BY designation_type, display_order, category_name"
    cursor.execute(query, tuple(params))
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def get_category_type_map(cursor, designation_type):
    """{ipcr_category_id: [target category_id, ...]} for one designation type."""
    cursor.execute("""
        SELECT ict.ipcr_category_id, ict.category_id
        FROM tbl_ipcr_category_types ict
        JOIN tbl_ipcr_categories ic ON ic.ipcr_category_id = ict.ipcr_category_id
        WHERE ic.designation_type = %s
    """, (designation_type,))
    mapping = {}
    for cat_id, type_id in cursor.fetchall():
        mapping.setdefault(cat_id, []).append(type_id)
    return mapping


def get_type_to_category(cursor, designation_type):
    """
    Reverse lookup {target category_id: ipcr_category_id} — used by the roll-up to
    decide which weighted category a target belongs to for this designation.
    """
    cursor.execute("""
        SELECT ict.category_id, ict.ipcr_category_id
        FROM tbl_ipcr_category_types ict
        JOIN tbl_ipcr_categories ic ON ic.ipcr_category_id = ict.ipcr_category_id
        WHERE ic.designation_type = %s AND ic.is_active = 1
    """, (designation_type,))
    return {type_id: cat_id for type_id, cat_id in cursor.fetchall()}


def save_ipcr_category(conn, cursor, designation_type, category_name, display_order,
                       type_ids, ipcr_category_id=None):
    """Create or update one IPCR category and replace its assigned target types."""
    name = (category_name or '').strip()
    if not name:
        return False, "Category name is required."
    if designation_type not in DESIGNATION_TYPES:
        return False, "Invalid designation type."
    try:
        if ipcr_category_id:
            cursor.execute("""
                UPDATE tbl_ipcr_categories
                SET category_name = %s, display_order = %s
                WHERE ipcr_category_id = %s
            """, (name, int(display_order or 100), ipcr_category_id))
        else:
            cursor.execute("""
                INSERT INTO tbl_ipcr_categories (designation_type, category_name, display_order)
                VALUES (%s, %s, %s)
            """, (designation_type, name, int(display_order or 100)))
            ipcr_category_id = cursor.lastrowid

        cursor.execute("DELETE FROM tbl_ipcr_category_types WHERE ipcr_category_id = %s",
                       (ipcr_category_id,))
        for type_id in (type_ids or []):
            cursor.execute("""
                INSERT INTO tbl_ipcr_category_types (ipcr_category_id, category_id)
                VALUES (%s, %s)
            """, (ipcr_category_id, int(type_id)))

        conn.commit()
        return True, f"Category '{name}' saved."
    except Exception as e:
        conn.rollback()
        return False, str(e)


def set_ipcr_category_active(conn, cursor, ipcr_category_id, is_active):
    """Soft-delete / restore an IPCR category (weights reference it)."""
    try:
        cursor.execute(
            "UPDATE tbl_ipcr_categories SET is_active = %s WHERE ipcr_category_id = %s",
            (1 if is_active else 0, ipcr_category_id))
        conn.commit()
        return True, ("Category activated." if is_active else "Category deactivated.")
    except Exception as e:
        conn.rollback()
        return False, str(e)


def get_criteria_weights_grid(cursor, term_id, designation_type):
    """Returns {rank_band: {ipcr_category_id: weight_pct}} for the term + designation type.
    Includes the GENERAL_BAND key when configured in General mode."""
    grid = {band: {} for band in RANK_BANDS}
    grid[GENERAL_BAND] = {}
    cursor.execute("""
        SELECT rank_band, ipcr_category_id, weight_pct FROM tbl_criteria_weights
        WHERE term_id = %s AND designation_type = %s
    """, (term_id, designation_type))
    for band, cat_id, pct in cursor.fetchall():
        grid.setdefault(band, {})[cat_id] = float(pct)
    return grid


def save_criteria_weights(conn, cursor, term_id, designation_type, mode, rows):
    """
    Replaces the term + designation type's weight allocation. `rows` is a list of
    (rank_band, ipcr_category_id, weight_pct) — a single GENERAL_BAND band in General
    mode, or one band per RANK_BANDS entry in Specific mode.

    Validation: any band whose entered percentages sum to a nonzero total must sum to
    exactly 100 (a MySQL cross-row CHECK isn't practical, so this lives here). A band left
    entirely at zero is treated as "not yet configured" and simply isn't stored, so a
    Specific matrix can still be filled in incrementally.

    All existing rows for the (term, designation type) are cleared first, so switching
    between General and Specific never leaves stale rows from the other mode behind.
    """
    if designation_type not in DESIGNATION_TYPES:
        return False, "Invalid designation type."
    if mode not in (MODE_GENERAL, MODE_SPECIFIC):
        return False, "Invalid weight allocation mode."
    try:
        by_band = {}
        for band, group, pct in rows:
            by_band.setdefault(band, []).append((group, pct))

        errors = []
        for band, entries in by_band.items():
            total = sum(pct for _, pct in entries)
            if total > 0 and abs(total - 100) > 0.01:
                label = 'General' if band == GENERAL_BAND else band
                errors.append(f"{label} totals {total:g}% (must be 100%)")
        if errors:
            return False, "Not saved — " + "; ".join(errors) + "."

        # Clear both modes' rows, then write only the submitted mode's rows.
        cursor.execute(
            "DELETE FROM tbl_criteria_weights WHERE term_id = %s AND designation_type = %s",
            (term_id, designation_type))

        for band, entries in by_band.items():
            for cat_id, pct in entries:
                if pct <= 0:
                    continue
                cursor.execute("""
                    INSERT INTO tbl_criteria_weights (term_id, designation_type, ipcr_category_id, rank_band, weight_pct)
                    VALUES (%s, %s, %s, %s, %s)
                """, (term_id, designation_type, cat_id, band, pct))

        conn.commit()
        label = "general (all ranks)" if mode == MODE_GENERAL else "per academic rank"
        return True, f"Weight allocations saved for {designation_type} — {label}."
    except Exception as e:
        conn.rollback()
        return False, str(e)


def get_applicable_weights(cursor, term_id, designation_type, academic_rank=None):
    """
    Resolve the {ipcr_category_id: weight_pct} that applies to one employee.
    General rows (if configured) win for every rank; otherwise falls back to the
    employee's rank band. Returns {} when nothing is configured.
    """
    cursor.execute("""
        SELECT ipcr_category_id, weight_pct FROM tbl_criteria_weights
        WHERE term_id = %s AND designation_type = %s AND rank_band = %s
    """, (term_id, designation_type, GENERAL_BAND))
    rows = cursor.fetchall()
    if rows:
        return {c: float(p) for c, p in rows}

    cursor.execute("""
        SELECT ipcr_category_id, weight_pct FROM tbl_criteria_weights
        WHERE term_id = %s AND designation_type = %s AND rank_band = %s
    """, (term_id, designation_type, rank_band(academic_rank)))
    return {c: float(p) for c, p in cursor.fetchall()}


def copy_weights_from_previous_term(conn, cursor, term_id, designation_type):
    """Copies the most recent other term's weight matrix for this designation type into
    `term_id`, only if that (term, designation_type) combination has none yet."""
    if designation_type not in DESIGNATION_TYPES:
        return False, "Invalid designation type."
    try:
        cursor.execute(
            "SELECT COUNT(*) FROM tbl_criteria_weights WHERE term_id = %s AND designation_type = %s",
            (term_id, designation_type))
        if cursor.fetchone()[0] > 0:
            return False, f"{designation_type} already has weight allocations for this term; copy skipped to avoid overwriting."

        cursor.execute("""
            SELECT term_id FROM tbl_criteria_weights
            WHERE term_id <> %s AND designation_type = %s
            ORDER BY term_id DESC LIMIT 1
        """, (term_id, designation_type))
        prev = cursor.fetchone()
        if not prev:
            return False, f"No other term has {designation_type} weight allocations to copy from."
        prev_term_id = prev[0]

        cursor.execute("""
            INSERT INTO tbl_criteria_weights (term_id, designation_type, ipcr_category_id, rank_band, weight_pct)
            SELECT %s, designation_type, ipcr_category_id, rank_band, weight_pct
            FROM tbl_criteria_weights WHERE term_id = %s AND designation_type = %s
        """, (term_id, prev_term_id, designation_type))
        conn.commit()
        return True, f"Copied {designation_type} weight allocations from term #{prev_term_id}."
    except Exception as e:
        conn.rollback()
        return False, str(e)
