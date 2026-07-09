from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core_anomalies.models import Anomaly
from core_anomalies.services import AnomalyService, enrich_anomaly, enrich_list


def dashboard(request):
    severity = request.GET.get("severity", "")
    q = request.GET.get("q", "")
    rule_code = request.GET.get("rule_code", "")

    anomalies = AnomalyService.get_open()

    if severity:
        anomalies = anomalies.filter(severity=severity)

    if q:
        anomalies = anomalies.filter(prescription_id__icontains=q)

    if rule_code:
        anomalies = anomalies.filter(rule_code=rule_code)

    context = {
        "stats": AnomalyService.get_statistics(),
        "anomalies": enrich_list(anomalies[:100]),
        "severity": severity,
        "q": q,
        "rule_code": rule_code,
        "rule_choices": AnomalyService.get_rule_choices(),
    }

    return render(request, "core_anomalies/dashboard.html", context)


def detail(request, pk):
    anomaly = enrich_anomaly(get_object_or_404(Anomaly, pk=pk))

    context = {
        "anomaly": anomaly,
        "prescription_url": f"/prescription/{anomaly.prescription_id}/",
        "patient_url": f"/admin-console/patients/{anomaly.patient_id}/edit/" if anomaly.patient_id else None,
        "statuses": Anomaly.STATUS_CHOICES,
    }

    return render(request, "core_anomalies/detail.html", context)


@require_POST
def change_status(request, pk):
    anomaly = get_object_or_404(Anomaly, pk=pk)
    new_status = request.POST.get("status")

    allowed = [x[0] for x in Anomaly.STATUS_CHOICES]

    if new_status in allowed:
        anomaly.status = new_status

        if new_status == "RESOLUE":
            anomaly.resolved_at = timezone.now()

        comment = request.POST.get("comment")
        if comment is not None:
            anomaly.comment = comment

        anomaly.save()

    return redirect("anomaly_detail", pk=anomaly.pk)
