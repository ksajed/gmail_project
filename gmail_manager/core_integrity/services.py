"""
API publique du module core_integrity.

Les modules externes doivent importer les fonctions d'intégrité depuis
ce fichier et non directement depuis les composants internes comme
runner.py, registry.py ou context.py.
"""

from core_integrity.runner import (
    integrity_score,
    run_integrity_for_prescription,
)

__all__ = [
    "run_integrity_for_prescription",
    "integrity_score",
]
