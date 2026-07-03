from django.shortcuts import get_object_or_404, render

from core_anomalies.models import Anomaly
from core_anomalies.services import AnomalyService


def dashboard(request):
    context = {
        "stats": AnomalyService.get_statistics(),
        "anomalies": AnomalyService.get_open()[:100],
    }
    return render(request, "core_anomalies/dashboard.html", context)


def detail(request, pk):
    anomaly = get_object_or_404(Anomaly, pk=pk)

    context = {
        "anomaly": anomaly,
        "prescription_url": f"/prescription/{anomaly.prescription_id}/",
    }

    return render(request, "core_anomalies/detail.html", context)
