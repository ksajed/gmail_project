# =====================================================
# DJANGO
# =====================================================
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import ensure_csrf_cookie
from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.core.paginator import Paginator
from django.db.models import Count
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
    SenderType,
)
from .models_assignment import PrescriptionAssignment
from core_emails.models import PrescriptionRenewalEvent

# =====================================================
# STATES & SERVICES
# =====================================================
from .states import PrescriptionStatusEnum, PRESCRIPTION_STATUS_TRANSITIONS
from .services import change_prescription_status
from core_emails.services import compute_renewals_watch_from_delivered

# =====================================================
# EXTERNES
# =====================================================
from core_attachments.models import PrescriptionAttachment
from core_gmail.services import fetch_new_gmail_messages
from core_people.models import Person

# (Optionnel) Si tu utilises Patient
from core_patients.models import Patient
from core_notifications.services import send_sms_logged
from core_notifications.models import SmsPurpose


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

    prescriptions_qs = Prescription.objects.select_related("patient")

    if view_filter == "todo":
        prescriptions_qs = prescriptions_qs.filter(
            status__in=[PrescriptionStatus.RECEIVED, PrescriptionStatus.IN_PROGRESS]
        )
    elif view_filter == "blocked":
        prescriptions_qs = prescriptions_qs.filter(status=PrescriptionStatus.BLOCKED)
    elif view_filter == "archived":
        prescriptions_qs = prescriptions_qs.filter(status=PrescriptionStatus.ARCHIVED)

    # Sécurité simple : n'appliquer le filtre que si valeur valide
    if status_filter and status_filter in dict(PrescriptionStatus.choices):
        prescriptions_qs = prescriptions_qs.filter(status=status_filter)

    prescriptions_qs = prescriptions_qs.order_by("-received_at")

    paginator = Paginator(prescriptions_qs, per_page)
    prescriptions = paginator.get_page(page_number)

    raw_stats = Prescription.objects.values("status").annotate(total=Count("id"))

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

@ensure_csrf_cookie
@login_required
def renewals_dashboard(request):
    """
    Dashboard Renouvellements — J-5 / J-3 / Retard

    ✅ Base = 1ère délivrance (premier statut DELIVERED)
    ✅ Source unique de vérité: services.compute_renewals_watch_from_delivered()
       (évite duplication et garde la logique centralisée)
    """
    from django.utils import timezone
    from django.shortcuts import render

    from .services import compute_renewals_watch_from_delivered

    today = timezone.localdate()
    renewals_due_5, renewals_due_3, renewals_overdue = compute_renewals_watch_from_delivered()

    context = {
        "today": today,
        "renewals_due_5": renewals_due_5,
        "renewals_due_3": renewals_due_3,
        "renewals_overdue": renewals_overdue,
    }
    return render(request, "core_emails/renewals_dashboard.html", context)



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

    current_enum = PrescriptionStatusEnum(prescription.status)
    allowed_enums = PRESCRIPTION_STATUS_TRANSITIONS.get(current_enum, set())

    # Labels (FR) depuis les choices du modèle + ordre stable
    status_label_map = dict(PrescriptionStatus.choices)

    _order = [
        PrescriptionStatusEnum.IN_PROGRESS.value,
        PrescriptionStatusEnum.READY.value,
        PrescriptionStatusEnum.DELIVERED.value,
        PrescriptionStatusEnum.BLOCKED.value,
        PrescriptionStatusEnum.ARCHIVED.value,
    ]

    def _order_key(v: str) -> int:
        try:
            return _order.index(v)
        except ValueError:
            return 999

    allowed_values = sorted((e.value for e in allowed_enums), key=_order_key)

    # STATUS_ORDER_SORT:BEGIN
    # Ordre stable d'affichage des statuts autorisés (évite l'ordre aléatoire des sets)
    STATUS_ORDER = [
        PrescriptionStatusEnum.IN_PROGRESS,
        PrescriptionStatusEnum.READY,
        PrescriptionStatusEnum.DELIVERED,
        PrescriptionStatusEnum.BLOCKED,
        PrescriptionStatusEnum.ARCHIVED,
    ]

    # Libellés FR (UI)
    STATUS_LABELS_FR = {
        PrescriptionStatusEnum.IN_PROGRESS: "En cours de préparation",
        PrescriptionStatusEnum.READY: "Prête à être délivrée",
        PrescriptionStatusEnum.DELIVERED: "Délivrée",
        PrescriptionStatusEnum.BLOCKED: "Bloquée (problème)",
        PrescriptionStatusEnum.ARCHIVED: "Archivée",
        PrescriptionStatusEnum.RECEIVED: "Reçue",
    }

    allowed_statuses = [
        (e.value, STATUS_LABELS_FR.get(e, e.name.replace("_", " ").title()))
        for e in STATUS_ORDER
        if e in allowed_enums
    ]

    # Si un enum “nouveau” apparaît un jour, on l'ajoute à la fin proprement
    for e in sorted((allowed_enums - set(STATUS_ORDER)), key=lambda x: x.value):
        allowed_statuses.append((e.value, STATUS_LABELS_FR.get(e, e.name.replace("_", " ").title())))
    # STATUS_ORDER_SORT:END

    persons_nurses = Person.objects.filter(role="nurse").order_by("last_name", "first_name")
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
            .filter(
                prescription=prescription,
                old_status=PrescriptionStatus.READY,
                new_status=PrescriptionStatus.DELIVERED,
            )
            .order_by('changed_at')
            .values_list('changed_at', flat=True)
            .first()
        )
        if first_delivered_at:
            renewal_patient_first_delivered_at = timezone.localtime(first_delivered_at)
            start_date = renewal_patient_first_delivered_at.date()
            renewal_patient_next_number = int(renewal_info.renewal_done_count) + 1
            renewal_patient_end_date = start_date + datetime.timedelta(
                days=renewal_patient_next_number * int(renewal_info.period_days)
            )
            renewal_patient_days_left = (renewal_patient_end_date - today).days
            if renewal_patient_days_left == 5:
                renewal_patient_bucket = 'J-5'
            elif renewal_patient_days_left == 3:
                renewal_patient_bucket = 'J-3'
            elif renewal_patient_days_left < 0:
                renewal_patient_bucket = 'RETARD'
            else:
                renewal_patient_bucket = 'HORS_LISTE'
        else:
            renewal_patient_bucket = 'NON_DEMARRE'

        # Historique des renouvellements (ordre 1..N)
        renewal_events = list(
            prescription.renewal_events.select_related('created_by').order_by('number')
        )
    context = {
    "prescription": prescription,
    "attachments": attachments,
    "history": history,
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


    # MODAL_RENEWAL_DONE_EXTRACT:BEGIN
    renewal_done_message = None
    try:
        _storage = messages.get_messages(request)
        _kept = []
        for _m in _storage:
            _kept.append(_m)
            if 'modal_renewal_done' in getattr(_m, 'tags', ''):
                renewal_done_message = str(_m)
        for _m in _kept:
            messages.add_message(
                request,
                _m.level,
                _m.message,
                extra_tags=getattr(_m, 'extra_tags', '') or '',
            )
    except Exception:
        renewal_done_message = None
    # MODAL_RENEWAL_DONE_EXTRACT:END
    __ctx = context
    try:
        if __ctx is None:
            __ctx = {}
        elif not isinstance(__ctx, dict):
            __ctx = dict(__ctx)
    except Exception:
        __ctx = {}
    __ctx['renewal_done_message'] = renewal_done_message

    return render(request, "core_emails/prescription_detail.html", __ctx)


# =====================================================
# CHANGEMENT DE STATUT
# =====================================================
@login_required
@require_POST
def change_status(request, pk):
    prescription = get_object_or_404(Prescription, pk=pk)

    # SMS_POST:BEGIN
    send_sms = request.POST.get("send_sms") in ("1", "true", "True", "on", "yes")
    sms_target = request.POST.get("sms_target", "").strip()  # patient|nurse|both
    if send_sms and sms_target not in ("patient", "nurse", "both"):
        send_sms = False
    # SMS_POST:END

    new_status = request.POST.get("status")
    if not new_status:
        messages.warning(request, "Aucun statut sélectionné.")
        return redirect("core_emails:prescription_detail", pk=pk)

    status_changed = False
    try:
        change_prescription_status(
            prescription=prescription,
            new_status=new_status,
            user=request.user,
        )
        # ✅ Renouvellement: message clair si auto-réinitialisation après DELIVERED
        try:
            prescription.refresh_from_db(fields=["status", "type"])
        except Exception:
            prescription.refresh_from_db()

        if (
            new_status == PrescriptionStatus.DELIVERED
            and getattr(prescription, "type", None) == PrescriptionType.RENOUVELLEMENT
        ):
            if prescription.status == PrescriptionStatus.RECEIVED:
                messages.success(
                    request,
                    "Délivrance enregistrée (renouvellement). Statut réinitialisé pour le prochain cycle."
                )
            else:
                messages.success(
                    request,
                    "Délivrance enregistrée (renouvellement). Dernier cycle atteint (aucune réinitialisation)."
                )
        else:
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

    # SMS_SEND:BEGIN
    if status_changed and send_sms:
        # Patient phone
        patient = getattr(prescription, "patient", None)
        patient_phone = None
        if patient:
            patient_phone = getattr(patient, "phone", None) or getattr(patient, "mobile", None)

        # Nurse phone (si affectée)
        nurse_phone = None
        try:
            assignment = (
                PrescriptionAssignment.objects
                .select_related("nurse")
                .filter(prescription=prescription)
                .first()
            )
            nurse = assignment.nurse if assignment and assignment.nurse else None
            if nurse:
                nurse_phone = getattr(nurse, "phone", None) or getattr(nurse, "mobile", None)
        except Exception:
            nurse_phone = None

        recipients = []
        if sms_target == "patient" and patient_phone:
            recipients.append(("patient", str(patient_phone)))
        elif sms_target == "nurse" and nurse_phone:
            recipients.append(("nurse", str(nurse_phone)))
        elif sms_target == "both":
            if patient_phone:
                recipients.append(("patient", str(patient_phone)))
            if nurse_phone:
                recipients.append(("nurse", str(nurse_phone)))

        label = prescription.get_status_display() if hasattr(prescription, "get_status_display") else str(prescription.status)
        msg_patient = f"Votre ordonnance est maintenant : {label}."
        msg_nurse = f"Statut ordonnance mis à jour : {label}."

        for who, phone in recipients:
            # On envoie seulement si format international (+33...)
            if phone.startswith("+"):
                text = msg_patient if who == "patient" else msg_nurse
                try:
                    send_sms_logged(
                        to_e164=phone,
                        text=text,
                        purpose=SmsPurpose.STATUS_UPDATE,
                        template_key=f"PRESCRIPTION_STATUS_{prescription.status}_{who}".upper(),
                        prescription=prescription,
                    )
                except Exception:
                    pass
    # SMS_SEND:END

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

    nurse = get_object_or_404(Person, pk=nurse_id, role="nurse")

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
    - Email obligatoire (contrainte DB)
    """
    first_name = request.POST.get("first_name", "").strip()
    last_name = request.POST.get("last_name", "").strip()
    email = request.POST.get("email", "").strip().lower()

    if not first_name or not last_name or not email:
        messages.error(
            request,
            "Nom, prénom et email sont obligatoires pour créer un infirmier.",
        )
        return redirect(request.META.get("HTTP_REFERER") or "core_emails:dashboard")

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
@login_required
@require_POST
def mark_renewal_done(request, pk):
    prescription = get_object_or_404(Prescription, pk=pk)

    if prescription.type != PrescriptionType.RENOUVELLEMENT:
        messages.error(request, "Cette ordonnance n’est pas un renouvellement.")
        return redirect("core_emails:prescription_detail", pk=pk)

    info, _ = PrescriptionRenewalInfo.objects.get_or_create(prescription=prescription)

    # Prochain cycle (1..N)
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

    # 5 / 3 / 0 (RETARD)
    if days not in (5, 3, 0):
        messages.error(request, "Jour de rappel invalide.")
        return redirect(next_url)

    patient = prescription.patient
    if not patient or not patient.email:
        messages.error(request, "Email patient manquant.")
        return redirect(next_url)

    info, _ = PrescriptionRenewalInfo.objects.get_or_create(prescription=prescription)
    # Anti-doublon: ne pas renvoyer J-5/J-3 si déjà envoyé
    if days == 5 and info.reminder_5_patient_email_sent_at is not None:
        messages.info(request, "Email J-5 déjà envoyé.")
        return redirect(next_url)
    if days == 3 and info.reminder_3_patient_email_sent_at is not None:
        messages.info(request, "Email J-3 déjà envoyé.")
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

    subject = (
        "Renouvellement en retard — échéance dépassée"
        if days == 0
        else f"Rappel renouvellement — échéance dans {days} jours"
    )

    body = "\n".join([
        "Bonjour,",
        "",
        (
            f"Votre ordonnance est en retard depuis le {end_date:%d/%m/%Y}."
            if days == 0
            else f"Votre ordonnance arrive à échéance le {end_date:%d/%m/%Y}."
        ),
        "Merci de contacter la pharmacie pour le renouvellement.",
        "",
        "Cordialement,",
        "Pharmacie",
    ])

    send_mail(
        subject,
        body,
        settings.DEFAULT_FROM_EMAIL,
        [patient.email],
        fail_silently=False,
    )

    # Historique renouvellement (event) — éviter doublons (unique_together)
    next_number = int(info.renewal_done_count) + 1
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

    now = timezone.now()
    if days == 5:
        info.reminder_5_patient_email_sent_at = now
        info.save(update_fields=["reminder_5_patient_email_sent_at"])
    elif days == 3:
        info.reminder_3_patient_email_sent_at = now
        info.save(update_fields=["reminder_3_patient_email_sent_at"])
    # days == 0 => RETARD : on ne touche pas les champs J-5/J-3

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

    if days not in (5, 3, 0):
        messages.error(request, "Jour de rappel invalide.")
        return redirect(next_url)

    patient = prescription.patient
    if not patient or not patient.phone_number:
        messages.error(request, "Téléphone patient manquant.")
        return redirect(next_url)

    info, _ = PrescriptionRenewalInfo.objects.get_or_create(prescription=prescription)
    # Anti-doublon: ne pas renvoyer J-5/J-3 si déjà envoyé
    if days == 5 and info.reminder_5_patient_sms_sent_at is not None:
        messages.info(request, "SMS J-5 déjà envoyé.")
        return redirect(next_url)
    if days == 3 and info.reminder_3_patient_sms_sent_at is not None:
        messages.info(request, "SMS J-3 déjà envoyé.")
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
    msg = (f"Pharmacie: renouvellement en retard. Échéance dépassée ({end_date:%d/%m/%Y}). Merci de nous contacter." if days == 0 else f"Pharmacie: rappel renouvellement. Échéance le {end_date:%d/%m/%Y}. Merci de nous contacter.")

    try:
        sms_backend_send(patient.phone_number, msg)
    except NotImplementedError as e:
        messages.error(request, str(e))
        return redirect(next_url)

    # Historique renouvellement (event) — éviter doublons (unique_together)
    next_number = int(info.renewal_done_count) + 1
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

    now = timezone.now()
    if days == 5:
        info.reminder_5_patient_sms_sent_at = now
        info.save(update_fields=["reminder_5_patient_sms_sent_at"])
    elif days == 3:
        info.reminder_3_patient_sms_sent_at = now
        info.save(update_fields=["reminder_3_patient_sms_sent_at"])
    else:
        # Retard: on ne renseigne pas les champs J-5/J-3
        pass
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

    info.doctor_email_sent_at = timezone.now()
    info.save(update_fields=["doctor_email_sent_at"])

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

