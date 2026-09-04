"""
ORDO V9 - Moteur de règles configurables pour les renouvellements.

Ce fichier est volontairement isolé pour éviter toute régression :
- ne modifie pas compute_renewals_watch() dans ce lot ;
- ne modifie pas le dashboard ;
- ne modifie pas les vues ;
- ne modifie pas le workflow ;
- ne remplace pas encore la logique V8 reminder_5 / reminder_3.

Objectif :
préparer le calcul V9 basé sur RenewalNotificationRule et Holiday.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional

from django.db.models import Q, QuerySet
from django.utils import timezone

from .models import (
    Holiday,
    Prescription,
    PrescriptionRenewalCycle,
    RenewalNotificationDelivery,
    RenewalNotificationRule,
)


# Une réservation protège contre les doubles envois concurrents, mais elle ne
# doit pas bloquer définitivement un rappel si le processus est interrompu.
DELIVERY_CLAIM_LEASE = timedelta(minutes=15)


def _today(value: Optional[date] = None) -> date:
    """
    Retourne une date propre.

    Si today est fourni en datetime, on prend uniquement .date().
    """
    if value is None:
        return timezone.localdate()

    if isinstance(value, datetime):
        return value.date()

    return value


def get_active_renewal_rules() -> QuerySet:
    """
    Retourne les règles de notification actives.

    Aucune valeur J-5 / J-1 n'est codée ici.
    Les délais viennent exclusivement de RenewalNotificationRule.
    """
    return (
        RenewalNotificationRule.objects
        .filter(active=True)
        .order_by("sort_order", "-days_before", "name")
    )


def calculate_notification_date(due_date: Any, rule: RenewalNotificationRule) -> Optional[date]:
    """
    Calcule la date de notification :

    date_notification = date_echeance - rule.days_before

    Si la notification tombe sur un jour fermé, elle est reportée
    au prochain jour ouvert.
    """
    if not due_date or rule is None:
        return None

    if isinstance(due_date, datetime):
        base_date = due_date.date()
    elif isinstance(due_date, date):
        base_date = due_date
    else:
        return None

    try:
        days_before = int(rule.days_before)
    except (TypeError, ValueError):
        return None

    notification_date = base_date - timedelta(days=days_before)
    return move_to_next_open_day(notification_date)


def is_closed_day(value: Any) -> bool:
    """
    Indique si une date est fermée.

    Règles actuelles V9 Lot 4 :
    - dimanche fermé ;
    - Holiday actif en base.

    La pharmacie ouvre lundi-samedi.
    """
    if not value:
        return False

    if isinstance(value, datetime):
        day = value.date()
    elif isinstance(value, date):
        day = value
    else:
        return False

    # Dimanche = 6 en Python.
    if day.weekday() == 6:
        return True

    return Holiday.objects.filter(date=day, active=True).exists()


def move_to_next_open_day(value: Any) -> Optional[date]:
    """
    Reporte une date au prochain jour ouvert si nécessaire.

    Sécurité :
    boucle limitée à 14 jours pour éviter tout blocage.
    """
    if not value:
        return None

    if isinstance(value, datetime):
        current = value.date()
    elif isinstance(value, date):
        current = value
    else:
        return None

    safety = 0
    while is_closed_day(current) and safety < 14:
        current = current + timedelta(days=1)
        safety += 1

    return current


def _get_cycle_due_date(cycle: Any) -> Optional[date]:
    """
    Calcule l'échéance réelle d'un cycle de renouvellement V9.

    Règle métier V9 :
    - le cycle 1 correspond à la délivrance initiale ;
    - le cycle 2 correspond au renouvellement 1 ;
    - le cycle 3 correspond au renouvellement 2 ;
    - échéance patient = date du premier DELIVERED + cycle_number * period_days.

    La fonction reste défensive :
    - si un ancien champ due_date existe, il est prioritaire ;
    - sinon, on calcule depuis l'historique DELIVERED.
    """
    # 1) Compatibilité éventuelle avec anciens champs.
    for attr in [
        "due_date",
        "expected_due_date",
        "next_due_date",
        "renewal_due_date",
    ]:
        value = getattr(cycle, attr, None)
        if value:
            if isinstance(value, datetime):
                return value.date()
            if isinstance(value, date):
                return value

    prescription = getattr(cycle, "prescription", None)
    if prescription is None:
        return None

    renewal_info = getattr(prescription, "renewal_info", None)
    if renewal_info is None:
        return None

    try:
        period_days = int(getattr(renewal_info, "period_days", 0) or 0)
        cycle_number = int(getattr(cycle, "cycle_number", 0) or 0)
    except (TypeError, ValueError):
        return None

    if period_days <= 0 or cycle_number <= 0:
        return None

    # 2) Source officielle patient : première délivrance réelle.
    try:
        from core_emails.models import PrescriptionStatusHistory, PrescriptionStatus

        first_delivered_at = (
            PrescriptionStatusHistory.objects
            .filter(
                prescription=prescription,
                new_status=PrescriptionStatus.DELIVERED,
            )
            .order_by("changed_at")
            .values_list("changed_at", flat=True)
            .first()
        )
    except Exception:
        first_delivered_at = None

    if first_delivered_at:
        if isinstance(first_delivered_at, datetime):
            start_date = first_delivered_at.date()
        elif isinstance(first_delivered_at, date):
            start_date = first_delivered_at
        else:
            start_date = None

        if start_date:
            try:
                return start_date + timedelta(days=cycle_number * period_days)
            except (TypeError, ValueError, OverflowError):
                return None

    # 3) Fallback si pas encore délivré : date médecin + cycle_number * period_days.
    established_at = getattr(prescription, "established_at", None)
    if established_at:
        if isinstance(established_at, datetime):
            established_at = established_at.date()
        if isinstance(established_at, date):
            try:
                return established_at + timedelta(days=cycle_number * period_days)
            except (TypeError, ValueError, OverflowError):
                return None

    return None


def _get_active_cycles() -> QuerySet:
    """
    Retourne les cycles non clôturés / non délivrés.

    Cette fonction reste prudente et n'écrit aucune donnée.
    """
    qs = PrescriptionRenewalCycle.objects.select_related(
        "prescription",
        "prescription__patient",
        "prescription__renewal_info",
    )

    if hasattr(PrescriptionRenewalCycle, "status"):
        qs = qs.exclude(status="DELIVERED").exclude(status="ARCHIVED")

    if hasattr(PrescriptionRenewalCycle, "closed_at"):
        qs = qs.filter(closed_at__isnull=True)

    return qs


def _legacy_channel_field(rule: RenewalNotificationRule, channel: str) -> Optional[str]:
    """Retourne le marqueur legacy correspondant à un délai et un canal."""
    try:
        days = int(rule.days_before)
    except (TypeError, ValueError):
        return None

    fields_by_day = {
        5: {
            "email": "reminder_5_patient_email_sent_at",
            "sms": "reminder_5_patient_sms_sent_at",
        },
        3: {
            "email": "reminder_3_patient_email_sent_at",
            "sms": "reminder_3_patient_sms_sent_at",
        },
        1: {
            "email": "reminder_1_patient_email_sent_at",
            "sms": "reminder_1_patient_sms_sent_at",
        },
    }
    return fields_by_day.get(days, {}).get(channel.lower())


def _rule_channel_already_sent(
    cycle: Any,
    rule: RenewalNotificationRule,
    channel: str,
    *,
    blocking_delivery_keys=None,
) -> bool:
    normalized_channel = str(channel or "").upper()
    cycle_id = getattr(cycle, "pk", None)
    rule_id = getattr(rule, "pk", None)
    if not cycle_id or not rule_id or normalized_channel not in {"SMS", "EMAIL"}:
        return False

    key = (cycle_id, rule_id, normalized_channel)
    if blocking_delivery_keys is not None:
        return key in blocking_delivery_keys

    pending_cutoff = timezone.now() - DELIVERY_CLAIM_LEASE
    return RenewalNotificationDelivery.objects.filter(
        cycle_id=cycle_id,
        rule_id=rule_id,
        channel=normalized_channel,
    ).filter(
        Q(status=RenewalNotificationDelivery.STATUS_SENT)
        | Q(
            status=RenewalNotificationDelivery.STATUS_PENDING,
            claimed_at__gte=pending_cutoff,
        )
    ).exists()


def _blocking_delivery_keys(cycles, rules):
    """Charge une seule fois les livraisons qui bloquent réellement un envoi."""
    cycle_ids = [cycle.pk for cycle in cycles if getattr(cycle, "pk", None)]
    rule_ids = [rule.pk for rule in rules if getattr(rule, "pk", None)]
    if not cycle_ids or not rule_ids:
        return set()

    pending_cutoff = timezone.now() - DELIVERY_CLAIM_LEASE
    rows = RenewalNotificationDelivery.objects.filter(
        cycle_id__in=cycle_ids,
        rule_id__in=rule_ids,
        status__in=[
            RenewalNotificationDelivery.STATUS_PENDING,
            RenewalNotificationDelivery.STATUS_SENT,
        ],
    ).values_list("cycle_id", "rule_id", "channel", "status", "claimed_at")

    return {
        (cycle_id, rule_id, channel)
        for cycle_id, rule_id, channel, status, claimed_at in rows
        if status == RenewalNotificationDelivery.STATUS_SENT
        or (
            status == RenewalNotificationDelivery.STATUS_PENDING
            and claimed_at >= pending_cutoff
        )
    }


def renewal_sms_template_key(base_key: str, rule=None, cycle=None) -> str:
    """Ajoute les identités règle/cycle à la clé anti-doublon SMS."""
    normalized = str(base_key or "renewal")
    rule_id = getattr(rule, "pk", None)
    cycle_id = getattr(cycle, "pk", None)
    if not rule_id and not cycle_id:
        return normalized[:100]

    suffix_parts = []
    if rule_id:
        suffix_parts.append(f":rule:{rule_id}")
    if cycle_id:
        suffix_parts.append(f":cycle:{cycle_id}")
    suffix = "".join(suffix_parts)
    return f"{normalized[: max(0, 100 - len(suffix))]}{suffix}"


def claim_rule_channel(
    cycle: PrescriptionRenewalCycle,
    rule: RenewalNotificationRule,
    channel: str,
) -> Optional[RenewalNotificationDelivery]:
    """Réserve atomiquement un canal avant l'appel au fournisseur.

    La contrainte unique ``cycle/rule/channel`` arbitre les appels concurrents.
    Une livraison en échec peut être reprise ; une réservation en cours ou un
    envoi réussi bloque toute nouvelle émission.
    """
    normalized_channel = str(channel or "").upper()
    if normalized_channel not in {"SMS", "EMAIL"}:
        raise ValueError("Canal de renouvellement invalide.")
    if not getattr(cycle, "pk", None) or not getattr(rule, "pk", None):
        raise ValueError("Le cycle et la règle doivent être enregistrés.")

    claimed_at = timezone.now()
    delivery, created = RenewalNotificationDelivery.objects.get_or_create(
        cycle=cycle,
        rule=rule,
        channel=normalized_channel,
        defaults={
            "status": RenewalNotificationDelivery.STATUS_PENDING,
            "claimed_at": claimed_at,
            "sent_at": None,
            "failure_reason": "",
        },
    )
    if created:
        return delivery

    pending_cutoff = claimed_at - DELIVERY_CLAIM_LEASE
    reclaimed = RenewalNotificationDelivery.objects.filter(pk=delivery.pk).filter(
        Q(status=RenewalNotificationDelivery.STATUS_FAILED)
        | Q(
            status=RenewalNotificationDelivery.STATUS_PENDING,
            claimed_at__lt=pending_cutoff,
        )
    ).update(
        status=RenewalNotificationDelivery.STATUS_PENDING,
        claimed_at=claimed_at,
        sent_at=None,
        failure_reason="",
    )
    if not reclaimed:
        return None

    delivery.refresh_from_db()
    return delivery


def mark_rule_channel_failed(
    delivery: RenewalNotificationDelivery,
    *,
    reason: str = "",
) -> None:
    """Marque une réservation comme échouée afin qu'elle soit retentable."""
    if not getattr(delivery, "pk", None):
        return
    RenewalNotificationDelivery.objects.filter(
        pk=delivery.pk,
        status=RenewalNotificationDelivery.STATUS_PENDING,
    ).update(
        status=RenewalNotificationDelivery.STATUS_FAILED,
        sent_at=None,
        failure_reason=str(reason or "")[:500],
    )


def mark_rule_channel_sent(
    cycle: PrescriptionRenewalCycle,
    rule: RenewalNotificationRule,
    channel: str,
    *,
    sent_at=None,
) -> RenewalNotificationDelivery:
    """Marque un canal envoyé, quelle que soit la valeur ``days_before``."""
    normalized_channel = str(channel or "").upper()
    if normalized_channel not in {"SMS", "EMAIL"}:
        raise ValueError("Canal de renouvellement invalide.")
    if not getattr(cycle, "pk", None) or not getattr(rule, "pk", None):
        raise ValueError("Le cycle et la règle doivent être enregistrés.")

    marker_time = sent_at or timezone.now()
    delivery, created = RenewalNotificationDelivery.objects.get_or_create(
        cycle=cycle,
        rule=rule,
        channel=normalized_channel,
        defaults={
            "status": RenewalNotificationDelivery.STATUS_SENT,
            "claimed_at": marker_time,
            "sent_at": marker_time,
            "failure_reason": "",
        },
    )
    if not created and delivery.status != RenewalNotificationDelivery.STATUS_SENT:
        RenewalNotificationDelivery.objects.filter(pk=delivery.pk).update(
            status=RenewalNotificationDelivery.STATUS_SENT,
            sent_at=marker_time,
            failure_reason="",
        )
        delivery.refresh_from_db()

    legacy_field = _legacy_channel_field(rule, normalized_channel)
    if legacy_field and not getattr(cycle, legacy_field, None):
        setattr(cycle, legacy_field, marker_time)
        cycle.save(update_fields=[legacy_field])

    return delivery


def _rule_already_sent(
    cycle: Any,
    rule: RenewalNotificationRule,
    *,
    blocking_delivery_keys=None,
) -> bool:
    """
    Évite les doublons grâce à la trace générique cycle/règle/canal.

    Les marqueurs historiques J-5/J-3/J-1 sont convertis en traces génériques
    par la migration, afin qu'ils ne puissent pas masquer une autre règle du
    même jour.
    """
    enabled_channels = []
    if bool(getattr(rule, "send_sms", False)):
        enabled_channels.append("sms")
    if bool(getattr(rule, "send_email", False)):
        enabled_channels.append("email")

    if not enabled_channels:
        return True

    return all(
        _rule_channel_already_sent(
            cycle,
            rule,
            channel,
            blocking_delivery_keys=blocking_delivery_keys,
        )
        for channel in enabled_channels
    )


def get_due_notifications(today: Optional[date] = None) -> List[Dict[str, Any]]:
    """
    Retourne les notifications à envoyer aujourd'hui selon les règles V9.

    Retour :
    [
        {
            "cycle": cycle,
            "prescription": prescription,
            "rule": rule,
            "due_date": date_echeance,
            "notification_date": date_notification,
            "send_sms": bool,
            "send_email": bool,
        }
    ]

    Ce service ne modifie rien.
    Il ne fait aucun envoi.
    """
    current_day = _today(today)
    results: List[Dict[str, Any]] = []

    rules = list(get_active_renewal_rules())
    if not rules:
        return results

    cycles = list(_get_active_cycles())
    blocking_delivery_keys = _blocking_delivery_keys(cycles, rules)

    for cycle in cycles:
        due_date = _get_cycle_due_date(cycle)
        if not due_date:
            continue

        for rule in rules:
            notification_date = calculate_notification_date(due_date, rule)
            # V9 Lot 18 : rattrapage automatique.
            # Si le serveur était arrêté le jour prévu,
            # on traite aussi les notifications passées non encore envoyées.
            if notification_date > current_day:
                continue

            if _rule_already_sent(
                cycle,
                rule,
                blocking_delivery_keys=blocking_delivery_keys,
            ):
                continue

            send_sms = (
                bool(getattr(rule, "send_sms", False))
                and not _rule_channel_already_sent(
                    cycle,
                    rule,
                    "sms",
                    blocking_delivery_keys=blocking_delivery_keys,
                )
            )
            send_email = (
                bool(getattr(rule, "send_email", False))
                and not _rule_channel_already_sent(
                    cycle,
                    rule,
                    "email",
                    blocking_delivery_keys=blocking_delivery_keys,
                )
            )

            if not send_sms and not send_email:
                continue

            results.append({
                "cycle": cycle,
                "prescription": getattr(cycle, "prescription", None),
                "rule": rule,
                "due_date": due_date,
                "notification_date": notification_date,
                "send_sms": send_sms,
                "send_email": send_email,
            })

    return results


def get_overdue_renewals(today: Optional[date] = None) -> List[Dict[str, Any]]:
    """
    Retourne les cycles en retard.

    Un cycle est en retard si :
    aujourd'hui > date échéance
    """
    current_day = _today(today)
    results: List[Dict[str, Any]] = []

    for cycle in _get_active_cycles():
        due_date = _get_cycle_due_date(cycle)
        if not due_date:
            continue

        if current_day > due_date:
            results.append({
                "cycle": cycle,
                "prescription": getattr(cycle, "prescription", None),
                "due_date": due_date,
                "overdue_days": (current_day - due_date).days,
            })

    return results


def _get_remaining_cycles(cycle: Any) -> Optional[int]:
    """
    Calcule les cycles restants si les informations sont disponibles.
    """
    prescription = getattr(cycle, "prescription", None)
    renewal_info = getattr(prescription, "renewal_info", None) if prescription else None

    if renewal_info is None:
        return None

    total = getattr(renewal_info, "renewal_times", None)
    done = getattr(renewal_info, "renewal_done_count", None)

    try:
        if total is not None and done is not None:
            return max(int(total) - int(done), 0)
    except (TypeError, ValueError):
        return None

    return None


def _get_final_alert_threshold_cycles() -> int:
    """
    Retourne le seuil d'alerte avant dernier renouvellement.

    Par défaut :
    - 0 = uniquement le dernier cycle réel, exemple Cycle 6/6.

    Si un seuil est configuré plus tard :
    - 1 = alerte aussi un cycle avant la fin, exemple Cycle 5/6.
    """
    try:
        from django.conf import settings
        value = getattr(settings, "ORDO_RENEWAL_FINAL_ALERT_THRESHOLD_CYCLES", 0)
        value = int(value or 0)
        return max(0, value)
    except Exception:
        return 0


def _get_cycle_total_cycles(cycle: Any) -> Optional[int]:
    """
    Nombre total de cycles patient.

    Règle V9 :
    total_cycles = renewal_times + 1

    Exemple :
    renewal_times = 2
    total_cycles = 3
    Cycle 1 = initial
    Cycle 2 = renouvellement 1
    Cycle 3 = renouvellement 2
    """
    prescription = getattr(cycle, "prescription", None)
    if prescription is None:
        return None

    renewal_info = getattr(prescription, "renewal_info", None)
    if renewal_info is None:
        return None

    try:
        renewal_times = int(getattr(renewal_info, "renewal_times", 0) or 0)
    except (TypeError, ValueError):
        return None

    if renewal_times < 0:
        return None

    return renewal_times + 1


def _get_cycle_remaining_until_final(cycle: Any) -> Optional[int]:
    """
    Nombre de cycles restants avant la fin, à partir du cycle courant.

    Exemple :
    Cycle 5/6 => 1
    Cycle 6/6 => 0
    """
    total_cycles = _get_cycle_total_cycles(cycle)
    if total_cycles is None:
        return None

    try:
        current_cycle_number = int(getattr(cycle, "cycle_number", 0) or 0)
    except (TypeError, ValueError):
        return None

    if current_cycle_number <= 0:
        return None

    return max(0, total_cycles - current_cycle_number)


def get_final_renewals(today: Optional[date] = None) -> List[Dict[str, Any]]:
    """
    Retourne les cycles considérés comme derniers renouvellements.

    Règle métier V9 :
    - cycle courant = dernier cycle réel ;
    - ou seuil configuré atteint si disponible.

    Exemples :
    - Cycle 6/6 avec seuil 0 => final ;
    - Cycle 12/12 avec seuil 0 => final ;
    - Cycle 5/6 avec seuil 1 => final précoce.

    Cette fonction :
    - ne crée aucun cycle ;
    - ne modifie aucune donnée ;
    - ne touche pas renewal_done_count ;
    - conserve l'historique.
    """
    threshold = _get_final_alert_threshold_cycles()
    results: List[Dict[str, Any]] = []

    for cycle in _get_active_cycles():
        total_cycles = _get_cycle_total_cycles(cycle)
        remaining_until_final = _get_cycle_remaining_until_final(cycle)

        if total_cycles is None or remaining_until_final is None:
            continue

        try:
            current_cycle_number = int(getattr(cycle, "cycle_number", 0) or 0)
        except (TypeError, ValueError):
            continue

        is_final = remaining_until_final <= threshold

        if not is_final:
            continue

        due_date = _get_cycle_due_date(cycle)

        results.append({
            "cycle": cycle,
            "prescription": getattr(cycle, "prescription", None),
            "cycle_number": current_cycle_number,
            "current_cycle_number": current_cycle_number,
            "total_cycles": total_cycles,
            "remaining_cycles": remaining_until_final,
            "remaining_until_final": remaining_until_final,
            "threshold": threshold,
            "due_date": due_date,
            "reason": "DERNIER_RENOUVELLEMENT" if remaining_until_final == 0 else "PROCHE_DERNIER_RENOUVELLEMENT",
        })

    return results


def get_urgent_renewals(today: Optional[date] = None) -> List[Dict[str, Any]]:
    """
    Retourne les urgences métier.

    Lot 4 :
    une urgence est :
    - un retard ;
    - un dernier renouvellement ;
    - une notification due avec échéance proche selon les règles configurées.

    Cette fonction ne modifie rien.
    """
    current_day = _today(today)
    urgent: List[Dict[str, Any]] = []

    seen = set()

    for item in get_overdue_renewals(today=current_day):
        cycle = item.get("cycle")
        key = getattr(cycle, "id", id(cycle))
        seen.add(key)
        item["reason"] = "RETARD"
        urgent.append(item)

    for item in get_final_renewals(today=current_day):
        cycle = item.get("cycle")
        key = getattr(cycle, "id", id(cycle))
        if key not in seen:
            seen.add(key)
            item["reason"] = "DERNIER_RENOUVELLEMENT"
            urgent.append(item)

    for item in get_due_notifications(today=current_day):
        cycle = item.get("cycle")
        key = getattr(cycle, "id", id(cycle))
        if key not in seen:
            due_date = item.get("due_date")
            if due_date and (due_date - current_day).days <= 5:
                seen.add(key)
                item["reason"] = "ECHEANCE_PROCHE"
                urgent.append(item)

    return urgent


def get_activity_metrics(today: Optional[date] = None) -> Dict[str, int]:
    """
    Retourne les métriques d'activité automatique Ordo V9.

    Objectif :
    - alimenter le dashboard ;
    - ne jamais faire planter l'interface ;
    - ne pas créer de logs parallèles ;
    - utiliser les modèles existants en priorité.

    Métriques :
    - sms_sent_today
    - emails_sent_today
    - cycles_created_today
    - cycles_closed_today
    - overdue_detected
    - urgent_detected
    """
    current_day = _today(today)

    metrics = {
        "sms_sent_today": 0,
        "emails_sent_today": 0,
        "cycles_created_today": 0,
        "cycles_closed_today": 0,
        "overdue_detected": 0,
        "urgent_detected": 0,
    }

    day_start = datetime.combine(current_day, datetime.min.time())
    day_end = datetime.combine(current_day, datetime.max.time())

    try:
        from django.utils import timezone
        if timezone.is_naive(day_start):
            day_start = timezone.make_aware(day_start, timezone.get_current_timezone())
        if timezone.is_naive(day_end):
            day_end = timezone.make_aware(day_end, timezone.get_current_timezone())
    except Exception:
        pass

    # 1) SMS envoyés aujourd'hui
    try:
        from core_notifications.models import SmsMessage

        metrics["sms_sent_today"] = SmsMessage.objects.filter(
            sent_at__gte=day_start,
            sent_at__lte=day_end,
        ).count()
    except Exception:
        try:
            from core_notifications.models import SmsAttempt

            metrics["sms_sent_today"] = SmsAttempt.objects.filter(
                success=True,
                requested_at__gte=day_start,
                requested_at__lte=day_end,
            ).count()
        except Exception:
            metrics["sms_sent_today"] = 0

    # 2) Emails envoyés aujourd'hui
    # Les rappels patient sont comptés par livraison (une ligne par
    # cycle/règle/canal). L'email médecin reste un marqueur historique séparé.
    try:
        from core_emails.models import PrescriptionRenewalCycle

        patient_email_count = RenewalNotificationDelivery.objects.filter(
            channel=RenewalNotificationDelivery.CHANNEL_EMAIL,
            status=RenewalNotificationDelivery.STATUS_SENT,
            sent_at__gte=day_start,
            sent_at__lte=day_end,
        ).count()
        doctor_email_count = PrescriptionRenewalCycle.objects.filter(
            doctor_email_sent_at__gte=day_start,
            doctor_email_sent_at__lte=day_end,
        ).count()
        metrics["emails_sent_today"] = (
            patient_email_count + doctor_email_count
        )
    except Exception:
        metrics["emails_sent_today"] = 0

    # 3) Cycles créés aujourd'hui
    try:
        from core_emails.models import PrescriptionRenewalCycle

        metrics["cycles_created_today"] = PrescriptionRenewalCycle.objects.filter(
            started_at__gte=day_start,
            started_at__lte=day_end,
        ).count()
    except Exception:
        metrics["cycles_created_today"] = 0

    # 4) Cycles clôturés aujourd'hui
    try:
        from core_emails.models import PrescriptionRenewalCycle

        metrics["cycles_closed_today"] = PrescriptionRenewalCycle.objects.filter(
            closed_at__gte=day_start,
            closed_at__lte=day_end,
        ).count()
    except Exception:
        metrics["cycles_closed_today"] = 0

    # 5) Retards détectés
    try:
        metrics["overdue_detected"] = len(get_overdue_renewals(today=current_day))
    except Exception:
        metrics["overdue_detected"] = 0

    # 6) Urgences détectées
    try:
        metrics["urgent_detected"] = len(get_urgent_renewals(today=current_day))
    except Exception:
        metrics["urgent_detected"] = 0

    return metrics
