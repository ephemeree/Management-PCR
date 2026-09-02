"""Auto-generated IPCR target descriptions.

Two generation modes, chosen per-indicator by what its `indicator_description` text contains:

**Placeholder mode** — the indicator text contains a `{qty}`/`{duration}` token, e.g.
`"Submit {qty} accurate report of grades within {duration} after the final examination
period"`. The tokens are substituted directly with the formatted quantity/duration. This is
the primary mode for this college's real indicator library: master indicators are authored as
complete, already-narrative sentences (matching the source DPCR's own fill-in-the-blank
convention) where the quantity typically sits mid-sentence, right after an introductory verb
("Submit *51*...", "Prepare *1* tracer studies...") — never at the start of the string. The
same indicator is also reused at multiple cascade levels with a *different* quantity each time
(a Dean-level total distributed down to a department, then to one faculty member), so the
number has to be *replaced* at a known position, not guessed at and prepended. See
REVISION MDs/target_desc.md, "Redesign: Placeholder-based generation".

A token may optionally carry the value it replaced, e.g. `{qty:1}` or `{duration:6:months}` —
this is purely cosmetic. It lets `render_indicator_preview()` show a normal-looking, readable
sentence with a real number in it (e.g. in the Admin's indicator list) instead of the bare
token, without affecting substitution: actual generation always uses the real assigned
quantity/duration, never the embedded default. The Admin's click-to-tag helper
(`admin_dashboard.html`) writes this form automatically; a bare `{qty}`/`{duration}` typed by
hand still works identically, it just has nothing to show in the preview.

**Legacy mode** — no placeholder tokens present. Falls back to the original prepend/append
design: "[Quantity] [Indicator Description] within [Duration Value] [Duration Unit]". This
still applies to every indicator authored before placeholders existed, and to genuinely bare
activity names with no embedded number (e.g. "Preparation and submission of syllabus for
assigned courses") that a manager never needs to write with tokens at all.

Legacy-mode cleaning is deliberately conservative and asymmetric between the two ends of the
string, because the two failure modes aren't equally dangerous:

- A leftover **leading quantity** that doesn't match (e.g. indicator text still says
  "1 Research paper..." while the assigned quantity is 2) is only cosmetic: it produces
  an odd-looking "2 1 Research paper..." but `build_actual_accomplishment()`
  (`scoring.py`) only ever substitutes the *anchored* leading token, so it can't land on
  the wrong text. So the leading quantity is stripped only when it exactly duplicates the
  quantity being inserted — anything else in the indicator text is left untouched, since
  it's free-form admin-authored content and blind stripping of "any leading number" risks
  corrupting legitimate wording (e.g. "3rd Year students' thesis mentoring"). This is also
  exactly why legacy mode can't fix the mid-sentence-quantity problem placeholder mode
  solves: an exact-match-only rule anchored at position 0 never even looks at a quantity
  sitting after a verb.
- A leftover **trailing duration clause** ("...within 6 months") is not just cosmetic: if
  the newly-assigned duration is later appended after it, the string ends up with two
  duration-shaped phrases, and `build_actual_accomplishment()`'s duration regex matches
  on the *first* one it finds — i.e. the stale leftover, not the one we just appended —
  silently substituting the actual duration into the wrong place. So this trailing clause
  is always stripped (not just on an exact match) before appending the current duration.
  As a last line of defense, if the cleaned text still contains *any* duration-shaped
  phrase afterwards (e.g. a mid-sentence, non-trailing mention we didn't anticipate), the
  generator skips appending its own duration clause entirely rather than risk a second
  match — see the guard in `_format_legacy`.
"""

import re

from app.models.scoring import BLANK, DURATION_UNITS, format_duration

# {qty} or {qty:<default>} — the trailing ":<default>" is optional and purely cosmetic (see
# module docstring); group(1) captures it when present.
PLACEHOLDER_QTY_RE = re.compile(r'\{qty(?::([^}]*))?\}')
# {duration}, {duration:<value>} or {duration:<value>:<unit>}.
PLACEHOLDER_DURATION_RE = re.compile(r'\{duration(?::([^:}]*)(?::([^}]*))?)?\}')

# A leading quantity token, e.g. "2 " or "100 " at the start of the indicator text.
_LEADING_QTY = re.compile(r'^\s*(\d+(?:\.\d+)?)\s+')

_UNIT_ALTERNATION = '|'.join(u[:-1] + '(?:s)?' for u in DURATION_UNITS)  # day(s)?|week(s)?|...

# A trailing "within/in <value> <unit>" duration clause at the end of the indicator text —
# always stripped before appending the current duration (see module docstring).
_TRAILING_DURATION = re.compile(
    rf'\s*\b(?:within|in)\s+\d+\s*(?:{_UNIT_ALTERNATION})\s*\.?\s*$',
    re.IGNORECASE,
)

# Any duration-shaped phrase anywhere in the text — used only as a post-hoc safety check
# (mirrors scoring.py's _DURATION_PHRASE) to decide whether it's safe to append our own.
_ANY_DURATION_PHRASE = re.compile(rf'\b\d+\s*(?:{_UNIT_ALTERNATION})\b', re.IGNORECASE)


def get_indicator_description(cursor, indicator_id):
    """Look up a master indicator's raw description by id — the input to the formatter below."""
    cursor.execute("SELECT indicator_description FROM tbl_master_indicators WHERE indicator_id = %s", (indicator_id,))
    row = cursor.fetchone()
    return row[0] if row else ''


def has_placeholders(indicator_description):
    """True if the indicator text uses the {qty}/{duration} placeholder convention."""
    text = indicator_description or ''
    return bool(PLACEHOLDER_QTY_RE.search(text) or PLACEHOLDER_DURATION_RE.search(text))


def render_indicator_preview(indicator_description):
    """
    Render a placeholder-tagged indicator for display (e.g. the Admin's indicator list) using
    each token's embedded default value, so browsing indicators shows a normal-looking sentence
    with a real number in it instead of raw "{qty:1}" syntax. Display only — never used to
    generate an actual target description; see module docstring.
    """
    text = indicator_description or ''
    if not has_placeholders(text):
        return text

    def _sub_qty(m):
        return m.group(1) if m.group(1) else BLANK

    def _sub_duration(m):
        value, unit = m.group(1), m.group(2)
        if value and unit:
            return format_duration(value, unit) or BLANK
        return value or BLANK

    text = PLACEHOLDER_QTY_RE.sub(_sub_qty, text)
    text = PLACEHOLDER_DURATION_RE.sub(_sub_duration, text)
    return text


def _format_quantity(quantity):
    """Render a quantity for display, or '' if it isn't a usable positive number."""
    if quantity in (None, ''):
        return ''
    try:
        value = float(quantity)
    except (TypeError, ValueError):
        return ''
    if value <= 0:
        return ''
    if value == int(value):
        return str(int(value))
    return str(value)


def format_ipcr_target_description(indicator_description, quantity, duration_value=None, duration_unit=None):
    """
    Build the standardized IPCR target description for an indicator, in whichever mode its
    text calls for (see module docstring).

        format_ipcr_target_description(
            "Submit {qty} accurate report of grades within {duration} after the exam period",
            15, 10, "days",
        )
        -> "Submit 15 accurate report of grades within 10 days after the exam period"

        format_ipcr_target_description(
            "Preparation and submission of syllabus for assigned courses",
            2, 1, "semesters",
        )
        -> "2 Preparation and submission of syllabus for assigned courses within 1 semester"
    """
    text = (indicator_description or '').strip()
    if not text:
        return ''

    if has_placeholders(text):
        return _format_placeholders(text, quantity, duration_value, duration_unit)
    return _format_legacy(text, quantity, duration_value, duration_unit)


def _format_placeholders(text, quantity, duration_value, duration_unit):
    """
    Substitute {qty}/{duration} tokens with the *actual* assigned quantity/duration —
    deterministic, no cleaning or guessing, since the author marked exactly where each value
    belongs. Any embedded default a token carries (e.g. "{qty:1}") is display-only and is
    always overridden here, never used as the substituted value. Falls back to the same '____'
    blank convention scoring.py uses for "not yet reported" when a value isn't set.
    """
    qty_text = _format_quantity(quantity) or BLANK
    duration_label = format_duration(duration_value, duration_unit) or BLANK

    def _qty(match):
        # A trailing '%' in the embedded default ("{qty:80%}") is a *unit*, not part of the
        # example number: the author wrote a percentage target, and the sentence has to keep
        # reading as one at whatever value is actually assigned. Dropping it produced "80 of
        # undergraduate programs..." here while the Admin's own preview showed "80%", so the
        # person retyped the '%' by hand — which permanently marked the row as customized and
        # froze whatever else was wrong in it. Carried over rather than substituted blindly:
        # the number is still the assigned quantity, only the unit comes from the token.
        default = match.group(1) or ''
        if default.endswith('%') and qty_text is not BLANK and not qty_text.endswith('%'):
            return qty_text + '%'
        return qty_text

    # Callback form (not a plain replacement string) so a value that happens to contain a
    # backslash is never misread as a regex backreference.
    text = PLACEHOLDER_QTY_RE.sub(_qty, text)
    text = PLACEHOLDER_DURATION_RE.sub(lambda m: duration_label, text)
    return text


def _format_legacy(text, quantity, duration_value, duration_unit):
    """Original prepend/append design — see module docstring for why it's conservative."""
    qty_text = _format_quantity(quantity)
    duration_label = format_duration(duration_value, duration_unit)

    # Strip a leading quantity only if it exactly matches the one we're about to prepend —
    # avoids "2 2 Research paper..." when the indicator was authored with the old
    # manual convention, without guessing at anything that doesn't match. A mismatched
    # leading quantity is left as-is: cosmetically odd, but harmless to downstream scoring
    # (see module docstring).
    if qty_text:
        m = _LEADING_QTY.match(text)
        if m and m.group(1) == qty_text:
            text = text[m.end():]

    # Always strip a trailing "within/in <value> <unit>" clause, regardless of whether it
    # matches the current duration — leaving a stale one in place would give the final
    # string two duration-shaped phrases, and the accomplishment engine substitutes on
    # the first it finds (see module docstring).
    text = _TRAILING_DURATION.sub('', text)

    text = text.strip().rstrip('.').strip()
    if not text:
        return ''

    result = f"{qty_text} {text}" if qty_text else text

    if duration_label:
        # Safety net: if a duration-shaped phrase still lurks somewhere in the cleaned
        # text (a mid-sentence mention the trailing-clause strip above wouldn't catch),
        # don't append our own — a second match would let the accomplishment engine
        # substitute into the wrong place. Fall back to "[Quantity] [Indicator]" instead.
        if not _ANY_DURATION_PHRASE.search(result):
            result = f"{result} within {duration_label}"

    return result
