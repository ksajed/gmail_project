"""
ORDO V10 - Service de présentation Renouvellements

Ce fichier ne modifie pas le moteur V9.
Il transforme les données existantes en informations lisibles par le pharmacien.
"""

from datetime import datetime
from django.urls import reverse


def _empty_dashboard():
    return {
        "v10_enabled": True,
        "generated_at": datetime.now(),
        "today_activity": {
            "title": "ORDO travaille pour vous",
            "sms_sent": 0,
            "emails_sent": 0,
            "notifications_created": 0,
            "cycles_created": 0,
            "cycles_closed": 0,
            "cycles_recalculated": 0,
        },
        "pharmacist_work": {
            "patients_to_call": 0,
            "renewals_to_check": 0,
            "urgent_files": 0,
            "anomalies_count": 0,
        },
        "sections": {
            "urgent": [],
            "overdue": [],
            "to_check": [],
            "active": [],
            "history": [],
            "anomalies": [],
        },
        "engine_status": {
            "v9_available": False,
            "source": None,
            "message": "Service V10 actif en mode lecture seule.",
        },
    }


def _safe_len(value):
    try:
        return len(value)
    except Exception:
        return 0


def _load_v9_data():
    """
    Essaie de récupérer les données V9 sans casser l'application.
    Si aucun service V9 compatible n'est trouvé, retourne {}.
    """

    candidates = [
        ("core_emails.services", "compute_renewals_watch_v9"),
        ("core_emails.services", "compute_renewals_dashboard"),
        ("core_emails.services_renewal_rules", "compute_renewals_watch_v9"),
        ("core_emails.services_renewal_rules", "compute_renewals_dashboard"),
    ]

    for module_name, function_name in candidates:
        try:
            module = __import__(module_name, fromlist=[function_name])
            func = getattr(module, function_name, None)

            if callable(func):
                data = func()
                return data or {}, f"{module_name}.{function_name}"

        except Exception:
            continue

    return {}, None




def _prescription_url(prescription):
    if not prescription:
        return "#"

    pk = getattr(prescription, "pk", None) or getattr(prescription, "id", None)

    if not pk:
        return "#"

    return f"/prescription/{pk}/"

def _format_item(item):
    """
    Transforme une donnée V9 brute en ligne lisible et cliquable.
    """
    if not isinstance(item, dict):
        return {
            "title": str(item),
            "url": "#",
            "due_date": "",
            "overdue_days": "",
            "reason": "",
            "action": "Contrôler le dossier",
        }

    prescription = item.get("prescription")
    cycle = item.get("cycle")
    due_date = item.get("due_date")
    overdue_days = item.get("overdue_days")
    reason = item.get("reason") or ""

    title = str(prescription or cycle or item)
    url = _prescription_url(prescription)

    if reason == "RETARD":
        action = "Appeler le patient"
    elif reason == "DERNIER_RENOUVELLEMENT":
        action = "Contrôler le dernier renouvellement"
    else:
        action = "Contrôler le dossier"

    return {
        "title": title,
        "prescription_id": getattr(prescription, "pk", None) or getattr(prescription, "id", None),
        "url": url,
        "due_date": due_date or "",
        "overdue_days": overdue_days or "",
        "reason": reason,
        "action": action,
    }


def _format_list(items, limit=10):
    try:
        return [_format_item(x) for x in list(items)[:limit]]
    except Exception:
        return []




def _integrity_results_for_item(item):
    try:
        from core_integrity.services import run_integrity_for_prescription, integrity_score
    except Exception:
        return [], 100

    if not isinstance(item, dict):
        return [], 100

    prescription = item.get("prescription")

    if not prescription:
        return [], 100

    try:
        results = run_integrity_for_prescription(prescription)
        score = integrity_score(results)
        return results, score
    except Exception:
        return [], 100


def _split_integrity(items):
    normal = []
    anomalies = []

    for item in items or []:
        results, score = _integrity_results_for_item(item)

        has_problem = any(
            r.get("severity") in {"ERROR", "WARNING"}
            for r in results
        )

        if has_problem:
            formatted = _format_item(item)
            formatted["integrity_score"] = score
            formatted["integrity_results"] = results
            anomalies.append(formatted)
        else:
            normal.append(item)

    return normal, anomalies


def compute_renewals_dashboard_v10():
    """
    Point d'entrée principal du Dashboard V10.

    Objectif :
    - ne pas modifier le moteur V9 ;
    - lire les données existantes ;
    - présenter le travail automatique ;
    - présenter le travail pharmacien.
    """

    dashboard = _empty_dashboard()

    v9_data, source = _load_v9_data()

    if not isinstance(v9_data, dict):
        return dashboard

    dashboard["engine_status"]["v9_available"] = bool(source)
    dashboard["engine_status"]["source"] = source

    metrics = v9_data.get("activity_metrics", {}) or {}

    dashboard["today_activity"]["sms_sent"] = (
        metrics.get("sms_sent_today")
        or metrics.get("sms_sent")
        or 0
    )

    dashboard["today_activity"]["emails_sent"] = (
        metrics.get("emails_sent_today")
        or metrics.get("emails_sent")
        or 0
    )

    dashboard["today_activity"]["notifications_created"] = (
        metrics.get("notifications_created_today")
        or metrics.get("notifications_created")
        or 0
    )

    dashboard["today_activity"]["cycles_created"] = (
        metrics.get("cycles_created_today")
        or metrics.get("cycles_created")
        or 0
    )

    dashboard["today_activity"]["cycles_closed"] = (
        metrics.get("cycles_closed_today")
        or metrics.get("cycles_closed")
        or 0
    )

    urgent = (
        v9_data.get("renewals_urgent")
        or v9_data.get("urgent")
        or []
    )

    overdue = (
        v9_data.get("renewals_overdue_v9")
        or v9_data.get("renewals_overdue")
        or v9_data.get("overdue")
        or []
    )

    to_check = (
        v9_data.get("renewals_final")
        or v9_data.get("renewals_to_check")
        or []
    )

    active = (
        v9_data.get("renewals_active")
        or v9_data.get("active")
        or []
    )

    urgent_normal, urgent_anomalies = _split_integrity(urgent)
    overdue_normal, overdue_anomalies = _split_integrity(overdue)
    to_check_normal, to_check_anomalies = _split_integrity(to_check)

    all_anomalies = urgent_anomalies + overdue_anomalies + to_check_anomalies

    dashboard["sections"]["urgent"] = _format_list(urgent_normal)
    dashboard["sections"]["overdue"] = _format_list(overdue_normal)
    dashboard["sections"]["to_check"] = _format_list(to_check_normal)
    dashboard["sections"]["active"] = _format_list(active)
    dashboard["sections"]["anomalies"] = all_anomalies[:20]

    dashboard["pharmacist_work"]["patients_to_call"] = _safe_len(overdue_normal)
    dashboard["pharmacist_work"]["renewals_to_check"] = _safe_len(to_check_normal)
    dashboard["pharmacist_work"]["urgent_files"] = _safe_len(urgent_normal)
    dashboard["pharmacist_work"]["anomalies_count"] = _safe_len(all_anomalies)

    return dashboard
