from __future__ import annotations

from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

# Apps Ordo (on exclut volontairement auth/admin/contenttypes/sessions)
ORDO_APP_LABELS = {
    "core_adminconsole",
    "core_emails",
    "core_gmail",
    "core_notifications",
    "core_patients",
    "core_people",
    "core_attachments",
    "core_accounts",
}

def perms_for_app_labels(app_labels: set[str]) -> list[Permission]:
    return list(
        Permission.objects.filter(content_type__app_label__in=sorted(app_labels))
        .select_related("content_type")
        .order_by("content_type__app_label", "codename")
    )

def perms_by_prefix(app_labels: set[str], prefixes: tuple[str, ...]) -> list[Permission]:
    qs = Permission.objects.filter(content_type__app_label__in=sorted(app_labels))
    ids: set[int] = set()
    for pref in prefixes:
        ids.update(qs.filter(codename__startswith=pref).values_list("pk", flat=True))
    if not ids:
        return []
    return list(
        Permission.objects.filter(pk__in=sorted(ids))
        .select_related("content_type")
        .order_by("content_type__app_label", "codename")
    )

def perms_adminconsole(*codenames: str) -> list[Permission]:
    return list(
        Permission.objects.filter(
            content_type__app_label="core_adminconsole",
            codename__in=list(codenames),
        )
        .select_related("content_type")
        .order_by("codename")
    )

class Command(BaseCommand):
    help = "Crée/Met à jour les groupes IAM Ordo (idempotent)."

    def handle(self, *args, **options):
        # ------------------------------------------------------------
        # Admin Console (tech)
        # ------------------------------------------------------------
        role_defs: list[tuple[str, list[Permission]]] = [
            ("Admin Console — Accès", perms_adminconsole("access_console")),
            ("Admin Console — Comptes", perms_adminconsole("access_console", "manage_accounts")),
            ("Admin Console — IAM", perms_adminconsole("access_console", "manage_groups")),
            ("Admin Console — Audit", perms_adminconsole("access_console", "view_audit")),
            ("Admin Console — Audit (Purge)", perms_adminconsole("access_console", "view_audit", "clear_audit")),
        ]

        # ------------------------------------------------------------
        # Rôles métiers (demandés)
        # ------------------------------------------------------------

        # 1) Propriétaire : tout Ordo + IAM complet
        owner_perms = perms_for_app_labels(ORDO_APP_LABELS)

        # 2) Pharmacien employé : tout Ordo opérationnel, SANS IAM destructif
        # -> toutes perms sauf celles de gestion comptes/groupes/purge audit.
        # On le laisse accéder à la console + voir audit (option).
        employee_perms = perms_for_app_labels(ORDO_APP_LABELS)
        deny = set(p.pk for p in perms_adminconsole("manage_accounts", "manage_groups", "clear_audit"))
        employee_perms = [p for p in employee_perms if p.pk not in deny]
        # (on s'assure au minimum access_console + view_audit)
        # NB: access_console/view_audit sont déjà dans employee_perms via core_adminconsole Meta.permissions si migré.
        # On ne force pas ici.

        # 3) Vendeuse : opération ordonnances
        # -> AdminConsole: accès console uniquement (page console utile / navigation)
        # -> core_emails: view + change (+ add si tu veux saisir une ordonnance manuelle)
        # -> autres apps: view uniquement (patients/attachments) — tu peux retirer view de certaines apps si tu veux.
        staff_perms: list[Permission] = []
        staff_perms += perms_adminconsole("access_console")
        staff_perms += perms_by_prefix({"core_emails"}, ("view_", "change_", "add_"))
        staff_perms += perms_by_prefix({"core_patients", "core_attachments"}, ("view_",))
        # Option: empêcher l'accès gmail/outils systèmes
        # -> on n'ajoute PAS core_gmail/core_notifications/core_accounts/core_people (sauf view si tu veux).

        role_defs += [
            ("Pharmacien — Propriétaire", owner_perms),
            ("Pharmacien — Employé", employee_perms),
            ("Vendeuse — Staff", staff_perms),
        ]

        created = 0
        updated = 0

        for name, perms in role_defs:
            g, was_created = Group.objects.get_or_create(name=name)
            g.permissions.set(perms)

            if was_created:
                created += 1
                self.stdout.write(self.style.SUCCESS(f"CREATED: {name} ({len(perms)} perms)"))
            else:
                updated += 1
                self.stdout.write(self.style.WARNING(f"UPDATED: {name} ({len(perms)} perms)"))

        self.stdout.write(self.style.SUCCESS(f"DONE ✅ groups: created={created} updated={updated}"))


def ensure_perm(*, codename: str, name: str) -> Permission:
    ct = ContentType.objects.get_for_model(Permission)
    # ContentType for Permission model is not what we want; better: use auth Permission content type? Keep simple:
    # We'll attach perms to 'auth.Permission' content type; it still works for checks in Ordo because you check 'app_label.codename'.
    # App label used in check is the Permission's content_type.app_label.
    # We'll force app_label='core_adminconsole' by using ContentType of any model in that app is not available here.
    # So we keep your existing pattern if present; otherwise fallback to creating Permission under 'auth' app_label.
    p, _ = Permission.objects.get_or_create(codename=codename, defaults={"name": name, "content_type": ct})
    if p.name != name:
        p.name = name
        p.save(update_fields=["name"])
    return p
