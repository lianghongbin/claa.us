"""Reconciliation variance registration and adjusting entries."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from apps.finance.bank_reconcile import apply_match, mark_ignored
from apps.finance.models import (
    BankLineMatchStatus,
    Category,
    ReconciliationVariance,
    ReconciliationVarianceKind,
    Transaction,
    TransactionType,
)


def _default_transaction_type(variance: ReconciliationVariance) -> str:
    if variance.bank_line_id:
        return variance.bank_line.transaction_type
    if variance.transaction_id:
        return variance.transaction.transaction_type
    if variance.kind in (
        ReconciliationVarianceKind.BANK_FEE,
        ReconciliationVarianceKind.UNRECORDED_BOOK,
    ):
        return TransactionType.EXPENSE
    return TransactionType.INCOME


def _account_name(variance: ReconciliationVariance) -> str:
    if variance.batch_id:
        return variance.batch.account_name
    if variance.bank_line_id:
        return variance.bank_line.batch.account_name
    if variance.transaction_id:
        return variance.transaction.account_name
    raise ValidationError(
        _("Cannot determine account name. Link an import batch or bank line.")
    )


def create_adjustment_transaction(
    variance: ReconciliationVariance,
    user,
    *,
    category: Category | None = None,
    tx_date: date | None = None,
) -> Transaction:
    """Create an adjusting entry from a variance and link reconciliation when possible."""
    if variance.adjustment_transaction_id:
        raise ValidationError(_("An adjusting entry already exists for this variance."))
    cat = category or variance.adjustment_category
    if cat is None:
        raise ValidationError(_("Select an adjustment category."))

    tx_type = _default_transaction_type(variance)
    if cat.kind != tx_type:
        raise ValidationError(
            _("Category type “%(kind)s” does not match required direction.")
            % {"kind": cat.get_kind_display()}
        )

    account = _account_name(variance)
    if variance.bank_line_id:
        line_date = variance.bank_line.line_date
    elif variance.transaction_id:
        line_date = variance.transaction.date
    else:
        line_date = date.today()
    use_date = tx_date or line_date

    note_parts = [_("[Reconciliation adjustment] %(kind)s") % {"kind": variance.get_kind_display()}]
    if variance.note:
        note_parts.append(variance.note.strip())
    if variance.bank_line_id and variance.bank_line.reference:
        note_parts.append(
            _("Bank reference: %(ref)s") % {"ref": variance.bank_line.reference}
        )

    tx_amount = variance.amount
    if (
        variance.kind == ReconciliationVarianceKind.UNRECORDED_BANK
        and variance.bank_line_id
    ):
        tx_amount = variance.bank_line.amount

    tx = Transaction.objects.create(
        date=use_date,
        transaction_type=tx_type,
        category=cat,
        amount=tx_amount,
        account_name=account,
        note="\n".join(str(p) for p in note_parts)[:4000],
        is_reconciled=False,
        created_by=user,
    )

    variance.adjustment_transaction = tx
    variance.is_resolved = True
    variance.save(
        update_fields=["adjustment_transaction", "is_resolved", "batch_id"]
    )

    if (
        variance.bank_line_id
        and variance.bank_line.match_status == BankLineMatchStatus.UNMATCHED
        and tx_amount == variance.bank_line.amount
    ):
        apply_match(variance.bank_line, tx)
    elif variance.transaction_id and variance.kind == ReconciliationVarianceKind.UNRECORDED_BOOK:
        Transaction.objects.filter(pk=variance.transaction.pk).update(is_reconciled=True)

    return tx


def resolve_without_adjustment(variance: ReconciliationVariance) -> None:
    """Mark resolved without creating an entry."""
    variance.is_resolved = True
    variance.save(update_fields=["is_resolved"])
    if (
        variance.bank_line_id
        and variance.kind == ReconciliationVarianceKind.OTHER
        and variance.bank_line.match_status == BankLineMatchStatus.UNMATCHED
    ):
        mark_ignored(variance.bank_line)
