from __future__ import annotations
from functools import wraps
from django.http import HttpResponseForbidden

def superuser_required(view):
    @wraps(view)
    def _wrapped(request, *args, **kwargs):
        u = getattr(request, "user", None)
        if not u or not u.is_authenticated:
            return view(request, *args, **kwargs)
        if not u.is_superuser:
            return HttpResponseForbidden("Accès réservé (superuser).")
        return view(request, *args, **kwargs)
    return _wrapped


# --- ADMINCONSOLE_PERMISSIONS_V2:BEGIN ---
def require_console_perm(codename: str):
    """Autorise superuser ou permission core_adminconsole.<codename>."""
    full_perm = f"core_adminconsole.{codename}"

    def decorator(view):
        @wraps(view)
        def _wrapped(request, *args, **kwargs):
            u = getattr(request, "user", None)
            if not u or not u.is_authenticated:
                return HttpResponseForbidden("Non authentifié.")
            if u.is_superuser:
                return view(request, *args, **kwargs)
            if not u.has_perm(full_perm):
                return HttpResponseForbidden("Accès refusé (droits insuffisants).")
            return view(request, *args, **kwargs)
        return _wrapped
    return decorator
# --- ADMINCONSOLE_PERMISSIONS_V2:END ---

# --- Ordo Admin Console: Permission decorator (added by patch) ---
from functools import wraps
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden

def require_perm(perm_codename: str):
    """
    Decorator: autorise si superuser OU si user.has_perm(perm_codename).
    Compatible avec une stratégie "SaaS blindée" (deny-by-default).
    """
    def _decorator(view):
        @login_required
        @wraps(view)
        def _wrapped(request, *args, **kwargs):
            u = getattr(request, "user", None)
            if u and (u.is_superuser or u.has_perm(perm_codename)):
                return view(request, *args, **kwargs)
            return HttpResponseForbidden("Accès refusé (permission requise).")
        return _wrapped
    return _decorator
# --- /Ordo Admin Console: Permission decorator ---

