from django.utils import timezone

from core_anomalies.models import Anomaly
from core_audit.integrity_audit import audit_prescriptions


def map_severity(result):
    severity = result.get("severity", "INFO")

    if severity == "ERROR":
        return "CRITIQUE"

    if severity == "WARNING":
        return "ELEVEE"

    return "INFO"


def sync_anomalies(limit=None):
    report = audit_prescriptions(limit=limit)
    active_keys = set()
    created = 0
    updated = 0
    resolved = 0

    for item in report.get("items", []):
        prescription_id = item["prescription_id"]
        score = item["score"]

        for result in item.get("results", []):
            rule_code = result.get("code", "UNKNOWN")
            key = (prescription_id, rule_code)
            active_keys.add(key)

            _, was_created = Anomaly.objects.update_or_create(
                prescription_id=prescription_id,
                rule_code=rule_code,
                defaults={
                    "severity": map_severity(result),
                    "score": score,
                    "title": result.get("title") or "",
                    "category": result.get("category") or "",
                    "message": result.get("message") or "",
                    "description": result.get("description") or "",
                    "solution": result.get("solution") or "",
                    "suggestion": result.get("suggestion") or result.get("solution") or "",
                    "autofix": bool(result.get("autofix")),
                    "status": "NOUVELLE",
                },
            )

            if was_created:
                created += 1
            else:
                updated += 1

    for anomaly in Anomaly.objects.exclude(status__in=["RESOLUE", "IGNOREE"]):
        key = (anomaly.prescription_id, anomaly.rule_code)

        if key not in active_keys:
            anomaly.status = "RESOLUE"
            anomaly.resolved_at = timezone.now()
            anomaly.comment = "Résolue automatiquement : absente du dernier audit."
            anomaly.save(update_fields=["status", "resolved_at", "comment", "updated_at"])
            resolved += 1

    return {
        "created": created,
        "updated": updated,
        "resolved": resolved,
        "total_active": len(active_keys),
    }
