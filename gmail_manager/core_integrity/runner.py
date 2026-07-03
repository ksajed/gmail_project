from core_integrity.registry import get_rules
from core_integrity.context import IntegrityContext

def run_integrity_for_prescription(prescription):
    context = IntegrityContext(prescription)
    results = []

    for rule in get_rules():
        try:
            results.extend(rule.check(context))
        except Exception as e:
            results.append({
                "code": "ENGINE_ERROR",
                "severity": "ERROR",
                "message": f"Erreur règle {rule.code}: {e}",
                "object": str(prescription),
                "suggestion": "Vérifier la règle d'intégrité.",
            })

    return [
        r.to_dict() if hasattr(r, "to_dict") else r
        for r in results
    ]


def integrity_score(results):
    score = 100

    for r in results:
        if r.get("severity") == "ERROR":
            score -= 25
        elif r.get("severity") == "WARNING":
            score -= 10

    return max(score, 0)
