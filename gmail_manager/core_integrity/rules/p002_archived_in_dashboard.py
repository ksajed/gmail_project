from core_integrity.rule import IntegrityRule, IntegrityResult

class P002ArchivedInDashboardRule(IntegrityRule):
    code = "P002"
    severity = "ERROR"
    title = "Ordonnance archivée visible dans les urgences"
    category = "Ordonnances"
    description = "Une ordonnance archivée apparaît encore dans les urgences du tableau de bord."
    solution = "Retirer cette ordonnance des urgences ou clôturer les cycles actifs liés."
    autofix = False

    def check(self, context):
        prescription = context.prescription

        if not context.is_archived:
            return []

        return [
            self.result(
                message="Ordonnance archivée : elle ne doit pas apparaître comme urgence normale.",
                obj=prescription,
                suggestion="Retirer cette ordonnance des urgences ou clôturer les cycles actifs liés.",
            )
        ]
