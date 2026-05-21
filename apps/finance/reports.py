"""财务报表查询（损益、现金流量、资产负债表等）。"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from django.db.models import F, Sum

from apps.finance.models import (
    APApprovalStatus,
    APInvoice,
    APInvoiceStatus,
    ARInvoice,
    ARInvoiceStatus,
    Project,
    Transaction,
    TransactionType,
)
from apps.finance.visibility import transactions_visible_for_user, visible_primary_keys


@dataclass
class CategoryTotalRow:
    category_id: int
    category_name: str
    total: Decimal


@dataclass
class ProjectTotalRow:
    project_id: int | None
    project_code: str
    project_name: str
    income: Decimal
    expense: Decimal

    @property
    def net(self) -> Decimal:
        return self.income - self.expense


@dataclass
class ProfitLossReport:
    date_from: date
    date_to: date
    project_id: int | None
    total_income: Decimal
    total_expense: Decimal
    income_rows: list[CategoryTotalRow] = field(default_factory=list)
    expense_rows: list[CategoryTotalRow] = field(default_factory=list)
    project_rows: list[ProjectTotalRow] = field(default_factory=list)

    @property
    def net_profit(self) -> Decimal:
        return self.total_income - self.total_expense


def _base_transactions(user, date_from: date, date_to: date, project_id: int | None):
    qs = Transaction.objects.filter(
        date__gte=date_from,
        date__lte=date_to,
    )
    if project_id is not None:
        qs = qs.filter(project_id=project_id)
    return transactions_visible_for_user(qs, user)


def build_profit_loss_report(
    user,
    *,
    date_from: date,
    date_to: date,
    project_id: int | None = None,
    include_project_breakdown: bool = True,
) -> ProfitLossReport:
    if date_from > date_to:
        date_from, date_to = date_to, date_from

    qs = _base_transactions(user, date_from, date_to, project_id)

    income_agg = (
        qs.filter(transaction_type=TransactionType.INCOME)
        .values("category_id", "category__name")
        .annotate(total=Sum("amount"))
        .order_by("category__name")
    )
    expense_agg = (
        qs.filter(transaction_type=TransactionType.EXPENSE)
        .values("category_id", "category__name")
        .annotate(total=Sum("amount"))
        .order_by("category__name")
    )

    income_rows = [
        CategoryTotalRow(
            category_id=r["category_id"],
            category_name=r["category__name"],
            total=r["total"] or Decimal("0"),
        )
        for r in income_agg
    ]
    expense_rows = [
        CategoryTotalRow(
            category_id=r["category_id"],
            category_name=r["category__name"],
            total=r["total"] or Decimal("0"),
        )
        for r in expense_agg
    ]

    total_income = sum((r.total for r in income_rows), Decimal("0"))
    total_expense = sum((r.total for r in expense_rows), Decimal("0"))

    project_rows: list[ProjectTotalRow] = []
    if include_project_breakdown and project_id is None:
        proj_ids = visible_primary_keys(
            Project.objects.filter(is_active=True),
            user,
            view_all_perm="finance.view_all_projects",
        )
        for pid in proj_ids:
            proj = Project.objects.get(pk=pid)
            sub = _base_transactions(user, date_from, date_to, pid)
            inc = sub.filter(transaction_type=TransactionType.INCOME).aggregate(
                s=Sum("amount")
            )["s"] or Decimal("0")
            exp = sub.filter(transaction_type=TransactionType.EXPENSE).aggregate(
                s=Sum("amount")
            )["s"] or Decimal("0")
            if inc == 0 and exp == 0:
                continue
            project_rows.append(
                ProjectTotalRow(
                    project_id=pid,
                    project_code=proj.code,
                    project_name=proj.name,
                    income=inc,
                    expense=exp,
                )
            )
        unscoped = _base_transactions(user, date_from, date_to, project_id=None).filter(
            project__isnull=True
        )
        inc_u = unscoped.filter(transaction_type=TransactionType.INCOME).aggregate(
            s=Sum("amount")
        )["s"] or Decimal("0")
        exp_u = unscoped.filter(transaction_type=TransactionType.EXPENSE).aggregate(
            s=Sum("amount")
        )["s"] or Decimal("0")
        if inc_u or exp_u:
            project_rows.append(
                ProjectTotalRow(
                    project_id=None,
                    project_code="—",
                    project_name="未归集项目",
                    income=inc_u,
                    expense=exp_u,
                )
            )
        project_rows.sort(key=lambda r: (-abs(r.net), r.project_code))

    return ProfitLossReport(
        date_from=date_from,
        date_to=date_to,
        project_id=project_id,
        total_income=total_income,
        total_expense=total_expense,
        income_rows=income_rows,
        expense_rows=expense_rows,
        project_rows=project_rows,
    )


def visible_projects_for_user(user):
    base = Project.objects.filter(is_active=True).order_by("code")
    ids = visible_primary_keys(
        base, user, view_all_perm="finance.view_all_projects"
    )
    return base.filter(pk__in=ids)


@dataclass
class AccountCashFlowRow:
    account_name: str
    inflow: Decimal
    outflow: Decimal

    @property
    def net(self) -> Decimal:
        return self.inflow - self.outflow


@dataclass
class CashFlowReport:
    """现金流量简表（直接法）：期间内收入/支出流水视为经营现金收付。"""

    date_from: date
    date_to: date
    project_id: int | None
    total_inflow: Decimal
    total_outflow: Decimal
    account_rows: list[AccountCashFlowRow] = field(default_factory=list)

    @property
    def net_cash_flow(self) -> Decimal:
        return self.total_inflow - self.total_outflow


@dataclass
class AccountBalanceRow:
    account_name: str
    balance: Decimal


@dataclass
class BalanceSheetReport:
    """资产负债表（轻量口径）：货币资金=流水账户累计净流入；应收/应付=未结清账单余额。"""

    as_of_date: date
    project_id: int | None
    cash_rows: list[AccountBalanceRow] = field(default_factory=list)
    total_cash: Decimal = Decimal("0")
    accounts_receivable: Decimal = Decimal("0")
    total_assets: Decimal = Decimal("0")
    accounts_payable: Decimal = Decimal("0")
    total_liabilities: Decimal = Decimal("0")
    retained_earnings: Decimal = Decimal("0")
    total_equity: Decimal = Decimal("0")

    @property
    def balance_gap(self) -> Decimal:
        """资产 − 负债 − 权益；理想为 0，非零表示应收/应付与流水累计净利口径差异。"""
        return self.total_assets - self.total_liabilities - self.total_equity


def _transactions_until(user, as_of_date: date, project_id: int | None):
    qs = Transaction.objects.filter(date__lte=as_of_date)
    if project_id is not None:
        qs = qs.filter(project_id=project_id)
    return transactions_visible_for_user(qs, user)


def _sum_income_expense(qs, transaction_type: str) -> Decimal:
    return qs.filter(transaction_type=transaction_type).aggregate(
        s=Sum("amount")
    )["s"] or Decimal("0")


def _account_flow_rows(qs) -> list[AccountCashFlowRow]:
    accounts = set(
        qs.exclude(account_name="")
        .values_list("account_name", flat=True)
        .distinct()
    )
    accounts.add("")
    rows: list[AccountCashFlowRow] = []
    for name in sorted(accounts, key=lambda n: (n == "", n)):
        sub = qs.filter(account_name=name)
        inc = _sum_income_expense(sub, TransactionType.INCOME)
        exp = _sum_income_expense(sub, TransactionType.EXPENSE)
        if inc == 0 and exp == 0:
            continue
        display = name or "（未填写账户）"
        rows.append(
            AccountCashFlowRow(account_name=display, inflow=inc, outflow=exp)
        )
    rows.sort(key=lambda r: (-abs(r.net), r.account_name))
    return rows


def build_cash_flow_report(
    user,
    *,
    date_from: date,
    date_to: date,
    project_id: int | None = None,
) -> CashFlowReport:
    if date_from > date_to:
        date_from, date_to = date_to, date_from

    qs = _base_transactions(user, date_from, date_to, project_id)
    total_inflow = _sum_income_expense(qs, TransactionType.INCOME)
    total_outflow = _sum_income_expense(qs, TransactionType.EXPENSE)
    account_rows = _account_flow_rows(qs)

    return CashFlowReport(
        date_from=date_from,
        date_to=date_to,
        project_id=project_id,
        total_inflow=total_inflow,
        total_outflow=total_outflow,
        account_rows=account_rows,
    )


def _visible_ar_unpaid_total(user, as_of_date: date) -> Decimal:
    base = ARInvoice.objects.filter(
        issue_date__lte=as_of_date,
        status__in=(ARInvoiceStatus.OPEN, ARInvoiceStatus.PARTIAL),
    )
    ids = visible_primary_keys(
        base, user, view_all_perm="finance.view_all_arinvoices"
    )
    return (
        base.filter(pk__in=ids).aggregate(
            t=Sum(F("amount_total") - F("amount_paid"))
        )["t"]
        or Decimal("0")
    )


def _visible_ap_unpaid_total(user, as_of_date: date) -> Decimal:
    base = APInvoice.objects.filter(
        issue_date__lte=as_of_date,
        approval_status=APApprovalStatus.APPROVED,
        status__in=(APInvoiceStatus.OPEN, APInvoiceStatus.PARTIAL),
    )
    ids = visible_primary_keys(
        base, user, view_all_perm="finance.view_all_apinvoices"
    )
    return (
        base.filter(pk__in=ids).aggregate(
            t=Sum(F("amount_total") - F("amount_paid"))
        )["t"]
        or Decimal("0")
    )


def _cash_balance_rows(qs) -> tuple[list[AccountBalanceRow], Decimal]:
    accounts = set(
        qs.exclude(account_name="")
        .values_list("account_name", flat=True)
        .distinct()
    )
    accounts.add("")
    rows: list[AccountBalanceRow] = []
    for name in sorted(accounts, key=lambda n: (n == "", n)):
        sub = qs.filter(account_name=name)
        inc = _sum_income_expense(sub, TransactionType.INCOME)
        exp = _sum_income_expense(sub, TransactionType.EXPENSE)
        bal = inc - exp
        if bal == 0:
            continue
        display = name or "（未填写账户）"
        rows.append(AccountBalanceRow(account_name=display, balance=bal))
    rows.sort(key=lambda r: (-abs(r.balance), r.account_name))
    total = sum((r.balance for r in rows), Decimal("0"))
    return rows, total


def build_balance_sheet_report(
    user,
    *,
    as_of_date: date,
    project_id: int | None = None,
) -> BalanceSheetReport:
    qs = _transactions_until(user, as_of_date, project_id)
    cash_rows, total_cash = _cash_balance_rows(qs)
    accounts_receivable = _visible_ar_unpaid_total(user, as_of_date)
    total_assets = total_cash + accounts_receivable

    accounts_payable = _visible_ap_unpaid_total(user, as_of_date)
    total_liabilities = accounts_payable

    retained = _sum_income_expense(qs, TransactionType.INCOME) - _sum_income_expense(
        qs, TransactionType.EXPENSE
    )
    total_equity = retained

    return BalanceSheetReport(
        as_of_date=as_of_date,
        project_id=project_id,
        cash_rows=cash_rows,
        total_cash=total_cash,
        accounts_receivable=accounts_receivable,
        total_assets=total_assets,
        accounts_payable=accounts_payable,
        total_liabilities=total_liabilities,
        retained_earnings=retained,
        total_equity=total_equity,
    )


@dataclass
class ForecastPeriodRow:
    due_date: date
    expected_inflow: Decimal
    expected_outflow: Decimal

    @property
    def net(self) -> Decimal:
        return self.expected_inflow - self.expected_outflow


@dataclass
class ForecastDetailRow:
    kind: str
    number: str
    counterparty_name: str
    due_date: date | None
    amount: Decimal
    title: str


@dataclass
class CashFlowForecastReport:
    """现金流预测：按约定收款/付款日汇总未结清应收、应付余额。"""

    date_from: date
    date_to: date
    total_expected_inflow: Decimal
    total_expected_outflow: Decimal
    period_rows: list[ForecastPeriodRow] = field(default_factory=list)
    overdue_inflow: Decimal = Decimal("0")
    overdue_outflow: Decimal = Decimal("0")
    beyond_inflow: Decimal = Decimal("0")
    beyond_outflow: Decimal = Decimal("0")
    undated_inflow: Decimal = Decimal("0")
    undated_outflow: Decimal = Decimal("0")
    detail_rows: list[ForecastDetailRow] = field(default_factory=list)

    @property
    def net_expected(self) -> Decimal:
        return self.total_expected_inflow - self.total_expected_outflow

    @property
    def in_period_inflow(self) -> Decimal:
        return sum((r.expected_inflow for r in self.period_rows), Decimal("0"))

    @property
    def in_period_outflow(self) -> Decimal:
        return sum((r.expected_outflow for r in self.period_rows), Decimal("0"))

    @property
    def in_period_net(self) -> Decimal:
        return self.in_period_inflow - self.in_period_outflow


def _visible_open_ar(user):
    base = ARInvoice.objects.filter(
        status__in=(ARInvoiceStatus.OPEN, ARInvoiceStatus.PARTIAL),
    ).select_related("counterparty")
    ids = visible_primary_keys(
        base, user, view_all_perm="finance.view_all_arinvoices"
    )
    return base.filter(pk__in=ids)


def _visible_open_ap(user):
    base = APInvoice.objects.filter(
        approval_status=APApprovalStatus.APPROVED,
        status__in=(APInvoiceStatus.OPEN, APInvoiceStatus.PARTIAL),
    ).select_related("counterparty")
    ids = visible_primary_keys(
        base, user, view_all_perm="finance.view_all_apinvoices"
    )
    return base.filter(pk__in=ids)


def build_cash_flow_forecast_report(
    user,
    *,
    date_from: date,
    date_to: date,
) -> CashFlowForecastReport:
    if date_from > date_to:
        date_from, date_to = date_to, date_from

    period_map: dict[date, tuple[Decimal, Decimal]] = {}
    overdue_in = overdue_out = Decimal("0")
    beyond_in = beyond_out = Decimal("0")
    undated_in = undated_out = Decimal("0")
    details: list[ForecastDetailRow] = []

    def _add_ar(inv: ARInvoice) -> None:
        nonlocal overdue_in, beyond_in, undated_in
        amt = inv.balance_unpaid
        if amt <= 0:
            return
        details.append(
            ForecastDetailRow(
                kind="ar",
                number=inv.number,
                counterparty_name=inv.counterparty.name,
                due_date=inv.due_date,
                amount=amt,
                title=inv.title,
            )
        )
        if inv.due_date is None:
            undated_in += amt
        elif inv.due_date < date_from:
            overdue_in += amt
        elif inv.due_date > date_to:
            beyond_in += amt
        else:
            cur = period_map.get(inv.due_date, (Decimal("0"), Decimal("0")))
            period_map[inv.due_date] = (cur[0] + amt, cur[1])

    def _add_ap(inv: APInvoice) -> None:
        nonlocal overdue_out, beyond_out, undated_out
        amt = inv.balance_unpaid
        if amt <= 0:
            return
        details.append(
            ForecastDetailRow(
                kind="ap",
                number=inv.number,
                counterparty_name=inv.counterparty.name,
                due_date=inv.due_date,
                amount=amt,
                title=inv.title,
            )
        )
        if inv.due_date is None:
            undated_out += amt
        elif inv.due_date < date_from:
            overdue_out += amt
        elif inv.due_date > date_to:
            beyond_out += amt
        else:
            cur = period_map.get(inv.due_date, (Decimal("0"), Decimal("0")))
            period_map[inv.due_date] = (cur[0], cur[1] + amt)

    for inv in _visible_open_ar(user):
        _add_ar(inv)
    for inv in _visible_open_ap(user):
        _add_ap(inv)

    period_rows = [
        ForecastPeriodRow(
            due_date=d,
            expected_inflow=period_map[d][0],
            expected_outflow=period_map[d][1],
        )
        for d in sorted(period_map)
    ]
    details.sort(key=lambda r: (r.due_date is None, r.due_date or date.max, r.kind, r.number))

    total_in = (
        sum((r.expected_inflow for r in period_rows), Decimal("0"))
        + overdue_in
        + beyond_in
        + undated_in
    )
    total_out = (
        sum((r.expected_outflow for r in period_rows), Decimal("0"))
        + overdue_out
        + beyond_out
        + undated_out
    )

    return CashFlowForecastReport(
        date_from=date_from,
        date_to=date_to,
        total_expected_inflow=total_in,
        total_expected_outflow=total_out,
        period_rows=period_rows,
        overdue_inflow=overdue_in,
        overdue_outflow=overdue_out,
        beyond_inflow=beyond_in,
        beyond_outflow=beyond_out,
        undated_inflow=undated_in,
        undated_outflow=undated_out,
        detail_rows=details,
    )
