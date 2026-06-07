
from __future__ import annotations

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render, get_object_or_404
from django.views.decorators.http import require_POST

from .permissions import superuser_required


def _admin_required(view_func):
    return login_required(superuser_required(view_func))


def _get_models():
    from core_emails import models as em

    return {
        "Rule": getattr(em, "RenewalNotificationRule", None),
        "Template": getattr(em, "RenewalNotificationTemplate", None),
        "Holiday": getattr(em, "Holiday", None),
    }


def _model_field_names(model):
    if not model:
        return set()
    return {f.name for f in model._meta.fields}


def _safe_bool(value):
    return str(value).lower() in ("1", "true", "on", "yes", "oui")


@_admin_required
def renewals_settings(request):
    """
    Paramètres généraux renouvellements.
    Pour ce lot : écran de synthèse non destructif.
    """
    models = _get_models()
    Rule = models["Rule"]
    Template = models["Template"]
    Holiday = models["Holiday"]

    context = {
        "rules_count": Rule.objects.count() if Rule else 0,
        "templates_count": Template.objects.count() if Template else 0,
        "holidays_count": Holiday.objects.count() if Holiday else 0,
        "engine_status": "Actif",
    }

    if request.method == "POST":
        messages.success(request, "Paramètres renouvellements vérifiés. Aucun changement moteur appliqué.")
        return redirect("core_adminconsole:renewals_settings")

    return render(request, "core_adminconsole/renewals_settings.html", context)


@_admin_required
def renewals_rules(request):
    """
    Gestion des règles de notification renouvellements.
    Création / modification simple.
    Suppression séparée en POST.
    """
    Rule = _get_models()["Rule"]
    if Rule is None:
        messages.error(request, "Modèle RenewalNotificationRule introuvable.")
        return render(request, "core_adminconsole/renewals_rules.html", {"rules": []})

    rule_fields = _model_field_names(Rule)

    form_fields = [
        f for f in [
            "name",
            "active",
            "days_before",
            "send_sms",
            "send_email",
            "sort_order",
        ]
        if f in rule_fields
    ]

    class RuleForm(forms.ModelForm):
        class Meta:
            model = Rule
            fields = form_fields

    edit_id = request.GET.get("edit")
    instance = None
    if edit_id:
        instance = get_object_or_404(Rule, pk=edit_id)

    if request.method == "POST":
        rule_id = request.POST.get("rule_id")
        instance = Rule.objects.filter(pk=rule_id).first() if rule_id else None
        form = RuleForm(request.POST, instance=instance)
        if form.is_valid():
            obj = form.save()
            messages.success(request, f"Règle enregistrée : {getattr(obj, 'name', obj)}")
            return redirect("core_adminconsole:renewals_rules")
        messages.error(request, "Formulaire règle invalide.")
    else:
        form = RuleForm(instance=instance)

    rules = Rule.objects.all().order_by("sort_order", "-days_before", "name")

    return render(request, "core_adminconsole/renewals_rules.html", {
        "rules": rules,
        "form": form,
        "edit_obj": instance,
    })


@require_POST
@_admin_required
def renewals_rule_delete(request, pk: int):
    Rule = _get_models()["Rule"]
    if Rule is None:
        messages.error(request, "Modèle RenewalNotificationRule introuvable.")
        return redirect("core_adminconsole:renewals_rules")

    obj = get_object_or_404(Rule, pk=pk)
    label = getattr(obj, "name", str(obj))
    obj.delete()
    messages.success(request, f"Règle supprimée : {label}")
    return redirect("core_adminconsole:renewals_rules")


@_admin_required
def renewals_templates(request):
    """
    Gestion templates SMS / Email renouvellements.
    """
    Template = _get_models()["Template"]
    if Template is None:
        messages.error(request, "Modèle RenewalNotificationTemplate introuvable.")
        return render(request, "core_adminconsole/renewals_templates.html", {"templates": []})

    template_fields = _model_field_names(Template)

    template_form_fields = [
        f for f in ["name", "channel", "active", "subject", "body"]
        if f in template_fields
    ]

    template_widgets = {}
    if "body" in template_fields:
        template_widgets["body"] = forms.Textarea(attrs={"rows": 8})
    if "subject" in template_fields:
        template_widgets["subject"] = forms.TextInput(attrs={"style": "width:100%;"})

    class TemplateForm(forms.ModelForm):
        class Meta:
            model = Template
            fields = template_form_fields
            widgets = template_widgets

    edit_id = request.GET.get("edit")
    instance = Template.objects.filter(pk=edit_id).first() if edit_id else None

    if request.method == "POST":
        tpl_id = request.POST.get("template_id")
        instance = Template.objects.filter(pk=tpl_id).first() if tpl_id else None
        form = TemplateForm(request.POST, instance=instance)
        if form.is_valid():
            obj = form.save()
            messages.success(request, f"Template enregistré : {getattr(obj, 'name', obj)}")
            return redirect("core_adminconsole:renewals_templates")
        messages.error(request, "Formulaire template invalide.")
    else:
        form = TemplateForm(instance=instance)

    templates = Template.objects.all().order_by("channel", "name")

    return render(request, "core_adminconsole/renewals_templates.html", {
        "templates": templates,
        "form": form,
        "edit_obj": instance,
    })


@_admin_required
def renewals_holidays(request):
    """
    Gestion jours fermés.
    Compatible si le modèle Holiday existe.
    """
    Holiday = _get_models()["Holiday"]
    if Holiday is None:
        messages.error(request, "Modèle Holiday introuvable.")
        return render(request, "core_adminconsole/renewals_holidays.html", {
            "holidays": [],
            "form": None,
            "holiday_model_missing": True,
        })

    holiday_fields = _model_field_names(Holiday)

    holiday_form_fields = [
        f for f in ["date", "name", "label", "active"]
        if f in holiday_fields
    ]

    holiday_widgets = {}
    if "date" in holiday_fields:
        holiday_widgets["date"] = forms.DateInput(attrs={"type": "date"})

    class HolidayForm(forms.ModelForm):
        class Meta:
            model = Holiday
            fields = holiday_form_fields
            widgets = holiday_widgets

    edit_id = request.GET.get("edit")
    instance = Holiday.objects.filter(pk=edit_id).first() if edit_id else None

    if request.method == "POST":
        holiday_id = request.POST.get("holiday_id")
        instance = Holiday.objects.filter(pk=holiday_id).first() if holiday_id else None
        form = HolidayForm(request.POST, instance=instance)
        if form.is_valid():
            obj = form.save()
            messages.success(request, f"Jour fermé enregistré : {obj}")
            return redirect("core_adminconsole:renewals_holidays")
        messages.error(request, "Formulaire jour fermé invalide.")
    else:
        form = HolidayForm(instance=instance)

    holidays = Holiday.objects.all().order_by("-date") if "date" in holiday_fields else Holiday.objects.all().order_by("-id")

    return render(request, "core_adminconsole/renewals_holidays.html", {
        "holidays": holidays,
        "form": form,
        "edit_obj": instance,
        "holiday_model_missing": False,
    })


@require_POST
@_admin_required
def renewals_holiday_delete(request, pk: int):
    Holiday = _get_models()["Holiday"]
    if Holiday is None:
        messages.error(request, "Modèle Holiday introuvable.")
        return redirect("core_adminconsole:renewals_holidays")

    obj = get_object_or_404(Holiday, pk=pk)
    label = str(obj)
    obj.delete()
    messages.success(request, f"Jour fermé supprimé : {label}")
    return redirect("core_adminconsole:renewals_holidays")


@_admin_required

@_admin_required
def renewals_logs(request):
    """
    Logs automatiques renouvellements V9.
    Lecture seule.
    Filtrage par période et par type de log.
    """
    from pathlib import Path
    from django.utils.dateparse import parse_date
    from django.utils import timezone
    from datetime import datetime, time

    log_type = request.GET.get("type", "all")
    date_from_raw = request.GET.get("from", "")
    date_to_raw = request.GET.get("to", "")

    date_from = parse_date(date_from_raw) if date_from_raw else None
    date_to = parse_date(date_to_raw) if date_to_raw else None

    dt_from = None
    dt_to = None

    if date_from:
        dt_from = timezone.make_aware(datetime.combine(date_from, time.min))
    if date_to:
        dt_to = timezone.make_aware(datetime.combine(date_to, time.max))

    def apply_range(qs, field):
        if dt_from:
            qs = qs.filter(**{f"{field}__gte": dt_from})
        if dt_to:
            qs = qs.filter(**{f"{field}__lte": dt_to})
        return qs

    sms_messages = []
    sms_attempts = []
    renewal_events = []
    status_history = []
    file_logs = []

    if log_type in ("all", "sms"):
        try:
            from core_notifications.models import SmsMessage
            qs = SmsMessage.objects.select_related("related_prescription").order_by("-created_at")
            qs = apply_range(qs, "created_at")
            sms_messages = qs[:200]
        except Exception:
            sms_messages = []

    if log_type in ("all", "attempts"):
        try:
            from core_notifications.models import SmsAttempt
            qs = SmsAttempt.objects.select_related("sms_message").order_by("-requested_at")
            qs = apply_range(qs, "requested_at")
            sms_attempts = qs[:200]
        except Exception:
            sms_attempts = []

    if log_type in ("all", "events"):
        try:
            from core_emails.models import PrescriptionRenewalEvent
            qs = PrescriptionRenewalEvent.objects.select_related("prescription", "created_by").order_by("-ordered_at")
            qs = apply_range(qs, "ordered_at")
            renewal_events = qs[:200]
        except Exception:
            renewal_events = []

    if log_type in ("all", "history"):
        try:
            from core_emails.models import PrescriptionStatusHistory
            qs = (
                PrescriptionStatusHistory.objects
                .select_related("prescription", "changed_by")
                .filter(comment__icontains="renouvellement")
                .order_by("-changed_at")
            )
            qs = apply_range(qs, "changed_at")
            status_history = qs[:200]
        except Exception:
            status_history = []

    if log_type in ("all", "cron"):
        try:
            log_path = Path("/home/ksajed/gmail_project/logs/renewals.log")
            if log_path.exists():
                lines = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()
                file_logs = lines[-300:]
        except Exception:
            file_logs = []

    counts = {
        "sms": len(sms_messages),
        "attempts": len(sms_attempts),
        "events": len(renewal_events),
        "history": len(status_history),
        "cron": len(file_logs),
    }

    return render(request, "core_adminconsole/renewals_logs.html", {
        "sms_messages": sms_messages,
        "sms_attempts": sms_attempts,
        "renewal_events": renewal_events,
        "status_history": status_history,
        "file_logs": file_logs,
        "counts": counts,
        "log_type": log_type,
        "date_from": date_from_raw,
        "date_to": date_to_raw,
    })


@_admin_required
def renewals_stats(request):
    """
    Statistiques Renouvellements V9.
    Lecture seule.
    """
    from datetime import timedelta
    from django.utils import timezone
    from django.utils.dateparse import parse_date

    period = request.GET.get("period", "today")
    custom_from = request.GET.get("from", "")
    custom_to = request.GET.get("to", "")

    today = timezone.localdate()

    if period == "7d":
        date_from = today - timedelta(days=6)
        date_to = today
    elif period == "30d":
        date_from = today - timedelta(days=29)
        date_to = today
    elif period == "month":
        date_from = today.replace(day=1)
        date_to = today
    elif period == "custom":
        date_from = parse_date(custom_from) or today
        date_to = parse_date(custom_to) or today
    else:
        period = "today"
        date_from = today
        date_to = today

    stats = {
        "sms_sent": 0,
        "sms_failed": 0,
        "email_marked": 0,
        "cycles_created": 0,
        "cycles_closed": 0,
        "due_notifications_today": 0,
        "overdue_detected": 0,
        "urgent_detected": 0,
        "final_renewals": 0,
        "active_cycles": 0,
        "confirmed_cycles": 0,
        "preparing_cycles": 0,
        "ready_cycles": 0,
    }

    def make_dt_range(d1, d2):
        from datetime import datetime, time
        start = timezone.make_aware(datetime.combine(d1, time.min))
        end = timezone.make_aware(datetime.combine(d2, time.max))
        return start, end

    dt_from, dt_to = make_dt_range(date_from, date_to)

    try:
        from core_notifications.models import SmsMessage
        stats["sms_sent"] = SmsMessage.objects.filter(
            sent_at__gte=dt_from,
            sent_at__lte=dt_to,
            status="SENT",
        ).count()
        stats["sms_failed"] = SmsMessage.objects.filter(
            created_at__gte=dt_from,
            created_at__lte=dt_to,
            status="FAILED",
        ).count()
    except Exception:
        pass

    try:
        from django.db.models import Q
        from core_emails.models import PrescriptionRenewalCycle, PrescriptionStatus

        stats["cycles_created"] = PrescriptionRenewalCycle.objects.filter(
            started_at__gte=dt_from,
            started_at__lte=dt_to,
        ).count()

        stats["cycles_closed"] = PrescriptionRenewalCycle.objects.filter(
            closed_at__gte=dt_from,
            closed_at__lte=dt_to,
        ).count()

        email_q = (
            Q(reminder_5_patient_email_sent_at__gte=dt_from, reminder_5_patient_email_sent_at__lte=dt_to)
            | Q(reminder_3_patient_email_sent_at__gte=dt_from, reminder_3_patient_email_sent_at__lte=dt_to)
            | Q(doctor_email_sent_at__gte=dt_from, doctor_email_sent_at__lte=dt_to)
        )
        stats["email_marked"] = PrescriptionRenewalCycle.objects.filter(email_q).distinct().count()

        active_qs = PrescriptionRenewalCycle.objects.filter(closed_at__isnull=True).exclude(status=PrescriptionStatus.DELIVERED)
        stats["active_cycles"] = active_qs.count()
        stats["confirmed_cycles"] = active_qs.filter(status=PrescriptionStatus.RECEIVED).count()
        stats["preparing_cycles"] = active_qs.filter(status=PrescriptionStatus.IN_PROGRESS).count()
        stats["ready_cycles"] = active_qs.filter(status=PrescriptionStatus.READY).count()
    except Exception:
        pass

    try:
        from core_emails.services_renewal_rules import (
            get_due_notifications,
            get_overdue_renewals,
            get_urgent_renewals,
            get_final_renewals,
        )

        stats["due_notifications_today"] = len(get_due_notifications(today=today))
        stats["overdue_detected"] = len(get_overdue_renewals(today=today))
        stats["urgent_detected"] = len(get_urgent_renewals(today=today))
        stats["final_renewals"] = len(get_final_renewals(today=today))
    except Exception:
        pass

    return render(request, "core_adminconsole/renewals_stats.html", {
        "stats": stats,
        "period": period,
        "date_from": date_from,
        "date_to": date_to,
        "custom_from": custom_from,
        "custom_to": custom_to,
    })
