"""Project middleware."""


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
