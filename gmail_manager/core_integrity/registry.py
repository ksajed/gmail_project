from core_integrity.rules.p001_archived_active_cycle import P001ArchivedActiveCycleRule
from core_integrity.rules.p002_archived_in_dashboard import P002ArchivedInDashboardRule

def get_rules():
    return [
        P001ArchivedActiveCycleRule(),
        P002ArchivedInDashboardRule(),
    ]
