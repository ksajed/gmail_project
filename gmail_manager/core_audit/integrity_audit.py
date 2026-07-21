from django.apps import apps
from core_integrity.services import run_integrity_for_prescription, integrity_score

def find_prescription_model():
    for model in apps.get_models():
        if model.__name__.lower() == "prescription":
            return model
    return None


def audit_prescriptions(limit=None):
    Prescription = find_prescription_model()

    if not Prescription:
        return {
            "total": 0,
            "items": [],
            "error": "Modèle Prescription introuvable",
        }

    qs = Prescription.objects.all().order_by("id")
    if limit:
        qs = qs[:limit]

    items = []

    for prescription in qs:
        results = run_integrity_for_prescription(prescription)
        score = integrity_score(results)

        if results:
            items.append({
                "prescription_id": prescription.pk,
                "prescription": str(prescription),
                "score": score,
                "results": results,
            })

    return {
        "total": Prescription.objects.count(),
        "anomalies_count": len(items),
        "items": items,
    }
