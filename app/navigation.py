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
                ('nav-overview', 'Overview', 'ti-layout-dashboard'),
            ]),
            ('Phases', [
                ('nav-phase1', 'Quota Cascading', 'ti-sitemap'),
                ('nav-draft-ipcr', 'IPCR Draft Approval', 'ti-file-check'),
                ('nav-phase6', 'Batch Approvals', 'ti-checks'),
                ('nav-target-assign', 'Target Assignment', 'ti-user-plus'),
                ('nav-final-verification', 'Final Verification', 'ti-clipboard-check'),
            ]),
        ],
    },
    'PROGRAM_CHAIR': {
        'endpoint': 'prog_chair.prog_chair_dashboard',
        'label': 'Program Chair Dashboard',
        'groups': [
            ('Dashboard', [
                ('nav-overview', 'Overview', 'ti-layout-dashboard'),
            ]),
            ('Phases', [
                ('nav-phase1', 'Target Allocation', 'ti-sitemap'),
                ('nav-phase2', 'Commitments', 'ti-user-check'),
                ('nav-phase3', 'Grading Engine', 'ti-calculator'),
            ]),
            ('Verification', [
                ('nav-evidence-verification', 'Evidence Verification', 'ti-file-check'),
            ]),
        ],
    },
    'RET_CHAIR': {
        'endpoint': 'ret_chair.ret_chair_dashboard',
        'label': 'RET Chair Dashboard',
        'groups': [
            ('Dashboard', [
                ('nav-overview', 'Overview', 'ti-layout-dashboard'),
            ]),
            ('Phases', [
                ('nav-phase1', 'Cascaded Targets', 'ti-download'),
                ('nav-target-assignment', 'Target Assignment', 'ti-clipboard-check'),
                ('nav-phase2', 'Menu Config', 'ti-list-check'),
                ('nav-phase4', 'Commitments', 'ti-user-check'),
            ]),
            ('Verification', [
                ('nav-evidence-verification', 'Evidence Verification', 'ti-file-check'),
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
