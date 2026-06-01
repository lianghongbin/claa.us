"""django-simpleui sidebar menus (English msgids, translated via gettext)."""

from django.utils.translation import gettext_lazy as _


def get_simpleui_menus():
    """Return SIMPLEUI_CONFIG['menus'] (safe to call on each request)."""
    return [
        {
            "name": _("Overview"),
            "icon": "fas fa-chart-pie",
            "models": [
                {
                    "name": _("Finance dashboard"),
                    "icon": "fas fa-tachometer-alt",
                    "url": "finance/dashboard/",
                    "permission": "finance.view_incometransaction",
                },
            ],
        },
        {
            "name": _("Reports"),
            "icon": "fas fa-chart-bar",
            "models": [
                {
                    "name": _("Report center"),
                    "icon": "fas fa-th-large",
                    "url": "finance/reports/",
                    "permission": "finance.view_incometransaction",
                },
                {
                    "name": _("Profit & loss"),
                    "icon": "fas fa-chart-line",
                    "url": "finance/reports/profit-loss/",
                    "permission": "finance.view_incometransaction",
                },
                {
                    "name": _("Cash flow statement"),
                    "icon": "fas fa-exchange-alt",
                    "url": "finance/reports/cash-flow/",
                    "permission": "finance.view_incometransaction",
                },
                {
                    "name": _("Balance sheet"),
                    "icon": "fas fa-balance-scale",
                    "url": "finance/reports/balance-sheet/",
                    "permission": "finance.view_incometransaction",
                },
                {
                    "name": _("Cash flow forecast"),
                    "icon": "fas fa-calendar-check",
                    "url": "finance/reports/cash-flow-forecast/",
                    "permission": "finance.view_incometransaction",
                },
            ],
        },
        {
            "name": _("Transactions"),
            "icon": "fas fa-book",
            "models": [
                {
                    "name": _("Income entries"),
                    "icon": "fas fa-arrow-circle-down",
                    "url": "finance/incometransaction/",
                    "permission": "finance.view_incometransaction",
                },
                {
                    "name": _("Expense entries"),
                    "icon": "fas fa-arrow-circle-up",
                    "url": "finance/expensetransaction/",
                    "permission": "finance.view_expensetransaction",
                },
            ],
        },
        {
            "name": _("Master data"),
            "icon": "fas fa-database",
            "models": [
                {
                    "name": _("Categories"),
                    "icon": "fas fa-sitemap",
                    "url": "finance/category/",
                    "permission": "finance.view_category",
                },
                {
                    "name": _("Projects"),
                    "icon": "fas fa-project-diagram",
                    "url": "finance/project/",
                    "permission": "finance.view_project",
                },
                {
                    "name": _("Tags"),
                    "icon": "fas fa-tags",
                    "url": "finance/tag/",
                    "permission": "finance.view_tag",
                },
                {
                    "name": _("Counterparties"),
                    "icon": "fas fa-address-book",
                    "url": "finance/counterparty/",
                    "permission": "finance.view_counterparty",
                },
            ],
        },
        {
            "name": _("AR / AP"),
            "icon": "fas fa-handshake",
            "models": [
                {
                    "name": _("AR invoices"),
                    "icon": "fas fa-file-invoice-dollar",
                    "url": "finance/arinvoice/",
                    "permission": "finance.view_arinvoice",
                },
                {
                    "name": _("AP invoices"),
                    "icon": "fas fa-file-invoice",
                    "url": "finance/apinvoice/",
                    "permission": "finance.view_apinvoice",
                },
            ],
        },
        {
            "name": _("Bank reconciliation"),
            "icon": "fas fa-university",
            "models": [
                {
                    "name": _("Bank statement import"),
                    "icon": "fas fa-file-upload",
                    "url": "finance/bankstatementbatch/",
                    "permission": "finance.view_bankstatementbatch",
                },
                {
                    "name": _("Bank statement lines"),
                    "icon": "fas fa-list-ul",
                    "url": "finance/bankstatementline/",
                    "permission": "finance.view_bankstatementline",
                },
                {
                    "name": _("Reconciliation variances"),
                    "icon": "fas fa-balance-scale",
                    "url": "finance/reconciliationvariance/",
                    "permission": "finance.view_reconciliationvariance",
                },
            ],
        },
        {
            "name": _("Audit"),
            "icon": "fas fa-clipboard-list",
            "models": [
                {
                    "name": _("Audit log"),
                    "icon": "fas fa-history",
                    "url": "audit/auditlog/",
                    "permission": "audit.view_auditlog",
                },
            ],
        },
        {
            "name": _("System"),
            "icon": "fas fa-cogs",
            "models": [
                {
                    "name": _("Users"),
                    "icon": "fas fa-user",
                    "url": "accounts/user/",
                    "permission": "accounts.view_user",
                },
                {
                    "name": _("Groups"),
                    "icon": "fas fa-users-cog",
                    "url": "auth/group/",
                    "permission": "auth.view_group",
                },
                {
                    "name": _("System settings"),
                    "icon": "fas fa-sliders-h",
                    "url": "finance/system-settings/",
                    "permission": "finance.manage_database",
                },
            ],
        },
    ]


SIMPLEUI_MENU_DISPLAY = [
    _("Overview"),
    _("Reports"),
    _("Transactions"),
    _("AR / AP"),
    _("Bank reconciliation"),
    _("Audit"),
    _("Master data"),
    _("System"),
]
