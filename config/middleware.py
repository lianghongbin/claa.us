"""Project middleware."""

from django.conf import settings
from django.utils import translation
from django.utils.encoding import force_str


class AdminFinanceStaticNoCacheMiddleware:
    """Avoid CDN/browser serving stale admin patch JS for weeks."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        path = request.path
        if path.startswith("/static/admin/finance/") or path.startswith(
            "/static/admin/simpleui-x/js/menu.js"
        ) or "dashboard_charts.js" in path or "finance_dashboard.css" in path or "chart.umd.min.js" in path:
            response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response["Pragma"] = "no-cache"
        return response


class AdminLocaleNoCacheMiddleware:
    """Prevent CDN/browser from caching admin HTML across django_language cookie values."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        path = request.path
        if path.startswith("/admin/") or path.startswith("/i18n/"):
            response["Cache-Control"] = "private, no-cache, no-store, must-revalidate"
            response["Pragma"] = "no-cache"
            response["Vary"] = "Cookie"
        return response


def _force_menu_labels(items):
    """Resolve gettext_lazy menu names to plain str for the active language."""
    for item in items:
        if "name" in item:
            item["name"] = force_str(item["name"])
        models = item.get("models")
        if models:
            _force_menu_labels(models)


class RefreshSimpleuiMenusMiddleware:
    """
    Rebuild SimpleUI menus each request in the active language.
    Clear cached session menus when language changes (SimpleUI caches JSON in session).
    """

    SESSION_LANG_KEY = "_finance_menu_lang"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        lang = translation.get_language() or settings.LANGUAGE_CODE
        session = getattr(request, "session", None)
        if session is not None:
            prev = session.get(self.SESSION_LANG_KEY)
            if prev and prev != lang:
                session.pop("_menus", None)
            session[self.SESSION_LANG_KEY] = lang

        with translation.override(lang):
            from config.simpleui_menus import SIMPLEUI_MENU_DISPLAY, get_simpleui_menus

            menus = get_simpleui_menus()
            _force_menu_labels(menus)

            config = getattr(settings, "SIMPLEUI_CONFIG", None)
            if isinstance(config, dict):
                config["menus"] = menus
                config["menu_display"] = [force_str(label) for label in SIMPLEUI_MENU_DISPLAY]

        return self.get_response(request)
