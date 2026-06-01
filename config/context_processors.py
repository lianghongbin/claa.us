import os

from django.conf import settings
from django.utils.translation import get_language_info


def finance_asset_version(request):
    """Cache-bust version for admin JS/CSS (set FINANCE_ASSET_VERSION on deploy)."""
    return {
        "FINANCE_ASSET_VERSION": os.getenv(
            "FINANCE_ASSET_VERSION",
            "20260601-dashboard2",
        ),
    }


def language_switcher(request):
    """
    Language dropdown labels use each locale's autonym (name_local).
    Do not use {% get_available_languages %} — Django runs gettext() on
    LANGUAGES labels, so "English" becomes "英语" in zh-hans.
    """
    choices = []
    for code, _fallback in settings.LANGUAGES:
        info = get_language_info(code)
        label = info.get("name_local") or _fallback
        choices.append((code, label))
    return {"language_switcher_choices": choices}
