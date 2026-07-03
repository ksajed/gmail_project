from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="anomalies_dashboard"),
    path("<int:pk>/", views.detail, name="anomaly_detail"),
]
