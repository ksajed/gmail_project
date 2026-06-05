
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
