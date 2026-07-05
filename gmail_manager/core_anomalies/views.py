from django.shortcuts import get_object_or_404, render

from core_anomalies.models import Anomaly
from core_anomalies.services import AnomalyService, enrich_anomaly, enrich_list


def dashboard(request):
    severity = request.GET.get("severity", "")
    q = request.GET.get("q", "")

    anomalies = AnomalyService.get_open()

    if severity:
        anomalies = anomalies.filter(severity=severity)

    if q:
        anomalies = anomalies.filter(prescription_id__icontains=q)

    context = {
        "stats": AnomalyService.get_statistics(),
        "anomalies": enrich_list(anomalies[:100]),
        "severity": severity,
        "q": q,
    }

    return render(request, "core_anomalies/dashboard.html", context)


def detail(request, pk):
    anomaly = enrich_anomaly(get_object_or_404(Anomaly, pk=pk))

    context = {
        "anomaly": anomaly,
        "prescription_url": f"/prescription/{anomaly.prescription_id}/",
    }

    return render(request, "core_anomalies/detail.html", context)
