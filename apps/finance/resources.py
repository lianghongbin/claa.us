from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.utils.dateparse import parse_date
from django.utils.translation import gettext_lazy as _

from import_export import fields, resources

from apps.audit.models import AuditLog
from apps.audit.services import log_model_change
from apps.finance.models import (
    Category,
    Counterparty,
    ExpenseTransaction,
    IncomeTransaction,
    Project,
    Tag,
    Transaction,
    TransactionType,
)


# Import column aliases (English + legacy Chinese headers).
_TYPE_ALIASES = {
    "收入": TransactionType.INCOME,
    "income": TransactionType.INCOME,
    "Income": TransactionType.INCOME,
    "支出": TransactionType.EXPENSE,
    "expense": TransactionType.EXPENSE,
    "Expense": TransactionType.EXPENSE,
}

_COL_TYPE = ("transaction_type", "收支类型", "Type")
_COL_CATEGORY = ("category_name", "科目名称", "Category")
_COL_PROJECT = ("project_code", "项目编码", "Project code")
_COL_COUNTERPARTY = ("counterparty_code", "单位编码", "Counterparty code")
_COL_TAGS = ("tag_names", "标签", "Tags")
_COL_AMOUNT = ("amount", "金额", "Amount")
_COL_NOTE = ("note", "摘要", "备注", "Memo")
_COL_DATE = ("date", "日期", "Date")
_COL_ACCOUNT = ("account_name", "账户名称", "Account name")
_COL_RECONCILED = ("is_reconciled", "已对账", "Reconciled")


def _first_key(data: dict, keys: tuple[str, ...]):
    for key in keys:
        if key in data and data[key] not in (None, ""):
            return data[key]
    return None


def _normalize_type(raw: str | None) -> str:
    if raw is None:
        raise ValueError(_("Transaction type is required"))
    key = str(raw).strip().lower()
    if key in (TransactionType.INCOME, TransactionType.EXPENSE):
        return key
    orig = str(raw).strip()
    if orig in _TYPE_ALIASES:
        return _TYPE_ALIASES[orig]
    raise ValueError(_("Unrecognized transaction type: %(raw)s") % {"raw": raw})


class CategoryResource(resources.ModelResource):
    class Meta:
        model = Category
        fields = ("id", "name", "kind", "sort_order", "is_active")
        export_order = ("id", "name", "kind", "sort_order", "is_active")
        import_id_fields = ("id",)


class TransactionResource(resources.ModelResource):
    category_name = fields.Field(column_name=_("Category"), attribute=None, readonly=True)
    project_code = fields.Field(column_name=_("Project code"), attribute=None, readonly=True)
    counterparty_code = fields.Field(
        column_name=_("Counterparty code"), attribute=None, readonly=True
    )
    tag_names = fields.Field(column_name=_("Tags"), attribute=None, readonly=True)

    class Meta:
        model = Transaction
        fields = (
            "id",
            "date",
            "transaction_type",
            "category_name",
            "project_code",
            "counterparty_code",
            "tag_names",
            "note",
            "amount",
            "account_name",
            "is_reconciled",
        )
        export_order = fields
        import_id_fields = ("id",)

    def dehydrate_category_name(self, transaction: Transaction) -> str:
        return transaction.category.name

    def dehydrate_project_code(self, transaction: Transaction) -> str:
        if transaction.project_id:
            return transaction.project.code
        return ""

    def dehydrate_counterparty_code(self, transaction: Transaction) -> str:
        if transaction.counterparty_id:
            return transaction.counterparty.code
        return ""

    def dehydrate_tag_names(self, transaction: Transaction) -> str:
        return ", ".join(transaction.tags.values_list("name", flat=True))

    def dehydrate_note(self, transaction: Transaction) -> str:
        return transaction.note or ""

    def before_import_row(self, row, row_number=None, **kwargs) -> None:
        data = dict(row)
        fixed = self._fixed_transaction_type
        raw_type = _first_key(data, _COL_TYPE)
        if fixed is not None:
            if raw_type in (None, ""):
                row["_resolved_type"] = fixed
            else:
                resolved = _normalize_type(raw_type)
                if resolved != fixed:
                    label = _("Income") if fixed == TransactionType.INCOME else _("Expense")
                    raise ValueError(
                        _("Row %(row)s: type does not match this list (%(label)s).")
                        % {"row": row_number, "label": label}
                    )
                row["_resolved_type"] = resolved
        else:
            row["_resolved_type"] = _normalize_type(raw_type)

        name = (_first_key(data, _COL_CATEGORY) or "").strip()
        if not name:
            raise ValueError(_("Category name is required"))

        kind = row["_resolved_type"]
        try:
            cat = Category.objects.get(name=name, kind=kind, is_active=True)
        except Category.DoesNotExist as exc:
            raise ValueError(
                _("Row %(row)s: no active category “%(name)s” for type %(kind)s")
                % {"row": row_number, "name": name, "kind": kind}
            ) from exc
        row["_resolved_category_id"] = cat.pk

        amount_raw = _first_key(data, _COL_AMOUNT)
        if amount_raw in (None, ""):
            raise ValueError(_("Amount is required"))
        try:
            amount = Decimal(str(amount_raw).replace(",", ""))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError(
                _("Invalid amount: %(raw)s") % {"raw": amount_raw}
            ) from exc
        if amount <= Decimal("0"):
            raise ValueError(_("Amount must be greater than zero"))
        row["_parsed_amount"] = amount

        raw_note = _first_key(data, _COL_NOTE)
        row["_parsed_note"] = str(raw_note or "").strip()[:4000]

        proj_code = (_first_key(data, _COL_PROJECT) or "").strip()
        if proj_code:
            try:
                proj = Project.objects.get(code=proj_code, is_active=True)
            except Project.DoesNotExist as exc:
                raise ValueError(
                    _("Row %(row)s: unknown active project code “%(code)s”")
                    % {"row": row_number, "code": proj_code}
                ) from exc
            row["_resolved_project_id"] = proj.pk
        else:
            row["_resolved_project_id"] = None

        cp_code = (_first_key(data, _COL_COUNTERPARTY) or "").strip()
        if cp_code:
            try:
                cp = Counterparty.objects.get(code=cp_code, is_active=True)
            except Counterparty.DoesNotExist as exc:
                raise ValueError(
                    _("Row %(row)s: unknown active counterparty code “%(code)s”")
                    % {"row": row_number, "code": cp_code}
                ) from exc
            row["_resolved_counterparty_id"] = cp.pk
        else:
            row["_resolved_counterparty_id"] = None

        raw_tags = _first_key(data, _COL_TAGS) or ""
        tag_ids: list[int] = []
        for part in str(raw_tags).split(","):
            tag_name = part.strip()
            if not tag_name:
                continue
            try:
                tag_ids.append(Tag.objects.get(name=tag_name).pk)
            except Tag.DoesNotExist as exc:
                raise ValueError(
                    _("Row %(row)s: unknown tag “%(name)s”. Create it in admin first.")
                    % {"row": row_number, "name": tag_name}
                ) from exc
        row["_resolved_tag_ids"] = tag_ids

    def get_import_fields(self):
        return []

    def import_instance(self, instance, row, **kwargs):
        data = dict(row)
        instance.transaction_type = data["_resolved_type"]
        instance.category_id = int(data["_resolved_category_id"])
        instance.amount = data["_parsed_amount"]
        instance.note = data.get("_parsed_note", "")
        instance.project_id = data.get("_resolved_project_id")
        instance.counterparty_id = data.get("_resolved_counterparty_id")

        raw_date = _first_key(data, _COL_DATE)
        if raw_date is None or raw_date == "":
            raise ValueError(_("Date is required"))
        if hasattr(raw_date, "year"):
            instance.date = raw_date
        else:
            parsed = parse_date(str(raw_date).strip()[:10])
            if not parsed:
                raise ValueError(_("Invalid date: %(raw)s") % {"raw": raw_date})
            instance.date = parsed

        acc = (_first_key(data, _COL_ACCOUNT) or "").strip()
        if not acc:
            raise ValueError(_("Account name is required"))
        instance.account_name = acc

        irr = _first_key(data, _COL_RECONCILED)
        if irr is not None and str(irr).strip() != "":
            s = str(irr).strip().lower()
            instance.is_reconciled = s in (
                "1",
                "true",
                "yes",
                "y",
                "是",
                "已对账",
                "reconciled",
            )
        elif not instance.pk:
            instance.is_reconciled = False

    def __init__(self, **kwargs):
        self._fixed_transaction_type = kwargs.pop("fixed_transaction_type", None)
        self._http_request = kwargs.pop("request", None)
        super().__init__(**kwargs)

    def save_instance(self, instance, is_create, row, **kwargs):
        instance._import_is_create = is_create
        super().save_instance(instance, is_create, row, **kwargs)

    def after_save_instance(self, instance, row, **kwargs):
        if kwargs.get("dry_run"):
            super().after_save_instance(instance, row, **kwargs)
            return
        data = dict(row)
        instance.tags.set(data.get("_resolved_tag_ids", []))
        req = self._http_request
        if req is None:
            user = kwargs.get("user")
            if user is not None and getattr(user, "is_authenticated", False):

                class _Mini:
                    META = {}

                req = _Mini()
                req.user = user
            else:
                req = None
        is_create = getattr(instance, "_import_is_create", False)
        if is_create and req is not None and req.user.is_authenticated:
            Transaction.objects.filter(pk=instance.pk).update(created_by=req.user)
        instance = Transaction.objects.prefetch_related("tags").get(pk=instance.pk)
        snap = instance.audit_snapshot()
        if req is not None:
            if is_create:
                log_model_change(
                    req,
                    action=AuditLog.Action.CREATE,
                    instance=instance,
                    changes={"after": snap, "source": "import"},
                )
            else:
                log_model_change(
                    req,
                    action=AuditLog.Action.UPDATE,
                    instance=instance,
                    changes={"after": snap, "source": "import"},
                )
        super().after_save_instance(instance, row, **kwargs)


class IncomeTransactionResource(TransactionResource):
    class Meta:
        model = IncomeTransaction
        fields = TransactionResource.Meta.fields
        export_order = TransactionResource.Meta.export_order
        import_id_fields = ("id",)


class ExpenseTransactionResource(TransactionResource):
    class Meta:
        model = ExpenseTransaction
        fields = TransactionResource.Meta.fields
        export_order = TransactionResource.Meta.export_order
        import_id_fields = ("id",)
