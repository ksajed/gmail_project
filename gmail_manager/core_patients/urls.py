from django.urls import path

from .views import (
    complete_patient,
    patient_detail,
)

app_name = "core_patients"

urlpatterns = [
    # 🔍 Consultation du profil patient (lecture)
    path(
        "<int:pk>/",
        patient_detail,
        name="patient_detail",
    ),

    # ✏️ Compléter le patient
    path(
        "<int:patient_id>/complete/",
        complete_patient,
        name="complete_patient",
    ),
]
