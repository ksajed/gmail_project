from core_integrity.rule import IntegrityRule, IntegrityResult

class P001ArchivedActiveCycleRule(IntegrityRule):
    code = "P001"
    severity = "ERROR"
    description = "Prescription archivée avec cycle actif"

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
                        IntegrityResult(
                            code=self.code,
                            severity=self.severity,
                            message="Ordonnance archivée avec un cycle encore actif.",
                            obj=cycle,
                            suggestion="Vérifier si le cycle doit être clôturé ou si l'ordonnance ne doit plus être archivée.",
                        )
                    )

        return results
