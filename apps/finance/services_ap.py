"""应付相关服务函数。"""
from __future__ import annotations

from decimal import Decimal

from django.db.models import Sum

from apps.finance.models import APInvoice, APPaymentAllocation


def recalc_ap_invoice_amount_paid(ap_invoice_id: int) -> None:
    """按核销明细汇总回写应付账单的已付金额与付款状态。"""
    if not APInvoice.objects.filter(pk=ap_invoice_id).exists():
        return
    total = APPaymentAllocation.objects.filter(ap_invoice_id=ap_invoice_id).aggregate(
        s=Sum("amount")
    )["s"] or Decimal("0")
    inv = APInvoice.objects.get(pk=ap_invoice_id)
    inv.amount_paid = total
    inv._sync_status_from_amounts()
    inv.save(update_fields=["amount_paid", "status", "updated_at"])
