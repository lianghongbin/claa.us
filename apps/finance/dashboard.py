"""财务看板：收支趋势与分类占比。"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from django.db.models import Sum
from django.db.models.functions import TruncMonth

from apps.finance.models import TransactionType
from apps.finance.reports import _base_transactions


@dataclass
class MonthlyTrendRow:
    month_start: date
    label: str
    income: Decimal
    expense: Decimal

    @property
    def net(self) -> Decimal:
        return self.income - self.expense


@dataclass
class CategoryShareRow:
    category_id: int
    category_name: str
    total: Decimal
    share_pct: Decimal


@dataclass
class FinanceDashboard:
    date_from: date
    date_to: date
    project_id: int | None
    total_income: Decimal
    total_expense: Decimal
    monthly_trends: list[MonthlyTrendRow] = field(default_factory=list)
    income_by_category: list[CategoryShareRow] = field(default_factory=list)
    expense_by_category: list[CategoryShareRow] = field(default_factory=list)

    @property
    def net_profit(self) -> Decimal:
        return self.total_income - self.total_expense

    @property
    def max_monthly_value(self) -> Decimal:
        if not self.monthly_trends:
            return Decimal("1")
        peak = max(
            max((r.income for r in self.monthly_trends), default=Decimal("0")),
            max((r.expense for r in self.monthly_trends), default=Decimal("0")),
        )
        return peak if peak > 0 else Decimal("1")


def _month_label(d: date) -> str:
    return f"{d.year}年{d.month}月"


def _iter_month_starts(date_from: date, date_to: date):
    y, m = date_from.year, date_from.month
    end_y, end_m = date_to.year, date_to.month
    while (y, m) <= (end_y, end_m):
        yield date(y, m, 1)
        if m == 12:
            y, m = y + 1, 1
        else:
            m += 1


def _category_share_rows(qs, transaction_type: str) -> list[CategoryShareRow]:
    agg = list(
        qs.filter(transaction_type=transaction_type)
        .values("category_id", "category__name")
        .annotate(total=Sum("amount"))
        .order_by("-total")
    )
    grand = sum((r["total"] or Decimal("0") for r in agg), Decimal("0"))
    rows: list[CategoryShareRow] = []
    for r in agg:
        total = r["total"] or Decimal("0")
        if total <= 0:
            continue
        pct = (total / grand * Decimal("100")).quantize(Decimal("0.01")) if grand else Decimal("0")
        rows.append(
            CategoryShareRow(
                category_id=r["category_id"],
                category_name=r["category__name"],
                total=total,
                share_pct=pct,
            )
        )
    return rows


def build_finance_dashboard(
    user,
    *,
    date_from: date,
    date_to: date,
    project_id: int | None = None,
) -> FinanceDashboard:
    if date_from > date_to:
        date_from, date_to = date_to, date_from

    qs = _base_transactions(user, date_from, date_to, project_id)

    def _month_key(raw) -> date:
        if hasattr(raw, "date") and callable(raw.date):
            raw = raw.date()
        return date(raw.year, raw.month, 1)

    income_map: dict[date, Decimal] = {}
    for r in (
        qs.filter(transaction_type=TransactionType.INCOME)
        .annotate(month=TruncMonth("date"))
        .values("month")
        .annotate(total=Sum("amount"))
    ):
        income_map[_month_key(r["month"])] = r["total"] or Decimal("0")

    expense_map: dict[date, Decimal] = {}
    for r in (
        qs.filter(transaction_type=TransactionType.EXPENSE)
        .annotate(month=TruncMonth("date"))
        .values("month")
        .annotate(total=Sum("amount"))
    ):
        expense_map[_month_key(r["month"])] = r["total"] or Decimal("0")

    monthly_trends: list[MonthlyTrendRow] = []
    for month_start in _iter_month_starts(date_from, date_to):
        monthly_trends.append(
            MonthlyTrendRow(
                month_start=month_start,
                label=_month_label(month_start),
                income=income_map.get(month_start, Decimal("0")),
                expense=expense_map.get(month_start, Decimal("0")),
            )
        )

    total_income = sum((r.income for r in monthly_trends), Decimal("0"))
    total_expense = sum((r.expense for r in monthly_trends), Decimal("0"))

    return FinanceDashboard(
        date_from=date_from,
        date_to=date_to,
        project_id=project_id,
        total_income=total_income,
        total_expense=total_expense,
        monthly_trends=monthly_trends,
        income_by_category=_category_share_rows(qs, TransactionType.INCOME),
        expense_by_category=_category_share_rows(qs, TransactionType.EXPENSE),
    )
