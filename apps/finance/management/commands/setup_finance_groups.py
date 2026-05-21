"""创建「财务管理员」「普通财务」分组并绑定权限（可安全重复执行）。

用法:
    python manage.py setup_finance_groups

分组说明（详见 README.md「权限与数据范围」）:
    财务管理员 — 全权财务、view_all_*、应付审批、对账、用户/组管理、操作日志
    普通财务   — 流水与账单日常录入/核销/对账匹配，无删流水、无审批、无 view_all_*
"""
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand

from apps.finance.permissions import GROUP_FINANCE_ADMIN, GROUP_FINANCE_STAFF

# 旧版单一 Transaction 后台权限（已拆成收入/支出代理模型）
_LEGACY_FINANCE_TX = (
    "add_transaction",
    "change_transaction",
    "delete_transaction",
    "view_transaction",
)


def _perm(app_label: str, codename: str) -> Permission:
    return Permission.objects.get(content_type__app_label=app_label, codename=codename)


class Command(BaseCommand):
    help = (
        "创建或更新「财务管理员」「普通财务」分组及 Django 权限绑定（幂等）。"
        "部署后、增删自定义权限后均可重复执行。详见 README.md。"
    )

    def handle(self, *args, **options):
        admin_group, _ = Group.objects.get_or_create(name=GROUP_FINANCE_ADMIN)
        staff_group, _ = Group.objects.get_or_create(name=GROUP_FINANCE_STAFF)

        legacy = Permission.objects.filter(
            content_type__app_label="finance",
            codename__in=_LEGACY_FINANCE_TX,
        )
        admin_group.permissions.remove(*legacy)
        staff_group.permissions.remove(*legacy)

        admin_pairs = [
            ("finance", "add_category"),
            ("finance", "change_category"),
            ("finance", "delete_category"),
            ("finance", "view_category"),
            ("finance", "add_project"),
            ("finance", "change_project"),
            ("finance", "delete_project"),
            ("finance", "view_project"),
            ("finance", "add_tag"),
            ("finance", "change_tag"),
            ("finance", "delete_tag"),
            ("finance", "view_tag"),
            ("finance", "add_counterparty"),
            ("finance", "change_counterparty"),
            ("finance", "delete_counterparty"),
            ("finance", "view_counterparty"),
            ("finance", "view_all_counterparties"),
            ("finance", "view_all_projects"),
            ("finance", "view_all_finance_transactions"),
            ("finance", "add_arinvoice"),
            ("finance", "change_arinvoice"),
            ("finance", "delete_arinvoice"),
            ("finance", "view_arinvoice"),
            ("finance", "view_all_arinvoices"),
            ("finance", "add_arpaymentallocation"),
            ("finance", "change_arpaymentallocation"),
            ("finance", "delete_arpaymentallocation"),
            ("finance", "view_arpaymentallocation"),
            ("finance", "add_apinvoice"),
            ("finance", "change_apinvoice"),
            ("finance", "delete_apinvoice"),
            ("finance", "view_apinvoice"),
            ("finance", "view_all_apinvoices"),
            ("finance", "approve_apinvoice"),
            ("finance", "add_appaymentallocation"),
            ("finance", "change_appaymentallocation"),
            ("finance", "delete_appaymentallocation"),
            ("finance", "view_appaymentallocation"),
            ("finance", "add_bankstatementbatch"),
            ("finance", "change_bankstatementbatch"),
            ("finance", "delete_bankstatementbatch"),
            ("finance", "view_bankstatementbatch"),
            ("finance", "view_bankstatementline"),
            ("finance", "change_bankstatementline"),
            ("finance", "add_reconciliationvariance"),
            ("finance", "change_reconciliationvariance"),
            ("finance", "delete_reconciliationvariance"),
            ("finance", "view_reconciliationvariance"),
            ("finance", "add_incometransaction"),
            ("finance", "change_incometransaction"),
            ("finance", "delete_incometransaction"),
            ("finance", "view_incometransaction"),
            ("finance", "add_expensetransaction"),
            ("finance", "change_expensetransaction"),
            ("finance", "delete_expensetransaction"),
            ("finance", "view_expensetransaction"),
            ("audit", "view_auditlog"),
            ("accounts", "add_user"),
            ("accounts", "change_user"),
            ("accounts", "delete_user"),
            ("accounts", "view_user"),
            ("auth", "add_group"),
            ("auth", "change_group"),
            ("auth", "delete_group"),
            ("auth", "view_group"),
        ]
        staff_pairs = [
            ("finance", "view_category"),
            ("finance", "view_project"),
            ("finance", "view_tag"),
            ("finance", "view_counterparty"),
            ("finance", "add_arinvoice"),
            ("finance", "change_arinvoice"),
            ("finance", "view_arinvoice"),
            ("finance", "add_arpaymentallocation"),
            ("finance", "change_arpaymentallocation"),
            ("finance", "delete_arpaymentallocation"),
            ("finance", "view_arpaymentallocation"),
            ("finance", "add_apinvoice"),
            ("finance", "change_apinvoice"),
            ("finance", "view_apinvoice"),
            ("finance", "add_appaymentallocation"),
            ("finance", "change_appaymentallocation"),
            ("finance", "delete_appaymentallocation"),
            ("finance", "view_appaymentallocation"),
            ("finance", "view_bankstatementbatch"),
            ("finance", "view_bankstatementline"),
            ("finance", "change_bankstatementline"),
            ("finance", "add_reconciliationvariance"),
            ("finance", "change_reconciliationvariance"),
            ("finance", "view_reconciliationvariance"),
            ("finance", "add_incometransaction"),
            ("finance", "change_incometransaction"),
            ("finance", "view_incometransaction"),
            ("finance", "add_expensetransaction"),
            ("finance", "change_expensetransaction"),
            ("finance", "view_expensetransaction"),
        ]

        for app_label, codename in admin_pairs:
            admin_group.permissions.add(_perm(app_label, codename))
        for app_label, codename in staff_pairs:
            staff_group.permissions.add(_perm(app_label, codename))

        self.stdout.write(
            self.style.SUCCESS(
                f"已更新分组「{GROUP_FINANCE_ADMIN}」「{GROUP_FINANCE_STAFF}」的权限。"
            )
        )
