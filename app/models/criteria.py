"""Central semantics for target criteria (categories).

Replaces the category-name string literals formerly hardcoded across the
faculty / prog_chair / designated / dean modules. A criterion's behaviour is
now driven by data columns on tbl_target_categories:

    review_lane   -> which review pipeline it routes through (CHAIR vs RET)
    is_core       -> participates in weighting / structured review items
    weight_group  -> scoring bucket (Research + Extension both map to 'ret')
    slug          -> stable machine key, independent of display name
"""

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
