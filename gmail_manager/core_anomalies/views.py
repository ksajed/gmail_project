from django.shortcuts import render

from core_anomalies.services import AnomalyService


def dashboard(request):
    context = {
        "stats": AnomalyService.get_statistics(),
        "anomalies": AnomalyService.get_open()[:50],
    }

    return render(
        request,
        "core_anomalies/dashboard.html",
        context,
    )
