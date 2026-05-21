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
        from django.shortcuts import redirect
        from django.urls import reverse

        return redirect(reverse("admin:password_change"))
