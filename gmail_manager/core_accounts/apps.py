from django.apps import AppConfig


class CoreAccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core_accounts"

    def ready(self):
        import core_accounts.signals  # noqa
