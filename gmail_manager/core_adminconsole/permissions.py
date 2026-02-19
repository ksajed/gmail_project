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
