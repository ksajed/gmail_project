class IntegrityContext:
    def __init__(self, prescription):
        self.prescription = prescription
        self.cycles = self._load_related("cycle")
        self.notifications = self._load_related("notification")
        self.sms = self._load_related("sms")
        self.emails = self._load_related("email")

    def _load_related(self, keyword):
        items = []

        for rel in self.prescription._meta.related_objects:
            model_name = rel.related_model.__name__.lower()

            if keyword not in model_name:
                continue

            try:
                manager = getattr(self.prescription, rel.get_accessor_name())
                items.extend(list(manager.all()))
            except Exception:
                continue

        return items

    @property
    def prescription_status(self):
        return str(getattr(self.prescription, "status", "")).upper()

    @property
    def is_archived(self):
        return "ARCH" in self.prescription_status
