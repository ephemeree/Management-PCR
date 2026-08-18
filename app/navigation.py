"""
Sidebar navigation shared between dashboards.

The IPCR flow under /designated/ is one implementation used by every designated role
(Program Chair, RET Chair, Dean, and any other designated title). Because it is a separate
page, arriving there would otherwise replace the visitor's sidebar. This map lets that page
re-render the visitor's own navigation as links back to their home dashboard, so they keep
their bearings without the panels having to be duplicated per dashboard.

Each item is (section_id, label, icon). Section ids match the `.dashboard-section` ids on the
home dashboard; base.html opens the matching section when the URL carries it as a hash.
"""

HOME_NAV = {
    'DEAN': {
        'endpoint': 'dean.dean_dashboard',
        'label': 'Dean Dashboard',
        'groups': [
            ('Dashboard', [
                ('nav-overview', 'Overview', 'bi-grid-1x2-fill'),
            ]),
            ('Phases', [
                ('nav-phase1', 'Quota Cascading', 'bi-diagram-3-fill'),
                ('nav-draft-ipcr', 'IPCR Draft Approval', 'bi-file-earmark-check-fill'),
                ('nav-phase6', 'Batch Approvals', 'bi-check-all'),
                ('nav-target-assign', 'Target Assignment', 'bi-person-plus-fill'),
                ('nav-final-verification', 'Final Verification', 'bi-file-earmark-diff-fill'),
            ]),
        ],
    },
    'PROGRAM_CHAIR': {
        'endpoint': 'prog_chair.prog_chair_dashboard',
        'label': 'Program Chair Dashboard',
        'groups': [
            ('Dashboard', [
                ('nav-overview', 'Overview', 'bi-grid-1x2-fill'),
            ]),
            ('Phases', [
                ('nav-phase1', 'Target Allocation', 'bi-diagram-3-fill'),
                ('nav-phase2', 'Commitments', 'bi-person-check-fill'),
                ('nav-phase3', 'Grading Engine', 'bi-calculator'),
            ]),
            ('Verification', [
                ('nav-evidence-verification', 'Evidence Verification', 'bi-file-earmark-check-fill'),
            ]),
        ],
    },
    'RET_CHAIR': {
        'endpoint': 'ret_chair.ret_chair_dashboard',
        'label': 'RET Chair Dashboard',
        'groups': [
            ('Dashboard', [
                ('nav-overview', 'Overview', 'bi-grid-1x2-fill'),
            ]),
            ('Phases', [
                ('nav-phase1', 'Cascaded Targets', 'bi-journal-arrow-down'),
                ('nav-target-assignment', 'Target Assignment', 'bi-clipboard2-check-fill'),
                ('nav-phase2', 'Menu Config', 'bi-list-check'),
                ('nav-phase4', 'Commitments', 'bi-person-check-fill'),
            ]),
            ('Verification', [
                ('nav-evidence-verification', 'Evidence Verification', 'bi-file-earmark-check-fill'),
            ]),
        ],
    },
}


def home_nav_for(role):
    """
    The visitor's home dashboard navigation, or None when they are already home.

    DESIGNATED_FACULTY has no separate home — /designated/ *is* their dashboard — so they
    get their own sidebar rather than a set of links back somewhere else.
    """
    return HOME_NAV.get((role or '').upper())
