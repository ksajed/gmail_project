import datetime
import uuid
from django.urls import reverse

from django.apps import apps
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from core_emails.models import (
    Prescription,
    PrescriptionType,
    PrescriptionStatus,
    PrescriptionStatusHistory,
    PrescriptionRenewalEvent,
    PrescriptionRenewalInfo,
)


def _rand_email():
    return f"t_{uuid.uuid4().hex[:10]}@example.com"


def make_minimal_instance(Model, **overrides):
    data = {}
    for f in Model._meta.fields:
        if f.primary_key:
            continue
        if f.name in overrides:
            continue
        if getattr(f, "auto_now", False) or getattr(f, "auto_now_add", False):
            continue
        if getattr(f, "null", False) or getattr(f, "blank", False):
            continue
        if f.has_default():
            continue

        itype = f.get_internal_type()
        if itype in ("CharField", "TextField", "SlugField"):
            data[f.name] = f"{f.name}_{uuid.uuid4().hex[:6]}"
        elif itype in ("EmailField",):
            data[f.name] = _rand_email()
        elif itype in ("IntegerField", "SmallIntegerField", "PositiveIntegerField", "BigIntegerField"):
            data[f.name] = 0
        elif itype in ("BooleanField",):
            data[f.name] = False
        elif itype in ("DateField",):
            data[f.name] = timezone.localdate()
        elif itype in ("DateTimeField",):
            data[f.name] = timezone.now()
        elif itype in ("FloatField", "DecimalField"):
            data[f.name] = 0
        elif itype == "ForeignKey":
            rel = f.remote_field.model
            if rel == get_user_model():
                pass
            else:
                try:
                    data[f.name] = make_minimal_instance(rel)
                except Exception:
                    pass

    data.update(overrides)
    return Model.objects.create(**data)


def set_first_delivered_at(prescription, user, delivered_date):
    dt = timezone.make_aware(datetime.datetime.combine(delivered_date, datetime.time(12, 0)))
    h = PrescriptionStatusHistory.objects.create(
        prescription=prescription,
        old_status=prescription.status,
        new_status=PrescriptionStatus.DELIVERED,
        changed_by=user,
        comment="TEST: first delivered",
    )
    PrescriptionStatusHistory.objects.filter(pk=h.pk).update(changed_at=dt)
    return dt


@override_settings(
    ALLOWED_HOSTS=["testserver", "localhost"],
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class RenewalsFunctionalTests(TestCase):
    def setUp(self):
        self.client = Client(HTTP_HOST="localhost")
        User = get_user_model()
        self.user = User.objects.create_user(username="u1", password="pass12345")
        self.client.login(username="u1", password="pass12345")

        Patient = apps.get_model("core_patients", "Patient")
        kwargs = {"email": _rand_email()}
        if any(f.name == "phone_number" for f in Patient._meta.fields):
            kwargs["phone_number"] = "0600000000"
        self.patient = make_minimal_instance(Patient, **kwargs)

    def _mk_prescription(self, *, delivered_date, renewal_times, done_count, period_days=30):
        p = Prescription.objects.create(
            type=PrescriptionType.RENOUVELLEMENT,
            status=PrescriptionStatus.DELIVERED,
            patient=self.patient,
        )
        set_first_delivered_at(p, self.user, delivered_date)

        info, _ = PrescriptionRenewalInfo.objects.get_or_create(prescription=p)
        info.renewal_times = renewal_times
        info.renewal_done_count = done_count
        info.period_days = period_days
        info.save()
        return p

    def test_dashboard_returns_200(self):
        resp = self.client.get("/dashboard/renewals/")
        self.assertEqual(resp.status_code, 200)

    def test_mark_done_merge_truncate_and_limit(self):
        today = timezone.localdate()
        period = 30

        p = self._mk_prescription(
            delivered_date=today - datetime.timedelta(days=period),
            renewal_times=1,
            done_count=0,
            period_days=period,
        )

        PrescriptionRenewalEvent.objects.create(
            prescription=p,
            number=1,
            created_by=self.user,
            note="Rappel renouvellement patient (EMAIL) — RETARD.",
        )

        long_note = "X" * 400
        r1 = self.client.post(f"/renewal/{p.pk}/done/", {"note": long_note}, follow=False)
        self.assertEqual(r1.status_code, 302)

        info = PrescriptionRenewalInfo.objects.get(prescription=p)
        self.assertEqual(int(info.renewal_done_count), 1)

        ev = PrescriptionRenewalEvent.objects.get(prescription=p, number=1)
        self.assertIn("Renouvellement marqué comme réalisé.", ev.note or "")
        self.assertLessEqual(len(ev.note or ""), 255)
        self.assertTrue((ev.note or "").endswith("..."))

        r2 = self.client.post(f"/renewal/{p.pk}/done/", {"note": "DONE again"}, follow=False)
        self.assertEqual(r2.status_code, 302)

        info.refresh_from_db()
        self.assertEqual(int(info.renewal_done_count), 1)
        self.assertEqual(PrescriptionRenewalEvent.objects.filter(prescription=p).count(), 1)

    def test_mark_done_modal_popup_present_in_html(self):
        from django.utils import timezone
        from django.db import models
        from django.contrib.auth import get_user_model
        from django.urls import reverse
        import uuid

        from core_emails.models import (
            Prescription,
            PrescriptionRenewalInfo,
            PrescriptionType,
            PrescriptionStatus,
        )

        User = get_user_model()
        user = getattr(self, "user", None)
        if user is None:
            user = User.objects.create_user(username=f"u{uuid.uuid4().hex[:8]}", password="pass12345")
        self.client.force_login(user)

        def _min_val(field):
            if getattr(field, "choices", None):
                ch = list(field.choices)
                if ch:
                    return ch[0][0]
            if isinstance(field, models.UUIDField):
                return uuid.uuid4()
            if isinstance(field, models.EmailField):
                return f"u{uuid.uuid4().hex[:8]}@example.com"
            if isinstance(field, (models.CharField, models.TextField, models.SlugField)):
                return f"{field.name}_{uuid.uuid4().hex[:8]}"
            if isinstance(field, (models.IntegerField, models.BigIntegerField, models.SmallIntegerField,
                                  models.PositiveIntegerField, models.PositiveSmallIntegerField)):
                return 1
            if isinstance(field, models.BooleanField):
                return False
            if isinstance(field, models.DateTimeField):
                return timezone.now()
            if isinstance(field, models.DateField):
                return timezone.now().date()
            if isinstance(field, models.TimeField):
                return timezone.now().time().replace(microsecond=0)
            if isinstance(field, models.DecimalField):
                return 0
            if isinstance(field, models.FloatField):
                return 0.0
            if isinstance(field, models.URLField):
                return "https://example.com"
            if field.__class__.__name__ == "JSONField":
                return {}
            if isinstance(field, models.FileField):
                return ""
            return 1

        def _min_create(model, overrides=None, depth=0, seen=None):
            overrides = overrides or {}
            if seen is None:
                seen = set()
            key = model._meta.label
            if key in seen or depth > 3:
                return model.objects.create(**overrides)
            seen = set(seen)
            seen.add(key)

            data = {}
            for field in model._meta.concrete_fields:
                if getattr(field, "primary_key", False) or getattr(field, "auto_created", False):
                    continue
                if field.name in overrides:
                    continue
                if getattr(field, "auto_now", False) or getattr(field, "auto_now_add", False):
                    continue
                if field.default is not models.NOT_PROVIDED:
                    continue
                if getattr(field, "null", False):
                    continue

                if isinstance(field, (models.ForeignKey, models.OneToOneField)):
                    rel = field.remote_field.model
                    if rel == User:
                        data[field.name] = user
                    else:
                        data[field.name] = _min_create(rel, depth=depth + 1, seen=seen)
                else:
                    data[field.name] = _min_val(field)

            data.update(overrides)
            return model.objects.create(**data)

        p = getattr(self, "p", None) or getattr(self, "prescription", None) or Prescription.objects.first()
        if p is None:
            p = _min_create(Prescription)

        # Forcer type/status si dispo
        if hasattr(p, "type") and hasattr(PrescriptionType, "RENOUVELLEMENT"):
            try:
                p.type = PrescriptionType.RENOUVELLEMENT
            except Exception:
                pass
        if hasattr(p, "status") and hasattr(PrescriptionStatus, "DELIVERED"):
            try:
                p.status = PrescriptionStatus.DELIVERED
            except Exception:
                pass
        p.save()

        info, _ = PrescriptionRenewalInfo.objects.get_or_create(prescription=p)
        # Assurer renouvellement actif
        if hasattr(info, "renewal_times"):
            info.renewal_times = max(int(getattr(info, "renewal_times", 0) or 0), 1)
        if hasattr(info, "renewal_done_count"):
            info.renewal_done_count = 0
        if hasattr(info, "period_days") and not getattr(info, "period_days", None):
            info.period_days = 30
        info.save()

        url = reverse("core_emails:mark_renewal_done", args=[p.id])
        resp = self.client.post(url, {"note": "DONE popup test"}, follow=True, HTTP_HOST="localhost")
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode("utf-8", errors="ignore")

        self.assertIn('id="renewalDoneModal"', html)
        self.assertIn("Renouvellement marqué comme réalisé.", html)
        self.assertTrue(
            ('openModal("renewalDoneModal")' in html)
            or ("openModal('renewalDoneModal')" in html)
        )

    def test_mark_done_limit_reached_shows_modal_popup(self):
        # Crée une ordonnance renouvellement et simule quota atteint (done == times)
        from django.utils import timezone
        from core_emails.models import Prescription, PrescriptionType, PrescriptionRenewalInfo
        from django.urls import reverse

        # On réutilise l'utilisateur créé dans setUp (self.user)
        # On crée une Prescription minimale (adaptée à ton modèle)
        p = Prescription.objects.create(
            status="DELIVERED" or "DELIVERED",
            type=PrescriptionType.RENOUVELLEMENT,
        )

        info, _ = PrescriptionRenewalInfo.objects.get_or_create(prescription=p)
        info.renewal_times = 1
        info.renewal_done_count = 1  # => next_number = 2 > 1 => quota atteint
        info.save()

        url = reverse("core_emails:mark_renewal_done", args=[p.id])
        resp = self.client.post(url, {}, follow=True, HTTP_HOST="localhost")

        html = resp.content.decode("utf-8")
        self.assertEqual(resp.status_code, 200)

        # On attend le modal overlay et le texte du quota atteint
        self.assertIn('id="renewalDoneModal"', html)
        self.assertIn("Nombre de renouvellements autorisés déjà atteint.", html)

