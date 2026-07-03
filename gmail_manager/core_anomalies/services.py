from django.db.models import Count

from core_anomalies.models import Anomaly


class AnomalyService:

    @staticmethod
    def get_all():
        return Anomaly.objects.all()

    @staticmethod
    def get_open():
        return Anomaly.objects.exclude(
            status__in=["RESOLVED", "IGNORED"]
        )

    @staticmethod
    def get_critical():
        return Anomaly.objects.filter(
            severity="CRITICAL"
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
            "critical": Anomaly.objects.filter(severity="CRITICAL").count(),
            "high": Anomaly.objects.filter(severity="HIGH").count(),
            "medium": Anomaly.objects.filter(severity="MEDIUM").count(),
            "low": Anomaly.objects.filter(severity="LOW").count(),
            "resolved": Anomaly.objects.filter(status="RESOLVED").count(),
            "by_rule": list(
                Anomaly.objects.values("rule_code")
                .annotate(total=Count("id"))
                .order_by("-total")
            ),
        }
