"""财务相关权限与角色名常量。

数据范围（谁「看得到」什么）：
- 项目、往来单位可配置「可见分组」：仅所选 Django 分组内的用户可在列表/下拉中看到该记录；
  不选可见分组表示不限制（所有具备 view_* 的用户可见）。
- 应收账单（ARInvoice）同样支持「可见分组」与 finance.view_all_arinvoices。
- 应收/应付核销在对应「应收账单」「应付账单」页维护，关联收入/expense 流水；不在收入/支出明细页录入。
- 应付账单（APInvoice）含审批状态；仅「已批准」账单可付款核销。finance.approve_apinvoice 或财务管理员可改审批。
- 银行对账：账单明细与系统流水匹配后，系统流水自动标记「已对账」；普通财务可 change_bankstatementline 做手工匹配。
- 对账差异（ReconciliationVariance）：可登记手续费/尾差/有账未记账/已记账未到账等，并生成调整流水；普通财务可增改差异，删除仅管理员。

跨组查看：为用户授予对应模型的「view_all_*」自定义权限（或超级用户）可绕过可见分组限制。

初始化分组:
    python manage.py setup_finance_groups

报表/看板（需 view_incometransaction）:
    /admin/finance/dashboard/
    /admin/finance/reports/

数据库备份/还原（需超级用户或 finance.manage_database）:
    /admin/finance/system-settings/
"""

GROUP_FINANCE_ADMIN = "财务管理员"
GROUP_FINANCE_STAFF = "普通财务"


def is_finance_admin(request) -> bool:
    u = request.user
    return bool(
        u.is_active
        and (u.is_superuser or u.groups.filter(name=GROUP_FINANCE_ADMIN).exists())
    )


def can_approve_ap_invoice(request) -> bool:
    u = request.user
    return bool(
        u.is_active
        and (
            u.is_superuser
            or is_finance_admin(request)
            or u.has_perm("finance.approve_apinvoice")
        )
    )
