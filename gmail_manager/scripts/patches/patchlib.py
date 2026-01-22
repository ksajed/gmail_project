#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Lib utilitaire pour scripts patch (réutilisable, anti-duplication).

RÈGLES :
- Toujours faire un backup horodaté AVANT de modifier un fichier existant.
- UTF-8, indentation propre.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


def ts() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


@dataclass(frozen=True)
class BackupResult:
    backup_path: Optional[Path]
    message: str


def backup_file(path: Path, stamp: Optional[str] = None) -> BackupResult:
    """Backup horodaté: file.ext -> file.ext.bak-YYYYmmdd-HHMMSS"""
    if not path.exists():
        return BackupResult(None, f"INFO: no backup (missing): {path}")
    stamp = stamp or ts()
    bak = path.with_name(f"{path.name}.bak-{stamp}")
    bak.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    return BackupResult(bak, f"BACKUP: {path} => {bak}")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
