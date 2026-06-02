from django import forms
from .permissions import require_perm
from core_emails.models import Prescription, PrescriptionStatus
import datetime as dt
from django.utils import timezone
import datetime
from django.contrib import messages
from django.db.models.deletion import ProtectedError


def _prescription_ordering() -> str:
    """Retourne le meilleur champ d'ordre pour Prescription selon les champs existants."""
    try:
        from core_emails.models import Prescription
        fields = {f.name for f in Prescription._meta.get_fields() if hasattr(f, "name")}
    except Exception:
        fields = set()
    for f in ("created_at", "established_at", "updated_at", "id"):
        if f in fields:
            return f"-{f}"
    return "-id"

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.db.models import Q
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST

from .permissions import superuser_required, require_perm
from .forms_accounts import UserAdminCreateForm

from .permissions import require_console_perm

from .services import audit
from .services import guard_not_last_superuser_change, guard_not_last_superuser_deactivate, guard_self_lockout
from .services import soft_delete_user, reactivate_user

from .models import AdminAuditEvent

from django.contrib.auth import get_user_model
from core_people.models import Person
from core_patients.models import Patient
from core_emails.models import Prescription

User = get_user_model()

# --- ADMINCONSOLE_AUDIT_LABELS_V1:BEGIN ---

def _user_label(u) -> str:
    if not u:
        return "—"
    username = getattr(u, "username", "") or ""
    first = getattr(u, "first_name", "") or ""
    last = getattr(u, "last_name", "") or ""
    email = getattr(u, "email", "") or ""
    name = (first + " " + last).strip()
    parts = [p for p in [username, name, email] if p]
    return " — ".join(parts) if parts else str(u)


def _person_label(p) -> str:
    if not p:
        return "—"
    fn = getattr(p, "first_name", "") or ""
    ln = getattr(p, "last_name", "") or ""
    email = getattr(p, "email", "") or ""
    phone = getattr(p, "phone", "") or ""
    name = (fn + " " + ln).strip() or ("Personne #%s" % (getattr(p, "id", "?"),))
    parts = [name]
    if email:
        parts.append(email)
    if phone:
        parts.append(phone)
    return " — ".join(parts)


def _action_fr(code: str) -> str:
    c = (code or "").upper().strip()
    mapping = {
    "LOGIN": "Connexion Admin",
    "ACCOUNT_ENABLE": "Réactivation compte",
    "ACCOUNT_DISABLE": "Mise en veille compte",
    "NURSE_CREATE": "Création infirmier mandaté",
    "NURSE_EDIT": "Modification infirmier mandaté",
    "ACTIVATE_NURSE": "Activation infirmier mandaté",
    "DEACTIVATE_NURSE": "Désactivation infirmier mandaté",
    "UPDATE_NURSE": "Mise à jour infirmier mandaté",
    "CREATE_NURSE": "Création infirmier mandaté",
    "EDIT_NURSE": "Modification infirmier mandaté",
    }
    return mapping.get(c, c)

# --- ADMINCONSOLE_AUDIT_LABELS_V1:END ---


@require_POST
@require_perm("core_adminconsole.prescriptions_purge")
@login_required
@superuser_required
def prescription_purge(request, pk: int):
    """Purge définitive (superuser-only).
    - Normal: taper l'ID (ex: 334) dans 'confirm'
    - Force: taper '1' dans 'confirm' (ignore la règle des 30 jours et certains garde-fous métier)
    """
    confirm = (request.POST.get("confirm") or "").strip()
    force = (confirm == "1")

    if not force and confirm != str(pk):
        messages.error(request, "Confirmation incorrecte. Tape exactement l'ID de l'ordonnance, ou '1' pour forcer.")
        return redirect("core_adminconsole:prescriptions_trash")

    p = get_object_or_404(Prescription, pk=pk)

    if not force:
        try:
            if not _can_purge_prescription(p):
                messages.error(
                    request,
                    f"Purge refusée pour l'ordonnance #{pk} : possible seulement après {PURGE_MIN_DAYS} jours et sous réserve des règles de sécurité."
                )
                return redirect("core_adminconsole:prescriptions_trash")
        except Exception as e:
            messages.error(request, f"Contrôle de sécurité purge impossible pour l'ordonnance #{pk} : {e}")
            return redirect("core_adminconsole:prescriptions_trash")

    try:
        p.delete()
        try:
            audit(
                request,
                action=AdminAuditEvent.Action.PURGE,
                summary=f"Ordonnance purgée #{pk}",
                target_type="Prescription",
                target_id=str(pk),
            )
        except Exception:
            pass

        messages.success(request, f"Ordonnance #{pk} purgée définitivement.")
    except ProtectedError as e:
        messages.error(request, f"Purge impossible pour l'ordonnance #{pk} : dépendances protégées ({e}).")
    except Exception as e:
        messages.error(request, f"Purge impossible pour l'ordonnance #{pk} : {e}")

    return redirect("core_adminconsole:prescriptions_trash")

@require_perm("core_adminconsole.patients_write")

def patient_edit(request, pk: int):
    """Admin Console: édition safe d'un titulaire (nom complet + téléphone)."""
    from django.contrib import messages
    from django.shortcuts import get_object_or_404, redirect, render

    patient = get_object_or_404(Patient, pk=pk)

    # Champs réellement présents dans ton modèle Patient (selon l'erreur Django)
    PHONE_FIELD = "phone_number"

    class PatientEditForm(forms.Form):
        full_name = forms.CharField(label="Nom complet", required=False, max_length=255)
        phone_number = forms.CharField(label="Téléphone", required=False, max_length=64)

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            # init depuis l'objet
            if hasattr(patient, "full_name"):
                self.fields["full_name"].initial = getattr(patient, "full_name") or ""
            if hasattr(patient, PHONE_FIELD):
                self.fields["phone_number"].initial = getattr(patient, PHONE_FIELD) or ""

        def save(self):
            changed_fields = []

            if hasattr(patient, "full_name"):
                val = (self.cleaned_data.get("full_name") or "").strip()
                if getattr(patient, "full_name") != val:
                    setattr(patient, "full_name", val)
                    changed_fields.append("full_name")

            if hasattr(patient, PHONE_FIELD):
                val = (self.cleaned_data.get("phone_number") or "").strip()
                if getattr(patient, PHONE_FIELD) != val:
                    setattr(patient, PHONE_FIELD, val)
                    changed_fields.append(PHONE_FIELD)

            if changed_fields:
                patient.save(update_fields=changed_fields)
            return changed_fields

    if request.method == "POST":
        form = PatientEditForm(request.POST)
        if form.is_valid():
            changed = form.save()
            if changed:
                messages.success(request, "Patient mis à jour ✅")
            else:
                messages.info(request, "Aucune modification.")
            return redirect("core_adminconsole:patients_list")
        messages.error(request, "Formulaire invalide (vérifie les champs).")
    else:
        form = PatientEditForm()

    return render(request, "core_adminconsole/patient_edit.html", {
        "patient": patient,
        "form": form,
    })



@require_perm("core_adminconsole.prescriptions_list")
def prescriptions_search(request: HttpRequest) -> HttpResponse:
    """
    Admin Console — Ordonnances (liste + recherche + pagination).
    Route attendue par urls.py : views.prescriptions_search
    """
    q = (request.GET.get("q") or "").strip()
    try:
        per_page_i = int(request.GET.get("per_page") or 25)
    except Exception:
        per_page_i = 25
    if per_page_i not in (10, 15, 25, 50, 100):
        per_page_i = 25

    qs = Prescription.objects.select_related("patient").all()

    # si le modèle a is_deleted, on peut masquer la corbeille ici
    try:
        qs = qs.filter(is_deleted=False)
    except Exception:
        pass

    if q:
        qs = qs.filter(
            Q(id__icontains=q)
            | Q(patient__full_name__icontains=q)
            | Q(patient__email__icontains=q)
            | Q(patient__phone_number__icontains=q)
        )

    qs = qs.order_by("-id")

    paginator = Paginator(qs, per_page_i)
    page_obj = paginator.get_page(request.GET.get("page") or 1)

    return render(
        request,
        "core_adminconsole/prescriptions_list.html",
        {
            "q": q,
            "page_obj": page_obj,
            "per_page": per_page_i,
            "total_count": paginator.count,
        },
    )

# compat: certaines routes/templates utilisent prescriptions_list
prescriptions_list = prescriptions_search


@require_POST
@require_perm("core_adminconsole.prescription_soft_delete")
def prescriptions_bulk_action(request):
    """
    Admin Console — action groupée ordonnances.

    V1 SAFE:
    - action supportée: trash uniquement
    - utilise les champs de corbeille existants si présents
    - notifications utilisateur via messages Django uniquement
    """
    action = (request.POST.get("bulk_action") or "").strip()
    raw_ids = request.POST.getlist("selected_prescriptions")

    ids = []
    for value in raw_ids:
        try:
            ids.append(int(value))
        except (TypeError, ValueError):
            continue

    if not ids:
        messages.warning(request, "Aucune ordonnance sélectionnée.")
        return redirect("core_adminconsole:prescriptions_list")

    if action != "trash":
        messages.error(request, "Action groupée non autorisée.")
        return redirect("core_adminconsole:prescriptions_list")

    qs = Prescription.objects.filter(id__in=ids)

    updated = 0
    now = timezone.now()

    for prescription in qs:
        changed = False

        if hasattr(prescription, "is_deleted"):
            setattr(prescription, "is_deleted", True)
            changed = True

        if hasattr(prescription, "deleted_at"):
            setattr(prescription, "deleted_at", now)
            changed = True

        if hasattr(prescription, "deleted_by"):
            setattr(prescription, "deleted_by", request.user)
            changed = True

        if changed:
            prescription.save()
            updated += 1

    if updated:
        messages.success(request, f"{updated} ordonnance(s) mise(s) en corbeille.")
    else:
        messages.warning(request, "Aucune ordonnance modifiée.")

    return redirect("core_adminconsole:prescriptions_list")


# === ADMINCONSOLE — CORBEILLE ORDONNANCES (V1 SAFE) ===
# But: réparer urls.py (views.prescriptions_trash + purge/restore/delete)
# et fournir un comportement stable même si certains champs n'existent pas.

PURGE_MIN_DAYS = 30

def _can_purge_prescription_safe(p) -> bool:
    """
    Garde-fou soft assoupli:
    - l'ordonnance doit être en corbeille (deleted_at renseigné)
    - deleted_at doit être antérieur d'au moins PURGE_MIN_DAYS
    - n'impose pas archived_at ni un statut ARCHIVED
    """
    try:
        da = getattr(p, "deleted_at", None)
        if not da:
            return False
        if timezone.is_naive(da):
            da = timezone.make_aware(da, timezone.get_current_timezone())
        return da <= timezone.now() - dt.timedelta(days=PURGE_MIN_DAYS)
    except Exception:
        return False

@require_perm("core_adminconsole.prescriptions_trash")
def prescriptions_trash(request):
    q = (request.GET.get("q") or "").strip()
    try:
        per_page_i = int(request.GET.get("per_page") or 25)
    except Exception:
        per_page_i = 25
    if per_page_i not in (10, 15, 25, 50, 100):
        per_page_i = 25

    qs = Prescription.objects.all()
    # ne lister que la corbeille si le champ existe
    try:
        qs = qs.filter(is_deleted=True)
    except Exception:
        # fallback: pas de corbeille possible sans champ => liste vide
        qs = qs.none()

    if q:
        qs = qs.filter(
            Q(id__icontains=q)
            | Q(patient__email__icontains=q)
            | Q(patient__phone_number__icontains=q)
            | Q(patient__full_name__icontains=q)
        )

    # tri
    try:
        qs = qs.order_by("-deleted_at", "-id")
    except Exception:
        qs = qs.order_by("-id")

    paginator = Paginator(qs, per_page_i)
    page_obj = paginator.get_page(request.GET.get("page") or 1)

    return render(
        request,
        "core_adminconsole/prescriptions_trash.html",
        {"q": q, "page_obj": page_obj, "per_page": per_page_i, "purge_min_days": PURGE_MIN_DAYS},
    )


@require_POST
@require_perm("core_adminconsole.prescription_soft_delete")
def prescription_soft_delete(request, pk: int):
    p = get_object_or_404(Prescription, pk=pk)
    reason = (request.POST.get("reason") or "").strip()

    # si méthode soft_delete existe, l'utiliser
    if hasattr(p, "soft_delete") and callable(getattr(p, "soft_delete")):
        try:
            p.soft_delete(actor=request.user, reason=reason)
        except TypeError:
            p.soft_delete()
    else:
        # fallback champs
        if hasattr(p, "is_deleted"):
            p.is_deleted = True
        if hasattr(p, "deleted_at"):
            p.deleted_at = timezone.now()
        if hasattr(p, "deleted_by"):
            p.deleted_by = request.user
        if hasattr(p, "delete_reason"):
            p.delete_reason = reason[:255]
        try:
            p.save()
        except Exception:
            pass

    try:
        audit(
            request,
            action="PRESCRIPTION_TRASH",
            summary=f"Ordonnance en corbeille id={p.pk}",
            target_type="Prescription",
            target_id=str(p.pk),
            metadata={"reason": reason[:255]},
        )
    except Exception:
        pass

    messages.success(request, "Ordonnance mise à la corbeille.")
    return redirect("core_adminconsole:prescriptions_list")


@require_POST
@require_perm("core_adminconsole.prescription_restore")
def prescription_restore(request, pk: int):
    p = get_object_or_404(Prescription, pk=pk)

    if hasattr(p, "restore") and callable(getattr(p, "restore")):
        try:
            p.restore(actor=request.user)
        except TypeError:
            p.restore()
    else:
        if hasattr(p, "is_deleted"):
            p.is_deleted = False
        if hasattr(p, "deleted_at"):
            p.deleted_at = None
        if hasattr(p, "deleted_by"):
            p.deleted_by = None
        if hasattr(p, "delete_reason"):
            p.delete_reason = ""
        try:
            p.save()
        except Exception:
            pass

    try:
        audit(
            request,
            action="PRESCRIPTION_RESTORE",
            summary=f"Ordonnance restaurée id={p.pk}",
            target_type="Prescription",
            target_id=str(p.pk),
            metadata={},
        )
    except Exception:
        pass

    messages.success(request, "Ordonnance restaurée.")
    return redirect("core_adminconsole:prescriptions_trash")


@require_POST
@login_required
@superuser_required
@require_perm("core_adminconsole.prescription_purge")
def prescription_purge(request, pk: int):
    """
    Purge définitive (superuser-only).
    Confirmation: taper l'ID dans le champ POST 'confirm' (ou '1' pour override).
    """
    p = get_object_or_404(Prescription, pk=pk)
    confirm = (request.POST.get("confirm") or "").strip()

    if confirm not in (str(pk), "1"):
        messages.error(request, "Confirmation incorrecte. Tape l'ID de l'ordonnance pour purger.")
        return redirect("core_adminconsole:prescriptions_trash")

    # délai mini (soft)
    if confirm != "1":
        if not _can_purge_prescription_safe(p):
            messages.error(
                request,
                f"Purge refusée: délai minimum {PURGE_MIN_DAYS}j non atteint (ou ordonnance non en corbeille)."
            )
            return redirect("core_adminconsole:prescriptions_trash")

    # tenter de supprimer fichiers pièces jointes si relation connue
    try:
        rel = getattr(p, "attachments", None)
        if rel is not None and hasattr(rel, "all"):
            for a in rel.all():
                f = getattr(a, "file", None)
                if f:
                    try:
                        f.delete(save=False)
                    except Exception:
                        pass
                try:
                    a.delete()
                except Exception:
                    pass
    except Exception:
        pass

    pid = getattr(p, "id", pk)

    try:
        # HARD DELETE via QuerySet pour éviter un éventuel delete() override de soft-delete
        deleted_count, _ = Prescription.objects.filter(pk=pk).delete()

        if deleted_count:
            try:
                audit(
                    request,
                    action="PRESCRIPTION_PURGE",
                    summary=f"Ordonnance purgée définitivement id={pid}",
                    target_type="Prescription",
                    target_id=str(pid),
                    metadata={"confirm": confirm},
                )
            except Exception:
                pass

            messages.success(request, f"Ordonnance #{pid} purgée définitivement.")
        else:
            messages.error(request, f"Purge: aucune suppression effective pour l'ordonnance #{pid}.")
    except ProtectedError:
        messages.error(
            request,
            "Purge bloquée: dépendances protégées (PROTECT). Supprime d'abord les objets liés."
        )
    except Exception as e:
        messages.error(request, f"Erreur purge: {e}")

    return redirect("core_adminconsole:prescriptions_trash")

# === /ADMINCONSOLE — CORBEILLE ORDONNANCES (V1 SAFE) ===

# --- ADMINCONSOLE_AUDIT_VIEWS_V1:BEGIN ---

import csv
from django.http import HttpResponse
from django.views.decorators.http import require_http_methods

def _audit_filter_qs(qs, q: str):
    q = (q or "").strip()
    if not q:
        return qs, ""
    return qs.filter(
        Q(action__icontains=q)
        | Q(summary__icontains=q)
        | Q(target_type__icontains=q)
        | Q(target_id__icontains=q)
        | Q(actor__username__icontains=q)
        | Q(actor__email__icontains=q)
        | Q(ip_address__icontains=q)
        | Q(user_agent__icontains=q)
    ), q

@require_perm("core_adminconsole.audit_log")
def audit_log(request):
    q = (request.GET.get("q") or "").strip()
    try:
        page_size = int(request.GET.get("page_size") or 25)
    except Exception:
        page_size = 25
    if page_size not in (10, 15, 25, 50, 100, 200):
        page_size = 25

    qs = AdminAuditEvent.objects.select_related("actor").all().order_by("-created_at", "-id")
    qs, q = _audit_filter_qs(qs, q)

    paginator = Paginator(qs, page_size)
    page_obj = paginator.get_page(request.GET.get("page") or 1)

    return render(
        request,
        "core_adminconsole/audit_log.html",
        {"page_obj": page_obj,
            "events": page_obj.object_list, "paginator": paginator, "q": q, "page_size": page_size},
    )

@require_perm("core_adminconsole.audit_export_csv")
def audit_export_csv(request):
    q = (request.GET.get("q") or "").strip()

    qs = AdminAuditEvent.objects.select_related("actor").all().order_by("-created_at", "-id")
    qs, q = _audit_filter_qs(qs, q)

    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = "attachment; filename=audit_adminconsole.csv"

    w = csv.writer(resp)
    w.writerow([
        "created_at", "action", "actor_id", "actor_username", "actor_email",
        "target_type", "target_id", "ip_address", "user_agent", "summary", "metadata",
    ])

    for e in qs.iterator():
        actor = getattr(e, "actor", None)
        w.writerow([
            getattr(e, "created_at", "") or "",
            getattr(e, "action", "") or "",
            getattr(e, "actor_id", "") or "",
            getattr(actor, "username", "") if actor else "",
            getattr(actor, "email", "") if actor else "",
            getattr(e, "target_type", "") or "",
            getattr(e, "target_id", "") or "",
            getattr(e, "ip_address", "") or "",
            getattr(e, "user_agent", "") or "",
            getattr(e, "summary", "") or "",
            getattr(e, "metadata", {}) or {},
        ])

    # journaliser l'export (best-effort)
    try:
        audit(request, action=AdminAuditEvent.Action.EXPORT_CSV, summary=f"Export CSV audit (q={q!r})", target_type="AdminAuditEvent", target_id="*")
    except Exception:
        pass

    return resp

@require_perm("core_adminconsole.audit_clear")
@require_POST
def audit_clear(request):
    # garde-fou: confirmation double
    confirm = (request.POST.get("confirm") or "").strip().lower()
    if confirm not in ("oui", "yes", "y", "ok", "confirm"):
        messages.error(request, "Confirmation requise. Tape 'oui' pour vider l'audit.")
        return redirect("core_adminconsole:audit_log")

    n = AdminAuditEvent.objects.count()
    AdminAuditEvent.objects.all().delete()

    try:
        audit(request, action=AdminAuditEvent.Action.PURGE, summary=f"Audit vidé ({n} lignes)", target_type="AdminAuditEvent", target_id="*")
    except Exception:
        pass

    messages.success(request, f"Audit vidé ({n} lignes).")
    return redirect("core_adminconsole:audit_log")
# --- ADMINCONSOLE_AUDIT_VIEWS_V1:END ---

# --- ADMINCONSOLE_URL_STUBS_V1:BEGIN ---

from django.http import HttpResponse
from django.shortcuts import redirect
from django.contrib.auth.models import User, Group
from django.contrib.auth.decorators import login_required, user_passes_test

def is_superuser(user):
    return user.is_authenticated and user.is_superuser


def admin_home(request):
    # Fallback: page d'accueil Admin Console
    try:
        return redirect('core_adminconsole:prescriptions_list')
    except Exception:
        return HttpResponse('Admin Console', content_type='text/plain; charset=utf-8')

def account_create(request, *args, **kwargs):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return redirect("/accounts/login/?next=/admin-console/accounts/create/")

    if not getattr(request.user, "is_superuser", False):
        return HttpResponse("Forbidden", status=403, content_type="text/plain; charset=utf-8")

    if request.method == "POST":
        form = UserAdminCreateForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data

            user = User.objects.create_user(
                username=cd["username"],
                email=cd.get("email") or "",
                password=cd["password1"],
            )
            user.first_name = cd.get("first_name") or ""
            user.last_name = cd.get("last_name") or ""
            user.is_active = bool(cd.get("is_active"))
            user.is_staff = bool(cd.get("is_staff"))
            user.is_superuser = bool(cd.get("is_superuser"))
            user.save()

            try:
                user.groups.set(cd.get("groups") or [])
            except Exception:
                pass

            try:
                user.user_permissions.set(cd.get("user_permissions") or [])
            except Exception:
                pass

            try:
                audit(
                    request,
                    action=AdminAuditEvent.Action.ACCOUNT_CREATE,
                    summary=f"Compte créé: {_user_label(user)}",
                    target_type="User",
                    target_id=str(user.pk),
                )
            except Exception:
                pass

            messages.success(request, f"Compte créé: {user.username}")
            return redirect("core_adminconsole:accounts_list")
    else:
        form = UserAdminCreateForm()

    return render(
        request,
        "core_adminconsole/account_create.html",
        {
            "form": form,
        },
    )

@login_required
@user_passes_test(is_superuser)
def account_edit(request, user_id):
    user_obj = get_object_or_404(User, id=user_id)

    if request.method == "POST":
        username = (request.POST.get("username") or "").strip()
        email = (request.POST.get("email") or "").strip()
        first_name = (request.POST.get("first_name") or "").strip()
        last_name = (request.POST.get("last_name") or "").strip()
        is_active = request.POST.get("is_active") == "on"
        is_staff = request.POST.get("is_staff") == "on"
        group_ids = request.POST.getlist("groups")

        if not username:
            messages.error(request, "Le nom d'utilisateur est obligatoire.")
        else:
            existing_qs = User.objects.filter(username=username).exclude(id=user_obj.id)
            if existing_qs.exists():
                messages.error(request, "Ce nom d'utilisateur existe déjà.")
            else:
                user_obj.username = username
                user_obj.email = email
                user_obj.first_name = first_name
                user_obj.last_name = last_name
                user_obj.is_active = is_active
                user_obj.is_staff = is_staff
                user_obj.save()

                groups = Group.objects.filter(id__in=group_ids)
                user_obj.groups.set(groups)

                messages.success(request, "Compte mis à jour avec succès.")
                return redirect(request.META.get("HTTP_REFERER", "/admin-console/"))

    groups = Group.objects.all().order_by("name")

    return render(
        request,
        "core_adminconsole/account_edit.html",
        {
            "edit_user": user_obj,
            "groups": groups,
        },
    )

@login_required
@user_passes_test(is_superuser)
def account_reactivate(request, user_id):
    from django.contrib.auth.models import User
    from django.shortcuts import get_object_or_404, redirect
    from django.contrib import messages

    user_obj = get_object_or_404(User, id=user_id)

    # Sécurité : éviter de se modifier soi-même si besoin
    if request.user.id == user_obj.id:
        messages.warning(request, "Vous ne pouvez pas modifier votre propre statut ici.")
        return redirect(request.META.get("HTTP_REFERER", "/admin-console/"))

    if user_obj.is_active:
        messages.info(request, f"Le compte {user_obj.username} est déjà actif.")
    else:
        user_obj.is_active = True
        user_obj.save()
        messages.success(request, f"Compte {user_obj.username} réactivé avec succès.")

    return redirect(request.META.get("HTTP_REFERER", "/admin-console/"))
def account_soft_delete(request, *args, **kwargs):
    return HttpResponse('Not implemented: core_adminconsole.views.account_soft_delete', content_type='text/plain; charset=utf-8')

def account_soft_delete_confirm(request, *args, **kwargs):
    return HttpResponse('Not implemented: core_adminconsole.views.account_soft_delete_confirm', content_type='text/plain; charset=utf-8')

@login_required
@user_passes_test(is_superuser)
def account_toggle_active(request, user_id):
    from django.contrib.auth.models import User
    from django.shortcuts import get_object_or_404, redirect
    from django.contrib import messages

    user_obj = get_object_or_404(User, id=user_id)

    # Sécurité : éviter de désactiver soi-même
    if request.user.id == user_obj.id:
        messages.error(request, "Vous ne pouvez pas désactiver votre propre compte.")
        return redirect(request.META.get("HTTP_REFERER", "/admin-console/"))

    # Toggle actif
    user_obj.is_active = not user_obj.is_active
    user_obj.save()

    status = "activé" if user_obj.is_active else "désactivé"
    messages.success(request, f"Compte {user_obj.username} {status} avec succès.")

    return redirect(request.META.get("HTTP_REFERER", "/admin-console/"))
def accounts_list(request, *args, **kwargs):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return redirect("/accounts/login/?next=/admin-console/accounts/")

    if not getattr(request.user, "is_superuser", False):
        return HttpResponse("Forbidden", status=403, content_type="text/plain; charset=utf-8")

    q = (request.GET.get("q") or "").strip()

    qs = User.objects.all().prefetch_related("groups")

    if q:
        qs = qs.filter(
            Q(username__icontains=q)
            | Q(email__icontains=q)
            | Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
        )

    users = qs.order_by("username", "id")

    return render(
        request,
        "core_adminconsole/accounts_list.html",
        {
            "q": q,
            "users": users,
        },
    )

def gmail_tools(request, *args, **kwargs):
    return HttpResponse('Not implemented: core_adminconsole.views.gmail_tools', content_type='text/plain; charset=utf-8')

def group_create(request, *args, **kwargs):
    from django.contrib.auth.models import Group, Permission

    class GroupAdminCreateForm(forms.Form):
        name = forms.CharField(max_length=150, required=True, label="Nom du groupe")
        permissions = forms.ModelMultipleChoiceField(
            queryset=Permission.objects.all().select_related("content_type").order_by("content_type__app_label", "codename"),
            required=False,
            widget=forms.SelectMultiple,
            label="Permissions",
        )

        def clean_name(self):
            name = (self.cleaned_data.get("name") or "").strip()
            if not name:
                raise forms.ValidationError("Nom du groupe obligatoire.")
            if Group.objects.filter(name=name).exists():
                raise forms.ValidationError("Un groupe avec ce nom existe déjà.")
            return name

    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return redirect("/accounts/login/?next=/admin-console/groups/create/")

    if not getattr(request.user, "is_superuser", False):
        return HttpResponse("Forbidden", status=403, content_type="text/plain; charset=utf-8")

    if request.method == "POST":
        form = GroupAdminCreateForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data

            group = Group.objects.create(name=cd["name"])

            try:
                group.permissions.set(cd.get("permissions") or [])
            except Exception:
                pass

            try:
                audit(
                    request,
                    action=getattr(AdminAuditEvent.Action, "GROUP_CREATE", "GROUP_CREATE"),
                    summary=f"Groupe créé: {group.name}",
                    target_type="Group",
                    target_id=str(group.pk),
                )
            except Exception:
                pass

            messages.success(request, f"Groupe créé: {group.name}")
            return redirect("core_adminconsole:groups_list")
    else:
        form = GroupAdminCreateForm()

    return render(
        request,
        "core_adminconsole/group_form.html",
        {
            "form": form,
            "mode": "create",
            "target": None,
        },
    )

@require_POST
def group_delete(request, group_id, *args, **kwargs):
    from django.contrib.auth.models import Group

    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return redirect("/accounts/login/?next=/admin-console/groups/")

    if not getattr(request.user, "is_superuser", False):
        return HttpResponse("Forbidden", status=403, content_type="text/plain; charset=utf-8")

    group = get_object_or_404(Group, pk=group_id)
    group_label = getattr(group, "name", "") or f"Groupe #{group.pk}"

    try:
        group.delete()
        try:
            audit(
                request,
                action=getattr(AdminAuditEvent.Action, "GROUP_DELETE", "GROUP_DELETE"),
                summary=f"Groupe supprimé: {group_label}",
                target_type="Group",
                target_id=str(group_id),
            )
        except Exception:
            pass

        messages.success(request, f"Groupe supprimé: {group_label}")
    except Exception as e:
        messages.error(request, f"Suppression impossible: {e}")

    return redirect("core_adminconsole:groups_list")

def group_delete_confirm(request, group_id, *args, **kwargs):
    from django.contrib.auth.models import Group

    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return redirect("/accounts/login/?next=/admin-console/groups/")

    if not getattr(request.user, "is_superuser", False):
        return HttpResponse("Forbidden", status=403, content_type="text/plain; charset=utf-8")

    group = get_object_or_404(
        Group.objects.prefetch_related("permissions", "user_set"),
        pk=group_id,
    )

    return render(
        request,
        "core_adminconsole/group_delete_confirm.html",
        {
            "target": group,
            "group": group,
        },
    )

def group_edit(request, group_id, *args, **kwargs):
    from django.contrib.auth.models import Group, Permission

    class GroupAdminEditForm(forms.Form):
        name = forms.CharField(max_length=150, required=True, label="Nom du groupe")
        permissions = forms.ModelMultipleChoiceField(
            queryset=Permission.objects.all().select_related("content_type").order_by("content_type__app_label", "codename"),
            required=False,
            widget=forms.SelectMultiple,
            label="Permissions",
        )

        def __init__(self, *args, **kwargs):
            self.instance = kwargs.pop("instance", None)
            super().__init__(*args, **kwargs)

        def clean_name(self):
            name = (self.cleaned_data.get("name") or "").strip()
            if not name:
                raise forms.ValidationError("Nom du groupe obligatoire.")
            qs = Group.objects.filter(name=name)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError("Un groupe avec ce nom existe déjà.")
            return name

    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return redirect("/accounts/login/?next=/admin-console/groups/")

    if not getattr(request.user, "is_superuser", False):
        return HttpResponse("Forbidden", status=403, content_type="text/plain; charset=utf-8")

    group = get_object_or_404(Group, pk=group_id)

    if request.method == "POST":
        form = GroupAdminEditForm(request.POST, instance=group)
        if form.is_valid():
            cd = form.cleaned_data
            old_name = group.name

            group.name = cd["name"]
            group.save()

            try:
                group.permissions.set(cd.get("permissions") or [])
            except Exception:
                pass

            try:
                audit(
                    request,
                    action=getattr(AdminAuditEvent.Action, "GROUP_EDIT", "GROUP_EDIT"),
                    summary=f"Groupe modifié: {old_name} -> {group.name}",
                    target_type="Group",
                    target_id=str(group.pk),
                )
            except Exception:
                pass

            messages.success(request, f"Groupe modifié: {group.name}")
            return redirect("core_adminconsole:groups_list")
    else:
        form = GroupAdminEditForm(
            instance=group,
            initial={
                "name": group.name,
                "permissions": group.permissions.all(),
            },
        )

    return render(
        request,
        "core_adminconsole/group_form.html",
        {
            "form": form,
            "mode": "edit",
            "target": group,
        },
    )

def groups_list(request, *args, **kwargs):
    from django.contrib.auth.models import Group

    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return redirect("/accounts/login/?next=/admin-console/groups/")

    if not getattr(request.user, "is_superuser", False):
        return HttpResponse("Forbidden", status=403, content_type="text/plain; charset=utf-8")

    q = (request.GET.get("q") or "").strip()

    qs = Group.objects.all().prefetch_related("permissions", "user_set")

    if q:
        qs = qs.filter(name__icontains=q)

    groups = qs.order_by("name", "id")

    return render(
        request,
        "core_adminconsole/groups_list.html",
        {
            "q": q,
            "groups": groups,
        },
    )

def iam_matrix(request, *args, **kwargs):
    from django.contrib.auth.models import Group, Permission

    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return redirect("/accounts/login/?next=/admin-console/iam/")

    if not getattr(request.user, "is_superuser", False):
        return HttpResponse("Forbidden", status=403, content_type="text/plain; charset=utf-8")

    q = (request.GET.get("q") or "").strip()

    groups = list(
        Group.objects.all().prefetch_related("permissions").order_by("name", "id")
    )

    permissions_qs = Permission.objects.select_related("content_type").order_by(
        "content_type__app_label",
        "codename",
        "id",
    )

    if q:
        permissions_qs = permissions_qs.filter(
            Q(codename__icontains=q)
            | Q(name__icontains=q)
            | Q(content_type__app_label__icontains=q)
            | Q(content_type__model__icontains=q)
        )
        groups = [
            g for g in groups
            if q.lower() in (g.name or "").lower()
            or any(
                q.lower() in ((p.codename or "").lower())
                or q.lower() in ((p.name or "").lower())
                or q.lower() in ((getattr(p.content_type, "app_label", "") or "").lower())
                for p in g.permissions.all()
            )
        ]

    group_perm_ids = {
        g.id: {p.id for p in g.permissions.all()}
        for g in groups
    }

    rows = []
    for perm in permissions_qs:
        action = (perm.name or perm.codename or "").strip()
        row = {
            "action": action,
            "codename": perm.codename,
            "permission": perm,
            "cells": [],
        }

        has_any = False
        for g in groups:
            enabled = perm.id in group_perm_ids.get(g.id, set())
            if enabled:
                has_any = True
            row["cells"].append({
                "group": g,
                "enabled": enabled,
            })

        if q:
            if has_any or q.lower() in action.lower() or q.lower() in (perm.codename or "").lower():
                rows.append(row)
        else:
            rows.append(row)

    return render(
        request,
        "core_adminconsole/iam_matrix.html",
        {
            "q": q,
            "groups": groups,
            "rows": rows,
        },
    )

def notifications_settings(request):
    """
    Admin Console — Notifications (Global)
    V1: page UI (placeholder) pour:
      - kill-switch SMS / Email
      - templates globaux
      - garde-fous RGPD (pas de nom patient / pas d’info médicale dans SMS)
    """
    from django.shortcuts import render

    return render(
        request,
        "core_adminconsole/notifications_settings.html",
        {
            "section": "notifications",
        },
    )

def nurse_create(request):
    """
    Admin Console — Création d'un mandataire de retrait (Infirmier)
    Métier:
      - crée une Person avec role="nurse"
      - is_active=True par défaut
      - champs: first_name, last_name, email, phone
    UI:
      - réutilise le template core_adminconsole/nurse_form.html (mode=create)
    """
    from django.contrib import messages
    from django.shortcuts import redirect, render
    from django import forms
    from core_people.models import Person

    class NurseCreateForm(forms.ModelForm):
        class Meta:
            model = Person
            fields = ["first_name", "last_name", "email", "phone"]

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            # style UI cohérent (si tes classes existent)
            for f in self.fields.values():
                try:
                    f.widget.attrs.setdefault("class", "px-input")
                except Exception:
                    pass

        def clean_email(self):
            email = (self.cleaned_data.get("email") or "").strip()
            return email

        def clean_phone(self):
            phone = (self.cleaned_data.get("phone") or "").strip()
            return phone

    if request.method == "POST":
        form = NurseCreateForm(request.POST)
        if form.is_valid():
            nurse = form.save(commit=False)
            nurse.role = "nurse"
            nurse.is_active = True
            nurse.save()
            messages.success(request, "✅ Mandataire de retrait créé.")
            return redirect("core_adminconsole:nurses_list")
        messages.error(request, "❌ Merci de corriger les erreurs du formulaire.")
    else:
        form = NurseCreateForm()

    return render(
        request,
        "core_adminconsole/nurse_form.html",
        {"form": form, "mode": "create"},
    )

def nurse_edit(request, *args, **kwargs):
    return HttpResponse('Not implemented: core_adminconsole.views.nurse_edit', content_type='text/plain; charset=utf-8')

def nurse_toggle_confirm(request, pk: int, action: str):
    """
    Admin Console — Confirmation + exécution (Activer/Désactiver) d'un mandataire de retrait.

    URL:
      /admin-console/nurses/<pk>/activate/
      /admin-console/nurses/<pk>/deactivate/

    Sécurité:
      - GET = affiche la confirmation
      - POST + CSRF + confirm=1 = exécute l'action
    """
    from django.contrib import messages
    from django.http import Http404
    from django.shortcuts import get_object_or_404, redirect, render

    # Audit (optionnel selon ton code)
    try:
        from .services import audit as audit_log
    except Exception:
        audit_log = None

    try:
        from core_people.models import Person
    except Exception as e:
        raise Http404("Modèle Person introuvable") from e

    action = (action or "").strip().lower()
    if action not in ("activate", "deactivate"):
        raise Http404("Action inconnue")

    nurse = get_object_or_404(Person, pk=pk)

    # garde-fou métier : on ne toggle que les Person role nurse
    # (si ton modèle ne possède pas role, on évite de casser)
    role = getattr(nurse, "role", None)
    if role is not None and str(role) != "nurse":
        raise Http404("Ce profil n’est pas un mandataire de retrait")

    if request.method == "POST":
        if (request.POST.get("confirm") or "") != "1":
            messages.error(request, "Confirmation requise (confirm=1).")
            return redirect("core_adminconsole:nurses_list")

        want_active = True if action == "activate" else False

        # no-op friendly
        if getattr(nurse, "is_active", True) == want_active:
            if want_active:
                messages.info(request, "ℹ️ Ce mandataire est déjà actif.")
            else:
                messages.info(request, "ℹ️ Ce mandataire est déjà inactif.")
            return redirect("core_adminconsole:nurses_list")

        nurse.is_active = want_active
        nurse.save(update_fields=["is_active"])

        # Audit SaaS
        if audit_log:
            try:
                audit_log(
                    request,
                    action=f"nurse.{action}",
                    summary=("Réactivation mandataire" if want_active else "Désactivation mandataire"),
                    target_type="Person",
                    target_id=str(nurse.pk),
                    metadata={
                        "role": getattr(nurse, "role", None),
                        "email": getattr(nurse, "email", None),
                    },
                )
            except Exception:
                pass

        if want_active:
            messages.success(request, "✅ Mandataire réactivé.")
        else:
            messages.success(request, "✅ Mandataire désactivé.")

        return redirect("core_adminconsole:nurses_list")

    # GET = page de confirmation
    return render(
        request,
        "core_adminconsole/nurse_confirm_toggle.html",
        {"nurse": nurse, "action": action},
    )

def nurses_list(request, *args, **kwargs):
    """
    Admin Console — Infirmiers mandatés (Person.role="nurse")
    - filtre chips state: all|active|inactive
    - compteurs chips
    """
    from django.shortcuts import render
    from django.db.models import Q, Count
    from core_people.models import Person

    q = (request.GET.get("q") or "").strip()
    state = (request.GET.get("state") or "all").strip().lower()

    base = (
        Person.objects
        .filter(role="nurse")
        .annotate(
            assigned_total=Count("assigned_prescriptions", distinct=True),
            assigned_active=Count(
                "assigned_prescriptions",
                filter=Q(assigned_prescriptions__prescription__is_deleted=False),
                distinct=True,
            ),
        )
        .order_by("-updated_at", "-id")
    )

    if q:
        base = base.filter(
            Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(email__icontains=q)
            | Q(phone__icontains=q)
        )

    counts = {
        "all": base.count(),
        "active": base.filter(is_active=True).count(),
        "inactive": base.filter(is_active=False).count(),
    }

    qs = base
    if state == "active":
        qs = qs.filter(is_active=True)
    elif state == "inactive":
        qs = qs.filter(is_active=False)
    else:
        state = "all"

    state_items = [
        ("all", "Tous", counts["all"]),
        ("active", "Actifs", counts["active"]),
        ("inactive", "Inactifs", counts["inactive"]),
    ]

    return render(
        request,
        "core_adminconsole/nurses_list.html",
        {"nurses": qs, "q": q, "state": state, "state_items": state_items},
    )

def patients_list(request, *args, **kwargs):
    """
    Admin Console — Patients (métier)
    - base: uniquement patients ayant >=1 ordonnance
    - compteurs par filtre (chips): all/active/inactive/delivered/archived/trash
    - actif = ordonnance ouverte (non supprimée, non livrée, non archivée)
    """
    from django.shortcuts import render
    from django.core.paginator import Paginator
    from django.db.models import Q, Count
    from core_patients.models import Patient

    q = (request.GET.get("q") or "").strip()
    flt = (request.GET.get("filter") or "all").strip().lower()

    try:
        per_page = int(request.GET.get("per_page") or 25)
    except Exception:
        per_page = 25
    if per_page not in (10, 15, 25, 50, 100):
        per_page = 25

    CLOSED_STATUSES = ["Livrée", "Archivée"]

    base = (
        Patient.objects
        .filter(prescriptions__isnull=False)
        .distinct()
        .annotate(
            prescriptions_total=Count("prescriptions", distinct=True),
            prescriptions_trash=Count("prescriptions", filter=Q(prescriptions__is_deleted=True), distinct=True),
            prescriptions_delivered=Count(
                "prescriptions",
                filter=Q(prescriptions__is_deleted=False) & Q(prescriptions__status="Livrée"),
                distinct=True,
            ),
            prescriptions_archived=Count(
                "prescriptions",
                filter=Q(prescriptions__is_deleted=False) & Q(prescriptions__status="Archivée"),
                distinct=True,
            ),
            prescriptions_active=Count(
                "prescriptions",
                filter=Q(prescriptions__is_deleted=False) & ~Q(prescriptions__status__in=CLOSED_STATUSES),
                distinct=True,
            ),
        )
    )

    if q:
        base = base.filter(
            Q(full_name__icontains=q)
            | Q(email__icontains=q)
            | Q(phone_number__icontains=q)
        )

    # Compteurs (chips) calculés AVANT application du filtre courant
    counts = {
        "all": base.count(),
        "active": base.filter(prescriptions_active__gt=0).count(),
        "inactive": base.filter(prescriptions_active__lte=0).count(),
        "delivered": base.filter(prescriptions_delivered__gt=0).count(),
        "archived": base.filter(prescriptions_archived__gt=0).count(),
        "trash": base.filter(prescriptions_trash__gt=0).count(),
    }

    # Appliquer filtre courant
    qs = base
    if flt == "active":
        qs = qs.filter(prescriptions_active__gt=0)
    elif flt == "inactive":
        qs = qs.filter(prescriptions_active__lte=0)
    elif flt == "delivered":
        qs = qs.filter(prescriptions_delivered__gt=0)
    elif flt == "archived":
        qs = qs.filter(prescriptions_archived__gt=0)
    elif flt == "trash":
        qs = qs.filter(prescriptions_trash__gt=0)
    else:
        flt = "all"

    qs = qs.order_by("-created_at", "-id")

    paginator = Paginator(qs, per_page)
    page_obj = paginator.get_page(request.GET.get("page") or 1)

    filter_items = [
        ("all", "Tous", counts["all"]),
        ("active", "Actifs", counts["active"]),
        ("inactive", "Inactifs", counts["inactive"]),
        ("delivered", "Livrées", counts["delivered"]),
        ("archived", "Archivées", counts["archived"]),
        ("trash", "Corbeille", counts["trash"]),
    ]

    return render(
        request,
        "core_adminconsole/patients_list.html",
        {
            "patients": page_obj.object_list,
            "page_obj": page_obj,
            "q": q,
            "per_page": per_page,
            "filter": flt,
            "filter_items": filter_items,
            "total_count": paginator.count,
        },
    )

def users_home(request, *args, **kwargs):
    return HttpResponse('Not implemented: core_adminconsole.views.users_home', content_type='text/plain; charset=utf-8')

# --- ADMINCONSOLE_URL_STUBS_V1:END ---

@login_required
@user_passes_test(is_superuser)
def account_soft_delete_confirm(request, user_id):
    user_obj = get_object_or_404(User, id=user_id)

    if request.method == "POST":
        if request.user.id == user_obj.id:
            messages.error(request, "Vous ne pouvez pas supprimer logiquement votre propre compte.")
            return redirect(request.META.get("HTTP_REFERER", "/admin-console/"))

        # Soft delete simplifié :
        # dans l'état actuel du projet, on conserve les données
        # et on désactive le compte.
        user_obj.is_active = False
        user_obj.save()

        messages.success(
            request,
            f"Compte {user_obj.username} marqué comme supprimé logiquement. "
            f"Le compte est désactivé et les données sont conservées."
        )
        return redirect(request.META.get("HTTP_REFERER", "/admin-console/"))

    return render(
        request,
        "core_adminconsole/account_soft_delete_confirm.html",
        {
            "user_obj": user_obj,
            "soft_delete_explanation": (
                "Le soft delete correspond à une suppression logique : "
                "le compte est retiré de l'usage normal sans suppression physique des données."
            ),
            "deactivate_explanation": (
                "La désactivation bloque simplement l'accès au compte, souvent de façon temporaire."
            ),
        },
    )

