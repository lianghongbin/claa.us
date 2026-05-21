"""应收相关服务函数。"""
from __future__ import annotations

from decimal import Decimal

from django.db.models import Sum

from apps.finance.models import ARInvoice, ARPaymentAllocation


def recalc_ar_invoice_amount_paid(ar_invoice_id: int) -> None:
    """按核销明细汇总回写应收账单的已收金额与状态。"""
    if not ARInvoice.objects.filter(pk=ar_invoice_id).exists():
        return
    total = ARPaymentAllocation.objects.filter(ar_invoice_id=ar_invoice_id).aggregate(
        s=Sum("amount")
    )["s"] or Decimal("0")
    inv = ARInvoice.objects.get(pk=ar_invoice_id)
    inv.amount_paid = total
    inv._sync_status_from_amounts()
    inv.save(update_fields=["amount_paid", "status", "updated_at"])
