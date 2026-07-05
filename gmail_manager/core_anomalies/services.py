from django.apps import apps
from django.db.models import Count

from core_anomalies.models import Anomaly


def find_prescription_model():
    for model in apps.get_models():
        if model.__name__.lower() == "prescription":
            return model
    return None


def enrich_anomaly(anomaly):
    anomaly.prescription_obj = None
    anomaly.patient_label = "Patient inconnu"

    Prescription = find_prescription_model()

    if not Prescription:
        return anomaly

    try:
        prescription = Prescription.objects.get(pk=anomaly.prescription_id)
        anomaly.prescription_obj = prescription

        patient = getattr(prescription, "patient", None)

        if patient:
            anomaly.patient_label = str(patient)
        else:
            anomaly.patient_label = "Patient non renseigné"

    except Exception:
        anomaly.patient_label = "Ordonnance introuvable"

    return anomaly


def enrich_list(anomalies):
    return [enrich_anomaly(a) for a in anomalies]


class AnomalyService:

    @staticmethod
    def get_all():
        return Anomaly.objects.all()

    @staticmethod
    def get_open():
        return Anomaly.objects.exclude(
            status__in=["RESOLUE", "IGNOREE"]
        )

    @staticmethod
    def get_critical():
        return Anomaly.objects.filter(
            severity="CRITIQUE"
        )

    @staticmethod
    def get_by_prescription(prescription_id):
        return Anomaly.objects.filter(
            prescription_id=prescription_id
        )

    @staticmethod
    def get_statistics():
        return {
            "total": Anomaly.objects.count(),
            "critical": Anomaly.objects.filter(severity="CRITIQUE").count(),
            "high": Anomaly.objects.filter(severity="ELEVEE").count(),
            "medium": Anomaly.objects.filter(severity="MOYENNE").count(),
            "low": Anomaly.objects.filter(severity="FAIBLE").count(),
            "resolved": Anomaly.objects.filter(status="RESOLUE").count(),
            "by_rule": list(
                Anomaly.objects.values("rule_code")
                .annotate(total=Count("id"))
                .order_by("-total")
            ),
        }
