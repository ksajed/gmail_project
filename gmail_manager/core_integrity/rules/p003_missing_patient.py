from core_integrity.rule import IntegrityRule


class P003MissingPatientRule(IntegrityRule):
    code = "P003"
    severity = "ERROR"
    title = "Ordonnance sans patient"
    category = "Ordonnances"
    description = "Une ordonnance existe sans patient associé."
    solution = "Associer un patient à l'ordonnance ou supprimer l'ordonnance si elle est invalide."
    autofix = False

    def check(self, context):
        prescription = context.prescription

        if getattr(prescription, "patient_id", None):
            return []

        return [
            self.result(
                message="Cette ordonnance n'a aucun patient associé.",
                obj=prescription,
            )
        ]
