from core_integrity.rule import IntegrityRule, IntegrityResult

class P001ArchivedActiveCycleRule(IntegrityRule):
    code = "P001"
    severity = "ERROR"
    title = "Cycle actif sur ordonnance archivée"
    category = "Ordonnances"
    description = "Une ordonnance archivée possède encore un cycle actif."
    solution = "Clôturer le cycle actif ou réactiver l'ordonnance si elle est encore valide."
    autofix = True

    ACTIVE_STATUSES = {"RECEIVED", "ACTIVE", "PENDING", "OPEN", "EN_COURS"}

    def check(self, context):
        results = []

        prescription = context.prescription
        status = context.prescription_status

        if "ARCH" not in status:
            return results

        for rel in prescription._meta.related_objects:
            model_name = rel.related_model.__name__.lower()

            if "cycle" not in model_name:
                continue

            accessor = rel.get_accessor_name()

            try:
                manager = getattr(prescription, accessor)
                cycles = manager.all()
            except Exception:
                continue

            for cycle in cycles:
                cycle_status = str(getattr(cycle, "status", "")).upper()

                if cycle_status in self.ACTIVE_STATUSES:
                    results.append(
                        self.result(
                            message="Ordonnance archivée avec un cycle encore actif.",
                            obj=cycle,
                            suggestion="Clôturer le cycle actif ou réactiver l'ordonnance si elle est encore valide.",
                        )
                    )

        return results
