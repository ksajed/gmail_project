from django.db.models import Count

from core_anomalies.models import Anomaly


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
