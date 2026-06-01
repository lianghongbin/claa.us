from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"
    label = "accounts"
    verbose_name = "Accounts"

    def ready(self):
        from django.contrib import admin

        from apps.accounts.forms import EmailAdminAuthenticationForm

        admin.site.login_form = EmailAdminAuthenticationForm
