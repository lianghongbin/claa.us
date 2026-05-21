"""django-simpleui 侧边栏：按财务业务模块分组，每项独立图标与权限。"""

# 菜单项 permission 使用 Django 权限码 app_label.codename；无 permission 的仅超级用户场景慎用。


def get_simpleui_menus():
    """返回 SIMPLEUI_CONFIG['menus'] 列表（可安全重复读取）。"""
    return [
        {
            "name": "财务概览",
            "icon": "fas fa-chart-pie",
            "models": [
                {
                    "name": "财务看板",
                    "icon": "fas fa-tachometer-alt",
                    "url": "finance/dashboard/",
                    "permission": "finance.view_incometransaction",
                },
            ],
        },
        {
            "name": "财务报表",
            "icon": "fas fa-chart-bar",
            "models": [
                {
                    "name": "报表中心",
                    "icon": "fas fa-th-large",
                    "url": "finance/reports/",
                    "permission": "finance.view_incometransaction",
                },
                {
                    "name": "损益表",
                    "icon": "fas fa-chart-line",
                    "url": "finance/reports/profit-loss/",
                    "permission": "finance.view_incometransaction",
                },
                {
                    "name": "现金流量表",
                    "icon": "fas fa-exchange-alt",
                    "url": "finance/reports/cash-flow/",
                    "permission": "finance.view_incometransaction",
                },
                {
                    "name": "资产负债表",
                    "icon": "fas fa-balance-scale",
                    "url": "finance/reports/balance-sheet/",
                    "permission": "finance.view_incometransaction",
                },
                {
                    "name": "现金流预测",
                    "icon": "fas fa-calendar-check",
                    "url": "finance/reports/cash-flow-forecast/",
                    "permission": "finance.view_incometransaction",
                },
            ],
        },
        {
            "name": "日常记账",
            "icon": "fas fa-book",
            "models": [
                {
                    "name": "收入明细",
                    "icon": "fas fa-arrow-circle-down",
                    "url": "finance/incometransaction/",
                    "permission": "finance.view_incometransaction",
                },
                {
                    "name": "支出明细",
                    "icon": "fas fa-arrow-circle-up",
                    "url": "finance/expensetransaction/",
                    "permission": "finance.view_expensetransaction",
                },
            ],
        },
        {
            "name": "基础资料",
            "icon": "fas fa-database",
            "models": [
                {
                    "name": "科目分类",
                    "icon": "fas fa-sitemap",
                    "url": "finance/category/",
                    "permission": "finance.view_category",
                },
                {
                    "name": "项目",
                    "icon": "fas fa-project-diagram",
                    "url": "finance/project/",
                    "permission": "finance.view_project",
                },
                {
                    "name": "流水标签",
                    "icon": "fas fa-tags",
                    "url": "finance/tag/",
                    "permission": "finance.view_tag",
                },
                {
                    "name": "往来单位",
                    "icon": "fas fa-address-book",
                    "url": "finance/counterparty/",
                    "permission": "finance.view_counterparty",
                },
            ],
        },
        {
            "name": "应收应付",
            "icon": "fas fa-handshake",
            "models": [
                {
                    "name": "应收账单",
                    "icon": "fas fa-file-invoice-dollar",
                    "url": "finance/arinvoice/",
                    "permission": "finance.view_arinvoice",
                },
                {
                    "name": "应付账单",
                    "icon": "fas fa-file-invoice",
                    "url": "finance/apinvoice/",
                    "permission": "finance.view_apinvoice",
                },
            ],
        },
        {
            "name": "银行对账",
            "icon": "fas fa-university",
            "models": [
                {
                    "name": "银行账单导入",
                    "icon": "fas fa-file-upload",
                    "url": "finance/bankstatementbatch/",
                    "permission": "finance.view_bankstatementbatch",
                },
                {
                    "name": "银行账单明细",
                    "icon": "fas fa-list-ul",
                    "url": "finance/bankstatementline/",
                    "permission": "finance.view_bankstatementline",
                },
                {
                    "name": "对账差异",
                    "icon": "fas fa-balance-scale",
                    "url": "finance/reconciliationvariance/",
                    "permission": "finance.view_reconciliationvariance",
                },
            ],
        },
        {
            "name": "审计中心",
            "icon": "fas fa-clipboard-list",
            "models": [
                {
                    "name": "操作日志",
                    "icon": "fas fa-history",
                    "url": "audit/auditlog/",
                    "permission": "audit.view_auditlog",
                },
            ],
        },
        {
            "name": "系统管理",
            "icon": "fas fa-cogs",
            "models": [
                {
                    "name": "用户",
                    "icon": "fas fa-user",
                    "url": "accounts/user/",
                    "permission": "accounts.view_user",
                },
                {
                    "name": "用户组",
                    "icon": "fas fa-users-cog",
                    "url": "auth/group/",
                    "permission": "auth.view_group",
                },
                {
                    "name": "系统设置",
                    "icon": "fas fa-sliders-h",
                    "url": "finance/system-settings/",
                    "permission": "finance.manage_database",
                },
            ],
        },
    ]


SIMPLEUI_MENU_DISPLAY = [
    "财务概览",
    "财务报表",
    "日常记账",
    "应收应付",
    "银行对账",
    "审计中心",
    "基础资料",
    "系统管理",
]
