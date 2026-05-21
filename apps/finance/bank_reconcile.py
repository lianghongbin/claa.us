"""银行账单明细与系统流水对账匹配。"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal

from apps.finance.models import (
    BankLineMatchStatus,
    BankStatementBatch,
    BankStatementLine,
    Transaction,
)
from apps.finance.visibility import transactions_visible_for_user

# 日期容差（天）：自动匹配时允许系统流水日期与账单日期相差不超过该值
DATE_TOLERANCE_DAYS = 3


@dataclass
class AutoMatchResult:
    matched: int = 0
    ambiguous: int = 0
    no_candidate: int = 0
    details: list[str] = field(default_factory=list)


def _already_matched_tx_ids(exclude_line_id: int | None = None) -> set[int]:
    qs = BankStatementLine.objects.filter(
        match_status=BankLineMatchStatus.MATCHED,
        matched_transaction_id__isnull=False,
    )
    if exclude_line_id:
        qs = qs.exclude(pk=exclude_line_id)
    return set(qs.values_list("matched_transaction_id", flat=True))


def candidate_transactions(
    line: BankStatementLine,
    user,
    *,
    date_tolerance: int = DATE_TOLERANCE_DAYS,
) -> list[Transaction]:
    """返回可与该账单行匹配的系统流水候选（未被他行占用、账户与类型一致）。"""
    batch = line.batch
    date_from = line.line_date - timedelta(days=date_tolerance)
    date_to = line.line_date + timedelta(days=date_tolerance)
    used = _already_matched_tx_ids(exclude_line_id=line.pk)

    qs = Transaction.objects.filter(
        account_name=batch.account_name,
        transaction_type=line.transaction_type,
        amount=line.amount,
        date__gte=date_from,
        date__lte=date_to,
        is_reconciled=False,
    ).exclude(pk__in=used)
    qs = transactions_visible_for_user(qs, user)
    return list(qs.order_by("date", "pk"))


def _score_candidate(line: BankStatementLine, tx: Transaction) -> int:
    """分数越高越优先；用于在多个候选中择优。"""
    score = 0
    if tx.date == line.line_date:
        score += 100
    if line.reference and line.reference in (tx.note or ""):
        score += 50
    if line.description and line.description in (tx.note or ""):
        score += 30
    if line.counterparty_hint and tx.counterparty_id:
        if line.counterparty_hint in str(tx.counterparty.name):
            score += 20
    return score


def find_auto_match(line: BankStatementLine, user) -> Transaction | None:
    """
    自动匹配：金额+账户+类型+日期容差内仅一条候选则命中；
    多条时若存在唯一最高分且分数>=100（同日）则命中。
    """
    if line.match_status == BankLineMatchStatus.IGNORED:
        return None
    candidates = candidate_transactions(line, user, date_tolerance=0)
    if len(candidates) == 1:
        return candidates[0]

    candidates = candidate_transactions(line, user)
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    scored = [(tx, _score_candidate(line, tx)) for tx in candidates]
    scored.sort(key=lambda x: (-x[1], x[0].date, x[0].pk))
    best_tx, best_score = scored[0]
    if len(scored) > 1 and scored[1][1] == best_score:
        return None
    if best_score >= 100:
        return best_tx
    if line.reference:
        ref_hits = [
            tx
            for tx, _ in scored
            if line.reference in (tx.note or "") or line.reference in tx.account_name
        ]
        if len(ref_hits) == 1:
            return ref_hits[0]
    return None


def apply_match(line: BankStatementLine, transaction: Transaction) -> None:
    """绑定匹配并标记系统流水已对账。"""
    if line.batch.account_name != transaction.account_name:
        raise ValueError("账户名称不一致，无法匹配。")
    if line.transaction_type != transaction.transaction_type:
        raise ValueError("收支方向不一致，无法匹配。")
    if line.amount != transaction.amount:
        raise ValueError("金额不一致，无法匹配。")
    used = _already_matched_tx_ids(exclude_line_id=line.pk)
    if transaction.pk in used:
        raise ValueError("该系统流水已被其他账单明细匹配。")

    line.matched_transaction = transaction
    line.match_status = BankLineMatchStatus.MATCHED
    line.save(update_fields=["matched_transaction", "match_status"])
    if not transaction.is_reconciled:
        Transaction.objects.filter(pk=transaction.pk).update(is_reconciled=True)


def clear_match(line: BankStatementLine, *, unmark_transaction: bool = True) -> None:
    tx_id = line.matched_transaction_id
    line.matched_transaction = None
    line.match_status = BankLineMatchStatus.UNMATCHED
    line.save(update_fields=["matched_transaction", "match_status"])
    if unmark_transaction and tx_id:
        still_linked = BankStatementLine.objects.filter(
            matched_transaction_id=tx_id,
            match_status=BankLineMatchStatus.MATCHED,
        ).exists()
        if not still_linked:
            Transaction.objects.filter(pk=tx_id, is_reconciled=True).update(
                is_reconciled=False
            )


def mark_ignored(line: BankStatementLine) -> None:
    if line.matched_transaction_id:
        clear_match(line)
    line.match_status = BankLineMatchStatus.IGNORED
    line.save(update_fields=["match_status"])


def auto_match_lines(
    lines,
    user,
) -> AutoMatchResult:
    result = AutoMatchResult()
    for line in lines:
        if line.match_status != BankLineMatchStatus.UNMATCHED:
            continue
        tx = find_auto_match(line, user)
        if tx is None:
            cands = candidate_transactions(line, user)
            if len(cands) > 1:
                result.ambiguous += 1
                result.details.append(
                    f"行 {line.pk}（{line.line_date} {line.amount}）存在 {len(cands)} 条候选，未自动匹配。"
                )
            else:
                result.no_candidate += 1
            continue
        apply_match(line, tx)
        result.matched += 1
    return result


def auto_match_batch(batch: BankStatementBatch, user) -> AutoMatchResult:
    lines = batch.lines.filter(match_status=BankLineMatchStatus.UNMATCHED)
    return auto_match_lines(lines, user)
