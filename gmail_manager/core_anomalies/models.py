from django.db import models


class Anomaly(models.Model):
    SEVERITY_CHOICES = [
        ("CRITIQUE", "Critique"),
        ("ELEVEE", "Élevée"),
        ("MOYENNE", "Moyenne"),
        ("FAIBLE", "Faible"),
        ("INFO", "Information"),
    ]

    STATUS_CHOICES = [
        ("NOUVELLE", "Nouvelle"),
        ("EN_COURS", "En cours"),
        ("EN_ATTENTE", "En attente"),
        ("RESOLUE", "Résolue"),
        ("IGNOREE", "Ignorée"),
    ]

    rule_code = models.CharField(max_length=20)
    title = models.CharField(max_length=255, blank=True)
    category = models.CharField(max_length=100, blank=True)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default="FAIBLE")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="NOUVELLE")
    prescription_id = models.IntegerField()
    score = models.PositiveSmallIntegerField(default=100)
    message = models.TextField()
    description = models.TextField(blank=True)
    solution = models.TextField(blank=True)
    autofix = models.BooleanField(default=False)
    suggestion = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.CharField(max_length=150, blank=True)
    comment = models.TextField(blank=True)

    class Meta:
        ordering = ["score", "-created_at"]

    def __str__(self):
        return f"{self.rule_code} - Prescription {self.prescription_id}"
