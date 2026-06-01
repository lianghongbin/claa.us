from django.conf import settings
from django.core.mail import send_mail
from django.utils.translation import gettext as _


def send_initial_password_email(*, user, raw_password: str, request=None) -> None:
    login_url = request.build_absolute_uri(settings.LOGIN_URL) if request else settings.LOGIN_URL

    subject = _("Your Claa Finance account is ready")
    body = _(
        "Hello,\n\n"
        "An administrator created a back-office account for you.\n\n"
        "Sign-in URL: %(login_url)s\n"
        "Email: %(email)s\n"
        "Initial password: %(password)s\n\n"
        "Change your password after first sign-in. Do not share the initial password.\n"
    ) % {
        "login_url": login_url,
        "email": user.email,
        "password": raw_password,
    }

    send_mail(
        subject,
        body,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )
