from core_integrity.rules.p001_archived_active_cycle import P001ArchivedActiveCycleRule
from core_integrity.rules.p002_archived_in_dashboard import P002ArchivedInDashboardRule
from core_integrity.rules.p003_missing_patient import P003MissingPatientRule


def get_rules():
    return [
        P001ArchivedActiveCycleRule(),
        P002ArchivedInDashboardRule(),
        P003MissingPatientRule(),
    ]


def get_rule_by_code(code):
    for rule in get_rules():
        if rule.code == code:
            return rule
    return None


def get_rules_catalog():
    return [
        {
            "code": rule.code,
            "title": rule.title,
            "category": rule.category,
            "severity": rule.severity,
            "description": rule.description,
            "solution": rule.solution,
            "autofix": rule.autofix,
        }
        for rule in get_rules()
    ]
