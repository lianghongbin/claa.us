from django.contrib.auth.views import PasswordChangeDoneView, PasswordChangeView
from django.urls import reverse


def staff_password_change(request):
    from django.contrib import admin

    from apps.accounts.forms import ClearMustChangePasswordForm

    return PasswordChangeView.as_view(
        form_class=ClearMustChangePasswordForm,
        success_url=reverse("admin:password_change_done"),
        extra_context={**admin.site.each_context(request)},
    )(request)


def staff_password_change_done(request):
    from django.contrib import admin

    return PasswordChangeDoneView.as_view(
        extra_context={**admin.site.each_context(request)}
    )(request)
