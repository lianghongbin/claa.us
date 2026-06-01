"""Bank / channel statement CSV parsing and import."""
from __future__ import annotations

from django.utils.translation import gettext_lazy as _

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.utils.dateparse import parse_date, parse_datetime

from apps.finance.models import BankStatementBatch, BankStatementLine, TransactionType


@dataclass
class ParsedBankLine:
    line_date: date
    transaction_type: str
    amount: Decimal
    description: str = ""
    reference: str = ""
    counterparty_hint: str = ""
    row_number: int = 0


@dataclass
class BankImportResult:
    imported: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


_HEADER_MAP: dict[str, list[str]] = {
    "date": [
        "交易日期",
        "日期",
        "记账日期",
        "入账时间",
        "交易时间",
        "发生时间",
        "date",
        "time",
    ],
    "income": ["收入", "收入金额", "贷方金额", "入账金额", "收入（元）"],
    "expense": ["支出", "支出金额", "借方金额", "支出（元）"],
    "amount": ["金额", "交易金额", "amount", "交易金额(元)"],
    "direction": ["借贷", "借贷标志", "收支", "收/支", "交易类型"],
    "description": [
        "摘要",
        "备注",
        "用途",
        "交易说明",
        "商品说明",
        "description",
        "交易摘要",
        "附言",
    ],
    "reference": [
        "流水号",
        "交易号",
        "凭证号",
        "订单号",
        "reference",
        "业务流水号",
        "支付宝交易号",
        "交易单号",
    ],
    "counterparty": ["对方户名", "对方名称", "交易对方", "对方账号", "对手户名"],
}


def _normalize_header(name: str) -> str:
    return re.sub(r"\s+", "", (name or "").strip().lower())


def _resolve_columns(headers: list[str]) -> dict[str, int]:
    normalized = {_normalize_header(h): i for i, h in enumerate(headers)}
    resolved: dict[str, int] = {}
    for key, aliases in _HEADER_MAP.items():
        for alias in aliases:
            idx = normalized.get(_normalize_header(alias))
            if idx is not None:
                resolved[key] = idx
                break
    return resolved


def _cell(row: list[str], col_map: dict[str, int], key: str) -> str:
    idx = col_map.get(key)
    if idx is None or idx >= len(row):
        return ""
    return (row[idx] or "").strip()


def _parse_decimal(raw: str) -> Decimal | None:
    if raw in (None, "", "-", "—"):
        return None
    s = str(raw).strip().replace(",", "").replace("￥", "").replace("¥", "")
    if not s:
        return None
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def _parse_line_date(raw: str) -> date | None:
    if not raw:
        return None
    s = str(raw).strip()
    if len(s) >= 10:
        d = parse_date(s[:10])
        if d:
            return d
    dt = parse_datetime(s.replace("/", "-"))
    if dt:
        return dt.date()
    for fmt in ("%Y%m%d", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(s[:19], fmt).date()
        except ValueError:
            continue
    return None


def _direction_to_type(direction: str, amount: Decimal) -> str | None:
    d = direction.strip().lower()
    if d in ("贷", "贷方", "收", "收入", "in", "income", "入账", "转入"):
        return TransactionType.INCOME
    if d in ("借", "借方", "支", "支出", "out", "expense", "出账", "转出", "付款"):
        return TransactionType.EXPENSE
    if amount < 0:
        return TransactionType.EXPENSE
    if amount > 0:
        return TransactionType.INCOME
    return None


def parse_csv_rows(
    content: bytes | str,
    *,
    encoding: str | None = None,
) -> tuple[list[ParsedBankLine], list[str]]:
    """解析 CSV 为结构化行；返回 (成功行, 错误信息列表)。"""
    errors: list[str] = []
    if isinstance(content, bytes):
        text = None
        for enc in (encoding, "utf-8-sig", "utf-8", "gb18030", "gbk"):
            if enc is None:
                continue
            try:
                text = content.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if text is None:
            return [], [str(_("Unrecognized file encoding. Save CSV as UTF-8 or GBK."))]
    else:
        text = content

    reader = csv.reader(io.StringIO(text))
    try:
        headers = next(reader)
    except StopIteration:
        return [], [str(_("CSV file is empty."))]

    col_map = _resolve_columns(headers)
    if "date" not in col_map:
        return [], [
            str(_("No date column found. Headers should include date fields (e.g. 交易日期 / Date)."))
        ]
    has_amount = "amount" in col_map or "income" in col_map or "expense" in col_map
    if not has_amount:
        return [], [
            str(_("No amount column found. Headers should include amount / income / expense."))
        ]

    lines: list[ParsedBankLine] = []
    for row_number, row in enumerate(reader, start=2):
        if not row or all(not (c or "").strip() for c in row):
            continue
        raw_date = _cell(row, col_map, "date")
        line_date = _parse_line_date(raw_date)
        if not line_date:
            errors.append(
                str(_("Row %(row)s: invalid date “%(raw)s”") % {"row": row_number, "raw": raw_date})
            )
            continue

        amount: Decimal | None = None
        tx_type: str | None = None

        inc = _parse_decimal(_cell(row, col_map, "income"))
        exp = _parse_decimal(_cell(row, col_map, "expense"))
        if inc is not None and inc > 0:
            amount = inc
            tx_type = TransactionType.INCOME
        elif exp is not None and exp > 0:
            amount = exp
            tx_type = TransactionType.EXPENSE
        else:
            raw_amt = _parse_decimal(_cell(row, col_map, "amount"))
            if raw_amt is None:
                errors.append(
                    str(_("Row %(row)s: amount missing or invalid") % {"row": row_number})
                )
                continue
            direction = _cell(row, col_map, "direction")
            if direction:
                tx_type = _direction_to_type(direction, raw_amt)
                amount = abs(raw_amt)
            elif raw_amt != 0:
                tx_type = (
                    TransactionType.INCOME
                    if raw_amt > 0
                    else TransactionType.EXPENSE
                )
                amount = abs(raw_amt)
            else:
                errors.append(
                    str(_("Row %(row)s: zero amount, skipped") % {"row": row_number})
                )
                continue

        if tx_type is None or amount is None or amount <= 0:
            errors.append(
                str(_("Row %(row)s: cannot determine income vs expense") % {"row": row_number})
            )
            continue

        lines.append(
            ParsedBankLine(
                line_date=line_date,
                transaction_type=tx_type,
                amount=amount,
                description=_cell(row, col_map, "description")[:500],
                reference=_cell(row, col_map, "reference")[:100],
                counterparty_hint=_cell(row, col_map, "counterparty")[:200],
                row_number=row_number,
            )
        )
    return lines, errors


def import_csv_into_batch(batch: BankStatementBatch) -> BankImportResult:
    """读取批次关联文件并写入 BankStatementLine。"""
    result = BankImportResult()
    if not batch.file:
        result.errors.append("未上传文件。")
        return result

    batch.file.open("rb")
    try:
        content = batch.file.read()
    finally:
        batch.file.close()

    parsed, parse_errors = parse_csv_rows(content)
    result.errors.extend(parse_errors)

    if not parsed and parse_errors:
        return result

    to_create: list[BankStatementLine] = []
    for item in parsed:
        to_create.append(
            BankStatementLine(
                batch=batch,
                line_date=item.line_date,
                transaction_type=item.transaction_type,
                amount=item.amount,
                description=item.description,
                reference=item.reference,
                counterparty_hint=item.counterparty_hint,
                source_row_number=item.row_number,
            )
        )

    if to_create:
        BankStatementLine.objects.bulk_create(to_create, batch_size=500)
        result.imported = len(to_create)

    result.skipped = len(parse_errors)
    return result
