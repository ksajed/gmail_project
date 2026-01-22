#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PATCH TEMPLATE (copier/adapter)

USAGE:
  ./gmail_manager/scripts/patches/patch_xxx.py
  (ou) python gmail_manager/scripts/patches/patch_xxx.py

RÈGLES:
- backup horodaté AVANT modification
- indentation parfaite
- pas de duplication de logique (réutiliser patchlib)
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from patchlib import backup_file, ts, write_text


def repo_root() -> Path:
    out = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip()
    return Path(out).resolve()


def main() -> None:
    stamp = ts()
    root = repo_root()

    # Exemple cible (à adapter)
    target = root / "gmail_manager" / "templates" / "auth" / "login.html"

    backup_file(target, stamp=stamp)
    s = target.read_text(encoding="utf-8")
    out = s  # TODO: appliquer transformation

    write_text(target, out)
    print("OK:", target)


if __name__ == "__main__":
    main()
