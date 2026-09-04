from core_emails.services_renewal_v10 import compute_renewals_dashboard_v10
# =====================================================
# DJANGO
# =====================================================
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .models import PrescriptionRenewalInfo

import datetime
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.dateparse import parse_date
from django.core.mail import send_mail
import logging

logger = logging.getLogger(__name__)

from django.core.validators import validate_email
from django.db import transaction
# =====================================================
# MODELS — CORE EMAILS
# =====================================================
from .models import (
    Prescription,
    PrescriptionStatus,
    PrescriptionStatusHistory,
    PrescriptionType,
    RenewalNotificationRule,
    SenderType,
)
from .models_assignment import PrescriptionAssignment
from core_emails.models import PrescriptionRenewalEvent, PrescriptionRenewalCycle

# =====================================================
# STATES & SERVICES
# =====================================================
from .states import PrescriptionStatusEnum, PRESCRIPTION_STATUS_TRANSITIONS
from .services_workflow import change_prescription_status
from .services import send_prescription_notifications
from .services_renewal_templates import render_renewal_message
from .services_renewal_rules import (
    _rule_channel_already_sent,
    mark_rule_channel_sent,
)
from core_emails.services import compute_renewals_watch, compute_renewals_watch_v9
from core_emails.timeline import build_prescription_timeline_events


def _is_prescription_structure_locked(prescription) -> bool:
    """Verrouillage structurel durable.

    Une ordonnance n'est plus structurellement modifiable dès qu'elle a
    commencé son traitement au moins une fois.
    """
    return getattr(prescription, "processing_started_at", None) is not None

# =====================================================
# EXTERNES
# =====================================================
from core_attachments.models import PrescriptionAttachment
from core_gmail.services import fetch_new_gmail_messages
from core_people.models import Person

# (Optionnel) Si tu utilises Patient
from core_patients.models import Patient
from core_notifications.models import SmsPurpose
from core_notifications.messages_sms import render_status_sms_rgpd_bilingual_compact
from core_notifications.utils_phone import to_e164_fr

# =====================================================
# CONSTANTES PJ (évite NameError)
# =====================================================
MAX_FILE_SIZE = getattr(settings, "PRESCRIPTION_MAX_FILE_SIZE", 10 * 1024 * 1024)  # 10 Mo par défaut
ALLOWED_MIME_TYPES = tuple(
    getattr(
        settings,
        "PRESCRIPTION_ALLOWED_MIME_TYPES",
        (
            "application/pdf",
            "image/jpeg",
            "image/png",
        ),
    )
)

# =====================================================
# AUTH (Login/Logout)
# =====================================================

class PharmacyLoginView(LoginView):
    # adapte si ton template est ailleurs
    template_name = "core_emails/login.html"
    redirect_authenticated_user = True

class PharmacyLogoutView(LogoutView):
    # redirige vers la page login après logout
    next_page = reverse_lazy("core_emails:login")

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
    search_query = (request.GET.get("q") or "").strip()
    page_number = request.GET.get("page")

    allowed_per_page = (10, 25, 50)

    per_page = getattr(getattr(request.user, "profile", None), "per_page", 10)

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

    prescriptions_qs = Prescription.objects.select_related("patient").filter(is_deleted=False)

    if view_filter == "todo":
        prescriptions_qs = prescriptions_qs.filter(
            status__in=[PrescriptionStatus.RECEIVED, PrescriptionStatus.IN_PROGRESS]
        )
    elif view_filter == "blocked":
        prescriptions_qs = prescriptions_qs.filter(
            status__in=[PrescriptionStatus.BLOCKED, PrescriptionStatus.REJECTED]
        )
    elif view_filter == "archived":
        prescriptions_qs = prescriptions_qs.filter(status=PrescriptionStatus.ARCHIVED)

    # Sécurité simple : n'appliquer le filtre que si valeur valide
    if status_filter and status_filter in dict(PrescriptionStatus.choices):
        prescriptions_qs = prescriptions_qs.filter(status=status_filter)

    if search_query:
        q_obj = (
            Q(patient__email__icontains=search_query) |
            Q(patient__full_name__icontains=search_query) |
            Q(sender_type__icontains=search_query)
        )

        cleaned_ref = search_query.replace("#", "").strip()
        if cleaned_ref.isdigit():
            q_obj = q_obj | Q(id=int(cleaned_ref))

        prescriptions_qs = prescriptions_qs.filter(q_obj)

    prescriptions_qs = prescriptions_qs.order_by("-received_at")

    paginator = Paginator(prescriptions_qs, per_page)
    prescriptions = paginator.get_page(page_number)

    raw_stats = Prescription.objects.filter(is_deleted=False).values("status").annotate(total=Count("id"))

    counters = {
        PrescriptionStatus.RECEIVED: 0,
        PrescriptionStatus.IN_PROGRESS: 0,
        PrescriptionStatus.READY: 0,
        PrescriptionStatus.DELIVERED: 0,
        PrescriptionStatus.REJECTED: 0,
        PrescriptionStatus.BLOCKED: 0,
        PrescriptionStatus.ARCHIVED: 0,
    }

    for row in raw_stats:
        if row["status"] in counters:
            counters[row["status"]] = row["total"]
    # ORDO V9 - Données renouvellements enrichies.
    # Compatibilité : ces données sont ajoutées au contexte sans modifier l'affichage actuel.
    try:
        renewals_v9_context = compute_renewals_watch_v9()
    except Exception:
        renewals_v9_context = {
            "renewals_notifications_due": [],
            "renewals_overdue_v9": [],
            "renewals_urgent": [],
            "renewals_final": [],
            "activity_metrics": {},
        }

    context = {
        "prescriptions": prescriptions,
        "statuses": PrescriptionStatus.choices,
        "current_status": status_filter,
        "current_view": view_filter,
        "current_search": search_query,
        "current_per_page": per_page,
        "total_prescriptions": sum(counters.values()),
        "count_received": counters[PrescriptionStatus.RECEIVED],
        "count_in_progress": counters[PrescriptionStatus.IN_PROGRESS],
        "count_ready": counters[PrescriptionStatus.READY],
        "count_delivered": counters[PrescriptionStatus.DELIVERED],
        "count_blocked": counters[PrescriptionStatus.BLOCKED] + counters[PrescriptionStatus.REJECTED],
        "count_archived": counters[PrescriptionStatus.ARCHIVED],
        "context_sender_types": SenderType.choices,
    }

    # ORDO V9 - Injection non destructive des données renouvellements.
    context.update(renewals_v9_context)

    return render(request, "core_emails/dashboard.html", context)

# =====================================================
# DÉTAIL ORDONNANCE
# =====================================================

@login_required
def renewals_dashboard(request):
    """
    ORDO V10 - Dashboard Renouvellements lecture seule.

    Cette vue utilise le service V10 sans modifier le moteur V9.
    """
    context = compute_renewals_dashboard_v10()
    return render(request, "core_emails/renewals_dashboard_v10.html", context)

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
    prescription = get_object_or_404(
        Prescription.objects.select_related("patient").prefetch_related("attachments"),
        pk=pk,
    )
    # =====================================================
    # INFIRMIER AFFECTÉ (SI EXISTE)
    # =====================================================
    
    assignment = (
        PrescriptionAssignment.objects
        .select_related("nurse")
        .filter(prescription=prescription)
        .first()
    )
    assigned_nurse = assignment.nurse if assignment and assignment.nurse else None

    attachments = prescription.attachments.all()

    history = (
        PrescriptionStatusHistory.objects.filter(prescription=prescription)
        .select_related("changed_by")
        .order_by("-changed_at")
    )

    timeline_events = build_prescription_timeline_events(prescription)

    # UI-C: les ordonnances de renouvellement ne doivent pas suivre le mode
    # "archivé classique" du parent. L'UI suit les cycles, pas le ARCHIVED parent.
    if prescription.type == PrescriptionType.RENOUVELLEMENT:
        ui_is_archived = False
        ui_history = history.exclude(new_status=PrescriptionStatus.ARCHIVED)
        ui_timeline_events = [
            e for e in timeline_events
            if getattr(e, "kind", "") != "archive"
            and "ARCHIV" not in (getattr(e, "subtitle", "") or "").upper()
        ]
    else:
        ui_is_archived = (prescription.status == PrescriptionStatus.ARCHIVED)
        ui_history = history
        ui_timeline_events = timeline_events

    current_enum = PrescriptionStatusEnum(prescription.status)
    allowed_enums = PRESCRIPTION_STATUS_TRANSITIONS.get(current_enum, set())

    allowed_statuses = [
        (enum.value, enum.name.replace("_", " ").title()) for enum in allowed_enums
    ]

    # UI-E: pour une ordonnance RENOUVELLEMENT encore active,
    # ne pas proposer ARCHIVED dans le dropdown classique.
    if prescription.type == PrescriptionType.RENOUVELLEMENT:
        try:
            tmp_info, _ = PrescriptionRenewalInfo.objects.get_or_create(prescription=prescription)
            tmp_times = int(getattr(tmp_info, "renewal_times", 0) or 0)
            tmp_done = int(getattr(tmp_info, "renewal_done_count", 0) or 0)
        except Exception:
            tmp_times = 0
            tmp_done = 0

        if tmp_done < tmp_times:
            allowed_statuses = [
                (value, label)
                for (value, label) in allowed_statuses
                if value != PrescriptionStatus.ARCHIVED
            ]

    persons_nurses = Person.objects.filter(role__in=["nurse","NURSE"]).order_by("last_name", "first_name")
    renewal_info = None
    renewal_remaining = None

    renewal_end_date = None
    renewal_days_left = None
    renewal_validity_total_days = None

    renewal_patient_first_delivered_at = None
    renewal_patient_end_date = None
    renewal_patient_days_left = None
    renewal_patient_bucket = None
    renewal_patient_next_number = None

    renewal_events = []
    if prescription.type == PrescriptionType.RENOUVELLEMENT:
        renewal_info, _ = PrescriptionRenewalInfo.objects.get_or_create(prescription=prescription)
    # --- Renewal cycle affiché dans l'UI (V9) ---
    # Source officielle : PrescriptionRenewalCycle.
    # Important : une vue de détail ne doit jamais créer de cycle métier.
    renewal_cycle = None
    renewal_cycle_number = None
    if getattr(prescription, "type", None) == PrescriptionType.RENOUVELLEMENT:
        open_cycle = (
            PrescriptionRenewalCycle.objects
            .filter(prescription=prescription, closed_at__isnull=True)
            .order_by("-cycle_number")
            .first()
        )

        if open_cycle:
            renewal_cycle = open_cycle
            renewal_cycle_number = int(open_cycle.cycle_number)
        else:
            last_cycle = (
                PrescriptionRenewalCycle.objects
                .filter(prescription=prescription)
                .order_by("-cycle_number")
                .first()
            )
            renewal_cycle = last_cycle
            renewal_cycle_number = int(last_cycle.cycle_number) if last_cycle else None

        renewal_remaining = max(
            0,
            int(renewal_info.renewal_times) - int(renewal_info.renewal_done_count),
        )

        # --------------------------
        # A) Validité ordonnance (date médecin)
        # --------------------------
        today = timezone.localtime(timezone.now()).date()
        if prescription.established_at:
            renewal_validity_total_days = (
                (int(renewal_info.renewal_times) + 1) * int(renewal_info.period_days)
            )
            renewal_end_date = prescription.established_at + datetime.timedelta(
                days=renewal_validity_total_days
            )
            renewal_days_left = (renewal_end_date - today).days

        # --------------------------
        # B) Rappels patient (1er retrait = 1ère DELIVERED)
        # --------------------------
        first_delivered_at = (
            PrescriptionStatusHistory.objects
            .filter(prescription=prescription, new_status=PrescriptionStatus.DELIVERED)
            .order_by('changed_at')
            .values_list('changed_at', flat=True)
            .first()
        )
        if first_delivered_at:
            renewal_patient_first_delivered_at = timezone.localtime(first_delivered_at)
            start_date = renewal_patient_first_delivered_at.date()
            # V9 : le prochain cycle patient affiché doit être le cycle ouvert réel.
            renewal_patient_next_number = renewal_cycle_number or (int(renewal_info.renewal_done_count) + 1)
            renewal_patient_end_date = start_date + datetime.timedelta(
                days=renewal_patient_next_number * int(renewal_info.period_days)
            )
            renewal_patient_days_left = (renewal_patient_end_date - today).days
            if renewal_patient_days_left == 5:
                renewal_patient_bucket = 'J-5'
            elif renewal_patient_days_left == 1:
                renewal_patient_bucket = 'J-1'
            elif renewal_patient_days_left < 0:
                renewal_patient_bucket = 'RETARD'
            else:
                renewal_patient_bucket = 'HORS_LISTE'
        else:
            renewal_patient_bucket = 'NON_DEMARRE'

        # Historique des renouvellements — source officielle = cycles
        renewal_events = list(
            PrescriptionRenewalCycle.objects
            .filter(prescription=prescription)
            .order_by('cycle_number')
        )
    structure_locked = _is_prescription_structure_locked(prescription)

    context = {
        'renewal_cycle': renewal_cycle,
        'renewal_cycle_number': renewal_cycle_number,
        "context_structure_locked": structure_locked,
    "prescription": prescription,
    "attachments": attachments,
    "history": history,
    "timeline_events": timeline_events,
    "ui_history": ui_history,
    "ui_timeline_events": ui_timeline_events,
    "ui_is_archived": ui_is_archived,
    "allowed_statuses": allowed_statuses,
    "persons_nurses": persons_nurses,
    "assigned_nurse": assigned_nurse,

    # Expéditeur
    "context_sender_types": SenderType.choices,

    # Type d’ordonnance
    "context_prescription_types": PrescriptionType.choices,

    # V7 — RENOUVELLEMENT
    "renewal_info": renewal_info,
    "renewal_remaining": renewal_remaining,
    "renewal_end_date": renewal_end_date,
    "renewal_days_left": renewal_days_left,
    "renewal_validity_total_days": renewal_validity_total_days,
    "renewal_patient_first_delivered_at": renewal_patient_first_delivered_at,
    "renewal_patient_end_date": renewal_patient_end_date,
    "renewal_patient_days_left": renewal_patient_days_left,
    "renewal_patient_bucket": renewal_patient_bucket,
    "renewal_patient_next_number": renewal_patient_next_number,
    "renewal_events": renewal_events,
            }

    return render(request, "core_emails/prescription_detail.html", context)

# =====================================================
# CHANGEMENT DE STATUT
# =====================================================
@login_required
@require_POST
def change_status(request, pk):
    prescription = get_object_or_404(Prescription, pk=pk)
    new_status = request.POST.get("status")
    notification_message = (request.POST.get("notification_message") or "").strip()
    # ORDO_NOTIF_FREE_TEXT_V2_BACKEND: message libre optionnel (pharmacien)
    if not new_status:
        messages.warning(request, "Aucun statut sélectionné.")
        return redirect("core_emails:prescription_detail", pk=pk)

    status_changed = False
    try:
        change_prescription_status(
            prescription=prescription,
            new_status=new_status,
            user=request.user,
            notification_message=notification_message,
        )
        messages.success(request, "Statut mis à jour avec succès.")
        status_changed = True
    except ValidationError as e:
        # Message plus clair + liste des choix autorisés
        try:
            current_enum = PrescriptionStatusEnum(prescription.status)
            allowed = PRESCRIPTION_STATUS_TRANSITIONS.get(current_enum, set())
            allowed_labels = ", ".join(
                [enum.name.replace("_", " ").title() for enum in allowed]
            ) or "Aucun"
            messages.error(
                request,
                f"Changement de statut interdit. Choix possibles : {allowed_labels}."
            )
        except Exception:
            messages.error(request, str(e))
    return redirect("core_emails:prescription_detail", pk=pk)

# AFFECTATION INFIRMIER (HISTORIQUE INCLUS)
# =====================================================
@login_required
@require_POST
def assign_nurse(request, pk):
    prescription = get_object_or_404(Prescription, pk=pk)

    nurse_id = request.POST.get("nurse_id")
    if not nurse_id:
        messages.warning(request, "Aucun infirmier sélectionné.")
        return redirect("core_emails:prescription_detail", pk=pk)

    nurse = get_object_or_404(Person, pk=nurse_id, role__in=["nurse","NURSE"])

    assignment, _ = PrescriptionAssignment.objects.get_or_create(prescription=prescription)
    assignment.nurse = nurse
    assignment.save(update_fields=["nurse"])

    # 📝 Historique organisationnel
    PrescriptionStatusHistory.objects.create(
        prescription=prescription,
        old_status=prescription.status,
        new_status=prescription.status,
        changed_by=request.user,
        comment=f"Infirmier affecté à l’ordonnance : {nurse.first_name} {nurse.last_name}",
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
        assignment = PrescriptionAssignment.objects.get(prescription=prescription)
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
        comment=f"Infirmier retiré de l’ordonnance : {nurse.first_name} {nurse.last_name}",
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
    - Email obligatoire
    - Téléphone FR obligatoire (normalisé en E.164)
    """
    first_name = request.POST.get("first_name", "").strip()
    last_name = request.POST.get("last_name", "").strip()
    email = request.POST.get("email", "").strip().lower()
    phone_raw = request.POST.get("phone_number", "").strip()
    phone_e164 = to_e164_fr(phone_raw)

    if not first_name or not last_name or not email or not phone_e164:
        messages.error(
            request,
            "Nom, prénom, email et téléphone (France) sont obligatoires pour créer un infirmier.",
        )
        return redirect(request.META.get("HTTP_REFERER") or "core_emails:dashboard")

    nurse, created = Person.objects.get_or_create(
        email=email,
        defaults={
            "first_name": first_name,
            "last_name": last_name,
            "role": "nurse",
            "phone": phone_e164,
        },
    )

    # Si l’infirmier existait déjà, on met à jour le téléphone si manquant/différent
    if not created:
        current = (getattr(nurse, "phone", "") or "").strip()
        if not current or current != phone_e164:
            nurse.phone = phone_e164
            nurse.save(update_fields=["phone"])

    if created:
        messages.success(request, "Infirmier créé avec succès.")
    else:
        messages.info(request, "Cet infirmier existe déjà (téléphone mis à jour si nécessaire).")

    return redirect(request.META.get("HTTP_REFERER") or "core_emails:dashboard")

# =====================================================
# SYNC GMAIL
# =====================================================
@login_required
def sync_gmail_now(request):
    """
    Sync Gmail (UI SaaS: appelé en AJAX depuis le dashboard)
    - Si XHR: renvoie JSON {ok, message, stats}
    - Sinon: messages + redirect dashboard
    """
    # IMPORTANT: éviter de rater des emails déjà "vus" => on scanne une fenêtre récente et on déduplique en DB
    criteria = ["X-GM-RAW", "newer_than:7d"]

    stats = fetch_new_gmail_messages(search_criteria=criteria)

    created = int(stats.get("created_messages") or 0)
    presc = int(stats.get("created_prescriptions") or 0)
    pj = int(stats.get("saved_attachments") or 0)
    skipped = int(stats.get("skipped_existing") or 0)
    missing = int(stats.get("missing_message_id") or 0)
    duration = stats.get("duration_s")

    msg = (
        f"Synchronisation Gmail terminée ✅ "
        f"(nouveaux={created}, ordonnances={presc}, PJ={pj}, doublons={skipped}, sans-id={missing}, durée={duration}s)."
    )

    is_xhr = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    if is_xhr:
        return JsonResponse({"ok": True, "message": msg, "stats": stats})

    # mode classique
    if created:
        messages.success(request, msg)
    else:
        messages.info(request, msg)

    return redirect("core_emails:dashboard")

def change_sender_type(request, pk):
    prescription = get_object_or_404(Prescription, pk=pk)

    if _is_prescription_structure_locked(prescription):
        messages.error(
            request,
            "Cette ordonnance a déjà commencé son traitement. Les paramètres médicaux sont verrouillés."
        )
        return redirect("core_emails:prescription_detail", pk=pk)

    new_sender_type = request.POST.get("sender_type")
    if new_sender_type not in dict(SenderType.choices):
        return redirect("core_emails:prescription_detail", pk=pk)

    old_sender_type = prescription.sender_type
    if old_sender_type == new_sender_type:
        return redirect("core_emails:prescription_detail", pk=pk)

    prescription.sender_type = new_sender_type
    # NOTE: garde updated_at seulement si ton modèle a bien ce champ
    prescription.save(update_fields=["sender_type", "updated_at"])

    PrescriptionStatusHistory.objects.create(
        prescription=prescription,
        old_status=prescription.status,
        new_status=prescription.status,
        changed_by=request.user,
        comment=f"Origine de l’ordonnance modifiée : {old_sender_type} → {new_sender_type}",
    )

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
        email = request.POST.get("email", "").strip().lower()

        # Sécurité : sender_type valide
        if sender_type not in dict(SenderType.choices):
            messages.error(request, "Type d’expéditeur invalide.")
            return redirect("core_emails:prescription_create")

        prescription = Prescription.objects.create(
            sender_type=sender_type,
            status=PrescriptionStatusEnum.RECEIVED.value,
            created_by=request.user,
        )

        # =====================================================
        # UPLOAD DES PIÈCES JOINTES + VALIDATION
        # =====================================================
        files = request.FILES.getlist("attachments")
        valid_count = 0

        for f in files:
            if f.size > MAX_FILE_SIZE:
                messages.warning(
                    request,
                    f"Le fichier {f.name} dépasse la taille maximale "
                    f"de {MAX_FILE_SIZE // (1024 * 1024)} Mo et n’a pas été ajouté."
                )
                continue

            if f.content_type not in ALLOWED_MIME_TYPES:
                messages.warning(
                    request,
                    f"Le fichier {f.name} a un type MIME non autorisé "
                    f"({f.content_type}) et n’a pas été ajouté."
                )
                continue

            PrescriptionAttachment.objects.create(
                prescription=prescription,
                file=f,
                original_filename=f.name,
                mime_type=f.content_type,
                uploaded_by=request.user,
            )
            valid_count += 1

        # Si l'utilisateur a sélectionné des fichiers mais aucun n'est valide → on annule proprement
        if files and valid_count == 0:
            prescription.delete()
            messages.error(request, "Aucune pièce jointe valide n’a été ajoutée à l’ordonnance.")
            return redirect("core_emails:prescription_create")

        # =====================================================
        # ASSOCIATION DU PATIENT (SI FOURNI)
        # =====================================================
        if email:
            patient, _ = Patient.objects.get_or_create(email=email)
            prescription.patient = patient
            prescription.save(update_fields=["patient"])

        # =====================================================
        # HISTORIQUE OPPOSABLE (CRÉATION)
        # =====================================================
        PrescriptionStatusHistory.objects.create(
            prescription=prescription,
            old_status=prescription.status,
            new_status=prescription.status,
            changed_by=request.user,
        )

        return redirect("core_emails:prescription_detail", pk=prescription.pk)

    return render(request, "core_emails/prescription_create.html")

# =====================================================
# CHANGEMENT TYPE D’ORDONNANCE
# =====================================================
@login_required
@require_POST
def change_prescription_type(request, pk):
    prescription = get_object_or_404(Prescription, pk=pk)

    if _is_prescription_structure_locked(prescription):
        messages.error(
            request,
            "Cette ordonnance a déjà commencé son traitement. Les paramètres médicaux sont verrouillés."
        )
        return redirect("core_emails:prescription_detail", pk=pk)

    new_type = request.POST.get("type")
    if new_type not in dict(PrescriptionType.choices):
        return redirect("core_emails:prescription_detail", pk=pk)

    old_type = prescription.type
    if old_type == new_type:
        return redirect("core_emails:prescription_detail", pk=pk)

    prescription.type = new_type
    # NOTE: garde updated_at seulement si ton modèle a bien ce champ
    prescription.save(update_fields=["type", "updated_at"])

    PrescriptionStatusHistory.objects.create(
        prescription=prescription,
        old_status=prescription.status,
        new_status=prescription.status,
        changed_by=request.user,
        comment=f"Type d’ordonnance modifié : {old_type} → {new_type}",
    )

    return redirect("core_emails:prescription_detail", pk=pk)

# =====================================================
# V7 — ACTIONS RENOUVELLEMENT (EMAIL/SMS PATIENT + EMAIL MÉDECIN)
# =====================================================

def sms_backend_send(phone: str, message: str):
    """
    Backend SMS à brancher (Twilio/OVH/etc).
    Pour l’instant: non configuré => erreur propre.
    """
    raise NotImplementedError("SMS non configuré (ajouter un provider SMS).")


def _renewal_rule_for_manual_send(request, days):
    """Résout uniquement une règle active correspondant au délai demandé."""
    if days == 0:
        return None

    rules = RenewalNotificationRule.objects.filter(
        active=True,
        days_before=days,
    ).order_by("sort_order", "pk")

    rule_id = request.POST.get("rule_id")
    if rule_id:
        return rules.filter(pk=rule_id).first()
    return rules.first()

#====================================================
# V7 — MARQUER RENOUVELLEMENT COMME RÉALISÉ
#====================================================

# RENEWAL_NOTE_HELPERS:BEGIN
def _renewal_note_max_len(default: int = 255) -> int:
    try:
        v = PrescriptionRenewalEvent._meta.get_field("note").max_length
        return int(v or default)
    except Exception:
        return int(default)

def _renewal_truncate(text: str, max_len: int = 255) -> str:
    text = (text or "").strip()
    if not max_len:
        return text
    if len(text) <= max_len:
        return text
    if max_len <= 3:
        return text[:max_len]
    return (text[: max_len - 3].rstrip() + "...")[:max_len]

def _renewal_merge_notes(existing: str, addition: str, max_len: int = 255) -> str:
    existing = (existing or "").strip()
    addition = (addition or "").strip()
    merged = existing
    if addition and addition not in merged:
        # chr(10) = newline (évite tout risque de string cassée)
        merged = (merged + (chr(10) if merged else "") + addition).strip()
    return _renewal_truncate(merged, max_len)
# RENEWAL_NOTE_HELPERS:END

# RENEWAL_CYCLE_HELPER_V1:BEGIN
def _get_or_create_current_renewal_cycle(prescription, info):
    """Retourne le cycle courant (numéro = renewal_done_count + 1).
    Idempotent: crée le cycle si absent.
    """
    try:
        current_number = int(getattr(info, "renewal_done_count", 0) or 0) + 1
    except Exception:
        current_number = 1
    cycle, _ = PrescriptionRenewalCycle.objects.get_or_create(
        prescription=prescription,
        cycle_number=current_number,
        defaults={"status": PrescriptionStatus.RECEIVED},
    )
    return cycle, current_number
# RENEWAL_CYCLE_HELPER_V1:END

@login_required
@require_POST
def mark_renewal_done(request, pk):
    prescription = get_object_or_404(Prescription, pk=pk)

    if prescription.type != PrescriptionType.RENOUVELLEMENT:
        messages.error(request, "Cette ordonnance n’est pas un renouvellement.")
        return redirect("core_emails:prescription_detail", pk=pk)

    info, _ = PrescriptionRenewalInfo.objects.get_or_create(prescription=prescription)

    # next_number = numéro du renouvellement en cours de validation
    # renewal_done_count reste le compteur des renouvellements réalisés
    total_cycles = int(info.renewal_times) + 1
    next_number = int(info.renewal_done_count) + 1
    if next_number > int(info.renewal_times):
        messages.info(request, "Nombre de renouvellements autorisés déjà atteint.", extra_tags="modal_renewal_done")
        return redirect("core_emails:prescription_detail", pk=pk)

    max_len = _renewal_note_max_len()
    note_user = (request.POST.get("note") or "").strip()
    base_note = "Renouvellement marqué comme réalisé."
    note = _renewal_truncate((base_note + ("\n" + note_user if note_user else "")).strip(), max_len)

    from django.db import transaction
    now = timezone.now()

    with transaction.atomic():
        # Event idempotent (unique_together prescription+number)
        ev, created = PrescriptionRenewalEvent.objects.get_or_create(
            prescription=prescription,
            number=next_number,
            defaults={"created_by": request.user, "note": note, "ordered_at": now},
        )

        if not created:
            merged = _renewal_merge_notes(ev.note, note, max_len)
            update_fields = []
            if merged != (ev.note or ""):
                ev.note = merged
                update_fields.append("note")
            if request.user and ev.created_by_id is None:
                ev.created_by = request.user
                update_fields.append("created_by")
            if getattr(ev, "ordered_at", None) is None:
                ev.ordered_at = now
                update_fields.append("ordered_at")
            if update_fields:
                ev.save(update_fields=update_fields)

        info.renewal_done_count = next_number
        info.last_renewal_ordered_at = now
        info.save(update_fields=["renewal_done_count", "last_renewal_ordered_at"])

        # CYCLE_V1:BEGIN
        # Cycle autonome : on clôture le cycle courant (numéro = next_number)
        # et on crée le cycle suivant si des renouvellements restent disponibles.
        cycle, _ = PrescriptionRenewalCycle.objects.get_or_create(
            prescription=prescription,
            cycle_number=next_number,
            defaults={"status": PrescriptionStatus.DELIVERED},
        )
        # On marque le cycle comme clôturé (idempotent)
        if cycle.closed_at is None:
            cycle.closed_at = now
        # Si le cycle n'est pas déjà "Délivrée", on le positionne en fin de cycle
        if getattr(cycle, "status", None) != PrescriptionStatus.DELIVERED:
            cycle.status = PrescriptionStatus.DELIVERED
        cycle.save(update_fields=["closed_at", "status"])

        # Créer le prochain cycle (next_number+1) tant que l'on n'a pas atteint
        # le nombre total de cycles (renewal_times + 1)
        if next_number < total_cycles:
            PrescriptionRenewalCycle.objects.get_or_create(
                prescription=prescription,
                cycle_number=next_number + 1,
                defaults={"status": PrescriptionStatus.RECEIVED},
            )
        else:
            # Dernier cycle total terminé :
            # on journalise la fin métier du renouvellement,
            # sans archiver automatiquement le dossier parent.
            PrescriptionStatusHistory.objects.create(
                prescription=prescription,
                old_status=prescription.status,
                new_status=prescription.status,
                changed_by=request.user,
                comment="Dernier cycle de renouvellement clôturé.",
            )
        # CYCLE_V1:END


    # ✅ Message pour popup
    messages.success(request, "Renouvellement marqué comme réalisé.", extra_tags="modal_renewal_done")
    return redirect("core_emails:prescription_detail", pk=pk)

@login_required
@require_POST
def send_renewal_patient_email(request, pk, days):
    prescription = get_object_or_404(Prescription, pk=pk)

    next_url = request.POST.get("next") or request.GET.get("next") or reverse("core_emails:renewals_dashboard")
    if not url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        next_url = reverse("core_emails:renewals_dashboard")

    if prescription.type != PrescriptionType.RENOUVELLEMENT:
        messages.error(request, "Cette ordonnance n’est pas un renouvellement.")
        return redirect(next_url)

    rule = _renewal_rule_for_manual_send(request, days)
    if days != 0 and rule is None:
        messages.error(request, "Jour de rappel invalide.")
        return redirect(next_url)

    patient = prescription.patient
    if not patient or not patient.email:
        messages.error(request, "Email patient manquant.")
        return redirect(next_url)

    info, _ = PrescriptionRenewalInfo.objects.get_or_create(prescription=prescription)
    cycle, current_number = _get_or_create_current_renewal_cycle(prescription, info)

    if rule is not None and _rule_channel_already_sent(cycle, rule, "EMAIL"):
        messages.info(request, f"Email {rule.name} déjà envoyé.")
        return redirect(next_url)
    # Base = date du 1er retrait (1ère délivrance)
    first_delivered_at = (
        PrescriptionStatusHistory.objects
        .filter(prescription=prescription, new_status=PrescriptionStatus.DELIVERED)
        .order_by("changed_at")
        .values_list("changed_at", flat=True)
        .first()
    )

    if not first_delivered_at:
        messages.error(
            request,
            "Première délivrance (retrait) introuvable. "
            "Passez l’ordonnance en statut 'Délivrée' pour démarrer les rappels."
        )
        return redirect("core_emails:prescription_detail", pk=pk)

    start_date = timezone.localtime(first_delivered_at).date()

    # Échéance du prochain renouvellement = start_date + (done_count + 1) * period_days
    end_date = start_date + datetime.timedelta(
        days=(int(info.renewal_done_count) + 1) * int(info.period_days)
    )

    # ORDO V9 - Email via template configurable.
    # RGPD : ne pas inclure médicament, diagnostic ou pathologie.
    subject, body, _template = render_renewal_message(
        "EMAIL",
        prescription,
        cycle=cycle,
        extra_context={
            "date_echeance": end_date.strftime("%d/%m/%Y"),
            "jours_avant": days,
        },
    )

    if not subject:
        subject = (
            "Renouvellement en retard"
            if days == 0
            else "Votre renouvellement approche"
        )

    if not body:
        reference = f"#{prescription.pk}"
        body = "\n".join([
            "Bonjour,",
            "",
            (
                f"Votre renouvellement est en retard. Référence : {reference}."
                if days == 0
                else f"Votre renouvellement approche. Référence : {reference}."
            ),
            "Merci de contacter la pharmacie.",
            "",
            "Cordialement,",
            "La pharmacie",
        ])

    send_mail(
        subject,
        body,
        settings.DEFAULT_FROM_EMAIL,
        [patient.email],
        fail_silently=False,
    )

    # Historique renouvellement (event) — éviter doublons (unique_together)
    next_number = int(current_number)
    max_len = _renewal_note_max_len()
    note = (
        "Rappel renouvellement patient (EMAIL) — RETARD."
        if days == 0
        else "Rappel renouvellement patient (EMAIL) — J-%s." % days
    )
    note = _renewal_truncate(note, max_len)
    ev, created = PrescriptionRenewalEvent.objects.get_or_create(
        prescription=prescription,
        number=next_number,
        defaults={"created_by": request.user, "note": note},
    )
    if not created:
        merged = _renewal_merge_notes(ev.note, note, max_len)
        update_fields = []
        if merged != (ev.note or ""):
            ev.note = merged
            update_fields.append("note")
        if request.user and ev.created_by_id is None:
            ev.created_by = request.user
            update_fields.append("created_by")
        if update_fields:
            ev.save(update_fields=update_fields)

    if rule is not None:
        mark_rule_channel_sent(cycle, rule, "EMAIL")

    PrescriptionStatusHistory.objects.create(
        prescription=prescription,
        old_status=prescription.status,
        new_status=prescription.status,
        changed_by=request.user,
        comment=(
            "Rappel renouvellement envoyé au patient (EMAIL) — RETARD."
            if days == 0
            else f"Rappel renouvellement envoyé au patient (EMAIL) — J-{days}."
        ),
    )

    messages.success(
        request,
        ("Email patient envoyé (RETARD)." if days == 0 else f"Email patient envoyé (J-{days}).")
    )
    return redirect(next_url)

@login_required
@require_POST
def send_renewal_patient_sms(request, pk, days):
    prescription = get_object_or_404(Prescription, pk=pk)

    next_url = request.POST.get("next") or request.GET.get("next") or reverse("core_emails:renewals_dashboard")
    if not url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        next_url = reverse("core_emails:renewals_dashboard")

    if prescription.type != PrescriptionType.RENOUVELLEMENT:
        messages.error(request, "Cette ordonnance n’est pas un renouvellement.")
        return redirect(next_url)

    rule = _renewal_rule_for_manual_send(request, days)
    if days != 0 and rule is None:
        messages.error(request, "Jour de rappel invalide.")
        return redirect(next_url)

    patient = prescription.patient
    if not patient or not patient.phone_number:
        messages.error(request, "Téléphone patient manquant.")
        return redirect(next_url)

    info, _ = PrescriptionRenewalInfo.objects.get_or_create(prescription=prescription)
    cycle, current_number = _get_or_create_current_renewal_cycle(prescription, info)

    if rule is not None and _rule_channel_already_sent(cycle, rule, "SMS"):
        messages.info(request, f"SMS {rule.name} déjà envoyé.")
        return redirect(next_url)
    # Base = date du 1er retrait (1ère délivrance)
    first_delivered_at = (
        PrescriptionStatusHistory.objects
        .filter(prescription=prescription, new_status=PrescriptionStatus.DELIVERED)
        .order_by("changed_at")
        .values_list("changed_at", flat=True)
        .first()
    )

    if not first_delivered_at:
        messages.error(
            request,
            "Première délivrance (retrait) introuvable. "
            "Passez l’ordonnance en statut 'Délivrée' pour démarrer les rappels."
        )
        return redirect("core_emails:prescription_detail", pk=pk)

    start_date = timezone.localtime(first_delivered_at).date()

    # Échéance du prochain renouvellement = start_date + (done_count + 1) * period_days
    end_date = start_date + datetime.timedelta(
        days=(int(info.renewal_done_count) + 1) * int(info.period_days)
    )
    # ORDO V9 - SMS via template configurable.
    # RGPD : ne pas inclure médicament, diagnostic ou pathologie.
    _subject, msg, _template = render_renewal_message(
        "SMS",
        prescription,
        cycle=cycle,
        extra_context={
            "date_echeance": end_date.strftime("%d/%m/%Y"),
            "jours_avant": days,
        },
    )
    if not msg:
        # Fallback sécurisé si aucun template actif n'existe.
        reference = f"#{prescription.pk}"
        msg = (
            f"Votre renouvellement est en retard. Référence : {reference}. "
            "Merci de contacter la pharmacie."
            if days == 0
            else
            f"Votre renouvellement approche. Référence : {reference}. "
            "Merci de contacter la pharmacie."
        )

    try:
        sms_backend_send(patient.phone_number, msg)
    except NotImplementedError as e:
        messages.error(request, str(e))
        return redirect(next_url)

    # Historique renouvellement (event) — éviter doublons (unique_together)
    next_number = int(current_number)
    max_len = _renewal_note_max_len()
    note = (
        "Rappel renouvellement patient (SMS) — RETARD."
        if days == 0
        else "Rappel renouvellement patient (SMS) — J-%s." % days
    )
    note = _renewal_truncate(note, max_len)
    ev, created = PrescriptionRenewalEvent.objects.get_or_create(
        prescription=prescription,
        number=next_number,
        defaults={"created_by": request.user, "note": note},
    )
    if not created:
        merged = _renewal_merge_notes(ev.note, note, max_len)
        update_fields = []
        if merged != (ev.note or ""):
            ev.note = merged
            update_fields.append("note")
        if request.user and ev.created_by_id is None:
            ev.created_by = request.user
            update_fields.append("created_by")
        if update_fields:
            ev.save(update_fields=update_fields)

    if rule is not None:
        mark_rule_channel_sent(cycle, rule, "SMS")
    PrescriptionStatusHistory.objects.create(
        prescription=prescription,
        old_status=prescription.status,
        new_status=prescription.status,
        changed_by=request.user,
        comment=("Rappel renouvellement envoyé au patient (SMS) — RETARD." if days == 0 else f"Rappel renouvellement envoyé au patient (SMS) — J-{days}."),
    )

    messages.success(request, ("SMS patient envoyé (RETARD)." if days == 0 else f"SMS patient envoyé (J-{days})."))
    return redirect(next_url)

@login_required
@require_POST
def send_renewal_doctor_email(request, pk):
    prescription = get_object_or_404(Prescription, pk=pk)

    if prescription.type != PrescriptionType.RENOUVELLEMENT:
        messages.error(request, "Cette ordonnance n’est pas un renouvellement.")
        return redirect("core_emails:prescription_detail", pk=pk)

    info, _ = PrescriptionRenewalInfo.objects.get_or_create(prescription=prescription)
    cycle, current_number = _get_or_create_current_renewal_cycle(prescription, info)


    if not info.doctor_email:
        messages.error(request, "Email médecin manquant.")
        return redirect("core_emails:prescription_detail", pk=pk)

    patient = prescription.patient
    patient_name = getattr(patient, "full_name", "") if patient else ""
    patient_email = getattr(patient, "email", "") if patient else ""

    subject = "Demande de renouvellement d’ordonnance"
    body = (
        f"Bonjour,\n\n"
        f"Demande de renouvellement pour l’ordonnance #{prescription.id}.\n"
        f"Patient: {patient_name or 'N/A'}\n"
        f"Email patient: {patient_email or 'N/A'}\n\n"
        f"Cordialement,\nPharmacie"
    )

    send_mail(
        subject,
        body,
        settings.DEFAULT_FROM_EMAIL,
        [info.doctor_email],
        fail_silently=False,
    )

    cycle.doctor_email_sent_at = timezone.now()
    cycle.save(update_fields=["doctor_email_sent_at"])

    PrescriptionStatusHistory.objects.create(
        prescription=prescription,
        old_status=prescription.status,
        new_status=prescription.status,
        changed_by=request.user,
        comment="Demande renouvellement envoyée au médecin (EMAIL).",
    )

    messages.success(request, "Email médecin envoyé.")
    return redirect("core_emails:prescription_detail", pk=pk)

# =====================================================
# V7 — MAJ INFOS RENOUVELLEMENT (depuis la fiche ordonnance)
# =====================================================
@login_required
@require_POST
def update_renewal_info(request, pk):
    prescription = get_object_or_404(Prescription, pk=pk)

    if _is_prescription_structure_locked(prescription):
        messages.error(
            request,
            "Cette ordonnance a déjà commencé son traitement. Les paramètres médicaux sont verrouillés."
        )
        return redirect("core_emails:prescription_detail", pk=pk)

    if prescription.type != PrescriptionType.RENOUVELLEMENT:
        messages.error(request, "Cette ordonnance n’est pas de type Renouvellement.")
        return redirect("core_emails:prescription_detail", pk=pk)

    # ---- champs Prescription
    established_at_raw = (request.POST.get("established_at") or "").strip()
    established_at = None
    if established_at_raw:
        established_at = parse_date(established_at_raw)
        if established_at is None:
            messages.error(request, "Date médecin invalide (format attendu : AAAA-MM-JJ).")
            return redirect("core_emails:prescription_detail", pk=pk)

    # ---- champs RenewalInfo
    info, _ = PrescriptionRenewalInfo.objects.get_or_create(prescription=prescription)

    renewal_times_raw = (request.POST.get("renewal_times") or "").strip()
    period_days_raw = (request.POST.get("period_days") or "").strip()
    doctor_email = (request.POST.get("doctor_email") or "").strip().lower()
    doctor_name = (request.POST.get("doctor_name") or "").strip()

    # conversions sécurisées
    try:
        renewal_times = int(renewal_times_raw) if renewal_times_raw != "" else info.renewal_times
        period_days = int(period_days_raw) if period_days_raw != "" else info.period_days
    except ValueError:
        messages.error(request, "Renouvellements / période : valeur numérique invalide.")
        return redirect("core_emails:prescription_detail", pk=pk)

    if renewal_times < 0:
        messages.error(request, "Le nombre de renouvellements ne peut pas être négatif.")
        return redirect("core_emails:prescription_detail", pk=pk)

    if period_days <= 0:
        messages.error(request, "La durée de période doit être > 0.")
        return redirect("core_emails:prescription_detail", pk=pk)

    # validation email médecin
    if doctor_email:
        try:
            validate_email(doctor_email)
        except ValidationError:
            messages.error(request, "Email médecin invalide.")
            return redirect("core_emails:prescription_detail", pk=pk)

    # ---- sauvegarde "tout ou rien"
    with transaction.atomic():
        # 1) Prescription : on n’écrase pas la date si champ vide
        if established_at_raw != "":
            prescription.established_at = established_at
            prescription.save(update_fields=["established_at", "updated_at"])
        else:
            # on bump updated_at même si on ne touche pas established_at
            prescription.save(update_fields=["updated_at"])

        # 2) RenewalInfo
        info.renewal_times = renewal_times
        info.period_days = period_days
        info.doctor_email = doctor_email
        info.doctor_name = doctor_name
        info.save(update_fields=["renewal_times", "period_days", "doctor_email", "doctor_name"])

        # 3) trace opposable
        PrescriptionStatusHistory.objects.create(
            prescription=prescription,
            old_status=prescription.status,
            new_status=prescription.status,
            changed_by=request.user,
            comment=(
                "Infos renouvellement mises à jour : "
                f"date médecin={established_at_raw or 'inchangée'}, "
                f"renewal_times={renewal_times}, period_days={period_days}, "
                f"doctor_email={doctor_email or '—'}."
            ),
        )

    messages.success(request, "Infos renouvellement enregistrées.")
    return redirect("core_emails:prescription_detail", pk=pk)

# =====================================================
# 🔔 PARAMÉTRAGE NOTIFICATIONS — POST UNIQUEMENT (V8)
# =====================================================

@login_required
@require_POST
def update_prescription_notification_settings(request, prescription_id):
    from .models import PrescriptionNotificationSettings, Prescription

    prescription = get_object_or_404(Prescription, pk=prescription_id)

    settings_obj, _ = PrescriptionNotificationSettings.objects.get_or_create(
        prescription=prescription
    )

    settings_obj.patient_channel = request.POST.get("patient_channel", "NONE")

    # Infirmier : uniquement si associé
    if getattr(prescription, 'assignment', None) and getattr(prescription.assignment, 'nurse', None):
        settings_obj.nurse_channel = request.POST.get("nurse_channel", "NONE")
    else:
        settings_obj.nurse_channel = "NONE"

    # ORDO_NOTIF_FREE_TEXT_V2_BACKEND: persistance du message libre (popup)
    settings_obj.free_text_message = (request.POST.get("notification_message_modal") or "").strip()

    settings_obj.save(update_fields=["patient_channel", "nurse_channel", "free_text_message", "updated_at"])

    # Trace opposable (historique) : paramétrage notifications
    PrescriptionStatusHistory.objects.create(
        prescription=prescription,
        old_status=prescription.status,
        new_status=prescription.status,
        changed_by=request.user,
        comment=(
            'Paramétrage notifications mis à jour : '
            f"patient={settings_obj.patient_channel or 'NONE'}, "
            f"infirmier={settings_obj.nurse_channel or 'NONE'}"
        ),
    )

    messages.success(request, "Paramétrage des notifications mis à jour.")
    return redirect("core_emails:prescription_detail", prescription.id)
