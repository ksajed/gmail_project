from __future__ import annotations

import re

def to_e164_fr(phone: str | None) -> str | None:
    """Normalize FR phone numbers to E.164 (+33...).

    Accepts:
      - +33XXXXXXXXX
      - 0033XXXXXXXXX
      - 0XXXXXXXXX
      - 9 digits (assumed FR without leading 0)
    Returns None if cannot normalize.
    """
    if not phone:
        return None
    s = str(phone).strip()
    s = re.sub(r"[\s\.-]", "", s)

    # already E.164
    if s.startswith("+"):
        return s if len(s) >= 8 else None

    # 00 prefix
    if s.startswith("00"):
        s2 = "+" + s[2:]
        return s2 if s2.startswith("+") and len(s2) >= 8 else None

    # FR local: 0XXXXXXXXX -> +33XXXXXXXXX
    if s.startswith("0") and len(s) == 10 and s[1:].isdigit():
        return "+33" + s[1:]

    # 9 digits -> +33XXXXXXXXX
    if len(s) == 9 and s.isdigit():
        return "+33" + s

    return None

def pick_phone(*candidates: str | None) -> str | None:
    """Return the first non-empty candidate."""
    for c in candidates:
        if c is None:
            continue
        s = str(c).strip()
        if s:
            return s
    return None
