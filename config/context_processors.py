import os


def finance_asset_version(request):
    """Cache-bust version for admin JS/CSS (set FINANCE_ASSET_VERSION on deploy)."""
    return {
        "FINANCE_ASSET_VERSION": os.getenv(
            "FINANCE_ASSET_VERSION",
            "20260601-tabclose",
        ),
    }
