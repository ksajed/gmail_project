# gmail_manager/core_emails/views.py

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib.auth.views import LoginView, LogoutView

from .models import (
    Prescription,
    PrescriptionStatus,
    PrescriptionStatusHistory,
)
from .services import change_prescription_status
from .states import (
    PrescriptionStatusEnum,
    PRESCRIPTION_STATUS_TRANSITIONS,
)

# ✅ Gmail
from core_gmail.services import fetch_new_gmail_messages


# =====================================================
# DASHBOARD
# =====================================================
@login_required
def dashboard(request):
    """
    Dashboard pharmacie
    - KPI métier
    - Vues intelligentes (?view=...)
    - Filtres
    - Pagination
    """

    # =========================
    # PARAMÈTRES
    # =========================
    status_filter = request.GET.get("status")
    view_filter = request.GET.get("view")
    page_number = request.GET.get("page")

    # =========================
    # LIGNES PAR PAGE
    # =========================
    allowed_per_page = (10, 25, 50)

    per_page = getattr(
        getattr(request.user, "profile", None),
        "per_page",
        10,
    )

    per_page_param = request.GET.get("per_page")
    if per_page_param:
        try:
            per_page_param = int(per_page_param)
            if per_page_param in allowed_per_page:
                per_page = per_page_param
                if hasattr(request.user, "profile"):
                    request.user.profile.per_page = per_page
                    request.user.profile.save(update_fields=["per_page"])
        except ValueError:
            pass

    # =========================
    # BASE QUERYSET (LISTE)
    # =========================
    prescriptions_qs = (
        Prescription.objects
        .select_related("patient")
    )

    # =========================
    # VUES MÉTIER
    # =========================
    if view_filter == "todo":
        prescriptions_qs = prescriptions_qs.filter(
            status__in=[
                PrescriptionStatus.RECEIVED,
                PrescriptionStatus.IN_PROGRESS,
            ]
        )
    elif view_filter == "blocked":
        prescriptions_qs = prescriptions_qs.filter(
            status=PrescriptionStatus.BLOCKED
        )
    elif view_filter == "archived":
        prescriptions_qs = prescriptions_qs.filter(
            status=PrescriptionStatus.ARCHIVED
        )

    # =========================
    # FILTRE STATUT
    # =========================
    if status_filter:
        prescriptions_qs = prescriptions_qs.filter(
            status=status_filter
        )

    prescriptions_qs = prescriptions_qs.order_by("-received_at")

    # =========================
    # PAGINATION
    # =========================
    paginator = Paginator(prescriptions_qs, per_page)
    prescriptions = paginator.get_page(page_number)

    # =========================
    # KPI GLOBAUX
    # =========================
    raw_stats = (
        Prescription.objects
        .values("status")
        .annotate(total=Count("id"))
    )

    counters = {
        PrescriptionStatus.RECEIVED: 0,
        PrescriptionStatus.IN_PROGRESS: 0,
        PrescriptionStatus.READY: 0,
        PrescriptionStatus.DELIVERED: 0,
        PrescriptionStatus.BLOCKED: 0,
        PrescriptionStatus.ARCHIVED: 0,
    }

    for row in raw_stats:
        if row["status"] in counters:
            counters[row["status"]] = row["total"]

    # =========================
    # CONTEXT
    # =========================
    context = {
        # LISTE
        "prescriptions": prescriptions,

        # FILTRES
        "statuses": PrescriptionStatus.choices,
        "current_status": status_filter,
        "current_view": view_filter,
        "current_per_page": per_page,

        # KPI
        "total_prescriptions": sum(counters.values()),
        "count_received": counters[PrescriptionStatus.RECEIVED],
        "count_in_progress": counters[PrescriptionStatus.IN_PROGRESS],
        "count_ready": counters[PrescriptionStatus.READY],
        "count_delivered": counters[PrescriptionStatus.DELIVERED],
        "count_blocked": counters[PrescriptionStatus.BLOCKED],
        "count_archived": counters[PrescriptionStatus.ARCHIVED],
    }

    return render(
        request,
        "core_emails/dashboard.html",
        context,
    )


# =====================================================
# DÉTAIL ORDONNANCE
# =====================================================
@login_required
def prescription_detail(request, pk):
    prescription = (
        Prescription.objects
        .select_related("patient")
        .get(pk=pk)
    )

    attachments = prescription.attachments.all()

    history = (
        PrescriptionStatusHistory.objects
        .filter(prescription=prescription)
        .select_related("changed_by")
        .order_by("-changed_at")
    )

    current_enum = PrescriptionStatusEnum(prescription.status)
    allowed_enums = PRESCRIPTION_STATUS_TRANSITIONS.get(current_enum, set())

    allowed_statuses = [
        (enum.value, enum.name.replace("_", " ").title())
        for enum in allowed_enums
    ]

    context = {
        "prescription": prescription,
        "attachments": attachments,
        "history": history,
        "allowed_statuses": allowed_statuses,
    }

    return render(
        request,
        "core_emails/prescription_detail.html",
        context,
    )


# =====================================================
# CHANGEMENT DE STATUT
# =====================================================
@login_required
def change_status(request, pk):
    prescription = get_object_or_404(Prescription, pk=pk)

    if request.method != "POST":
        messages.warning(request, "Action non autorisée.")
        return redirect("core_emails:prescription_detail", pk=pk)

    new_status = request.POST.get("status")

    if not new_status:
        messages.warning(request, "Aucun statut sélectionné.")
        return redirect("core_emails:prescription_detail", pk=pk)

    try:
        change_prescription_status(
            prescription=prescription,
            new_status=new_status,
            user=request.user,
        )
        messages.success(request, "✅ Statut mis à jour avec succès.")
    except ValidationError as e:
        messages.error(request, f"⛔ {e}")

    return redirect("core_emails:prescription_detail", pk=pk)


# =====================================================
# SYNC GMAIL
# =====================================================
@login_required
def sync_gmail_now(request):
    try:
        fetch_new_gmail_messages()
        messages.success(
            request,
            "📩 Synchronisation Gmail lancée avec succès."
        )
    except Exception as e:
        messages.error(
            request,
            f"⛔ Erreur lors de la synchronisation Gmail : {e}"
        )

    return redirect("core_emails:dashboard")


# =====================================================
# AUTH
# =====================================================
class PharmacyLoginView(LoginView):
    template_name = "auth/login.html"


class PharmacyLogoutView(LogoutView):
    pass
