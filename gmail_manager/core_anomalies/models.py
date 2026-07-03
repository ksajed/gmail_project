from django.db import models


class Anomaly(models.Model):
    SEVERITY_CHOICES = [
        ("CRITICAL", "Critical"),
        ("HIGH", "High"),
        ("MEDIUM", "Medium"),
        ("LOW", "Low"),
        ("INFO", "Info"),
    ]

    STATUS_CHOICES = [
        ("NEW", "New"),
        ("IN_PROGRESS", "In Progress"),
        ("WAITING", "Waiting"),
        ("RESOLVED", "Resolved"),
        ("IGNORED", "Ignored"),
    ]

    rule_code = models.CharField(max_length=20)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default="LOW")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="NEW")
    prescription_id = models.IntegerField()
    score = models.PositiveSmallIntegerField(default=100)
    message = models.TextField()
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
