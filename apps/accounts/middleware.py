import time

from django.conf import settings
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin


class ForcePasswordChangeMiddleware(MiddlewareMixin):
    """
    职员用户若 must_change_password=True，仅允许访问登录/登出/改密相关路径，
    其余 /admin/ 下请求一律重定向到修改密码页。
    """

    ALLOW_PREFIXES = (
        "/admin/login/",
        "/admin/logout/",
        "/admin/password_change/",
        "/admin/password_change/done/",
        "/admin/jsi18n/",
    )

    def process_request(self, request):
        u = request.user
        if (
            not u.is_authenticated
            or not u.is_staff
            or not getattr(u, "must_change_password", False)
        ):
            return None
        path = request.path
        if not path.startswith("/admin/"):
            return None
        if any(path.startswith(p) for p in self.ALLOW_PREFIXES):
            return None
        return redirect(reverse("admin:password_change"))


class SessionInactivityMiddleware(MiddlewareMixin):
    """
    1 小时（SESSION_COOKIE_AGE）无服务端请求则强制登出。
    与 SESSION_SAVE_EVERY_REQUEST 配合：有操作会刷新 _finance_last_activity。
    """

    SESSION_KEY = "_finance_last_activity"
    SKIP_PREFIXES = (
        "/admin/login/",
        "/admin/logout/",
        "/static/",
        "/media/",
    )

    def process_request(self, request):
        if not request.user.is_authenticated:
            return None

        path = request.path
        if any(path.startswith(prefix) for prefix in self.SKIP_PREFIXES):
            return None

        timeout = int(getattr(settings, "SESSION_COOKIE_AGE", 3600))
        now = int(time.time())
        last = request.session.get(self.SESSION_KEY)

        if last is not None and now - int(last) > timeout:
            logout(request)
            request.session.flush()
            login_url = reverse("admin:login")
            if path.startswith("/admin/"):
                return redirect(f"{login_url}?next={request.get_full_path()}")
            return redirect(login_url)

        request.session[self.SESSION_KEY] = now
        return None
