from django.conf import settings
from django.core.mail import send_mail
from django.utils.translation import gettext as _


def send_initial_password_email(*, user, raw_password, request) -> None:
    login_url = request.build_absolute_uri("/admin/")
    subject = str(_("【财务管理】您的账户已开通"))
    body = str(
        _(
            "您好，\n\n"
            "管理员已在系统中为您开通后台账号。\n\n"
            "登录地址：%(login_url)s\n"
            "登录账号（邮箱）：%(email)s\n"
            "初始密码：%(password)s\n\n"
            "请首次登录后立即按系统提示修改密码；初始密码请勿转发他人。\n"
        )
        % {"login_url": login_url, "email": user.email, "password": raw_password}
    )
    send_mail(
        subject,
        body,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )
