from core_integrity.rule import IntegrityRule, IntegrityResult

class P002ArchivedInDashboardRule(IntegrityRule):
    code = "P002"
    severity = "ERROR"
    description = "Prescription archivée présente dans les urgences"

    def check(self, context):
        prescription = context.prescription

        if not context.is_archived:
            return []

        return [
            IntegrityResult(
                code=self.code,
                severity=self.severity,
                message="Ordonnance archivée : elle ne doit pas apparaître comme urgence normale.",
                obj=prescription,
                suggestion="Déplacer ce dossier vers le Centre des anomalies ou clôturer les cycles actifs.",
            )
        ]
