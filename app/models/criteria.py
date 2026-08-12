"""Central semantics for target criteria (categories).

Replaces the category-name string literals formerly hardcoded across the
faculty / prog_chair / designated / dean modules. A criterion's behaviour is
now driven by data columns on tbl_target_categories:

    review_lane   -> which review pipeline it routes through (CHAIR vs RET)
    is_core       -> participates in weighting / structured review items
    weight_group  -> scoring bucket (Research + Extension both map to 'ret')
    slug          -> stable machine key, independent of display name
"""
import re

# review_lane — which review pipeline a criterion routes through
LANE_CHAIR = 'CHAIR'   # Program Chair reviews (Instruction, Support, + future core)
LANE_RET = 'RET'       # RET Chair reviews (Research, Extension)

# weight_group — scoring buckets (Phase 3+); Research + Extension both -> 'ret'
GROUP_INSTRUCTION = 'instruction'
GROUP_RET = 'ret'
GROUP_SUPPORT = 'support'
GROUP_ADMIN = 'admin'

# stable category slugs backfilled in Phase 0
SLUG_INSTRUCTION = 'instruction'
SLUG_RESEARCH = 'research'
SLUG_EXTENSION = 'extension'
SLUG_SUPPORT = 'support'
SLUG_CUSTOM = 'custom'


def get_category_by_slug(cursor, slug):
    """Return the category row for a slug as a dict, or None."""
    cursor.execute(
        "SELECT category_id, category_name, slug, review_lane, is_core, weight_group "
        "FROM tbl_target_categories WHERE slug = %s",
        (slug,),
    )
    row = cursor.fetchone()
    if not row:
        return None
    keys = ('category_id', 'category_name', 'slug', 'review_lane', 'is_core', 'weight_group')
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
        SELECT category_id, category_name, slug, review_lane, is_core, weight_group,
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


def add_criteria(conn, cursor, name, slug, review_lane, is_core, weight_group, display_order):
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
                (category_name, slug, review_lane, is_core, weight_group, display_order, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, 1)
        """, (name, final_slug, review_lane, 1 if is_core else 0,
              (weight_group or None), int(display_order or 100)))
        conn.commit()
        return True, f"Criterion '{name}' added (slug: {final_slug})."
    except Exception as e:
        conn.rollback()
        return False, str(e)


def update_criteria(conn, cursor, category_id, name, review_lane, is_core, weight_group, display_order):
    """Update a criterion. Slug is immutable (code/data reference it)."""
    name = (name or '').strip()
    if not name:
        return False, "Criterion name is required."
    if review_lane not in ('CHAIR', 'RET'):
        return False, "Review lane must be CHAIR or RET."
    try:
        cursor.execute("""
            UPDATE tbl_target_categories
            SET category_name = %s, review_lane = %s, is_core = %s,
                weight_group = %s, display_order = %s
            WHERE category_id = %s
        """, (name, review_lane, 1 if is_core else 0, (weight_group or None),
              int(display_order or 100), category_id))
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

def get_weight_groups(cursor):
    """Distinct weight_group values actually in use by active criteria — the matrix columns."""
    cursor.execute("""
        SELECT DISTINCT weight_group FROM tbl_target_categories
        WHERE weight_group IS NOT NULL AND weight_group <> '' AND is_active = 1
        ORDER BY FIELD(weight_group, 'instruction', 'ret', 'support', 'admin'), weight_group
    """)
    return [r[0] for r in cursor.fetchall()]


def get_criteria_weights_grid(cursor, term_id):
    """Returns {rank_band: {weight_group: weight_pct}} for the term."""
    grid = {band: {} for band in RANK_BANDS}
    cursor.execute(
        "SELECT rank_band, weight_group, weight_pct FROM tbl_criteria_weights WHERE term_id = %s",
        (term_id,))
    for band, group, pct in cursor.fetchall():
        grid.setdefault(band, {})[group] = float(pct)
    return grid


def save_criteria_weights(conn, cursor, term_id, rows):
    """
    Replaces the term's weight matrix. `rows` is a list of (rank_band, weight_group, weight_pct).

    Validation: any rank_band whose entered percentages sum to a nonzero total must sum to
    exactly 100 (a MySQL cross-row CHECK isn't practical, so this lives here). A rank_band
    left entirely at zero is treated as "not yet configured" and its rows are cleared rather
    than saved, so an incomplete matrix can still be saved incrementally.
    """
    try:
        by_band = {}
        for band, group, pct in rows:
            by_band.setdefault(band, []).append((group, pct))

        errors = []
        for band, entries in by_band.items():
            total = sum(pct for _, pct in entries)
            if total > 0 and abs(total - 100) > 0.01:
                errors.append(f"{band} totals {total:g}% (must be 100%)")
        if errors:
            return False, "Not saved — " + "; ".join(errors) + "."

        for band, entries in by_band.items():
            cursor.execute(
                "DELETE FROM tbl_criteria_weights WHERE term_id = %s AND rank_band = %s",
                (term_id, band))
            for group, pct in entries:
                if pct <= 0:
                    continue
                cursor.execute("""
                    INSERT INTO tbl_criteria_weights (term_id, weight_group, rank_band, weight_pct)
                    VALUES (%s, %s, %s, %s)
                """, (term_id, group, band, pct))

        conn.commit()
        return True, "Weight allocations saved."
    except Exception as e:
        conn.rollback()
        return False, str(e)


def copy_weights_from_previous_term(conn, cursor, term_id):
    """Copies the most recent other term's weight matrix into `term_id`, only if it has none yet."""
    try:
        cursor.execute("SELECT COUNT(*) FROM tbl_criteria_weights WHERE term_id = %s", (term_id,))
        if cursor.fetchone()[0] > 0:
            return False, "This term already has weight allocations; copy skipped to avoid overwriting."

        cursor.execute("""
            SELECT term_id FROM tbl_criteria_weights WHERE term_id <> %s
            ORDER BY term_id DESC LIMIT 1
        """, (term_id,))
        prev = cursor.fetchone()
        if not prev:
            return False, "No other term has weight allocations to copy from."
        prev_term_id = prev[0]

        cursor.execute("""
            INSERT INTO tbl_criteria_weights (term_id, weight_group, rank_band, weight_pct)
            SELECT %s, weight_group, rank_band, weight_pct
            FROM tbl_criteria_weights WHERE term_id = %s
        """, (term_id, prev_term_id))
        conn.commit()
        return True, f"Copied weight allocations from term #{prev_term_id}."
    except Exception as e:
        conn.rollback()
        return False, str(e)
