from django.apps import AppConfig


class CoreEmailsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core_emails'
    def ready(self):
        import core_emails.signals  # noqa