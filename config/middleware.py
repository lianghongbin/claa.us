"""Project middleware."""

from django.conf import settings
from django.utils import translation


class AdminFinanceStaticNoCacheMiddleware:
    """Avoid CDN/browser serving stale admin patch JS for weeks."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        path = request.path
        if path.startswith("/static/admin/finance/") or path.startswith(
            "/static/admin/simpleui-x/js/menu.js"
        ):
            response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response["Pragma"] = "no-cache"
        return response


class RefreshSimpleuiMenusMiddleware:
    """Rebuild SimpleUI menus each request so gettext_lazy resolves to active language."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        lang = translation.get_language()
        with translation.override(lang):
            from config.simpleui_menus import get_simpleui_menus

            config = getattr(settings, "SIMPLEUI_CONFIG", None)
            if isinstance(config, dict):
                config["menus"] = get_simpleui_menus()
        return self.get_response(request)
