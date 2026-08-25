# D-IPCR Frontend Audit

Read-only audit using the `impeccable` skill (technical/UX audit) and `design-taste-frontend` skill
(visual-direction critique, where applicable). No code changes made. Findings are prioritized
P0 (blocking) → P3 (polish). This document accumulates one section per surface.

**Tooling note**: `design-taste-frontend` explicitly scopes itself to landing/marketing/portfolio
work and declares dashboards/admin UI **out of scope** (Section 13 of its own instructions — it
recommends Fluent UI/Carbon/Atlassian/Polaris for dashboards instead, which would mean replacing
the whole component stack, not something in scope here). So for every dashboard surface below,
`impeccable` does the real work; `design-taste-frontend` is only invoked where a surface is
landing/auth-page-like enough for its lens to apply.

---

## 1. Shared Shell — `base.html` + `auth_layout.html`

**Impeccable Audit Health Score: 12/20 — Acceptable (significant work needed)**

| # | Dimension | Score | Key Finding |
|---|-----------|-------|-------------|
| 1 | Accessibility | 2/4 | Collapsed sidebar hides nav-item text via `display:none`, removing the accessible name entirely — not just visually hidden |
| 2 | Performance | 2/4 | Two full icon-font libraries (Tabler + Bootstrap Icons) loaded simultaneously mid-migration |
| 3 | Theming | 3/4 | Real CSS custom-property token system, retints Bootstrap's own `--bs-*` vars too; a couple of literals duplicate tokens instead of referencing them |
| 4 | Responsive Design | 3/4 | Solid overlay/hamburger pattern; a few touch targets under 44px |
| 5 | Implementation Integrity | 2/4 | Detector found a repeated "side-tab" accent-border pattern (7 instances) — a well-known AI-generated-UI tell |

### Implementation Integrity Verdict
**Pass, with a caveat.** The shell expresses a coherent, product-specific system (real palette, real
domain labels, deliberate typography) — this is not generic scaffolding. The deduction is the
repeated side-tab border pattern flagged by the mechanical detector (`node detect.mjs`), which
recurs identically across all five status colors (info/success/warning/danger, twice each for
`border-start` and `border-top` variants).

### Findings

**[P1] Sidebar nav loses its accessible name entirely when collapsed** — ✅ Fixed (missed in earlier passes, caught on final review: every nav item now gets an `aria-label` alongside `data-tooltip`, independent of `.nav-text`'s `display:none` state)
- **Location**: `app/templates/base.html:242-250` (`.collapsed .nav-item .nav-text { display: none !important; }`)
- **Category**: Accessibility
- **Impact**: Every nav item, plus the logout button, is a bare icon with no text once the sidebar is
  collapsed. `display:none` removes the element from the accessibility tree, not just visually — so a
  screen-reader user gets an icon-only, unlabeled control. The `data-tooltip` attribute driving the
  hover tooltip (`::after { content: attr(data-tooltip) }`) is CSS-only and invisible to assistive
  tech. Collapse state persists via `localStorage`, so this can be a returning user's default state.
- **WCAG**: 4.1.2 Name, Role, Value (Level A)
- **Recommendation**: Add `aria-label` (populated from the same text already used for `data-tooltip`)
  to every `.nav-item`, or keep an `sr-only`/visually-hidden span instead of `display:none`.
- **Suggested command**: `$impeccable harden`

**[P1] `showCustomAlert()` writes untrusted content via `innerHTML`** — ✅ Fixed (switched to `textContent`)
- **Location**: `app/templates/base.html:1040` (`messageEl.innerHTML = message || '';`)
- **Category**: Implementation Integrity / Security
- **Impact**: This is the single shared alert modal every dashboard calls into. If any current or
  future call site ever passes user-influenced text (a validation message that echoes user input, an
  error string built from form data) without pre-sanitizing, this is a stored/reflected XSS sink by
  construction. Flagging because it's foundational — the risk compounds with every new caller.
- **Recommendation**: Default to `textContent`; only use `innerHTML` at specific call sites that
  deliberately need markup, with the value hard-coded, never interpolated from user/DB data.
- **Suggested command**: `$impeccable harden`

**[P2] Two full icon-font libraries loaded on every page** — ✅ Fixed (the actual migration was already complete app-wide; removed the now-redundant Bootstrap Icons `<link>`, stale comment, and the one dead code block still referencing `bi-` classes)
- **Location**: `app/templates/base.html:8-10`
- **Category**: Performance / Implementation Integrity
- **Impact**: Tabler Icons and Bootstrap Icons are both loaded on every request while the `bi-`→`ti-`
  migration (noted in the code's own comment) is incomplete. Extra font-file weight and two icon
  vocabularies to keep visually consistent indefinitely.
- **Recommendation**: Track remaining `bi-` usages per dashboard (a simple grep) and finish the
  migration in one pass; drop the Bootstrap Icons `<link>` once done.
- **Suggested command**: `$impeccable optimize`

**[P2] Repeated "side-tab" accent-border pattern (detector-flagged)**
- **Location**: `app/templates/base.html:471-479, 650-654` (`.border-start.border-*`, `.alert-*`)
- **Category**: Implementation Integrity (visual)
- **Impact**: A thick colored left-border accent on cards/alerts, repeated identically across all five
  status colors. The bundled mechanical detector calls this out by name as "the most recognizable
  tell of AI-generated UIs." It's used consistently (not sloppy), but it's worth a deliberate look at
  whether a subtler treatment better fits the rest of the token system's restraint.
- **Recommendation**: Consider a quieter accent — e.g. a smaller icon + text color pairing, or a
  1px top border instead of a 3px left border — while keeping the existing color tokens.
- **Suggested command**: `$impeccable colorize` or `$impeccable layout`

**[P2] No toggle/expand state exposed to assistive tech** — ✅ Fixed
- **Location**: `app/templates/base.html:882, 843` (`#sidebarToggle`, `#mobileToggle`)
- **Category**: Accessibility
- **Impact**: Both buttons change layout state (sidebar collapsed/expanded, mobile menu open/closed)
  but never set `aria-expanded`. A screen-reader user has no way to know the current state before
  activating the control.
- **WCAG**: 4.1.2 Name, Role, Value
- **Recommendation**: Toggle `aria-expanded="true|false"` alongside the existing class toggles in the
  same JS handlers.
- **Suggested command**: `$impeccable harden`

**[P2] Main content area has no `<h1>`** — ✅ Fixed
- **Location**: `app/templates/base.html` (`<main id="mainContent">` block)
- **Category**: Accessibility / Semantic HTML
- **Impact**: Every dashboard section header uses `<h2>` (`.page-header h2`); nothing in the shell
  establishes a page-level `<h1>`. Screen-reader users navigating by heading level lose the top of
  the hierarchy.
- **Recommendation**: Either promote the per-section header to `<h1>` or add a visually-hidden `<h1>`
  naming the current dashboard/section in the shell template.
- **Suggested command**: `$impeccable harden`

**[P3] Hard-coded color literals duplicate design tokens instead of referencing them**
- **Location**: `app/templates/base.html:39` (`color: #2B2822;` on `body`, before `--c-text` is even
  defined later in the file), `:764-780` (tooltip `background: #2B2822`)
- **Category**: Theming
- **Impact**: Both literals happen to match `--c-text`'s value today, but nothing enforces that — a
  future token change silently drifts these two spots out of sync.
- **Recommendation**: Replace with `var(--c-text)`.
- **Suggested command**: `$impeccable polish`

**[P3] No styled invalid/error state for form fields**
- **Location**: `app/templates/base.html:617-641` (`.form-control`, `.form-select` rules)
- **Category**: Theming / Forms
- **Impact**: Focus state is designed (custom glow using `--c-accent-glow`), but there's no
  `.is-invalid`/`:invalid` treatment in the shared system, so field-level validation errors likely
  fall back to raw Bootstrap red, inconsistent with the muted custom palette.
- **Recommendation**: Add an invalid-state block using `--c-danger` to match the rest of the palette.
- **Suggested command**: `$impeccable harden`

**[P3] A few touch targets under the 44px recommendation**
- **Location**: `app/templates/auth_layout.html:174-190` (`.toggle-password-btn`, ~24-32px)
- **Category**: Responsive Design
- **Impact**: Minor tap-precision friction on touch devices for the password-visibility toggle.
- **Recommendation**: Increase the button's hit area via padding without growing the visible icon.
- **Suggested command**: `$impeccable adapt`

**[P3] No skip-to-content link**
- **Location**: `app/templates/base.html` (top of `<body>`)
- **Category**: Accessibility
- **Impact**: Keyboard users must tab through the entire sidebar nav before reaching main content on
  every single page load.
- **Recommendation**: Add a standard visually-hidden-until-focused "Skip to content" link as the
  first focusable element.
- **Suggested command**: `$impeccable harden`

### Patterns & Systemic Issues (will recur across every dashboard unless fixed here)
- The collapsed-sidebar accessible-name gap (P1) and missing `aria-expanded` (P2) affect every
  dashboard that extends `base.html` — fixing it once here fixes it everywhere.
- The dual icon-font situation is shell-level but its resolution requires touching every dashboard's
  individual `bi-`/`ti-` class usages — flagged here, actual fix is per-dashboard.
- `showCustomAlert()`'s `innerHTML` sink is called from JS across all six dashboards — worth an
  audit of call sites once the shell fix lands.

### Positive Findings
- A genuinely disciplined design-token system: custom properties are used to retint Bootstrap's own
  `--bs-primary`/`--bs-success`/etc. so plain Bootstrap utility classes (`bg-primary`, `text-danger`)
  automatically pick up the custom palette — most hand-rolled Bootstrap overrides don't bother with
  this and end up with two competing color systems.
- Deliberate, consistently-applied type pairing (Lora for headings via `--font-heading`, Public Sans
  for body via `--font-body`) rather than default Bootstrap/system fonts.
- Mobile sidebar pattern (overlay + hamburger + backdrop blur, correct z-index layering) is properly
  implemented, not a common shortcut-taken area.
- Sidebar collapse state and last-active dashboard section persist via `localStorage` — thoughtful
  continuity across reloads that most SPA-style dashboards skip.
- A single shared `showCustomAlert()` modal replaces what would otherwise be inconsistent native
  `alert()` calls scattered across six large templates.

### Design-Taste-Frontend Note (scoped)
The skill declined to critique the sidebar/card/table UI (explicitly out of scope for dashboards).
Its lens does apply lightly to `auth_layout.html`'s hero panel, the one landing-page-like surface:
- **[P3]** The headline copy ("Efficiently manage your individual performance commitments... Secure,
  transparent, and easy to use.") reads as generic marketing copy for a page employees are required
  to use, not choosing to. Consider a plainer, more functional line.
- No AI-tell violations found otherwise (no em-dashes, no fake stats, no filler-verb overload); the
  restrained use of serif (Lora) for headings only, on an institutional system, is a defensible
  choice rather than the "creative brief = serif" default the skill normally flags.

### Recommended Actions (priority order)
1. **[P1] `$impeccable harden`** — fix the collapsed-sidebar accessible-name loss and the `innerHTML`
   sink in `showCustomAlert()`.
2. **[P2] `$impeccable harden`** — add `aria-expanded` to both toggle buttons and an `<h1>` to the
   main content area.
3. **[P2] `$impeccable optimize`** — finish the `bi-`→`ti-` icon migration and drop the redundant
   icon-font `<link>`.
4. **[P2] `$impeccable colorize`** or **`$impeccable layout`** — reconsider the repeated side-tab
   accent-border treatment.
5. **[P3] `$impeccable polish`** — replace duplicated hard-coded color literals with token references,
   add an invalid form-field state, add a skip-to-content link, grow the password-toggle touch target.

> You can ask me to run these one at a time, all at once, or in any order you prefer.
> Re-run `$impeccable audit` after fixes to see the score improve.

---

## 2. Faculty Dashboard — `app/templates/faculty_dashboard.html`

**Impeccable Audit Health Score: 12/20 — Acceptable (significant work needed)**

| # | Dimension | Score | Key Finding |
|---|-----------|-------|-------------|
| 1 | Accessibility | 2/4 | 79 of 81 `ti-` icons expose no `aria-hidden`, a radio group has no `fieldset`/`legend`, and icon-only delete/unclaim buttons depend solely on `title=` for an accessible name |
| 2 | Performance | 3/4 | No layout thrash or unoptimized assets; minor nit is re-constructing `new bootstrap.Modal()` on every open instead of reusing an instance |
| 3 | Theming | 2/4 | 104 inline `style=` attributes, and 10 spots hand-duplicate `--c-danger`/`--c-warning`/`--c-accent`/`--c-success`/`--c-text` as literal `rgba()` triples instead of referencing the token |
| 4 | Responsive Design | 3/4 | All 6 tables correctly wrapped in `.table-responsive`; icon-only action buttons (`p-0 border-0`) fall well under 44×44px touch targets |
| 5 | Implementation Integrity | 2/4 | Domain logic is coherent and genuinely IPCR-specific, but the file's own `escapeHtml()` helper is defined and used once, then bypassed exactly where chair/RET-chair remarks and co-author names get injected via `innerHTML` |

### Implementation Integrity Verdict
**Pass, with concrete execution bugs.** This file is not interchangeable template filler — the RET-eligibility branching, category-specific empty states, chair-vs-RET-chair rejection copy, and shortfall-quantity warning before evidence resubmission all reflect real SPMS/IPCR business rules from `app/models/faculty.py` and the review pipeline. The drift is at the execution level, not the modeling level: the file defines a safe-HTML helper and then doesn't use it in the one AJAX path that actually renders reviewer-authored free text, and its error handling silently reverts to native `alert()` outside the custom modal system it built for everything else.

### Findings

**[P1] `escapeHtml()` exists but is bypassed for reviewer-controlled and file-derived text rendered via `innerHTML`** — ✅ Fixed
- **Location**: `app/templates/faculty_dashboard.html:862` (helper defined), `:1040` (used correctly), `:1233-1288` (bypassed) — specifically `ev.supervisor_comment` at `:1246-1247` and `:1281`, `ev.uploaded_by` at `:1279`, and the filename-derived `cleanName` at `:1240,1276`
- **Category**: Implementation Integrity / Security
- **Impact**: `supervisor_comment` is free text entered by a Program Chair or RET Chair when returning evidence; `uploaded_by` is a co-author's display name. Both flow unescaped into `itemDiv.innerHTML`, so a chair remark or a crafted co-author/file name containing markup renders live in the faculty member's browser — a genuine stored-XSS path in the same file that already proves it knows how to escape (line 1040), making this an inconsistency bug rather than a missing-feature gap.
- **Recommendation**: Route every interpolated value in `reloadEvidenceModalSubmissions` through the existing `escapeHtml()` (including inside the `title="Reason: ..."` attribute, which also breaks on an unescaped `"`), or build the row with `textContent`/`createElement` instead of a template-literal HTML string.
- **Suggested command**: `$impeccable harden`

**[P2] Icon-only delete/unclaim buttons have no accessible name beyond `title=` and sub-44px hit areas** — ✅ Fixed
- **Location**: `app/templates/faculty_dashboard.html:1254-1266` (`unclaimEvidence`/`deleteEvidence` buttons, `class="btn btn-link ... p-0 border-0"`)
- **Category**: Accessibility / Responsive
- **Impact**: `title` is not read consistently across screen reader/browser combinations and is invisible until hover, so touch users get no cue at all; `p-0 border-0` around a bare icon glyph leaves a hit target far under the 44×44px minimum, in a modal used for managing uploaded PDFs.
- **WCAG**: 4.1.2 Name, Role, Value; 2.5.5 Target Size (AAA, but good practice generally)
- **Recommendation**: Add an explicit `aria-label="Delete evidence file"` / `aria-label="Unlink co-authored paper"`, and pad the buttons (e.g. `padding:.5rem`) to reach a real touch target.
- **Suggested command**: `$impeccable harden`

**[P2] 79 of 81 decorative icons expose no `aria-hidden="true"`** — ✅ Fixed
- **Location**: throughout — e.g. `:46,58,91,102,132,167,202,214,244,302,361,425,544,715` and nearly every generated badge in the JS at `:1244-1281`; only `:496` and one other instance set `aria-hidden`
- **Category**: Accessibility
- **Impact**: Tabler icon glyphs are CSS-generated content; some browser/AT pairings (notably Firefox+NVDA) announce that generated content as stray characters around every badge, button, and heading in this file, adding noise to a page a faculty member may navigate by screen reader through a multi-stage approval workflow.
- **WCAG**: 1.1.1 Non-text Content
- **Recommendation**: Add `aria-hidden="true"` to every purely decorative `<i class="ti ...">`, in both the Jinja markup and the JS-built `badgeHtml`/`actionHtml` strings.
- **Suggested command**: `$impeccable harden`

**[P2] Hardcoded `rgba()` literals duplicate design tokens instead of referencing them** — ✅ Fixed
- **Location**: `:130,524` (`rgba(176,69,61,…)` = `--c-danger` #B0453D), `:147,177,273,327` (`rgba(184,132,46,…)` = `--c-warning` #B8842E), `:165` (`rgba(62,92,130,…)` = `--c-accent` #3E5C82), `:212,832` (`rgba(63,125,88,…)` = `--c-success` #3F7D58), `:828` (`rgba(43,40,34,.08)` = `--c-text` #2B2822)
- **Category**: Theming
- **Impact**: Every one of these values is a hand-computed RGB decomposition of an existing custom property at a fixed alpha. If the palette is ever retuned centrally in `base.html`, these 10 spots (all alert backgrounds and the RET card hover fill) silently fall out of sync instead of following the token.
- **Recommendation**: Add tint tokens to `base.html` (e.g. `--c-danger-subtle-bg`) or use `color-mix(in srgb, var(--c-danger) 8%, transparent)` instead of literal `rgba()` triples.
- **Suggested command**: `$impeccable colorize`

**[P2] "Completion Status" radio group has no `fieldset`/`legend`** — ✅ Fixed
- **Location**: `:1607-1619`
- **Category**: Accessibility
- **Impact**: Each radio is individually labeled via `for`/`id`, but the group's shared question ("Completion Status") is only a visual `<label>` above it — a screen reader landing on any one radio hears its own text but not that it's one of three mutually exclusive options for a single question.
- **WCAG**: 1.3.1 Info and Relationships
- **Recommendation**: Wrap the three radios in `<fieldset><legend class="visually-hidden-focusable">Completion Status</legend>...</fieldset>`.
- **Suggested command**: `$impeccable harden`

**[P2] Error feedback silently reverts to native `alert()`, bypassing the file's own modal system** — ✅ Fixed
- **Location**: `:1344,1347,1376,1379,1472,1477`
- **Category**: Implementation Integrity
- **Impact**: Every confirmation in this file (submit, lock, delete, unclaim, resubmit) goes through the styled `showCustomConfirm()` modal, but the corresponding *failure* paths for those same actions (delete evidence fails, unclaim fails, upload fails) drop to a blocking, unstyled `window.alert()` — an inconsistent, thread-blocking UX regression right next to the pattern it should follow.
- **Recommendation**: Surface these errors through the same modal/toast mechanism already built for confirmations, or a lightweight inline error banner in the modal.
- **Suggested command**: `$impeccable polish`

**[P3] 104 inline `style="..."` attributes**
- **Location**: file-wide (confirmed count matches the top of the 75-104 per-dashboard range found across the app)
- **Category**: Theming / Implementation Integrity
- **Impact**: Many are one-off, repeated values (`border-radius: 12px; overflow: hidden;` appears on nearly every card; `max-height: 250px; overflow-y: auto;` on every RET list) that could be shared utility classes, making a future radius/spacing change require editing dozens of individual attributes instead of one rule.
- **Recommendation**: Extract the recurring card/scroll-box patterns into small utility classes in the shared stylesheet.
- **Suggested command**: `$impeccable distill`

### Patterns & Systemic Issues
- The same root cause as the shell's known `showCustomAlert()` XSS finding recurs locally: an ad hoc `innerHTML`-string-building habit for AJAX-rendered fragments, applied inconsistently even within this one file (escaped at `:1040`, not escaped at `:1233-1288`).
- Icon accessibility is effectively binary in this file — either fully decorative-and-hidden or fully exposed-with-no-name; there's no consistent policy, so 79/81 icons default to "exposed."
- The 9 tinted-background-plus-`!important`-left-border alert cards in this file are additional instances of the shell-documented "side-tab" idiom (`:130,147,165,177,200,212,273,327,524`) — already covered at the shell level, not re-flagged here as a separate issue, but worth noting this file accounts for the bulk of that pattern's occurrences app-wide.
- `!important` appears 19 times in this file's own `<style>` blocks and inline styles, on top of the shell's already-`!important`-heavy Bootstrap overrides — a specificity arms-race that makes future styling changes harder to reason about.

### Positive Findings
- **Icon migration is complete in this file**: 81 `ti-` icons, 0 legacy `bi-` icons — this template has already finished the Tabler migration the shared shell is still mid-way through.
- **Genuinely product-specific empty/loading/error states**, not generic placeholders: "No instruction workloads assigned," "No Research indicators available," a spinner + "Loading submissions...", "No weight allocation has been configured for this term yet, so a final rating cannot be computed," and a shortfall-quantity warning listing named targets before evidence resubmission.
- **All 6 tables are wrapped in `.table-responsive`**, and the RET selection lists use bounded, scrollable containers (`max-height: 250px; overflow-y: auto`) rather than growing unbounded as indicators accumulate.
- **Real form controls are correctly labeled**: `evidenceFile`, `evidenceQty`, `evidenceCompletedIn`, `evidenceEfficiency`, `evidenceRemarks`, and the completion-status radios all use `<label for>`; the RET research checkboxes are correctly wrapped by their `<label>` for implicit association. The P2 accessibility gaps above sit on top of this solid baseline rather than replacing it.

### Design-Taste-Frontend Note (scoped)
Out of scope (dashboard UI), consistent with the shared shell finding. No exception-worthy generic pattern beyond the already-covered side-tab alert idiom noted above.

### Recommended Actions (priority order)
1. **[P1] `$impeccable harden`**: Close the `escapeHtml()` gap in `reloadEvidenceModalSubmissions` (`:1233-1288`) — chair/RET-chair remarks and co-author names are reviewer-authored text rendered unescaped.
2. **[P2] `$impeccable harden`**: Add `aria-label` and real padding to the icon-only delete/unclaim buttons (`:1254-1266`).
3. **[P2] `$impeccable harden`**: Add `aria-hidden="true"` across the file's decorative icons (both static markup and JS-built badge strings).
4. **[P2] `$impeccable harden`**: Wrap the "Completion Status" radios in a `fieldset`/`legend` (`:1607-1619`).
5. **[P2] `$impeccable colorize`**: Replace the 10 hand-duplicated `rgba()` literals with proper subtle-tint tokens.
6. **[P2] `$impeccable polish`**: Route delete/unclaim/upload failure paths through the existing modal system instead of `window.alert()`.
7. **[P3] `$impeccable distill`**: Extract the repeated card-radius/scroll-box inline styles into shared utility classes.

## 3. Designated Dashboard — `app/templates/designated_dashboard.html`

**Impeccable Audit Health Score: 10/20 — Acceptable (significant work needed)**

| # | Dimension | Score | Key Finding |
|---|-----------|-------|-------------|
| 1 | Accessibility | 2/4 | Icon-only delete buttons with no accessible name, an unassociated `<label>`/`<select>` pair, and 3 modals missing `aria-labelledby` |
| 2 | Performance | 3/4 | No layout thrash, no images, small per-target JSON payload (`TARGET_META`) — fine at faculty-dashboard scale |
| 3 | Theming | 2/4 | 6+ hardcoded `rgba(...)` literals standing in for token-based tints; a local `<style>` block whose rules are 100% dead, already overridden by identical `!important` rules in `base.html` |
| 4 | Responsive Design | 2/4 | Tables correctly wrapped in `.table-responsive`, but repeated icon-only/scaled-checkbox controls fall well under the 24-44px touch-target minimum |
| 5 | Implementation Integrity | 1/4 | A real `ReferenceError` bug in the accomplishment-save handler, a dead/unused `categories` block, duplicate CSS, and duplicated-but-inconsistent category-matching logic |

### Implementation Integrity Verdict
**Fails.** This file is domain-specific and clearly purpose-built (the Core Functions / Strategic Priorities / Support Functions split, the `is_admin_function`/oversight-cascade handling, the Q/E/T rating pipeline) — it is not templated boilerplate. But verified evidence shows real drift: a genuine JavaScript bug that breaks a validation path (see P1 below), dead template code left over from an earlier icon/category scheme, a local `<style>` block that does nothing because `base.html` already `!important`-overrides the same selectors with the same tokens, and the repeated "side-tab" left-border card pattern the detector flagged 6 times in this file alone. The product logic is coherent; the execution around it has accumulated unverified/unreachable code and one confirmed runtime bug.

### Findings

**[P1] `ReferenceError` crashes accomplishment-save validation for Client-Satisfaction targets** — ✅ Fixed (moved `msg` declaration above its first use)
- **Location**: app/templates/designated_dashboard.html:1243-1268 (`window.saveAccomplishmentDetails`)
- **Category**: Implementation Integrity / Accessibility (status messaging)
- **Impact**: `const msg = document.getElementById('accomplishmentSaveMsg')` is declared at line 1264, but `msg` is referenced earlier, at line 1255, inside the early-return branch that fires when an Efficiency ("Client Satisfaction") target's rating is missing. Because `const` is temporal-dead-zoned for the whole function body, this throws `Cannot access 'msg' before initialization` the moment a Designated/chair user tries to save or submit accomplishment details for a Client-Satisfaction-type target without picking a rating. The intended inline message ("Please select a Client Satisfaction Rating.") never renders — the click silently does nothing from the user's perspective, and the WCAG 4.1.3-relevant status update is never delivered.
- **WCAG**: 4.1.3 Status Messages (AA)
- **Recommendation**: Move `const msg = document.getElementById('accomplishmentSaveMsg');` to the top of the function, before the `effRow` validation branch that references it.
- **Suggested command**: `$impeccable harden`

**[P2] Icon-only delete/trash buttons have no accessible name** — ✅ Fixed
- **Location**: app/templates/designated_dashboard.html:976-978 (custom-target row, injected via JS); also present in the pre-rendered evidence list item at line 1452 (which at least carries a `title` attribute, a partial mitigation)
- **Category**: Accessibility
- **Impact**: The custom-target row's delete button (`<button ... onclick="this.closest('tr').remove()..."><i class="ti ti-trash"></i></button>`) has no text, `aria-label`, or `title` — screen reader users hear only "button" with no indication of what it does or which row it removes.
- **WCAG**: 4.1.2 Name, Role, Value (A); 1.1.1 (A)
- **Recommendation**: Add `aria-label="Remove this custom target"` to the JS-generated button (and standardize the pattern already partially used at line 1452 across all icon-only actions in this file).
- **Suggested command**: `$impeccable harden`

**[P2] "Target Type" `<select>` has an unassociated label** — ✅ Fixed
- **Location**: app/templates/designated_dashboard.html:499-500
- **Category**: Accessibility
- **Impact**: `<label class="form-label small fw-bold">Target Type</label>` has no `for` attribute, and the following `<select class="form-select" name="Indicator" required>` has no `id`. Every other field in this same modal (`targetDescription`, `targetQuantity`, `targetDurationValue`) is correctly paired — this is the one inconsistent control, so a screen reader announces only "combo box, Support Functions" with no field name.
- **WCAG**: 1.3.1 Info and Relationships (A), 4.1.2 (A)
- **Recommendation**: Add `id="targetType"` to the select and `for="targetType"` to the label.
- **Suggested command**: `$impeccable harden`

**[P2] Three Bootstrap modals lack `aria-labelledby`, and one lacks `aria-hidden`** — ✅ Fixed
- **Location**: app/templates/designated_dashboard.html:489 (`#addTargetModal` — missing both `aria-hidden` and `aria-labelledby`), 1585 (`#evidenceGatheringModal` — has `aria-hidden`, missing `aria-labelledby`), 1772 (`#customConfirmModal` — has `aria-hidden`, missing `aria-labelledby`)
- **Category**: Accessibility
- **Impact**: None of the three dialogs point `aria-labelledby` at their visible `<h5 class="modal-title">`, so assistive tech announces the dialog as unnamed ("dialog") rather than by its actual purpose ("Add Custom Target", "Evidence Gathering Checklist"). `#addTargetModal` additionally omits `aria-hidden`, inconsistent with the other two in the same file.
- **WCAG**: 4.1.2 Name, Role, Value (A)
- **Recommendation**: Add `aria-labelledby` pointing to each modal's title `id`, and add `aria-hidden="true"` to `#addTargetModal` for consistency with the other two dialogs.
- **Suggested command**: `$impeccable harden`

**[P2] Repeated touch targets well under minimum size** — ✅ Fixed
- **Location**: app/templates/designated_dashboard.html:228, 327, 964 (`style="transform: scale(1.3);"` on checkboxes — Bootstrap default ~16px scaled to ~21px); :976-978 and :1452 (icon-only trash buttons with `p-0 border-0`, hit area close to the glyph's own ~16-20px box)
- **Category**: Responsive Design
- **Impact**: Both the target-selection checkboxes and the evidence-delete buttons are meaningfully below the 24×24px (WCAG 2.2 AA) / 44×44px (AAA) target size on any input method, including touch. This repeats across three separate flows in the file (target selection, custom-target removal, evidence removal).
- **WCAG**: 2.5.8 Target Size Minimum (AA, WCAG 2.2)
- **Recommendation**: Wrap icon-only buttons in a min 32-44px padded hit area; increase checkbox size via a real CSS rule (`width/height`) rather than a visual-only `transform: scale()`, which does not enlarge the actual hit box in most browsers.
- **Suggested command**: `$impeccable harden`

**[P2] Local `<style>` block is fully dead — its rules are already applied (and beaten) by `base.html`** — ✅ Fixed (I had wrongly told a later fix pass this was already done — caught and fixed on review: block deleted)
- **Location**: app/templates/designated_dashboard.html:550-564; duplicated/overridden by app/templates/base.html:626-630 and 684-691
- **Category**: Implementation Integrity / Theming
- **Impact**: `.strategic-checkbox:checked { background-color: var(--c-accent); border-color: var(--c-accent); }` targets an element that also carries `.form-check-input` (line 326), and `base.html:684` already defines `.form-check-input:checked { background-color: var(--c-accent) !important; border-color: var(--c-accent) !important; }`. The `!important` in the shell rule means this file's local override can never win — it's dead weight. Same story for `.form-control-sm:focus` here vs. `base.html:626`'s `.form-control:focus, .form-select:focus { ... !important; }`. This is exactly the "local `<style>` duplicating base.html" pattern the audit was asked to check for, confirmed with matching tokens on both sides.
- **Recommendation**: Delete the entire local `<style>` block (lines 550-564) — it has no effect.
- **Suggested command**: `$impeccable distill`

**[P2] Dead `categories` variable and orphaned legacy `bi-` icons** — ✅ Fixed
- **Location**: app/templates/designated_dashboard.html:190-196
- **Category**: Implementation Integrity
- **Impact**: `{% set categories = [...] %}` defines two dict entries (`bi-star-fill`, `bi-tools`) but `categories` is never iterated or referenced anywhere else in the file (verified via full-file search — its only other appearance is an unrelated JS variable `custom_categories[]` at line 972). This is the only place `bi-` (legacy Bootstrap Icons) classes appear in this template at all — and they're unreachable. Functionally, this file's *live* icon usage is already 100% migrated to Tabler (`ti-`, 74 occurrences / 38 unique classes) — worth noting as a positive counter-fact to the shared-shell's "two icon libraries loaded simultaneously" finding, scoped to this file.
- **Recommendation**: Delete the unused `categories` namespace block.
- **Suggested command**: `$impeccable distill`

**[P3] Category-type detection duplicated with inconsistent string-matching styles**
- **Location**: app/templates/designated_dashboard.html:337 (`{% if 'Instruction' in target.category_name %}`, substring match) vs. :614-616 (`{% if target.category_name == 'A. Instructions' %}`, exact match) — same underlying question ("is this row an Instruction target?") answered two different ways in two different tables in the same file
- **Category**: Implementation Integrity
- **Impact**: Both happen to agree for the current category-name values, but the inconsistency is fragile: a future rename of the category label (e.g. dropping the "A. " prefix per CLAUDE.md's category-slug guidance) would silently break the exact-match branch while the substring branch kept working, producing a badge mismatch between the "My IPCR" table and the "Evidence Gathering" table for the same underlying target.
- **Recommendation**: Match on the stable `slug`/`is_admin_function` flag mentioned in CLAUDE.md rather than free-text `category_name`, and use one comparison style consistently.
- **Suggested command**: `$impeccable harden`

**[P3] Hand-rolled JS-string escaping in an inline `onclick` handler**
- **Location**: app/templates/designated_dashboard.html:642
- **Category**: Implementation Integrity
- **Impact**: `openEvidenceModal('{{ target.target_id }}', ..., '{{ target.indicator_description|replace('\'', '\\\'')|replace('"', '\\"') }}', ...)` manually escapes quotes but not backslashes. A faculty-authored custom-target description containing a literal backslash (e.g., copy-pasted Windows path text) would corrupt the resulting JS string literal, likely breaking the modal open call rather than causing an XSS issue (Jinja's autoescape still protects the HTML-attribute boundary).
- **Recommendation**: Pass data via `data-*` attributes read in JS, or `| tojson` into a `<script>`-embedded object, rather than string-interpolating into an inline event handler.
- **Suggested command**: `$impeccable harden`

**[P3] Hardcoded `rgba()` literals stand in for token-based tint backgrounds**
- **Location**: app/templates/designated_dashboard.html:152, 167, 182 (`rgba(63,125,88,0.06)`, `rgba(184,132,46,0.08)` x2), 225, 322 (`rgba(13,110,253,0.0x)`), 837 (`rgba(63,125,88,0.08)`), and JS-injected at 872/874 (`rgba(62,92,130,...)`)
- **Category**: Theming
- **Impact**: These are literal RGB triples approximating the success/warning/primary hues, used only for alert/row background tints. The file already has the right pattern available (`var(--c-accent-glow)`, used correctly at lines 245, 361, 562, 1589) but doesn't apply it to success/warning/primary. If the token values are ever adjusted for contrast or a real dark theme, these six-plus literals will silently drift out of sync with the badges/icons/text sitting on top of them.
- **Recommendation**: Define `--c-success-glow` / `--c-warning-glow` / `--c-primary-glow` alongside the existing `--c-accent-glow` in `base.html`'s token block, and swap these literals for the tokens.
- **Suggested command**: `$impeccable colorize`

### Patterns & Systemic Issues
- **Side-tab accent border** (detector-flagged, 6 instances in this file: lines 137, 152, 167, 182, 245, 361) — consistent with the shared-shell finding; not re-litigated here beyond confirming it's present and repeated within this single file, not a one-off.
- **Inline styles**: 101 `style="..."` attributes counted in this file — at the high end of the survey's 75-104-per-file range — the large majority are one-off layout tweaks (`border-radius`, `max-width`, table `width`) that don't map to any reusable token or utility class, rather than genuinely novel patterns worth promoting into `base.html`.
- **Column-header-only labeling on editable table cells**: the inline quantity/duration inputs in both target tables (e.g. lines 368-370, 383-393) rely entirely on the `<th>` text ("Target Qty", "Deadline") for meaning, with no per-row `aria-label`/`aria-describedby`. This is a common, generally-tolerated data-grid pattern rather than a hard failure, but it compounds with the other labeling gaps above.
- **Two independent `DOMContentLoaded` listeners** (lines 860 and 1541) doing unrelated setup — harmless but avoidable code-organization drift; low priority.

### Positive Findings
- Icon migration is effectively complete in this file: only 2 legacy `bi-` classes exist, and both sit inside completely unreachable template code (see the dead `categories` block above) — the active UI is 100% Tabler (`ti-`).
- Genuinely good empty-state coverage: "No Core Function targets assigned," "No custom or support targets added yet," and a JS-generated "No indicators available in this category" empty row all give clear next-step guidance rather than a blank table.
- The evidence-gathering flow has real loading/error states (`Loading submissions...` spinner, try/catch with a rendered error message on fetch failure) rather than silent failure.
- The evidence-upload and delete flows correctly gate on `HAS_FINAL_IPCR` / `EVIDENCE_SUBMITTED` (`applyEvidenceLock()`), consistently disabling every relevant control and swapping in an explanatory locked-state notice — a solid state-machine-aware implementation of the lock/finalize semantics described in CLAUDE.md.
- Form-level validation (`dpcrForm` submit handler) correctly scopes its quantity/deadline checks to only the currently-selected checkboxes and clears stale `is-invalid` styling on uncheck — avoids the common bug of validating hidden/irrelevant fields.

### Design-Taste-Frontend Note (scoped)
design-taste-frontend: out of scope (dashboard UI), consistent with shared shell finding.

### Recommended Actions (priority order)
1. **[P1] `$impeccable harden`**: Fix the `msg` temporal-dead-zone `ReferenceError` in `saveAccomplishmentDetails` (line ~1264) — this is a confirmed runtime bug that silently breaks validation feedback for Client-Satisfaction-rated targets.
2. **[P2] `$impeccable harden`**: Add accessible names to icon-only delete buttons, fix the unassociated Target Type label, add `aria-labelledby`/`aria-hidden` consistently across the three modals, and enlarge touch targets on checkboxes and icon-only buttons.
3. **[P2] `$impeccable distill`**: Delete the dead local `<style>` block (lines 550-564, fully overridden by `base.html`) and the unused `categories` namespace (lines 190-196).
4. **[P3] `$impeccable colorize`**: Replace the hardcoded `rgba()` tint literals with proper `--c-success-glow`/`--c-warning-glow` tokens alongside the existing `--c-accent-glow` pattern.
5. **[P3] `$impeccable harden`**: Consolidate the duplicated category-matching logic onto a stable slug/flag, and replace the hand-rolled `onclick` string-escaping with `data-*` attributes.

> You can ask me to run these one at a time, all at once, or in any order you prefer.
> Re-run `$impeccable audit` after fixes to see your score improve.
## 4. Program Chair Dashboard — `app/templates/prog_chair_dashboard.html`

**Impeccable Audit Health Score: 13/20 — Acceptable (significant work needed)**

| # | Dimension | Score | Key Finding |
|---|-----------|-------|-------------|
| 1 | Accessibility | 2/4 | 14 form inputs in this file, only 2 `<label>` elements — quantity/deadline/description inputs in both Phase 1 tables and the JS-built review modal have no programmatic accessible name |
| 2 | Performance | 3/4 | Evidence images use `loading="lazy"`; minor cost from full-page `location.reload()` after single-item AJAX actions, but section state survives via localStorage |
| 3 | Theming | 3/4 | Tokens (`var(--c-accent/success/warning/border/surface-alt)`) used pervasively and correctly; a handful of inline badges hand-duplicate token RGB values with mismatched alpha instead of reusing the shared `.badge.bg-*` classes |
| 4 | Responsive Design | 3/4 | Every one of the file's 9 tables is wrapped in `.table-responsive` (no page-level horizontal scroll); only one local `@media` rule; dense 5-6 column tables degrade to horizontal scroll rather than reflowing |
| 5 | Implementation Integrity | 2/4 | Several verified issues: file-specific unescaped-innerHTML XSS-shaped pattern repeated across ~6 functions, skipped heading levels, un-paginated data tables |

### Implementation Integrity Verdict
**Pass, with real defects.** This is a coherent, product-specific implementation — the RET-vs-Chair review-lane split, the disabled/awaiting-approval states, and the empty-state copy all reflect actual domain rules from the cascade (not generic boilerplate). The detector's three findings (side-tab card-header accents at lines 155/240, border-top-on-rounded-card at line 1583) verify as a *consistent, intentional* status-color vocabulary (info/warning/success/accent mapped to pending/warning/approved/evidence) reused identically in both server-rendered and JS-rendered tables — lower-severity than a one-off cosmetic slip, though still worth simplifying per the shared shell finding. The more consequential integrity issue found by reading the file directly: nearly every JS function that populates a table (`populateModal`, `populateLockedModal`, `openFacultyEvidenceVerificationModal`, `openEvidenceViewer`) builds markup via unescaped template-literal `innerHTML`, injecting server/user-authored strings (custom target descriptions, remarks, evidence filenames, supervisor comments, faculty names) with no escaping step — a pattern distinct from (and in addition to) the already-documented shared `showCustomAlert()` issue, since these are this file's own locally-defined functions.

### Findings

**[P1] Unescaped innerHTML construction across this file's own JS (XSS-shaped risk)** — ✅ Fixed (added `escapeHtml()` helper, applied at all flagged sites)
- **Location**: `populateModal` (line 1175, `${item.indicator_description}`), `populateLockedModal` (line 1051), `openFacultyEvidenceVerificationModal` (lines 1856-1857, 1855), `openEvidenceViewer` (lines 1897 `alt="${fileName}"`, 1921 `${ev.supervisor_comment}`, 1928 `${fileName}`), and the locally-defined `showCustomConfirm` (line 1418 `.innerHTML = mainText`) invoked with an interpolated faculty name at lines 2061-2064
- **Category**: Implementation Integrity / Security
- **Impact**: `indicator_description` includes faculty-authored "Custom Target Items" text, `item_remarks`/`supervisor_comment` are free-text fields, and evidence `fileName` derives from an uploaded file's original name — any of these containing `<`/`"`/`onerror=` etc. renders live in the Program Chair's session with no escaping, distinct from the already-documented `showCustomAlert()` shell issue since these are locally defined in this template
- **WCAG**: N/A (security, not accessibility)
- **Recommendation**: Route all interpolated dynamic text through `textContent` assignment or a shared escape helper before insertion; reserve raw `innerHTML` for template scaffolding you control
- **Suggested command**: `$impeccable harden`

**[P1] Table/form inputs lack accessible names** — ✅ Fixed
- **Location**: Phase 1 allocation tables — `assigned_quantities` inputs (lines 191-197, 276-282), `target_duration_values` inputs (lines 201-205, 286-290), `custom_descriptions` textareas (lines 216-219, 301-304); review modal's JS-built `reviewed-qty-input`/`item-remarks-input` (lines 1182-1199)
- **Category**: Accessibility
- **Impact**: Screen reader users navigating by form control get an unlabeled spinbutton/textbox with no indication it's "Assigned Per Faculty," "Deadline," or "IPCR Target Description" — the association exists only visually via the `<th>` column header
- **WCAG**: 1.3.1 Info and Relationships (A), 4.1.2 Name, Role, Value (A)
- **Recommendation**: Add `aria-label` (e.g. `aria-label="Assigned per faculty for {{ ind.indicator_description }}"`) to each bare input, or `aria-labelledby` pointing at the column header cell
- **Suggested command**: `$impeccable harden`

**[P2] Skipped heading levels throughout the page**
- **Location**: e.g. `<h2>Program Chair Dashboard</h2>` (line 61) followed directly by `<h6>Active Faculty</h6>` (line 75) inside the same KPI card row; this h2→h6 jump (no h3/h4 anywhere) repeats across every section (9× `<h2>`, 14× `<h5>`, 9× `<h6>`, zero `<h3>`/`<h4>`)
- **Category**: Accessibility
- **Impact**: Assistive-tech users who navigate by heading outline get a document structure that jumps two levels at a time, obscuring the actual section/subsection relationship
- **WCAG**: 1.3.1 Info and Relationships (A)
- **Recommendation**: Insert intermediate `<h3>`/`<h4>` levels (or use `role="heading" aria-level`) so the outline steps down one level at a time
- **Suggested command**: `$impeccable clarify`

**[P2] Validation errors are visual-only — no `aria-invalid`/`aria-describedby`** — ✅ Fixed
- **Location**: `overallRemarks` textarea + `.invalid-feedback` div (lines 601-609), toggled via `classList.add('is-invalid')` at line 1455; Phase 1 save validation toggles `.is-invalid`/`.border-danger` on deadline/unit/description fields (lines 846-875) with no ARIA wiring
- **Category**: Accessibility
- **Impact**: Sighted users see a red border when a required remark or deadline is missing; screen reader users get no notification that the field failed validation or why
- **WCAG**: 3.3.1 Error Identification (A), 4.1.2 (A)
- **Recommendation**: When adding `.is-invalid`, also set `aria-invalid="true"` and `aria-describedby` pointing at the associated feedback text
- **Suggested command**: `$impeccable harden`

**[P2] No pagination, search, or filter on any of this dashboard's five data tables**
- **Location**: `#commitmentsTable` (pending drafts, lines 362-446), `#lockedTable` (locked drafts, lines 471-514), evidence-pending faculty table (lines 1530-1577), approved-evidence faculty table (lines 1589-1646), and the JS-built target-review tables inside modals
- **Category**: Responsive Design / Implementation Integrity
- **Impact**: Per CLAUDE.md this role distributes quotas and reviews submissions for an entire specialization/program — as faculty count grows past a screenful, chairs must scroll a single flat table with no way to search by name, sort, or filter by status
- **Recommendation**: Add a lightweight client-side search box and status filter (data volumes here don't yet require server-side pagination, but a lookup box is cheap and high-value)
- **Suggested command**: `$impeccable layout`

**[P2] Inline hand-rolled badge styling diverges from the shared token classes it duplicates** — ✅ Fixed
- **Location**: Status badges at lines 389-410 (`style="background-color: rgba(176,69,61,0.08) !important; ... color: var(--c-danger) !important;"` and the warning variant repeated 3×)
- **Category**: Theming
- **Impact**: `base.html` already defines `.badge.bg-danger { background: rgba(176,69,61,0.1); color: #8F372F }` and `.badge.bg-warning { background: rgba(184,132,46,0.12); color: #8F6421 }` (lines 535-536) — these inline styles duplicate the same RGB triplets by hand at slightly different alpha values (0.08 vs 0.1) and a different text color (`var(--c-danger)` vs the class's `#8F372F`), so these specific badges render subtly different from every other danger/warning badge in the same app
- **Recommendation**: Delete the inline `style` blocks and use `class="badge bg-danger"` / `class="badge bg-warning"` like the rest of the file already does elsewhere
- **Suggested command**: `$impeccable polish`

**[P2] Touch targets consistently below 44×44px in action-dense rows** — ✅ Verified: the two spots with adjacent small buttons already have `gap-2` spacing; no change needed
- **Location**: `base.html:608` (`.btn-sm { padding: 5px 12px; font-size: 12px }` → ~26-28px tall) exercised heavily in this file's row actions (lines 428-435, 504-509, 1562-1565, 1620-1632) and the evidence-viewer's adjacent Return/Approve buttons (lines 1938-1945)
- **Category**: Responsive Design
- **Impact**: On a tablet (a plausible device for a department chair reviewing evidence), tightly-packed small buttons like "Return"/"Approve" sitting side by side are easy to mis-tap
- **WCAG**: 2.5.5 Target Size (AAA, but worth flagging given how often this file relies on `.btn-sm` for primary actions)
- **Recommendation**: Bump row-action buttons to standard `.btn` size or add horizontal `gap` ≥ 8px between adjacent small buttons
- **Suggested command**: `$impeccable layout`

**[P2] Fragile inline `onclick` string-escaping instead of `data-*` attributes**
- **Location**: Lines 1563, 1621, 1630 — `onclick="openFacultyEvidenceVerificationModal({{ fac.emp_id }}, '{{ fac.first_name|replace('\'', '\\\'') }} {{ fac.last_name|replace('\'', '\\\'') }}')"`
- **Category**: Implementation Integrity
- **Impact**: Manually escaping only the single-quote character breaks on any name containing a backslash, and couples markup generation to hand-written JS-string construction — a maintenance trap most likely to surface as a broken onclick handler (not a rendering error) the next time someone edits a name field
- **Recommendation**: Replace with `data-emp-id`/`data-name` attributes read by the click handler, avoiding string interpolation into JS source entirely
- **Suggested command**: `$impeccable harden`

**[P3] Inconsistent error UX: native `alert()` alongside a purpose-built custom modal system**
- **Location**: `loadReviewModal`/`loadViewLockedModal` (lines 965, 987, 993), `openFacultyEvidenceVerificationModal` catch (line 1870), `returnEvidence` (line 1963), `verifyEvidence` (lines 2016, 2047), `submitFacultyEvidenceToDean` (line 2080)
- **Category**: Implementation Integrity
- **Impact**: This file already built `showCustomConfirm` for a polished confirmation UX, yet every network/error path falls back to a blocking native `alert()` — jarring and inconsistent within the same page
- **Recommendation**: Route these through the existing custom-modal/toast pattern instead of `alert()`
- **Suggested command**: `$impeccable polish`

### Patterns & Systemic Issues
- Unescaped `innerHTML` template-literal construction is not a one-off — it's the standard way every dynamic table in this file is built (4+ functions), so a single shared escaping helper would fix the whole class of risk at once.
- Heading levels skip by two throughout (h2 straight to h5/h6) in every section — a page-wide outline problem, not isolated to one card.
- None of this dashboard's five primary tables have search/filter/pagination — a dashboard-wide gap that will bite as faculty rosters grow, consistent with the "large tables, no filtering" risk called out for this role's context.
- Small pockets of inline `style="..."` (55 total in this file — within but at the low end of the 75-104/file survey range) exist specifically where the author reached for a one-off color effect that a token-driven class already covers elsewhere in the same file, suggesting inconsistent awareness of what `base.html` already provides rather than a deliberate one-off need.

### Positive Findings
- Icon-font migration is actually *finished* in this file: 90 `ti-` (Tabler) icons, 0 legacy `bi-` icons — unlike the shell-level mixed-library state, this surface is clean.
- Every table (9/9) is wrapped in `.table-responsive`, so none of this file's tables cause page-level horizontal scroll on narrow viewports.
- Evidence images use `loading="lazy"`.
- Empty states are handled well and consistently: icon + bold heading + contextual copy for every major table (e.g. "No Draft IPCRs Submitted," "No Locked IPCRs Yet," "No pending faculty evidence submissions found").
- The RET-vs-Program-Chair review-lane split is implemented faithfully to the actual domain rule (research/extension items are read-only to the Chair, with a clear "Awaiting RET Chair Approval" banner and a disabled Approve button carrying an explanatory `title`) — genuine product logic, not boilerplate.
- Design tokens (`var(--c-accent/success/warning/border/surface-alt)`) are the dominant color mechanism throughout modal headers, card accents, and category banners — theming discipline is generally good even where a few inline exceptions slipped through.

### Design-Taste-Frontend Note (scoped)
design-taste-frontend: out of scope (dashboard UI), consistent with shared shell finding. Nothing in this file's visual layer (status-color card accents, badge system, modal structure) reads as screamingly generic/AI-slop beyond the already-noted "side-tab" pattern, which here is used as a deliberate, consistent status-color vocabulary rather than a cosmetic default.

### Recommended Actions (priority order)
1. **[P1] `$impeccable harden`**: Escape all dynamic strings (indicator descriptions, remarks, evidence filenames, faculty names) before `innerHTML` insertion in `populateModal`, `populateLockedModal`, `openFacultyEvidenceVerificationModal`, `openEvidenceViewer`, and `showCustomConfirm`.
2. **[P1] `$impeccable harden`**: Add accessible names (`aria-label`/`aria-labelledby`) to every bare input in the Phase 1 allocation tables and the review-item modal, and wire `aria-invalid`/`aria-describedby` into the existing `.is-invalid` validation states.
3. **[P2] `$impeccable clarify`**: Fix the repeated h2→h6 heading-level skip across all sections, and consolidate error handling onto the existing custom-modal pattern instead of native `alert()`.
4. **[P2] `$impeccable layout`**: Add search/filter to the five un-paginated data tables, and increase touch-target size/spacing on the dense row-action buttons (`.btn-sm` clusters in the evidence viewer and commitment tables).
5. **[P2] `$impeccable harden`**: Replace the manually quote-escaped inline `onclick` handlers (lines 1563, 1621, 1630) with `data-*` attribute bindings.
6. **[P3] `$impeccable polish`**: Reconcile the hand-rolled inline rgba badge styles (lines 389-410) with the existing `.badge.bg-warning`/`.badge.bg-danger` token classes in `base.html`, then do a final consistency pass once the above land.
## 5. RET Chair Dashboard — `app/templates/ret_chair_dashboard.html`

**Impeccable Audit Health Score: 11/20 — Acceptable (significant work needed)**

| # | Dimension | Score | Key Finding |
|---|-----------|-------|-------------|
| 1 | Accessibility | 1/4 | 6 of 7 modals in this file have no `aria-labelledby`, and ~19 of 25 form inputs (dynamically built via JS) have no label of any kind |
| 2 | Performance | 3/4 | No lazy-loading gaps, no layout thrash; minor full-tbody re-renders and an undebounced keyup filter |
| 3 | Theming | 3/4 | Consistent, correct token usage throughout (no hardcoded hex found); one token-type misuse (`--c-text` as a background) |
| 4 | Responsive Design | 2/4 | Tables correctly wrapped in `.table-responsive`; but 6-7 column tables with no mobile-condensed alternative, and pervasive `btn-sm` touch targets |
| 5 | Implementation Integrity | 2/4 | Coherent, product-specific content, but repeated shortcuts: inconsistent XSS escaping, 4 different confirm-dialog patterns, undocumented destructive save, leftover debug logging |

### Implementation Integrity Verdict
**Pass, with reservations.** The file is genuinely RET-Chair-specific (rank menus, research/extension quotas, evidence verification) — not generic or interchangeable with an unrelated product. But it shows the same feature built multiple ways at different points in the file: two escaping strategies for user-supplied text in `innerHTML`, and four separate confirmation-dialog implementations doing the same job. That's drift within a single file, not just isolated polish gaps.

### Findings

**[P1] Six of seven modals in this file are missing `aria-labelledby`** — ✅ Fixed
- **Location**: `app/templates/ret_chair_dashboard.html:330` (`assignmentEditorModal`), `:910` (`confirmExtDistModal`), `:1900` (`customRetConfirmModal`), `:2060` (`retFacultyEvidenceVerificationModal`), `:2407` (`evidenceViewerModal`), `:2424` (`returnEvidenceReasonModal`)
- **Category**: Accessibility
- **Impact**: Screen reader users get no announced name when any of these dialogs opens — only `reviewRetModal` (line 1139) does this correctly, via `aria-labelledby="reviewRetModalLabel"`. The pattern already exists in the same file; it just wasn't applied consistently.
- **WCAG**: 4.1.2 Name, Role, Value (A)
- **Recommendation**: Add `aria-labelledby` pointing at each modal's `.modal-title` id (mirroring the one modal that already does this correctly).
- **Suggested command**: `$impeccable harden`

**[P1] Dynamically-generated form inputs have no accessible label** — ✅ Fixed
- **Location**: `app/templates/ret_chair_dashboard.html:181-206` (assignment editor qty/description/duration inputs, built in `openAssignmentEditor()`), `:1613-1625` (reviewed-quantity and remarks inputs in `populateRetReviewItems()`)
- **Category**: Accessibility
- **Impact**: Roughly 19 of the file's 25 `<input>` elements are assembled client-side with only a `placeholder` — never a `<label>` or `aria-label`. Placeholder text disappears on focus/input and isn't reliably announced, so a screen reader user reviewing or editing a faculty member's RET commitment has no idea what a given number field represents.
- **WCAG**: 3.3.2 Labels or Instructions (A), 4.1.2 Name, Role, Value (A)
- **Recommendation**: Add `aria-label` (e.g. `aria-label="Reviewed quantity for ${item.indicator_description}"`) to each JS-generated input, since visible `<label for>` wiring is awkward for templated rows.
- **Suggested command**: `$impeccable harden`

**[P1] Inconsistent escaping of user-supplied text into `innerHTML` — stored XSS risk** — ✅ Fixed (extended existing `escapeHtml()` to the RET review and evidence modal builders)
- **Location**: `app/templates/ret_chair_dashboard.html:126-129` and `:166,182` (escaped correctly via `escapeHtml()`) vs. `:1605-1665` (`populateRetReviewItems`) and `:2202-2213` (`openRetFacultyEvidenceVerificationModal`), where `item.indicator_description`, `displayCat`, and faculty names are interpolated into template literals and assigned via `innerHTML`/`.value` with no escaping
- **Category**: Implementation Integrity (Security)
- **Impact**: This is separate from base.html's documented `showCustomAlert()` XSS issue — it's a second, file-local instance of the same class of bug, and it's applied *inconsistently* even within this one file (one code path escapes, two don't). Indicator descriptions and remarks are admin-authored today, but the pattern is copy-pasted without the safeguard already present two functions away.
- **Recommendation**: Reuse the existing `escapeHtml()` helper (already defined at line 126) in `populateRetReviewItems` and the evidence modal's row-building code.
- **Suggested command**: `$impeccable harden`

**[P1] "Save Menu Rules" gives no warning that saving deletes and rewrites the rank's existing rule** — ✅ Fixed (inline warning banner + confirm dialog naming the selected rank)
- **Location**: `app/templates/ret_chair_dashboard.html:660-768` (form and "Save Menu Rules" button at line 763)
- **Category**: Implementation Integrity / UX copy
- **Impact**: Per project docs, RET rank rules are deleted-and-rewritten on save — a one-way operation. This form gives zero indication of that. Contrast with the Extension Distribution flow just below it (lines 838-928), which explicitly states "This is a one-time action and locks once distributed" both inline and in a dedicated confirmation modal. A chair editing one field of an existing rank's rule has no cue that they're replacing the whole rule, and no confirmation step at all (unlike the Delete button at line 807, which does use `confirm()`).
- **Recommendation**: Add inline warning text near the Save button when editing an existing rank (mirroring the Extension Distribution pattern), and/or a lightweight confirm step before submit.
- **Suggested command**: `$impeccable clarify`

**[P2] Heading hierarchy skips h3 and h4 throughout the file**
- **Location**: Representative: `app/templates/ret_chair_dashboard.html:68` (`<h2>`) directly followed by `:374` (`<h5>`) with no `<h3>`/`<h4>` in between; pattern repeats at every section (10× `<h2>`, 16× `<h5>`, 12× `<h6>`, zero `<h3>`/`<h4>`)
- **Category**: Accessibility
- **Impact**: Screen reader users navigating by heading level get a broken outline — every section jumps two or three levels. This is consistent enough (every single section) to be a structural pattern, not a one-off typo.
- **WCAG**: 1.3.1 Info and Relationships (A), 2.4.6 Headings and Labels (AA)
- **Recommendation**: Promote section/card headers to `<h3>` and sub-groupings to `<h4>`, reserving `<h5>`/`<h6>` for genuinely nested content.
- **Suggested command**: `$impeccable harden`

**[P2] Four different confirmation-dialog implementations coexist in this one file**
- **Location**: native `confirm()` at `app/templates/ret_chair_dashboard.html:807` (delete rule); `showCustomRetConfirm()` at `:1838-1869` + modal at `:1900-1929`; `showConfirmExtDistModal()` at `:930-987` + modal at `:910-928`; `returnEvidenceReasonModal` flow at `:2303-2330` + `:2424-2442`
- **Category**: Implementation Integrity
- **Impact**: Three separate bespoke "are you sure" modal components were built instead of reusing one, plus a plain browser `confirm()` for the fourth case. Visually and behaviorally inconsistent for the same job, and triples the maintenance surface for a single UI pattern.
- **Recommendation**: Consolidate into one reusable confirm-modal component/function; retire the raw `confirm()` call to match.
- **Suggested command**: `$impeccable harden`

**[P2] No search, filter, or pagination on most long lists**
- **Location**: `app/templates/ret_chair_dashboard.html:772-822` (Active Rules table), `:571-629` (per-indicator faculty distribution tables), `:1011-1075` and `:1090-1132` (Commitment Verification / Approved RET Choices), `:1950-1999` and `:2011-2053` (Evidence Verification tables). Only the Target Assignment faculty table (`:462-463`, `filterAssignFacultyTable()`) has client-side search.
- **Category**: Implementation Integrity / Usability
- **Impact**: Every other long list in a dashboard whose whole purpose is to manage rank rules and review dozens of faculty submissions has no way to narrow results — a chair with a large department has to scroll through everything.
- **Recommendation**: Extend the existing `filterAssignFacultyTable()` pattern (already built once in this file) to the other faculty-listing tables.
- **Suggested command**: `$impeccable layout`

**[P2] Token misuse: text color token used as a decorative background** — ✅ Fixed (new `--evidence-bg` token, same visual color)
- **Location**: `app/templates/ret_chair_dashboard.html:2501` — `.evidence-portrait-container { background: var(--c-text); ... }`
- **Category**: Theming
- **Impact**: `--c-text` (#2B2822) is defined in base.html as the body text color token, not a surface/background token. Using it as a background works today only because it happens to be dark, but it will silently break if the text color token is ever retuned for contrast or theme reasons — a hidden coupling between two unrelated tokens.
- **Recommendation**: Introduce or reuse a dedicated dark-surface token (or a local `--evidence-bg` variable) instead of repurposing `--c-text`.
- **Suggested command**: `$impeccable polish`

**[P2] Leftover debug logging shipped in production JS** — ✅ Fixed (removed all 9 `[DEBUG]` statements; kept and retagged the one legitimate `.catch()` error logger)
- **Location**: `app/templates/ret_chair_dashboard.html:1418`, `:1420-1429`, `:1470`, `:1483`, `:1487`, `:1491`, `:1502` — nine `console.log`/`console.error` calls, several explicitly tagged `"[DEBUG] ..."`, including one that fires unconditionally on every page load (`"[DEBUG] RET script loaded."`)
- **Category**: Implementation Integrity
- **Impact**: Cosmetic and low-risk, but it's the kind of thing that should have been removed before merge; it also logs internal `empId` values to the console.
- **Recommendation**: Strip the `[DEBUG]` console statements now that the RET review modal wiring is verified working.
- **Suggested command**: `$impeccable polish`

**[P3] 22 `!important` declarations fighting Bootstrap specificity**
- **Location**: e.g. `app/templates/ret_chair_dashboard.html:56-62` (disabled-button override block), `:373`, `:404` (card-header side-tab borders)
- **Category**: Theming / Implementation Integrity
- **Impact**: Functions correctly today but is brittle — every one of these is a sign the cascade is being fought rather than composed. The two at lines 373/404 also duplicate, via inline `style`, a visual effect (colored left-accent) that base.html already expresses reusably through `.border-start.border-info`/`.border-warning` utility classes (used correctly elsewhere in this same file, e.g. line 74) — same motif, two different implementations in one file.
- **Recommendation**: Replace the inline `border-left: ... !important` pairs with the existing `.border-start.border-*` utility classes already used elsewhere in this file.
- **Suggested command**: `$impeccable polish`

**[P3] Small touch targets on primary review actions**
- **Location**: `btn btn-sm` used for nearly every action button, e.g. `app/templates/ret_chair_dashboard.html:485-491`, `:802-811`, `:1116-1120`, `:1984-1987`, `:2283-2290`
- **Category**: Responsive Design
- **Impact**: Approve/Return/Assign/Delete are the core verbs of this dashboard's job, and they're all rendered at the smallest Bootstrap button size — tight on a tablet, which is a plausible device for a department chair reviewing evidence between meetings.
- **Recommendation**: Bump primary decision actions (Approve, Return, Assign) to default button size; reserve `btn-sm` for secondary/repeated row actions.
- **Suggested command**: `$impeccable adapt`

**[P3] Dense 6-7 column tables rely solely on horizontal scroll on narrow viewports**
- **Location**: `app/templates/ret_chair_dashboard.html:1011-1020` (6 columns), `:1950-1961` and `:2011-2021` (7 columns each)
- **Category**: Responsive Design
- **Impact**: `.table-responsive` correctly contains the overflow (no page-level horizontal scroll, which is good), but reading a 7-column table by side-scrolling on a phone is still a genuinely worse experience than a stacked-card layout would be.
- **Recommendation**: Consider a stacked/card view below a breakpoint for the two Evidence Verification tables specifically, since they're the most likely to be checked on the go.
- **Suggested command**: `$impeccable adapt`

### Patterns & Systemic Issues
- **Escaping applied inconsistently, not absently.** The file has the right tool (`escapeHtml()`) and uses it in one feature (assignment editor) but not in two others built later (RET review modal, evidence modal) — a sign of copy-paste-without-the-safety-net rather than a blanket oversight.
- **Confirmation UX reinvented four times** in a single file (native `confirm()`, and three separately coded custom modals) instead of once, reusably.
- **Side-tab accent pattern**: detector-confirmed at lines 373 and 404 (`border-left: 3px solid var(--c-accent/--c-warning) !important` on `.card-header`). This is the same AI-UI tell already documented at the shell level — not re-scored here — but worth noting it appears twice in this file specifically, and via a different mechanism (inline style) than the equivalent, already-established `.border-start.border-*` utility used elsewhere in the same file.
- **Icon migration is actually complete in this file**: 89 `ti-` (Tabler) icon classes, 0 legacy `bi-` classes — unlike the shell-level "two icon libraries loaded simultaneously" finding, this specific dashboard shows no leftover Bootstrap Icons usage.
- **Inline styles**: 59 `style="..."` occurrences — lower than the 75-104 range the wider survey found elsewhere, but still a meaningful bypass of the token/utility system, concentrated in one-off pixel widths (`width: 80px`, `240px`, `90px`) and the `!important` overrides above.

### Positive Findings
- **Comprehensive empty-state coverage.** Every list/table in the file — cascaded targets, menu rules, target assignment, commitment verification, evidence verification — has a real, purpose-written "no data yet" message with an icon, not a bare empty table.
- **Loading states are handled properly** for all three async-fetched modals (assignment editor, RET review, evidence viewer), each with a spinner and descriptive text rather than a blank flash.
- **Consistent, correct design-token usage.** No hardcoded hex colors were found anywhere in this file's markup or its two `<style>` blocks — everything routes through `var(--c-*)`, including the less-common `--c-indigo`, which is a legitimately defined base.html token (verified), not an invented one-off.
- **The Extension Distribution flow is a strong example of communicating irreversible action** — inline warning text plus a confirmation modal that restates the consequence in plain language. This is the pattern the Save Menu Rules flow (P1 finding above) should be following.
- **Full-screen slide-up evidence viewer** (lines 2407-2442, 2454-2540) with its own mobile breakpoint shows real thought given to the specific task of reviewing PDF/image evidence on a small screen.

### Design-Taste-Frontend Note (scoped)
Out of scope (dashboard UI), consistent with the shared shell finding. Nothing in this file rises to a screaming generic-AI-slop exception beyond the already-documented side-tab pattern noted above.

### Recommended Actions (priority order)
1. **[P1] `$impeccable harden`**: Add `aria-labelledby` to the six unlabeled modals, `aria-label` to the ~19 unlabeled dynamically-generated inputs, and extend `escapeHtml()` to the RET review and evidence modals' `innerHTML` building.
2. **[P1] `$impeccable clarify`**: Add explicit destructive-action warning copy to the "Save Menu Rules" flow, matching the existing Extension Distribution pattern.
3. **[P2] `$impeccable harden`**: Fix heading hierarchy (promote to h3/h4), consolidate the four confirmation-dialog implementations into one reusable component, and strip the leftover `[DEBUG]` console logging.
4. **[P2] `$impeccable layout`**: Extend the existing faculty-search pattern to the other long, unfiltered tables (Active Rules, per-indicator distribution, Evidence Verification lists).
5. **[P3] `$impeccable adapt`**: Bump primary decision-action buttons off `btn-sm`, and consider a stacked layout for the two widest Evidence Verification tables on narrow viewports.
6. **[P3] `$impeccable polish`**: Fix the `--c-text`-as-background token misuse, and replace the inline `border-left !important` side-tab overrides with the file's own existing `.border-start.border-*` utility classes.
## 6. Dean Dashboard — `app/templates/dean_dashboard.html`

**Impeccable Audit Health Score: 11/20 — Acceptable (significant work needed)**

| # | Dimension | Score | Key Finding |
|---|-----------|-------|-------------|
| 1 | Accessibility | 2/4 | 9 of this file's 10 modals have no `aria-labelledby`; zero `<th scope>` across every data table; dynamically-injected form inputs (quota grid, review editor, assignment editor) have no labels at all |
| 2 | Performance | 2/4 | All six dashboard-section tabs (including a dead one) render into the DOM on every load regardless of which tab is active; every AJAX action ends in a full `location.reload()` |
| 3 | Theming | 3/4 | 74 of 75 inline styles correctly reference `var(--c-*)` tokens; one `var(--bs-secondary)` and 3 raw `rgba()` values slip through |
| 4 | Responsive Design | 2/4 | Every table is correctly wrapped in `.table-responsive`, but the largest table (the quota-cascading matrix, one column per department) has no frozen label column, so entering values on mobile means scrolling blind |
| 5 | Implementation Integrity | 2/4 | Duplicate `id="confirmModalTitle"` silently breaks a confirmation dialog; free-text faculty/target data is interpolated into `innerHTML` unescaped in ~8 functions; a fully hardcoded mock section with a fake employee name is dead code with no sidebar entry point |

### Implementation Integrity Verdict
**Pass, with real defects.** The markup and JS are unmistakably product-specific — the Core Functions vs. Strategic Priorities & Support split, the `_key` vs `indicator_id` disambiguation for chairs who hold two rows on the same indicator, the RET/Chair vs. Dean evidence-review lane distinctions — this is not generic templated dashboard filler, and the inline code comments show real domain reasoning (e.g. lines 2147-2158, 2317-2323 explaining *why* row-keying had to change). That said, verified defects exist: a duplicate element ID that silently breaks a shared confirmation modal, several functions with near-total code duplication, unescaped interpolation of user-entered strings into `innerHTML`, and one entire dead section shipped with placeholder mock data.

### Findings

**[P1] Duplicate `id="confirmModalTitle"` breaks the shared confirmation dialog's title** — ✅ Fixed (I had wrongly told a later fix pass this was already done — caught and fixed on review: renamed `#customConfirmModal`'s title to `customConfirmModalTitle`)
- **Location**: `app/templates/dean_dashboard.html:674` (inside `#confirmDeanModal`) and `:2895` (inside `#customConfirmModal`)
- **Category**: Implementation Integrity
- **Impact**: `showCustomConfirm()` (lines 2845-2871) calls `document.getElementById('confirmModalTitle').textContent = title` to set the visible confirmation dialog's heading before Approve/Return-to-Faculty evidence actions (lines 1591-1618, 1620-1646). Because `getElementById` always resolves to the first matching ID in document order, this call updates the *hidden* `#confirmDeanModal` heading (line 674) instead of the actually-displayed `#customConfirmModal` heading (line 2895). The Dean sees the modal's static placeholder title text rather than "Approve IPCR?" / "Return to Faculty?" on two of the highest-stakes, most-clicked actions in this file.
- **WCAG**: Duplicate IDs also violate the "unique id" parsing requirement relied on by assistive tech's `id`-based references.
- **Recommendation**: Rename one of the two IDs (e.g. `customConfirmModalTitle`) and update both the markup and the four `getElementById` call sites that target it.
- **Suggested command**: `$impeccable harden`

**[P1] User-supplied text interpolated unescaped into `innerHTML` across ~8 render functions** — ✅ Fixed (added `escapeHtml()` helper, applied at all flagged sites)
- **Location**: e.g. `app/templates/dean_dashboard.html:1769-1770` (`t.indicator_description`, `t.actual_accomplishment`), `:1830` (`ev.supervisor_comment`), `:2438,2444,2514,2520` (`item.indicator_description`, `item.target_description` in `populateReviewItems`), `:2581,2609` (`ind.indicator_description` in `populateUnpickedItems`/`populateCollegeWideItems`)
- **Category**: Implementation Integrity / Security
- **Impact**: This is distinct from the already-documented `showCustomAlert()` XSS risk — these strings are genuine user-entered content: custom target descriptions typed by faculty/Dean, self-reported `actual_accomplishment` text, and supervisor rejection comments. None of it is HTML-escaped before being spliced into template literals assigned to `.innerHTML`. A faculty member (or a Program Chair/RET Chair, who submit similarly free-text fields) entering `<img src=x onerror=...>` in a custom target description would have it execute in the Dean's session the next time that draft is reviewed.
- **WCAG**: N/A (security, not a11y)
- **Recommendation**: Route all interpolated user text through a small `escapeHtml()` helper before insertion, or switch these blocks to `textContent`/DOM-node construction for the untrusted fields.
- **Suggested command**: `$impeccable harden`

**[P1] 9 of 10 modals in this file omit `aria-labelledby`** — ✅ Fixed
- **Location**: `#cascadeConfirmModal:213`, `#confirmDeanModal:669`, `#designatedAssignmentModal:816`, `#deanEvidenceModal:1415`, `#deanReturnEvidenceReasonModal:1444`, `#designatedEvidenceVerificationModal:1465`, `#designatedEvidenceViewerModal:1508`, `#designatedReturnEvidenceReasonModal:1524`, `#customConfirmModal:2887` — only `#reviewDeanModal:497` does this correctly (`aria-labelledby="reviewDeanModalLabel"`)
- **Category**: Accessibility
- **Impact**: Screen reader users get no programmatic announcement of what each modal is for when it opens — they must read forward through the dialog body to discover its purpose. This affects every approve/reject/return decision flow in the Dean's evidence pipeline.
- **WCAG**: 4.1.2 Name, Role, Value (A)
- **Recommendation**: Give each modal's header title an `id` and reference it via `aria-labelledby` on the `.modal` container, following the one correct example already in this file.
- **Suggested command**: `$impeccable harden`

**[P2] No sticky/frozen label column on the quota-cascading matrix**
- **Location**: `app/templates/dean_dashboard.html:152-198` (table with one `<th>`/`<td>` column per department plus special roles, columns generated dynamically from `departments`/`special_roles`)
- **Category**: Responsive Design
- **Impact**: This is the densest data-entry surface in the app — every master indicator row against every department/role column, disabled/locked once cascaded. On any viewport narrower than the total column count requires, `.table-responsive` correctly prevents page-level overflow, but scrolling right to reach a department column scrolls the indicator-description column out of view too, so the Dean loses track of which row they're editing while filling in quotas.
- **Recommendation**: Add `position: sticky; left: 0;` (with a solid background) to the first column's `<th>`/`<td>` so the indicator label stays visible during horizontal scroll.
- **Suggested command**: `$impeccable layout`

**[P2] Dynamically-injected form controls have no accessible labels** — ✅ Fixed
- **Location**: quota inputs `:186-192`; search input `#assignDesignatedSearch:755` (placeholder only); all AJAX-rendered inputs in `populateReviewItems` (`.review-qty`, `.review-remark`, `.review-desc`, `.review-dur-value`/`-unit`, e.g. `:2450,2458-2464,2470`) and in `openDesignatedAssignmentEditor` (`assign_quantity_*`, `assign_description_*`, `assign_dur_value_*`, `:983-999`)
- **Category**: Accessibility
- **Impact**: Every quantity/description/duration/remarks field a Dean fills in across the quota grid, the IPCR review modal, and the College-Wide assignment editor relies solely on table-column position or a placeholder for context — placeholders disappear on focus and are not a substitute for a label for most assistive tech.
- **WCAG**: 1.3.1 Info and Relationships, 3.3.2 Labels or Instructions (A)
- **Recommendation**: Add `aria-label` (built from the row's indicator description) to each dynamically-created input, since a visible `<label>` isn't practical in a dense table.
- **Suggested command**: `$impeccable harden`

**[P2] Zero `<th scope>` attributes across the file's data tables** — ✅ Fixed (all 76 `<th>` elements)
- **Location**: every `<thead>` in the file (quota matrix `:154-165`, draft-approval tables `:387-396`, `:447-456`, evidence/final-verification tables `:1168-1175`, `:1243-1251`, etc.)
- **Category**: Accessibility
- **Impact**: On the quota matrix specifically (10+ dynamic columns), a screen reader user moving cell-by-cell gets no "column X of row Y" context without `scope="col"`, making the busiest table in the app the hardest one to navigate non-visually.
- **WCAG**: 1.3.1 Info and Relationships (A)
- **Recommendation**: Add `scope="col"` to header cells across these tables (mechanical, low-risk fix).
- **Suggested command**: `$impeccable harden`

**[P2] Dead "Phase 2" section with hardcoded mock data and non-functional buttons** — ✅ Fixed (confirmed unreachable, deleted)
- **Location**: `app/templates/dean_dashboard.html:317-358`
- **Category**: Implementation Integrity
- **Impact**: This `<div id="nav-phase2">` section (header: "Phase 2: Commitment Verification (Digital Handshake)") has no corresponding sidebar `data-section="nav-phase2"` entry anywhere in `{% block sidebar_items %}` (verified: only `nav-overview`, `nav-phase1`, `nav-draft-ipcr`, `nav-target-assign`, `nav-evidence-verification`, `nav-final-verification` exist) — it is unreachable through normal navigation. It contains one static row of fully hardcoded fake data (`Chester Developer`, `Instructor I`) and two buttons (`View IPCR`, `Lock Commitment`) with no `onclick` handlers at all. It appears superseded by the real "IPCR Draft Approval" flow later in the file but was never removed.
- **Recommendation**: Delete the section, or if a real "Phase 2" is still planned, replace the mock row with the empty-state pattern used consistently elsewhere in this file.
- **Suggested command**: `$impeccable distill`

**[P2] Three different, inconsistently-applied error/feedback mechanisms**
- **Location**: native `alert()` at e.g. `:943,1011,1613,1616,1642,1644,1980,2310,2406`; custom `showCustomAlert()` (base.html, used at `:921`); `showToast()` defined locally at `:2834-2842` and used for save/decision results
- **Category**: Implementation Integrity
- **Impact**: Within the same file, some failures pop a native unstyled browser `alert()`, others use the app's own styled toast, and one uses the shared `showCustomAlert`. This produces an inconsistent, jarring experience depending on which action failed — e.g. a network error saving quota values shows a native `alert()` while a network error saving review items shows a styled `showToast`.
- **Recommendation**: Standardize all failure paths in this file on `showToast`/`showCustomAlert` and remove the native `alert()` fallbacks.
- **Suggested command**: `$impeccable polish`

**[P3] Toast messages aren't announced to assistive tech** — ✅ Fixed
- **Location**: `showToast()`, `app/templates/dean_dashboard.html:2834-2842`
- **Category**: Accessibility
- **Impact**: The dynamically-injected `.alert` div has no `role="alert"`/`aria-live`, so screen reader users get no notification when a save or decision succeeds or fails.
- **WCAG**: 4.1.3 Status Messages (AA)
- **Recommendation**: Add `role="alert"` (or wrap in a persistent `aria-live="polite"` region) to the generated toast element.
- **Suggested command**: `$impeccable harden`

**[P3] Whole-dashboard DOM render instead of per-tab loading**
- **Location**: all six `.dashboard-section` blocks (`:68`, `:117`, `:318`, `:365`, `:1148`, `:1219`) are rendered server-side unconditionally, toggled only by a CSS class
- **Category**: Performance
- **Impact**: Every faculty row, evidence record, and draft submission across all tabs is present in the initial page payload even though only one tab is visible at a time. As faculty/evidence counts grow across a real term, this scales the page weight regardless of which tab the Dean actually opens.
- **Recommendation**: Lazy-fetch a tab's table content on first `showSection()` activation instead of rendering everything up front, or at minimum paginate the largest lists (draft approvals, evidence verification).
- **Suggested command**: `$impeccable optimize`

**[P3] Full-page `location.reload()` after every AJAX decision**
- **Location**: `:1611,1639,1817` region and `:2817` (`submitDeanDecision`)
- **Category**: Performance
- **Impact**: Approving/returning an IPCR or evidence package reloads the entire page rather than patching the affected row, discarding scroll position and requiring the whole DOM (see above) to be rebuilt for a single status change.
- **Recommendation**: Update the affected row/badge in place (the code already does this for `submitDeanDecision`'s status badge before the reload) and drop the reload.
- **Suggested command**: `$impeccable optimize`

**[P3] Minor token-system drift**
- **Location**: `var(--bs-secondary)` at `:2905` (should be a `--c-*` token); raw `rgba()` colors at `:2435`, `:2925`, `:2950`
- **Category**: Theming
- **Impact**: Small, low-risk inconsistency against an otherwise well-disciplined token system (74/75 inline styles correctly use `var(--c-*)`).
- **Recommendation**: Replace with the matching `--c-*` token for consistency, in case theming/colors are ever revisited.
- **Suggested command**: `$impeccable colorize`

**[P3] Near-duplicate logic pairs**
- **Location**: `populateReviewItems`'s Core-Functions block (`:2422-2485`) vs. its Strategic-Priorities block (`:2487-2561`) are ~95% identical markup-generation code; `saveThenDecide` (`:2622-2689`) and `saveDeanReviewItems` (`:2691-2765`) duplicate the entire item-collection loop
- **Category**: Implementation Integrity
- **Impact**: Not a functional bug today, but the duplication already caused one documented micro-bug class in this file (the `_key` vs `indicator_id` comments at `:2147-2158`, `:2247-2250` describe fixes that had to be applied twice because of exactly this kind of duplication) and will keep costing double edits on the next fix.
- **Recommendation**: Extract a shared `buildReviewRow(item, isLocked)` helper and a shared `collectReviewItemsFromDOM()` helper.
- **Suggested command**: `$impeccable distill`

### Patterns & Systemic Issues
- **Table accessibility is uniformly absent**: no file-specific table has `scope` attributes, and the file's own dynamically-built tables/forms have zero labels — this is a blanket gap across the whole surface, not isolated cells.
- **Modal accessible-naming is inconsistent within the same file**: one modal (`#reviewDeanModal`) does `aria-labelledby` correctly; the other nine, built by the same author in the same file, don't — suggesting the pattern is known but not applied consistently.
- **`border-top: 3px solid var(--c-*) !important` accent-on-rounded-card** appears 4 times (detector-verified at `:378,438,1290,1351`) — this is the same family as the already-documented "side-tab" left-border AI-UI tell from the shared shell audit; noted here only for completeness, not scored as a new issue.
- **Error feedback and page-refresh strategy are unstandardized**, using three different mechanisms (native `alert`, `showCustomAlert`, `showToast`) and reload-vs-patch inconsistently across otherwise-similar action flows.

### Positive Findings
- **Full icon-library migration**: this file has zero legacy `bi-` (Bootstrap Icons) classes — 100% of its ~118 icon usages are the current `ti-` (Tabler) set, ahead of the mixed-library state flagged at the shell level.
- **Consistent, well-designed empty states**: nearly every list (pending drafts, approved drafts, evidence queues, both final-verification tables) has a matching icon + heading + one-line explanation empty state, not just a blank table.
- **No clickable-`<div>` anti-pattern**: every interactive control in this file is a real `<button>` or `<a>`, keeping native keyboard operability intact.
- **Every table is wrapped in `.table-responsive`**: no raw table overflow anywhere in the file, including the wide quota matrix (the missing piece is a sticky label column, not the wrapper itself).
- **Disciplined token usage**: 74 of 75 inline `style="..."` attributes correctly reference the shared `var(--c-*)` design tokens rather than hardcoding colors.
- **Genuinely product-specific domain logic with self-documenting rationale**: the code comments around `_key` vs `indicator_id` (`:2147-2158`, `:2317-2323`) and the Core/Strategic split for chairs are unusually clear about *why* the implementation is shaped the way it is — a strong signal this is bespoke, reasoned code rather than templated boilerplate.

### Design-Taste-Frontend Note (scoped)
Out of scope (dashboard UI), consistent with the shared shell finding.

### Recommended Actions (priority order)
1. **[P1] `$impeccable harden`**: Fix the duplicate `#confirmModalTitle` ID, escape user-entered text before every `innerHTML` interpolation (8+ sites), and add `aria-labelledby` to the 9 modals missing it.
2. **[P2] `$impeccable harden`**: Add `aria-label` to dynamically-generated form inputs and `scope="col"` to every table header in this file.
3. **[P2] `$impeccable layout`**: Add a sticky label column to the quota-cascading matrix so row context survives horizontal scroll.
4. **[P2] `$impeccable distill`**: Remove the dead, mock-data "Phase 2" section (lines 317-358).
5. **[P2] `$impeccable polish`**: Standardize error/feedback handling on one mechanism (`showToast`/`showCustomAlert`) instead of three.
6. **[P3] `$impeccable optimize`**: Move toward per-tab lazy loading and in-place row updates instead of whole-dashboard rendering plus full-page reloads.
7. **[P3] `$impeccable colorize`** and **`$impeccable distill`**: Clean up the remaining hardcoded colors and de-duplicate the near-identical `populateReviewItems`/`saveThenDecide` logic pairs.
## 7. Admin Dashboard — `app/templates/admin_dashboard.html`

**Impeccable Audit Health Score: 11/20 — Acceptable (significant work needed)**

| # | Dimension | Score | Key Finding |
|---|-----------|-------|-------------|
| 1 | Accessibility | 1/4 | 40 of 47 `<label>` elements have no `for` attribute — including cases where the paired input already carries an `id` (e.g. `catName`, `deptName`) and the label was simply never wired to it |
| 2 | Performance | 3/4 | No layout thrash, no images, no unbounded effects; every mutation (toggle/edit) is a full-page POST-redirect rather than partial update, which is the only real drag |
| 3 | Theming | 3/4 | No local `<style>` block, no hardcoded hex; correctly uses `var(--c-accent)`/`var(--c-text-muted)` in the two places it deviates from Bootstrap utility classes |
| 4 | Responsive Design | 2/4 | All 13 tables wrapped in `.table-responsive`, but action-column buttons (`btn-sm px-2 py-1`) are well under the 44px touch-target minimum throughout |
| 5 | Implementation Integrity | 2/4 | A verified, shippable bug: deactivating an IPCR Category is one-directional and unrecoverable from the UI, with no confirmation dialog |

### Implementation Integrity Verdict
**Partial pass.** The file is a coherent, product-specific admin console — no filler content, no unrelated boilerplate, and it correctly reuses the shell's token system rather than reinventing styling. But it fails on execution follow-through in two verified ways: a genuine functional trap in the Category toggle (below), and a hardcoded string-patch (`if (cat === 'A. Research') cat = 'B. Research';`) sitting in production JS as silent evidence of category-name drift that was band-aided rather than fixed at the data layer.

### Findings

**[P0] Deactivating an IPCR Category is a silent, one-way dead end** — ✅ Fixed (conditional toggle mirroring Criteria/Department pattern, plus confirm dialog)
- **Location**: `app/templates/admin_dashboard.html:429-433` (form posts to `admin.admin_toggle_category` with `<input type="hidden" name="is_active" value="0">` hardcoded, and the button always reads "Deactivate" — never conditioned on `c.is_active` the way the Criteria (366-372) and Department (876-882) toggles are)
- **Category**: Implementation Integrity / Accessibility (destructive action, no confirmation)
- **Impact**: `app/routes/admin.py:461-480` → `set_ipcr_category_active()` genuinely supports reactivation, but `admin_dashboard.html:21` fetches categories via `get_ipcr_categories(cursor, dt)` with its default `active_only=True` (`app/models/criteria.py:245-260`). Once an admin clicks Deactivate, the row vanishes from every list in this file with **no button anywhere in the template that could ever set `is_active` back to 1** for that category. Since categories carry the term's scoring weights, this can strand an entire designation type's weight configuration until someone hand-edits the database. There is also no `confirm()` guard, unlike every comparable destructive action elsewhere in the file (indicator delete, password reset, account lock).
- **WCAG**: N/A (functional integrity, not a rendering standard)
- **Recommendation**: Mirror the Criteria/Department pattern — make the hidden `is_active` value conditional (`{{ 0 if c.is_active else 1 }}`), the button label conditional (Deactivate/Activate), and either drop `active_only=True` for this admin view or add an "include inactive" toggle so deactivated rows stay visible and recoverable. Add a `confirm()` given weights depend on it.
- **Suggested command**: `$impeccable harden`

**[P1] Form labels are not programmatically associated with their controls (40 of 47)** — ✅ Fixed (verified pre-fix count was actually only 7/47 associated, not 40; brought to 46/47 — the one holdout labels a checkbox group, not a single control)
- **Location**: Pervasive — representative instances at `admin_dashboard.html:194` (Academic Year), `:199` (Semester), `:292` (Add Criterion Name), `:463` (`catName`, which already has an `id` the label ignores), `:781` (`editCritName`), `:1039` (College Full Name), `:1654-1743` (entire Add/Edit Faculty modal — 9 fields, 0 associated). Only 7 labels in the whole file use `for=`.
- **Category**: Accessibility
- **Impact**: Screen reader users get no announced label when focusing most inputs across every CRUD surface in this file (Term Configuration, Criteria, Category modal, Department modal, Institution Setup, Faculty modal, Add/Edit Indicator modals). Clicking a label also fails to focus/toggle its control for any user. This is the dashboard's densest form surface, so the blast radius is large.
- **WCAG**: 1.3.1 Info and Relationships (A), 4.1.2 Name, Role, Value (A)
- **Recommendation**: Add matching `id`/`for` pairs. Many inputs already have an `id` (the modals populated by JS need them) — those cases are a pure one-line `for="..."` add per label, no markup restructuring required.
- **Suggested command**: `$impeccable harden`

**[P1] Complex data tables have no header semantics (`scope`, row headers)** — ✅ Fixed
- **Location**: All 13 tables, most notably the Weight Allocation matrix (`:595-660`) and Teaching Load matrix (`:975-1003`), where the leftmost column (`Academic Rank` / `All Academic Ranks`) is a plain `<td class="fw-semibold">` acting as a row label for a row of numeric inputs
- **Category**: Accessibility
- **Impact**: A screen reader user tabbing through the weight-input grid gets no indication of which rank or category a given input belongs to — the exact kind of grid where header association matters most. No `<th>` in this file carries `scope="col"` or `scope="row"` either.
- **WCAG**: 1.3.1 Info and Relationships (A)
- **Recommendation**: Add `scope="col"` to all `<th>` column headers; convert the rank/category label cell in the weight and teaching-load matrices to `<th scope="row">`.
- **Suggested command**: `$impeccable harden`

**[P2] Radio-button "mode" groups lack a `<fieldset>`/`<legend>`** — ✅ Fixed
- **Location**: `admin_dashboard.html:569-589` (Weight Allocation "General vs Specific per Rank") and `:929-947` (Teaching Load "Same for all ranks" vs "Per academic rank") — each repeated per designation type, so 4 instances total
- **Category**: Accessibility
- **Impact**: The two radios are visually grouped under a plain `<span>` ("Allocation:" / "Applies:") with no programmatic grouping, so assistive tech announces two disconnected radio buttons rather than a labeled choice.
- **WCAG**: 1.3.1 Info and Relationships (A)
- **Recommendation**: Wrap each `form-check-inline` pair in `<fieldset><legend>Allocation</legend>…</fieldset>` (legend can be visually styled to match the current span).
- **Suggested command**: `$impeccable harden`

**[P2] Hardcoded category-name string patch in production JS** — ✅ Fixed (made resilient with a `console.warn` guard; data-layer rename left out of scope as instructed)
- **Location**: `admin_dashboard.html:1838-1839` — `let cat = btn.dataset.indCategory; if (cat === 'A. Research') cat = 'B. Research';`
- **Category**: Implementation Integrity
- **Impact**: This is a silent workaround for a stale/renamed category label, hardcoded into the Edit Indicator modal's fill logic. If category names are edited again (which the Category Management UI two sections up explicitly allows), the `<select>` in the Edit Indicator modal (`:1613-1617`) may have no matching `<option>`, and the field will silently render blank/unselected instead of the indicator's real category — an admin could resave the indicator into the wrong or a null category without any warning.
- **Recommendation**: Fix at the data layer (rename the stored value or the category consistently) and delete the JS patch; if a mismatch is currently unavoidable, at minimum make it resilient (log/warn when no matching option exists) instead of failing silently.
- **Suggested command**: `$impeccable harden`

**[P2] Action-button touch targets are consistently under 44px** — ✅ Fixed (added missing spacing wrapper in Category Management; widened `gap-1`→`gap-2` elsewhere)
- **Location**: Every roster/criteria/department/indicator table's Actions column, e.g. `:1302` (`btn-outline-secondary btn-sm px-2 py-1` — Edit) and `:1312` (Delete) repeated across all indicator tables, plus `:155/:160/:162` (roster Edit/Deactivate/Activate)
- **Category**: Responsive Design
- **Impact**: `btn-sm` plus `px-2 py-1` renders well under the 44×44px minimum; on any touch-capable device (tablet review of the roster, e.g.) mis-taps between adjacent Edit/Delete buttons are likely, with Delete being destructive.
- **WCAG**: 2.5.5 Target Size (AAA) / 2.5.8 Target Size Minimum (AA, 24px — still likely failing at ~28-30px effective height)
- **Recommendation**: Bump action-column buttons to at least `btn-sm` with `py-1.5`/normal padding, or increase tap spacing between adjacent Edit/Delete pairs.
- **Suggested command**: `$impeccable adapt`

**[P2] Heading hierarchy skips levels throughout**
- **Location**: Systemic — every section goes `<h2>` (section title, e.g. `:95`, `:182`, `:277`) directly to `<h5>` (card headers, e.g. `:189`, `:231`, `:287`) to `<h6>` (sub-labels, e.g. `:397`, `:1282`), with no `<h3>`/`<h4>` anywhere in the file
- **Category**: Accessibility
- **Impact**: Screen reader users navigating by heading level get a jarring, unpredictable outline; this is consistent enough across all six sections that it reads as a template convention rather than a mistake, making it cheap to fix everywhere at once.
- **WCAG**: 1.3.1 Info and Relationships (A) / 2.4.6 Headings and Labels (best practice)
- **Recommendation**: Shift card headers to `<h3>` and sub-labels to `<h4>` (or renumber consistently), independent of the current visual size, which can stay controlled by class.
- **Suggested command**: `$impeccable harden`

**[P3] Side-tab accent border (detector-confirmed, 2 instances, isolated to this file)**
- **Location**: `:1261` (`border-left: 3px solid var(--c-accent) !important`), `:1340` (`border-left: 3px solid var(--c-text-muted) !important`) — both on Master Indicators category-group headers
- **Category**: Implementation Integrity (design-system drift flag)
- **Impact**: Matches the shared shell's documented "side-tab" AI-tell pattern, but only 2 occurrences in ~1880 lines and both correctly reference design tokens (no hardcoded hex) — minor, not systemic for this file specifically.
- **Recommendation**: Low priority; if addressed shell-wide, fold these two in at the same time rather than treating as a separate pass.
- **Suggested command**: `$impeccable polish`

**[P3] No search/filter for Master Indicators, Term History, Departments, Criteria, or Audit Log**
- **Location**: Only HR Roster (`:112`) and Security Users (`:1479`) have a search input + status filter; Master Indicators (`:1216+`), Term History (`:234-266`), Criteria (`:330-384`), Departments (`:843-892`), and Audit Log (explicitly capped "Last 50", `:1553`) render every row with no client-side filtering
- **Category**: Performance / Responsive Design (data-dump risk)
- **Impact**: Low risk today (these are admin-configured, typically small lists), but Master Indicators in particular grows with every term and every category, and is already split into many separate per-category tables with no way to jump to or search a specific indicator.
- **Recommendation**: Reuse the existing `filterRoster`/`filterSecurity` pattern for Master Indicators at minimum, since it's the fastest-growing list here.
- **Suggested command**: `$impeccable layout`

### Patterns & Systemic Issues
- **Label association is a file-wide gap, not isolated typos**: 85% of labels lack `for=`, spanning every one of the file's ~9 forms/modals — this is a single mechanical fix applied everywhere, not case-by-case triage.
- **Two destructive-action confirmation conventions coexist inconsistently**: Delete Indicator, Lock Account, and Reset Password all use `onsubmit="return confirm(...)"`; Deactivate Criterion, Deactivate Department, Toggle Roster Status, and (most importantly) Deactivate Category do not — and the last one is also functionally irreversible via the UI. The confirm-guard should be applied by convention, not by which developer wrote that block.
- **Heading level skipping (h2→h5→h6) is a template-wide convention**, cheap to correct in one pass since it's consistent rather than ad hoc.

### Positive Findings
- No local `<style>` block and no hardcoded hex colors anywhere in the file — it defers entirely to `base.html`'s token/Bootstrap-retint system, which is exactly the right layering.
- All 13 tables are properly wrapped in `.table-responsive`, including the more complex weight/teaching-load matrices.
- Destructive delete (Indicator) and security-sensitive actions (Reset Password, Lock Account) do have `confirm()` guards with specific, informative dialog text — a good baseline that just needs to be applied consistently (see Category toggle finding above).
- The Weight Allocation matrix has solid client-side UX: live per-row total badges, red/green/gray state, and a clear modal explaining exactly which rows are wrong before blocking submission — this is meaningfully more helpful than a bare HTML5 validation message.
- Roster and Security tables both ship working client-side search + status filter, a good pattern that should simply be extended to the other lists (see P3 above).

### Design-Taste-Frontend Note (scoped)
`design-taste-frontend`: out of scope (dashboard UI), consistent with shared shell finding. Nothing in this file rises to the level of a screaming generic-AI-slop exception — the two side-tab borders are the only detector-flagged pattern and are minor/isolated (see P3).

### Recommended Actions (priority order)
1. **[P0] `$impeccable harden`**: Fix the Category deactivate toggle (`:429-433`) to mirror the Criteria/Department conditional pattern and add a confirmation dialog — currently the only truly unrecoverable admin action in this file.
2. **[P1] `$impeccable harden`**: Wire up `for=`/`id` pairs across all ~40 unassociated labels; many inputs already carry the needed `id`.
3. **[P1] `$impeccable harden`**: Add `scope="col"`/`scope="row"` to the Weight Allocation and Teaching Load matrix tables.
4. **[P2] `$impeccable harden`**: Wrap the two "mode" radio-button groups in `<fieldset>/<legend>`; fix or remove the hardcoded `'A. Research' → 'B. Research'` string patch at `:1839`; correct the h2→h5→h6 heading skip.
5. **[P2] `$impeccable adapt`**: Enlarge action-column buttons to clear the 44px touch-target guidance.
6. **[P3] `$impeccable layout`**: Add search/filter to Master Indicators at minimum.
7. **[P3] `$impeccable polish`**: Fold the two side-tab accent borders into any shell-wide pass on that pattern.
## 8. Print Form — `app/templates/ipcr_print.html`

**Impeccable Audit Health Score: 13/20 — Acceptable (significant work needed)**

| # | Dimension | Score | Key Finding |
|---|-----------|-------|-------------|
| 1 | Accessibility | 2/4 | No headings, landmarks, table `<caption>`s, or `scope` attributes anywhere in the document |
| 2 | Performance | 4/4 | Fully self-contained (no external CSS/JS/fonts/images) — negligible footprint |
| 3 | Theming | 2/4 | The only interactive chrome (toolbar) hardcodes Bootstrap blue + `system-ui`, ignoring the app's own `--c-accent`/`Public Sans` tokens |
| 4 | Responsive Design | 2/4 | An 8-column, fixed-layout 11in form is crammed to phone width with no dedicated mobile treatment |
| 5 | Implementation Integrity | 3/4 | Solid overall (correct dynamic rowspan math, correctly-scoped `\|safe` usage) but has dead CSS and a missing print-fidelity property |

### Implementation Integrity Verdict
**Pass, with minor drift.** This is a coherent, single-purpose document that clearly expresses "printable IPCR form" — no generic or interchangeable structure. The Jinja logic is unusually careful for a template this dense: `{{ form.signatories.REVIEWED_BY.name or '&nbsp;' | safe }}` correctly scopes `|safe` only to the literal fallback entity (Jinja's `or`/`|` precedence means the filter binds to `'&nbsp;'` alone), so a signatory's real name still gets auto-escaped — this is the kind of detail that's easy to get backwards and get an XSS hole from, and it's done right here. The `rowspan="{{ 5 + (form.score.breakdown | length) }}"` computation on line 197 also correctly accounts for the two header rows plus three summary rows against a variable number of breakdown categories — verified by hand-counting the actual `<tr>`s in that table (lines 195-236), it's exact, not off-by-one. The two flaws found (dead `.page-break` CSS, missing print-color-adjust) are isolated, not systemic.

### Findings

**[P1] Shaded section-row backgrounds are not guaranteed to print** — ✅ Fixed (I had wrongly told a later fix pass this was already done — caught and fixed on review: added `print-color-adjust: exact` / `-webkit-print-color-adjust: exact`)
- **Location**: ipcr_print.html:44 (`.section-row td { background: #f2f2f2; ... }`), :60-80 (`@media print` block)
- **Category**: Implementation Integrity / Print correctness
- **Impact**: Chrome, Edge, and most Chromium browsers omit background colors from print output by default unless the user manually checks "Background graphics" in the print dialog. The section-row shading is the only visual separator between "I. Strategic Priorities," "II. Core Functions," etc. on the printed page — for most users this structure will silently disappear on the physical printout even though it renders correctly on screen, and nothing in the UI warns them to enable that setting.
- **Recommendation**: Add `print-color-adjust: exact; -webkit-print-color-adjust: exact;` to the `@media print` block (on `body` or `.sheet`) so the shading survives printing regardless of the browser's default setting.
- **Suggested command**: `$impeccable harden`

**[P2] Print form has no mobile-friendly presentation**
- **Location**: ipcr_print.html:21-29 (`.sheet { width: 10.2in; max-width: 100%; ... }`), no viewport-width media query anywhere in the file
- **Category**: Responsive Design
- **Impact**: `max-width: 100%` prevents horizontal overflow, but the fixed 10pt font size and percentage-based `table-layout: fixed` columns (e.g., 26% of a ~340px phone-width sheet ≈ 88px) mean the 8-column rating table is squeezed into illegibly narrow cells rather than scrolling — text wraps into tall, hard-to-scan cells instead of staying readable. A faculty member checking their IPCR on a phone gets a much worse experience than the print target implies.
- **Recommendation**: Below a breakpoint (e.g., 768px), wrap `.sheet` in a container with `overflow-x: auto` and let it render at a fixed minimum width (its natural print width) so users scroll horizontally through a legible form, rather than shrinking an 11in document to fit a 6in screen.
- **Suggested command**: `$impeccable adapt`

**[P2] Toolbar chrome ignores the app's design tokens** — ✅ Fixed
- **Location**: ipcr_print.html:51-57 (`.toolbar`, `.toolbar button, .toolbar a`) vs. app tokens in auth_layout.html:16-24 and base.html:384-386 (`--c-accent: #3E5C82`, `--font-body: 'Public Sans'...`)
- **Category**: Theming / Implementation Integrity
- **Impact**: The printed form's Times New Roman styling is correct and intentional (it must match the government form). But the toolbar — the one piece of interactive on-screen UI a user actually touches before printing — hardcodes Bootstrap's default blue (`#0d6efd`) and a generic `system-ui` font stack instead of the app's own `--c-accent` (#3E5C82) and Public Sans. A user coming from any dashboard sees a visibly different button color and font the moment they land on this page, then it vanishes at print time — an unnecessary, avoidable brand inconsistency confined to a page most users only see briefly.
- **Recommendation**: Reuse the app's CSS custom properties for the toolbar (`background: var(--c-accent)`, `font-family: var(--font-body)`), or better, link the same button component styling used elsewhere (`.btn-dipcr`).
- **Suggested command**: `$impeccable polish`

**[P2] No headings, landmarks, captions, or table `scope` attributes** — ✅ Fixed
- **Location**: ipcr_print.html:83-280 (entire `<body>`); tables at :108-127, :130-191, :195-236, :243-275
- **Category**: Accessibility
- **WCAG**: 1.3.1 Info and Relationships
- **Impact**: The visual title (line 97, `.title` div) is not a heading element, there is no `<main>` landmark, and none of the four tables have a `<caption>` or `scope="col"` on header cells. A screen reader user gets a flat sequence of unlabeled tables and cannot jump to "the rating table" or understand which column a cell belongs to without linear reading through dense, heavily merged (`rowspan`/`colspan`) markup.
- **Recommendation**: Wrap the sheet in `<main>`, promote `.title` to an `<h1>`, add a `<caption class="visually-hidden">` to each table describing its purpose, and add `scope="col"` to the `<th>` cells in the main rating table header (lines 133-144). This is a low-cost, high-value change since it doesn't touch the visual/print layout at all.
- **Suggested command**: `$impeccable harden`

**[P3] Dead CSS: `.page-break` is defined but never used**
- **Location**: ipcr_print.html:77 (`.page-break { page-break-before: always; }`), never applied to any element in the body (lines 83-280)
- **Category**: Implementation Integrity
- **Impact**: No functional impact today, but it's a maintenance trap — a future editor may assume forcing a page break "already works" via this class and be surprised when nothing happens, or may not realize large forms currently rely entirely on the browser's natural (row-level) pagination.
- **Recommendation**: Either remove the unused rule, or apply it somewhere intentional (e.g., before the summary block when the target table is very long) and document why.
- **Suggested command**: `$impeccable harden`

### Patterns & Systemic Issues
- The page correctly treats print fidelity as the top priority (matching sheet width to `@page` size, hiding non-printing chrome, avoiding row splits) — the gaps that exist are all in the on-screen/accessibility layer that print fidelity doesn't require anyone to think about, which is exactly where they were missed.

### Positive Findings
- Careful, precedence-aware use of `{{ x or 'default' | safe }}` avoids escaping the fallback entity while still auto-escaping real user/DB data (no XSS surface found anywhere in the template).
- Dynamic `rowspan` calculation for the summary block is verified correct against the actual row count, including the variable-length `breakdown` loop.
- `page-break-inside: avoid` on `tr` and `.summary-block`, plus `thead { display: table-header-group; }`, show real print-pagination thought — rows won't split mid-content and the header repeats across pages.
- Zero external dependencies keep this the fastest-loading page in the app by a wide margin.

### Design-Taste-Frontend Note (scoped)
Not applicable — this is a fixed government form replica, not a designed marketing/product surface, so a design-taste critique wouldn't add value here.

### Recommended Actions (priority order)
1. **[P1] `$impeccable harden`**: Add `print-color-adjust: exact` so section-row shading actually survives printing.
2. **[P2] `$impeccable adapt`**: Give the form a real narrow-viewport strategy (horizontal scroll at natural width) instead of shrinking it illegibly.
3. **[P2] `$impeccable polish`**: Restyle the toolbar to use the app's own accent color and font tokens.
4. **[P2] `$impeccable harden`**: Add heading/landmark/caption/scope structure for screen reader users.
5. **[P3] `$impeccable harden`**: Remove or wire up the unused `.page-break` class.

---

## 9. Auth Pages — `app/templates/login.html`, `register.html`, `form.html`

**Impeccable Audit Health Score: 10/20 — Acceptable (significant work needed)**

| # | Dimension | Score | Key Finding |
|---|-----------|-------|-------------|
| 1 | Accessibility | 2/4 | Password-policy checklist conveys pass/fail by color alone (same checkmark icon both states) |
| 2 | Performance | 2/4 | Full Bootstrap + full Tabler icon webfont + multi-weight Google Fonts loaded for ~6 icons and two short forms |
| 3 | Theming | 2/4 | login.html/register.html hardcode inline hex colors that don't match the `--c-text`/`--c-accent` tokens defined one file away |
| 4 | Responsive Design | 3/4 | Layout reflows correctly; only minor crowding risk in register's two-column checklist on very narrow phones |
| 5 | Implementation Integrity | 1/4 | Orphaned prototype file (`form.html`), an internally-inconsistent password-toggle icon, and a jarring native `alert()` that bypasses the app's own flash-message system |

### Implementation Integrity Verdict
**Fail.** `form.html` is the deciding factor: it is a bare, unstyled, un-routed prototype ("SPMS Form" / "DPCR/IPCR Prototype") that shares no markup, styling, or design language with `login.html`/`register.html` — it reads like a scaffold from an early milestone that was never deleted. A repo-wide search (`grep -r "form.html" app/`) confirms it is not referenced by any `render_template()` call in any blueprint — it is genuinely dead code, not a low-traffic page. Sitting in the same `templates/` folder as a considered, on-brand auth flow, it is the literal case the rubric describes as "structure that is interchangeable with an unrelated product." On top of that, the two live pages have two verified functional/UX bugs (an inverted password-visibility icon and a plain-JS `alert()` where the rest of the app uses styled flash messages) — real, reproducible defects rather than taste judgments, which is why this scores 1/4 rather than 2-3.

### Findings

**[P1] Password-policy checklist relies on color alone to show pass/fail** — ✅ Fixed (icon now swaps `ti-circle`↔`ti-check`, not just color)
- **Location**: register.html:56-77 (all six `.policy-item` blocks use the identical `<i class="ti ti-check">` glyph); auth_layout.html:216-227 (`.policy-item.valid i { color: #2E5F42; }` / `.policy-item.invalid i { color: var(--c-border); }` — only color differs)
- **Category**: Accessibility
- **WCAG**: 1.4.1 Use of Color
- **Impact**: An unmet requirement still renders a checkmark — just a pale gray one — instead of an empty/×/pending icon. A colorblind user, or anyone glancing quickly, sees six checkmarks and may believe all requirements are met when several are not. This is the exact password-checklist page whose entire job is to communicate pass/fail state correctly.
- **Recommendation**: Swap the icon class itself between states (e.g., `ti-circle` or `ti-x` for invalid, `ti-check` for valid) in `updateReq()` (register.html:126-134), not just the color.
- **Suggested command**: `$impeccable clarify`

**[P2] Password-visibility icon is internally inconsistent for the same field state** — ✅ Fixed
- **Location**: auth_layout.html:284-306 (toggle script); markup at login.html:20-22, register.html:31-34 and :42-44
- **Category**: Implementation Integrity
- **Impact**: The initial markup ships `ti-eye-off` while the password field is masked. After one click-and-click-back round trip, the script's `else` branch (auth_layout.html:301-303) sets the icon to `ti-eye` for that *same masked state*. So the identical field state ("password hidden") renders two different icons depending on interaction history — regardless of which icon-convention you prefer, this is objectively inconsistent and will read as a glitch to attentive users on both the login and registration forms.
- **Recommendation**: Pick one convention (icon reflects current state, or icon reflects the next action) and make the initial markup and both branches of the click handler agree with it.
- **Suggested command**: `$impeccable harden`

**[P2] Registration failure falls back to a native blocking `alert()`** — ✅ Fixed
- **Location**: register.html:151 (`alert('Password does not meet all security policy requirements...')`)
- **Category**: Implementation Integrity / Consistency
- **Impact**: Every other piece of feedback in this exact flow uses styled, dismissible UI — the shared flash-message system in auth_layout.html:259-268, and the inline `#confirmPasswordError` text on register.html:46-49. A raw browser `alert()` dialog on submit failure is a jarring, unstyled interruption that breaks that pattern and cannot be styled, positioned, or dismissed like the rest of the app's messaging.
- **Recommendation**: Replace the `alert()` with an inline banner (or reuse the existing flash-message markup/classes) above the submit button.
- **Suggested command**: `$impeccable clarify`

**[P2] Orphaned prototype template with no accessibility or design-system integration** — ✅ Fixed (confirmed unreferenced, `form.html` deleted)
- **Location**: form.html:1-22 (entire file)
- **Category**: Implementation Integrity
- **Impact**: Confirmed via search that no route in `app/routes/` renders this template — it is dead code. Its `<label>` elements have no `for` attribute and its `<input>`s have no matching `id` (lines 10-17), so even if it were ever wired up it would fail WCAG 1.3.1/4.1.2 immediately. Its presence risks a future developer copy-pasting it as a starting point, or accidentally exposing it via a new route without realizing it has zero styling, validation, or CSRF handling.
- **Recommendation**: Delete the file, or if it documents a real planned feature, move its intent into a task/spec doc instead of a stray template.
- **Suggested command**: `$impeccable harden`

**[P2] Dynamic validation state changes are not announced to assistive tech** — ✅ Fixed
- **Location**: register.html:46-49 (`#confirmPasswordError`), :52-78 (`#passwordPolicyBox`)
- **Category**: Accessibility
- **WCAG**: 4.1.3 Status Messages
- **Impact**: Both the password-mismatch message and the live policy checklist update purely via `style.display`/`className` changes with no `aria-live` region. A screen reader user gets no feedback at all as they type — sighted users see live validation, screen reader users must submit blind and discover errors only from the post-submit `alert()`.
- **Recommendation**: Add `aria-live="polite"` to `#confirmPasswordError` and `#passwordPolicyBox` (or an `aria-live` summary region announcing count of unmet requirements).
- **Suggested command**: `$impeccable harden`

**[P3] Inline hardcoded colors bypass the auth layout's own token system**
- **Location**: login.html:6 (`style="color: #0f172a; ..."`), register.html:6 (`background-color: #fef9c3; color: #854d0e;`) and :11 (`color: #0f172a`)
- **Category**: Theming
- **Impact**: `auth_layout.html` defines `--c-text: #2B2822` (a warm near-black) and uses it consistently for body copy, but the page-title heading on both login and register hardcodes a different, cooler near-black (`#0f172a`) inline instead of the token — a subtle but visible mismatch within the same viewport. The HR-notice alert box on register.html introduces a third one-off color pair with no corresponding variable anywhere else in the app.
- **Recommendation**: Replace the inline `style="color: #0f172a"` with `var(--c-text)` (or a dedicated `--c-heading` token if a deliberate distinction from body text is wanted), and give the HR-notice its own named token if this warning pattern will recur.
- **Suggested command**: `$impeccable polish`

**[P3] Heavy shared asset payload for two lightweight forms**
- **Location**: auth_layout.html:8-13 (full Bootstrap 5 CSS, full Tabler icon webfont, two Google Font families/multiple weights) — loaded by every visit to login.html and register.html
- **Category**: Performance
- **Impact**: These two pages use roughly six icon glyphs (eye, eye-off, alert-triangle, alert-circle, shield-check, check) and a handful of Bootstrap components, yet pull the entire icon webfont and CSS framework from CDN on every unauthenticated page load — the highest-traffic, first-impression pages in the app.
- **Recommendation**: Consider a trimmed icon subset or inline SVGs for the handful of icons actually used on auth pages.
- **Suggested command**: `$impeccable optimize`

### Patterns & Systemic Issues
- Neither `<form>` (login.html:10, register.html:15) includes a CSRF token, and a repo-wide search found no `CSRFProtect`/`csrf_token` usage anywhere in the app — these two forms are the most security-sensitive templates in the audit (credential submission and account creation) and would be the first place a CSRF fix should land if the team ever adds one; noted here since it's directly visible in the template markup even though the actual fix is backend-side.
- Recall from the shell audit of `auth_layout.html`: the password-toggle button's touch target is under 44px, and there is no shared invalid/error field-state styling. Both apply unchanged to every password field on login.html and register.html — not re-detailed here per scope, but they compound with the new findings above (e.g., the color-only checklist state) into a broader theme of "dynamic feedback under-built" on this flow.

### Positive Findings
- Register's initial HTML state for the password-policy checklist matches the JS's computed state for an empty string exactly (no flash-of-wrong-state on load) — a detail that's easy to get wrong and wasn't.
- Both forms use real `<label for>`/`id` pairs, `required` attributes, and `autofocus` on the first field — solid baseline form hygiene on the live pages.
- The responsive breakpoint in auth_layout.html (991.98px) cleanly stacks the hero/form panels with no fixed-width leaks in either login.html or register.html.

### Design-Taste-Frontend Note (scoped)
Copy is clear and appropriately terse ("Claim Your Account," "HR Notice: Your profile must be pre-registered by HR") with no AI-tell filler phrasing. The one taste-adjacent nit: the HR-notice alert's yellow/amber styling is a one-off (not reused anywhere else in the app), so it reads as an ad hoc addition rather than a deliberate "warning" pattern — worth folding into a real alert-variant token if warning banners are going to recur elsewhere.

### Recommended Actions (priority order)
1. **[P1] `$impeccable clarify`**: Fix the password-policy checklist so unmet requirements use a distinct icon, not just a paler version of the same checkmark.
2. **[P2] `$impeccable harden`**: Reconcile the password-toggle icon logic so the same field state always renders the same icon.
3. **[P2] `$impeccable clarify`**: Replace the native `alert()` on registration failure with the app's own inline/flash messaging.
4. **[P2] `$impeccable harden`**: Remove (or properly wire up) the orphaned `form.html` prototype.
5. **[P2] `$impeccable harden`**: Add `aria-live` regions to the password-confirmation error and policy checklist.
6. **[P3] `$impeccable polish`**: Replace hardcoded inline heading/alert colors with the layout's existing CSS variables.
7. **[P3] `$impeccable optimize`**: Trim the icon/font payload loaded by the auth flow.
