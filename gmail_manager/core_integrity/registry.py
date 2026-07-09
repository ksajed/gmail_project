from core_integrity.rules.p001_archived_active_cycle import P001ArchivedActiveCycleRule
from core_integrity.rules.p002_archived_in_dashboard import P002ArchivedInDashboardRule
from core_integrity.rules.p003_missing_patient import P003MissingPatientRule

def get_rules():
    return [
        P001ArchivedActiveCycleRule(),
        P002ArchivedInDashboardRule(),
        P003MissingPatientRule(),
    ]
