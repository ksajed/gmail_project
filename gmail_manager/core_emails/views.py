from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST

from .models import Prescription, SenderType

from .models import Prescription, PrescriptionStatusHistory
from .states import PrescriptionStatusEnum
from core_attachments.models import PrescriptionAttachment

# =====================================================
# MODELS
# =====================================================
from .models import (
    Prescription,
    PrescriptionStatus,
    PrescriptionStatusHistory,
)

from .models_assignment import PrescriptionAssignment

# =====================================================
# SERVICES
# =====================================================
from .services import change_prescription_status
from .states import (
    PrescriptionStatusEnum,
    PRESCRIPTION_STATUS_TRANSITIONS,
)

# =====================================================
# EXTERNES
# =====================================================
from core_gmail.services import fetch_new_gmail_messages
from core_people.models import Person


# =====================================================
# DASHBOARD
# =====================================================
@login_required
def dashboard(request):
    """
    Tableau de bord pharmacie
    - KPI
    - Vues métier
    - Pagination paramétrable
    """

    status_filter = request.GET.get("status")
    view_filter = request.GET.get("view")
    page_number = request.GET.get("page")

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

    prescriptions_qs = (
        Prescription.objects
        .select_related("patient")
    )

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

    if status_filter:
        prescriptions_qs = prescriptions_qs.filter(status=status_filter)

    prescriptions_qs = prescriptions_qs.order_by("-received_at")

    paginator = Paginator(prescriptions_qs, per_page)
    prescriptions = paginator.get_page(page_number)

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

    context = {
        "prescriptions": prescriptions,
        "statuses": PrescriptionStatus.choices,
        "current_status": status_filter,
        "current_view": view_filter,
        "current_per_page": per_page,
        "total_prescriptions": sum(counters.values()),
        "count_received": counters[PrescriptionStatus.RECEIVED],
        "count_in_progress": counters[PrescriptionStatus.IN_PROGRESS],
        "count_ready": counters[PrescriptionStatus.READY],
        "count_delivered": counters[PrescriptionStatus.DELIVERED],
        "count_blocked": counters[PrescriptionStatus.BLOCKED],
        "count_archived": counters[PrescriptionStatus.ARCHIVED],
        "context_sender_types": SenderType.choices,
    }

    return render(request, "core_emails/dashboard.html", context)


# =====================================================
# DÉTAIL ORDONNANCE
# =====================================================
@login_required
def prescription_detail(request, pk):
    """
    Fiche ordonnance complète
    - Patient
    - Pièces jointes
    - Infirmier
    - Statut
    - Historique opposable
    """

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

    persons_nurses = (
        Person.objects
        .filter(role="nurse")
        .order_by("last_name", "first_name")
    )

    context = {
        "prescription": prescription,
        "attachments": attachments,
        "history": history,
        "allowed_statuses": allowed_statuses,
        "persons_nurses": persons_nurses,

        # ✅ AJOUT — nécessaire pour le select "Type d’ordonnance"
        "context_sender_types": SenderType.choices,
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
        messages.success(request, "Statut mis à jour avec succès.")
    except ValidationError as e:
        messages.error(request, str(e))

    return redirect("core_emails:prescription_detail", pk=pk)


# =====================================================
# AFFECTATION INFIRMIER (HISTORIQUE INCLUS)
# =====================================================

from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required

from .models import Prescription, SenderType
def assign_nurse(request, pk):
    prescription = get_object_or_404(Prescription, pk=pk)

    nurse_id = request.POST.get("nurse_id")
    if not nurse_id:
        messages.warning(request, "Aucun infirmier sélectionné.")
        return redirect("core_emails:prescription_detail", pk=pk)

    nurse = get_object_or_404(Person, pk=nurse_id, role="nurse")

    assignment, _ = PrescriptionAssignment.objects.get_or_create(
        prescription=prescription
    )
    assignment.nurse = nurse
    assignment.save()

    # 📝 Historique organisationnel
    PrescriptionStatusHistory.objects.create(
        prescription=prescription,
        old_status=prescription.status,
        new_status=prescription.status,
        changed_by=request.user,
        comment=(
            f"Infirmier affecté à l’ordonnance : "
            f"{nurse.first_name} {nurse.last_name}"
        ),
    )

    messages.success(request, "Infirmier affecté à l’ordonnance.")
    return redirect("core_emails:prescription_detail", pk=pk)


# =====================================================
# DÉSASSOCIATION INFIRMIER (HISTORIQUE INCLUS)
# =====================================================
@login_required
@require_POST
def unassign_nurse(request, pk):
    prescription = get_object_or_404(Prescription, pk=pk)

    try:
        assignment = PrescriptionAssignment.objects.get(
            prescription=prescription
        )
    except PrescriptionAssignment.DoesNotExist:
        messages.warning(request, "Aucune affectation à retirer.")
        return redirect("core_emails:prescription_detail", pk=pk)

    nurse = assignment.nurse
    assignment.delete()

    # 📝 Historique organisationnel
    PrescriptionStatusHistory.objects.create(
        prescription=prescription,
        old_status=prescription.status,
        new_status=prescription.status,
        changed_by=request.user,
        comment=(
            f"Infirmier retiré de l’ordonnance : "
            f"{nurse.first_name} {nurse.last_name}"
        ),
    )

    messages.success(request, "Infirmier retiré de l’ordonnance.")
    return redirect("core_emails:prescription_detail", pk=pk)


# =====================================================
# CRÉATION INFIRMIER
# =====================================================
@login_required
@require_POST
def create_nurse(request):
    """
    Création organisationnelle d’un infirmier
    - Email obligatoire (contrainte DB)
    """

    first_name = request.POST.get("first_name", "").strip()
    last_name = request.POST.get("last_name", "").strip()
    email = request.POST.get("email", "").strip().lower()

    if not first_name or not last_name or not email:
        messages.error(
            request,
            "Nom, prénom et email sont obligatoires pour créer un infirmier."
        )
        return redirect(request.META.get("HTTP_REFERER", "core_emails:dashboard"))

    nurse, created = Person.objects.get_or_create(
        email=email,
        defaults={
            "first_name": first_name,
            "last_name": last_name,
            "role": "nurse",
        },
    )

    if created:
        messages.success(request, "Infirmier créé avec succès.")
    else:
        messages.info(request, "Cet infirmier existe déjà.")

    return redirect(request.META.get("HTTP_REFERER", "core_emails:dashboard"))


# =====================================================
# SYNC GMAIL
# =====================================================
@login_required
def sync_gmail_now(request):
    try:
        fetch_new_gmail_messages()
        messages.success(request, "Synchronisation Gmail lancée.")
    except Exception as e:
        messages.error(request, f"Erreur Gmail : {e}")

    return redirect("core_emails:dashboard")


# =====================================================
# AUTH
# =====================================================
class PharmacyLoginView(LoginView):
    template_name = "auth/login.html"


class PharmacyLogoutView(LogoutView):
    pass
# =====================================================
# CHANGEMENT TYPE ORDONNANCE (EXPÉDITEUR)
# =====================================================

@login_required
@require_POST
def change_sender_type(request, pk):
    prescription = get_object_or_404(Prescription, pk=pk)

    sender_type = request.POST.get("sender_type")

    if sender_type in dict(SenderType.choices):
        prescription.sender_type = sender_type
        prescription.save(update_fields=["sender_type"])

    return redirect("core_emails:prescription_detail", pk=pk)


# =====================================================
# CRÉATION MANUELLE D’ORDONNANCE PAR LE PHARMACIEN
# =====================================================

@login_required
def prescription_create(request):
    """
    V3 — Création manuelle d’une ordonnance par le pharmacien
    """
    if request.method == "POST":
        sender_type = request.POST.get("sender_type")
        email = request.POST.get("email")

        # =====================================================
        # 1. CRÉATION DE L’ORDONNANCE
        # =====================================================
        prescription = Prescription.objects.create(
            sender_type=sender_type,
            status=PrescriptionStatusEnum.RECEIVED.value,
            created_by=request.user,
        )

        # =====================================================
        # 2. UPLOAD DES PIÈCES JOINTES (V3 + VALIDATION
        # =====================================================
        files = request.FILES.getlist("attachments")

        for f in files:
            if f.size > MAX_FILE_SIZE:
                messages.warning(
                    request,
                    f"Le fichier {f.name} dépasse la taille maximale "
                    f"de {MAX_FILE_SIZE // (1024 * 1024)} Mo et "
                    "n’a pas été ajouté."
                )
                continue
                # Type MIME autorisé
            if f.content_type not in ALLOWED_MIME_TYPES:
                messages.error(
                    request,
                    f"Le fichier {f.name} a un type MIME non autorisé "
                    f"({f.content_type}) et n’a pas été ajouté."
                )
                return redirect("core_emails:prescription_create")
            
            # Création de la pièce jointe
            PrescriptionAttachment.objects.create(
                prescription=prescription,
                file=f,
                original_filename=f.name,
                mime_type=f.content_type,
                uploaded_by=request.user,
            )
            # Optionnel : avertir si aucune PJ valide n’a été ajoutée
            if files and not prescription.attachments.exists():
                messages.error(
                    request,
                    "Aucune pièce jointe valide n’a été ajoutée "
                    "à l’ordonnance."
                )
                return redirect("core_emails:prescription_create")
        # =====================================================
        # 3. ASSOCIATION DU PATIENT (SI FOURNI)
        # =====================================================
        if email:
            from core_patients.models import Patient
            patient, _ = Patient.objects.get_or_create(email=email)
            prescription.patient = patient
            prescription.save()

        # =====================================================
        # 4. HISTORIQUE OPPOSABLE (CRÉATION)
        # =====================================================
        PrescriptionStatusHistory.objects.create(
            prescription=prescription,
            old_status=prescription.status,   # NOT NULL → OK
            new_status=prescription.status,   # statut initial
            changed_by=request.user,
        )

        # =====================================================
        # 5. REDIRECTION VERS LE DÉTAIL
        # =====================================================
        return redirect(
            "core_emails:prescription_detail",
            pk=prescription.pk,
        )

    # =====================================================
    # AFFICHAGE DU FORMULAIRE
    # =====================================================
    return render(
        request,
        "core_emails/prescription_create.html",
    )
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 Mo

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
}
