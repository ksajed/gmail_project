from __future__ import annotations
from typing import Any
from django.http import HttpRequest
from .models import AdminAuditEvent

def get_client_ip(request: HttpRequest) -> str | None:
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")

def audit(
    request: HttpRequest,
    *,
    action: str,
    summary: str = "",
    target_type: str = "",
    target_id: str = "",
    metadata: dict[str, Any] | None = None,
) -> None:
    AdminAuditEvent.objects.create(
        actor=request.user if getattr(request, "user", None) and request.user.is_authenticated else None,
        action=action,
        summary=summary,
        target_type=target_type,
        target_id=str(target_id or ""),
        metadata=metadata or {},
        ip_address=get_client_ip(request),
    )
