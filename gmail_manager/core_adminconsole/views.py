from __future__ import annotations
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST

from .permissions import superuser_required
from .services import audit
from .models import AdminAuditEvent

from django.contrib.auth import get_user_model
User = get_user_model()

@login_required
@superuser_required
def admin_home(request: HttpRequest) -> HttpResponse:
    audit(request, action=AdminAuditEvent.Action.LOGIN, summary="Ouverture Admin Console")
    return render(request, "core_adminconsole/home.html", {"users_count": User.objects.count()})

@login_required
@superuser_required
def accounts_list(request: HttpRequest) -> HttpResponse:
    q = (request.GET.get("q") or "").strip()
    qs = User.objects.all().order_by("-date_joined")
    if q:
        qs = qs.filter(Q(username__icontains=q) | Q(email__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q))
    return render(request, "core_adminconsole/accounts_list.html", {"q": q, "users": qs[:200]})

@login_required
@superuser_required
@require_POST
def account_toggle_active(request: HttpRequest, user_id: int) -> HttpResponse:
    u = User.objects.filter(pk=user_id).first()
    if not u:
        return redirect("core_adminconsole:accounts_list")
    u.is_active = not u.is_active
    u.save(update_fields=["is_active"])
    audit(
        request,
        action=AdminAuditEvent.Action.ACCOUNT_DISABLE if not u.is_active else AdminAuditEvent.Action.ACCOUNT_ENABLE,
        summary=f"User {u.pk} active={u.is_active}",
        target_type="User",
        target_id=str(u.pk),
    )
    return redirect("core_adminconsole:accounts_list")

@login_required
@superuser_required
def audit_log(request: HttpRequest) -> HttpResponse:
    q = (request.GET.get("q") or "").strip()
    qs = AdminAuditEvent.objects.all()
    if q:
        qs = qs.filter(Q(summary__icontains=q) | Q(action__icontains=q) | Q(target_id__icontains=q))
    return render(request, "core_adminconsole/audit_log.html", {"q": q, "events": qs[:200]})
