from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q, Sum
from django.utils.translation import gettext_lazy as _


class CategoryKind(models.TextChoices):
    INCOME = "income", _("Income")
    EXPENSE = "expense", _("Expense")


class TransactionType(models.TextChoices):
    INCOME = "income", _("Income")
    EXPENSE = "expense", _("Expense")


class Category(models.Model):
    name = models.CharField(_("Name"), max_length=100)
    kind = models.CharField(
        _("Type"),
        max_length=20,
        choices=CategoryKind.choices,
        db_index=True,
    )
    sort_order = models.PositiveSmallIntegerField(_("Sort Order"), default=0)
    is_active = models.BooleanField(_("Active"), default=True)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)

    class Meta:
        verbose_name = _("Account Category")
        verbose_name_plural = _("Account Categories")
        ordering = ("kind", "sort_order", "name")
        permissions = [
            ("manage_database", _("Backup and restore database")),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("name", "kind"),
                name="finance_category_unique_name_kind",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} · {self.name}"


class CounterpartyKind(models.TextChoices):
    CUSTOMER = "customer", _("Customer")
    VENDOR = "vendor", _("Vendor")
    BOTH = "both", _("Customer and Vendor")


class Counterparty(models.Model):
    """客户/供应商等往来单位（应收应付将挂接于此）。"""

    code = models.SlugField(_("Unit Code"), max_length=50, unique=True, db_index=True)
    name = models.CharField(_("Name"), max_length=200)
    kind = models.CharField(
        _("Type"),
        max_length=20,
        choices=CounterpartyKind.choices,
        db_index=True,
    )
    tax_id = models.CharField(_("Tax ID / Unified Social Credit Code"), max_length=40, blank=True)
    contact_name = models.CharField(_("Contact Name"), max_length=100, blank=True)
    contact_phone = models.CharField(_("Phone"), max_length=40, blank=True)
    contact_email = models.EmailField(_("Email"), blank=True)
    billing_address = models.TextField(_("Address"), blank=True)
    remark = models.CharField(_("Remark"), max_length=500, blank=True)
    is_active = models.BooleanField(_("Active"), default=True, db_index=True)
    visibility_groups = models.ManyToManyField(
        Group,
        blank=True,
        related_name="finance_counterparties_visible",
        verbose_name=_("Visible Groups"),
        help_text=_(
            "If empty, visible to all users who can view counterparties; "
            "if set, only users in selected groups can view."
        ),
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)

    class Meta:
        verbose_name = _("Counterparty")
        verbose_name_plural = _("Counterparties")
        ordering = ("code",)
        permissions = [
            ("view_all_counterparties", _("Can view all counterparties (ignore visibility groups)")),
        ]

    def __str__(self) -> str:
        return f"{self.code} · {self.name}"


class Project(models.Model):
    """项目/成本对象核算（流水可选关联）。"""

    code = models.SlugField(_("Project Code"), max_length=50, unique=True, db_index=True)
    name = models.CharField(_("Project Name"), max_length=200)
    is_active = models.BooleanField(_("Active"), default=True, db_index=True)
    remark = models.CharField(_("Remark"), max_length=500, blank=True)
    visibility_groups = models.ManyToManyField(
        Group,
        blank=True,
        related_name="finance_projects_visible",
        verbose_name=_("Visible Groups"),
        help_text=_(
            "If empty, visible to all users who can view projects; "
            "if set, only users in selected groups can view."
        ),
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)

    class Meta:
        verbose_name = _("Project")
        verbose_name_plural = _("Projects")
        ordering = ("code",)
        permissions = [
            ("view_all_projects", _("Can view all projects (ignore visibility groups)")),
        ]

    def __str__(self) -> str:
        return f"{self.code} · {self.name}"


class Tag(models.Model):
    name = models.CharField(_("Tag"), max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)

    class Meta:
        verbose_name = _("Transaction Tag")
        verbose_name_plural = _("Transaction Tags")
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class Transaction(models.Model):
    date = models.DateField(_("Date"), db_index=True)
    transaction_type = models.CharField(
        _("Transaction Type"),
        max_length=20,
        choices=TransactionType.choices,
        db_index=True,
    )
    category = models.ForeignKey(
        Category,
        verbose_name=_("Category"),
        on_delete=models.PROTECT,
        related_name="transactions",
    )
    amount = models.DecimalField(
        _("Amount"),
        max_digits=12,
        decimal_places=2,
        help_text=_("Positive amount in base currency"),
    )
    account_name = models.CharField(_("Account Name"), max_length=200)
    note = models.TextField(_("Description / Note"), blank=True)
    project = models.ForeignKey(
        Project,
        verbose_name=_("Project"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
    )
    counterparty = models.ForeignKey(
        Counterparty,
        verbose_name=_("Counterparty"),
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="transactions",
    )
    tags = models.ManyToManyField(
        Tag,
        verbose_name=_("Tags"),
        blank=True,
        related_name="transactions",
    )
    is_reconciled = models.BooleanField(_("Reconciled"), default=False, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Created By"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="finance_transactions_created",
        editable=False,
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Transaction")
        verbose_name_plural = _("Transactions")
        ordering = ("-date", "-pk")
        permissions = [
            (
                "view_all_finance_transactions",
                _("Can view all finance transactions (ignore project/counterparty visibility)"),
            ),
        ]

    def __str__(self) -> str:
        return f"{self.date} {self.get_transaction_type_display()} {self.amount}"

    def audit_snapshot(self) -> dict:
        return {
            "date": str(self.date),
            "transaction_type": self.transaction_type,
            "category_id": self.category_id,
            "amount": str(self.amount),
            "account_name": self.account_name,
            "note": self.note,
            "project_id": self.project_id,
            "counterparty_id": self.counterparty_id,
            "tag_ids": sorted(self.tags.values_list("pk", flat=True)) if self.pk else [],
            "is_reconciled": self.is_reconciled,
        }

    def clean(self) -> None:
        super().clean()
        if self.category_id and self.transaction_type:
            if self.category.kind != self.transaction_type:
                raise ValidationError(
                    {"category": _("The selected category type must match the transaction type.")}
                )
        if self.amount is not None and self.amount <= Decimal("0"):
            raise ValidationError({"amount": _("Amount must be greater than 0.")})


class TransactionAttachment(models.Model):
    """单笔流水的凭证、合同、回单等附件。"""

    transaction = models.ForeignKey(
        Transaction,
        verbose_name=_("Transaction"),
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    file = models.FileField(_("File"), upload_to="finance_attachments/%Y/%m/")
    caption = models.CharField(_("Caption"), max_length=200, blank=True)
    uploaded_at = models.DateTimeField(_("Uploaded At"), auto_now_add=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Uploaded By"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
    )

    class Meta:
        verbose_name = _("Transaction Attachment")
        verbose_name_plural = _("Transaction Attachments")
        ordering = ("pk",)

    def __str__(self) -> str:
        return self.caption or self.file.name


class ARInvoiceStatus(models.TextChoices):
    DRAFT = "draft", _("Draft")
    OPEN = "open", _("Open")
    PARTIAL = "partial", _("Partially Paid")
    PAID = "paid", _("Paid")
    VOID = "void", _("Void")


class ARInvoice(models.Model):
    """应收账单：记录对客户应收金额、账期与结清状态（收款核销在后续任务中对接）。"""

    number = models.CharField(_("AR Invoice Number"), max_length=40, unique=True, db_index=True)
    counterparty = models.ForeignKey(
        Counterparty,
        verbose_name=_("Customer"),
        on_delete=models.PROTECT,
        related_name="ar_invoices",
    )
    title = models.CharField(_("Title"), max_length=200, blank=True)
    issue_date = models.DateField(_("Issue Date"), db_index=True)
    due_date = models.DateField(
        _("Due Date"),
        null=True,
        blank=True,
        db_index=True,
    )
    amount_total = models.DecimalField(_("Total Amount Receivable"), max_digits=14, decimal_places=2)
    amount_paid = models.DecimalField(
        _("Amount Received"),
        max_digits=14,
        decimal_places=2,
        default=Decimal("0"),
        help_text=_("Automatically summarized from payment allocations; do not edit manually."),
    )
    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=ARInvoiceStatus.choices,
        default=ARInvoiceStatus.DRAFT,
        db_index=True,
    )
    remark = models.TextField(_("Remark"), blank=True)
    visibility_groups = models.ManyToManyField(
        Group,
        blank=True,
        related_name="finance_ar_invoices_visible",
        verbose_name=_("Visible Groups"),
        help_text=_(
            "If empty, visible to all users who can view AR invoices; "
            "if set, only users in selected groups can view."
        ),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Created By"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ar_invoices_created",
        editable=False,
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("AR Invoice")
        verbose_name_plural = _("AR Invoices")
        ordering = ("-issue_date", "-pk")
        permissions = [
            ("view_all_arinvoices", _("Can view all AR invoices (ignore visibility groups)")),
        ]
        constraints = [
            models.CheckConstraint(
                check=Q(amount_paid__lte=F("amount_total")),
                name="finance_ar_amount_paid_lte_total",
            ),
            models.CheckConstraint(
                check=Q(amount_total__gt=0),
                name="finance_ar_amount_total_positive",
            ),
        ]

    def __str__(self) -> str:
        return self.number

    @property
    def balance_unpaid(self) -> Decimal:
        return self.amount_total - self.amount_paid

    def _sync_status_from_amounts(self) -> None:
        if self.status in (ARInvoiceStatus.VOID, ARInvoiceStatus.DRAFT):
            return
        if self.amount_total is None or self.amount_total <= 0:
            return
        paid = self.amount_paid or Decimal("0")
        if paid >= self.amount_total:
            self.status = ARInvoiceStatus.PAID
        elif paid > 0:
            self.status = ARInvoiceStatus.PARTIAL
        else:
            self.status = ARInvoiceStatus.OPEN

    def clean(self) -> None:
        super().clean()
        if self.counterparty_id:
            k = self.counterparty.kind
            if k not in (CounterpartyKind.CUSTOMER, CounterpartyKind.BOTH):
                raise ValidationError(
                    {
                        "counterparty": _(
                            "AR invoices can only be linked to counterparties of type "
                            "Customer or Customer and Vendor."
                        )
                    }
                )
        if (
            self.amount_total is not None
            and self.amount_paid is not None
            and self.amount_paid > self.amount_total
        ):
            raise ValidationError({"amount_paid": _("Amount received cannot exceed total receivable.")})

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        self._sync_status_from_amounts()
        super().save(*args, **kwargs)


class ARPaymentAllocation(models.Model):
    """一笔收入流水核销到某张应收账单上的金额。"""

    ar_invoice = models.ForeignKey(
        ARInvoice,
        verbose_name=_("AR Invoice"),
        on_delete=models.CASCADE,
        related_name="payment_allocations",
    )
    transaction = models.ForeignKey(
        "Transaction",
        verbose_name=_("Receipt Transaction"),
        on_delete=models.CASCADE,
        related_name="ar_payment_allocations",
    )
    amount = models.DecimalField(_("Allocation Amount"), max_digits=14, decimal_places=2)
    note = models.CharField(_("Remark"), max_length=200, blank=True)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Created By"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ar_payment_allocations_created",
        editable=False,
    )

    class Meta:
        verbose_name = _("AR Payment Allocation")
        verbose_name_plural = _("AR Payment Allocations")
        ordering = ("-pk",)
        constraints = [
            models.UniqueConstraint(
                fields=("ar_invoice", "transaction"),
                name="finance_ar_payment_alloc_unique_invoice_tx",
            ),
            models.CheckConstraint(
                check=Q(amount__gt=0),
                name="finance_ar_payment_alloc_amount_positive",
            ),
        ]

    def __str__(self) -> str:
        return f"#{self.pk} {_('allocation')} {self.amount}"

    def clean(self) -> None:
        super().clean()
        if self.transaction_id:
            if self.transaction.transaction_type != TransactionType.INCOME:
                raise ValidationError(
                    {"transaction": _("Only income transactions can be allocated to AR invoices.")}
                )
            if (
                self.ar_invoice_id
                and self.transaction.counterparty_id != self.ar_invoice.counterparty_id
            ):
                raise ValidationError(
                    {"transaction": _("Transaction counterparty must match the AR invoice customer.")}
                )
        if self.ar_invoice_id and self.amount is not None:
            qs = ARPaymentAllocation.objects.filter(ar_invoice_id=self.ar_invoice_id)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            other = qs.aggregate(s=Sum("amount"))["s"] or Decimal("0")
            if other + self.amount > self.ar_invoice.amount_total:
                raise ValidationError({"amount": _("Total allocations cannot exceed invoice amount.")})
        if self.transaction_id and self.amount is not None:
            qs = ARPaymentAllocation.objects.filter(transaction_id=self.transaction_id)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            other = qs.aggregate(s=Sum("amount"))["s"] or Decimal("0")
            if other + self.amount > self.transaction.amount:
                raise ValidationError(
                    {"amount": _("Total allocated amount exceeds the transaction amount.")}
                )


class APApprovalStatus(models.TextChoices):
    DRAFT = "draft", _("Draft")
    PENDING = "pending", _("Pending Approval")
    APPROVED = "approved", _("Approved")
    REJECTED = "rejected", _("Rejected")


class APInvoiceStatus(models.TextChoices):
    DRAFT = "draft", _("Draft")
    OPEN = "open", _("Open")
    PARTIAL = "partial", _("Partially Paid")
    PAID = "paid", _("Paid")
    VOID = "void", _("Void")


class APInvoice(models.Model):
    """应付账单：记录对供应商应付金额、账期、审批与付款状态。"""

    number = models.CharField(_("AP Invoice Number"), max_length=40, unique=True, db_index=True)
    counterparty = models.ForeignKey(
        Counterparty,
        verbose_name=_("Vendor"),
        on_delete=models.PROTECT,
        related_name="ap_invoices",
    )
    title = models.CharField(_("Title"), max_length=200, blank=True)
    issue_date = models.DateField(_("Issue Date"), db_index=True)
    due_date = models.DateField(
        _("Due Date"),
        null=True,
        blank=True,
        db_index=True,
    )
    amount_total = models.DecimalField(_("Total Amount Payable"), max_digits=14, decimal_places=2)
    amount_paid = models.DecimalField(
        _("Amount Paid"),
        max_digits=14,
        decimal_places=2,
        default=Decimal("0"),
        help_text=_("Automatically summarized from payment allocations; do not edit manually."),
    )
    approval_status = models.CharField(
        _("Approval Status"),
        max_length=20,
        choices=APApprovalStatus.choices,
        default=APApprovalStatus.DRAFT,
        db_index=True,
    )
    status = models.CharField(
        _("Payment Status"),
        max_length=20,
        choices=APInvoiceStatus.choices,
        default=APInvoiceStatus.DRAFT,
        db_index=True,
    )
    remark = models.TextField(_("Remark"), blank=True)
    visibility_groups = models.ManyToManyField(
        Group,
        blank=True,
        related_name="finance_ap_invoices_visible",
        verbose_name=_("Visible Groups"),
        help_text=_(
            "If empty, visible to all users who can view AP invoices; "
            "if set, only users in selected groups can view."
        ),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Created By"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ap_invoices_created",
        editable=False,
    )
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("AP Invoice")
        verbose_name_plural = _("AP Invoices")
        ordering = ("-issue_date", "-pk")
        permissions = [
            ("view_all_apinvoices", _("Can view all AP invoices (ignore visibility groups)")),
            ("approve_apinvoice", _("Can approve AP invoices")),
        ]
        constraints = [
            models.CheckConstraint(
                check=Q(amount_paid__lte=F("amount_total")),
                name="finance_ap_amount_paid_lte_total",
            ),
            models.CheckConstraint(
                check=Q(amount_total__gt=0),
                name="finance_ap_amount_total_positive",
            ),
        ]

    def __str__(self) -> str:
        return self.number

    @property
    def balance_unpaid(self) -> Decimal:
        return self.amount_total - self.amount_paid

    def _sync_status_from_amounts(self) -> None:
        if self.status in (APInvoiceStatus.VOID, APInvoiceStatus.DRAFT):
            return
        if self.approval_status != APApprovalStatus.APPROVED:
            return
        if self.amount_total is None or self.amount_total <= 0:
            return
        paid = self.amount_paid or Decimal("0")
        if paid >= self.amount_total:
            self.status = APInvoiceStatus.PAID
        elif paid > 0:
            self.status = APInvoiceStatus.PARTIAL
        else:
            self.status = APInvoiceStatus.OPEN

    def clean(self) -> None:
        super().clean()
        if self.counterparty_id:
            k = self.counterparty.kind
            if k not in (CounterpartyKind.VENDOR, CounterpartyKind.BOTH):
                raise ValidationError(
                    {
                        "counterparty": _(
                            "AP invoices can only be linked to counterparties of type "
                            "Vendor or Customer and Vendor."
                        )
                    }
                )
        if (
            self.amount_total is not None
            and self.amount_paid is not None
            and self.amount_paid > self.amount_total
        ):
            raise ValidationError({"amount_paid": _("Amount paid cannot exceed total payable.")})

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        self._sync_status_from_amounts()
        super().save(*args, **kwargs)


class APPaymentAllocation(models.Model):
    """一笔支出流水核销到某张应付账单上的金额。"""

    ap_invoice = models.ForeignKey(
        APInvoice,
        verbose_name=_("AP Invoice"),
        on_delete=models.CASCADE,
        related_name="payment_allocations",
    )
    transaction = models.ForeignKey(
        "Transaction",
        verbose_name=_("Payment Transaction"),
        on_delete=models.CASCADE,
        related_name="ap_payment_allocations",
    )
    amount = models.DecimalField(_("Allocation Amount"), max_digits=14, decimal_places=2)
    note = models.CharField(_("Remark"), max_length=200, blank=True)
    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Created By"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ap_payment_allocations_created",
        editable=False,
    )

    class Meta:
        verbose_name = _("AP Payment Allocation")
        verbose_name_plural = _("AP Payment Allocations")
        ordering = ("-pk",)
        constraints = [
            models.UniqueConstraint(
                fields=("ap_invoice", "transaction"),
                name="finance_ap_payment_alloc_unique_invoice_tx",
            ),
            models.CheckConstraint(
                check=Q(amount__gt=0),
                name="finance_ap_payment_alloc_amount_positive",
            ),
        ]

    def __str__(self) -> str:
        return f"#{self.pk} {_('allocation')} {self.amount}"

    def clean(self) -> None:
        super().clean()
        if self.ap_invoice_id:
            if self.ap_invoice.approval_status != APApprovalStatus.APPROVED:
                raise ValidationError(
                    {"ap_invoice": _("Only approved AP invoices can receive payment allocations.")}
                )
        if self.transaction_id:
            if self.transaction.transaction_type != TransactionType.EXPENSE:
                raise ValidationError(
                    {"transaction": _("Only expense transactions can be allocated to AP invoices.")}
                )
            if (
                self.ap_invoice_id
                and self.transaction.counterparty_id != self.ap_invoice.counterparty_id
            ):
                raise ValidationError(
                    {"transaction": _("Transaction counterparty must match the AP invoice vendor.")}
                )
        if self.ap_invoice_id and self.amount is not None:
            qs = APPaymentAllocation.objects.filter(ap_invoice_id=self.ap_invoice_id)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            other = qs.aggregate(s=Sum("amount"))["s"] or Decimal("0")
            if other + self.amount > self.ap_invoice.amount_total:
                raise ValidationError({"amount": _("Total allocations cannot exceed invoice amount.")})
        if self.transaction_id and self.amount is not None:
            qs = APPaymentAllocation.objects.filter(transaction_id=self.transaction_id)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            other = qs.aggregate(s=Sum("amount"))["s"] or Decimal("0")
            if other + self.amount > self.transaction.amount:
                raise ValidationError(
                    {"amount": _("Total allocated amount exceeds the transaction amount.")}
                )


class BankStatementSource(models.TextChoices):
    BANK_CSV = "bank_csv", _("Bank CSV")
    ALIPAY = "alipay", _("Alipay Statement")
    WECHAT = "wechat", _("WeChat Pay Statement")
    OTHER = "other", _("Other")


class BankStatementBatchStatus(models.TextChoices):
    PENDING = "pending", _("Pending Import")
    SUCCESS = "success", _("Import Successful")
    PARTIAL = "partial", _("Partially Successful")
    FAILED = "failed", _("Import Failed")


class BankLineMatchStatus(models.TextChoices):
    UNMATCHED = "unmatched", _("Unmatched")
    MATCHED = "matched", _("Matched")
    IGNORED = "ignored", _("Ignored")


class BankStatementBatch(models.Model):
    """一次银行/渠道账单文件导入批次。"""

    account_name = models.CharField(
        _("Account Name"),
        max_length=200,
        help_text=_("Must match the account name on system transactions for reconciliation."),
    )
    source = models.CharField(
        _("Source"),
        max_length=20,
        choices=BankStatementSource.choices,
        default=BankStatementSource.BANK_CSV,
        db_index=True,
    )
    file = models.FileField(_("Statement File"), upload_to="bank_statements/%Y/%m/")
    status = models.CharField(
        _("Import Status"),
        max_length=20,
        choices=BankStatementBatchStatus.choices,
        default=BankStatementBatchStatus.PENDING,
        db_index=True,
    )
    total_rows = models.PositiveIntegerField(_("Total Rows"), default=0)
    imported_rows = models.PositiveIntegerField(_("Imported Rows"), default=0)
    error_rows = models.PositiveIntegerField(_("Failed Rows"), default=0)
    error_log = models.TextField(_("Error Log"), blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Imported By"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bank_statement_batches",
        editable=False,
    )
    created_at = models.DateTimeField(_("Imported At"), auto_now_add=True)

    class Meta:
        verbose_name = _("Bank Statement Import")
        verbose_name_plural = _("Bank Statement Imports")
        ordering = ("-created_at", "-pk")

    def __str__(self) -> str:
        return f"{self.account_name} · {self.created_at:%Y-%m-%d %H:%M}"


class BankStatementLine(models.Model):
    """导入的单条银行/渠道流水（待与系统 Transaction 对账匹配）。"""

    batch = models.ForeignKey(
        BankStatementBatch,
        verbose_name=_("Import Batch"),
        on_delete=models.CASCADE,
        related_name="lines",
    )
    line_date = models.DateField(_("Transaction Date"), db_index=True)
    transaction_type = models.CharField(
        _("Direction"),
        max_length=20,
        choices=TransactionType.choices,
        db_index=True,
    )
    amount = models.DecimalField(_("Amount"), max_digits=14, decimal_places=2)
    description = models.CharField(_("Description"), max_length=500, blank=True)
    reference = models.CharField(_("Reference Number"), max_length=100, blank=True, db_index=True)
    counterparty_hint = models.CharField(_("Counterparty Name"), max_length=200, blank=True)
    source_row_number = models.PositiveIntegerField(_("Source Row Number"), default=0)
    match_status = models.CharField(
        _("Match Status"),
        max_length=20,
        choices=BankLineMatchStatus.choices,
        default=BankLineMatchStatus.UNMATCHED,
        db_index=True,
    )
    matched_transaction = models.ForeignKey(
        Transaction,
        verbose_name=_("Matched Transaction"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bank_statement_lines",
    )

    class Meta:
        verbose_name = _("Bank Statement Line")
        verbose_name_plural = _("Bank Statement Lines")
        ordering = ("-line_date", "-pk")
        indexes = [
            models.Index(fields=["batch", "match_status"]),
        ]

    def __str__(self) -> str:
        return f"{self.line_date} {self.get_transaction_type_display()} {self.amount}"


class ReconciliationVarianceKind(models.TextChoices):
    BANK_FEE = "bank_fee", _("Bank Fee")
    ROUNDING = "rounding", _("Rounding Difference")
    UNRECORDED_BANK = "unrecorded_bank", _("Unrecorded in Books (bank has, system does not)")
    UNRECORDED_BOOK = "unrecorded_book", _("Unrecorded in Bank (system has, bank does not)")
    OTHER = "other", _("Other")


class ReconciliationVariance(models.Model):
    """对账差异登记；可生成调整流水以补齐账目。"""

    batch = models.ForeignKey(
        BankStatementBatch,
        verbose_name=_("Import Batch"),
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="variances",
    )
    bank_line = models.ForeignKey(
        BankStatementLine,
        verbose_name=_("Bank Statement Line"),
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="variances",
    )
    transaction = models.ForeignKey(
        Transaction,
        verbose_name=_("System Transaction"),
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="reconciliation_variances",
    )
    kind = models.CharField(
        _("Variance Type"),
        max_length=30,
        choices=ReconciliationVarianceKind.choices,
        db_index=True,
    )
    amount = models.DecimalField(
        _("Variance Amount"),
        max_digits=14,
        decimal_places=2,
        help_text=_("Positive amount representing the scale of adjustment or explanation."),
    )
    note = models.TextField(_("Note"), blank=True)
    adjustment_category = models.ForeignKey(
        Category,
        verbose_name=_("Adjustment Category"),
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reconciliation_variances",
        help_text=_("Category used when generating an adjustment transaction; required if creating one."),
    )
    adjustment_transaction = models.ForeignKey(
        Transaction,
        verbose_name=_("Adjustment Transaction"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="source_variance",
        editable=False,
    )
    is_resolved = models.BooleanField(_("Resolved"), default=False, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Recorded By"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reconciliation_variances_created",
        editable=False,
    )
    created_at = models.DateTimeField(_("Recorded At"), auto_now_add=True)

    class Meta:
        verbose_name = _("Reconciliation Variance")
        verbose_name_plural = _("Reconciliation Variances")
        ordering = ("-created_at", "-pk")

    def __str__(self) -> str:
        return f"{self.get_kind_display()} {self.amount}"

    def clean(self) -> None:
        super().clean()
        if not self.bank_line_id and not self.transaction_id and not self.batch_id:
            raise ValidationError(_("At least one of import batch, bank line, or system transaction is required."))
        if self.amount is not None and self.amount <= Decimal("0"):
            raise ValidationError({"amount": _("Variance amount must be greater than 0.")})
        if self.bank_line_id and not self.batch_id:
            self.batch_id = self.bank_line.batch_id
        elif self.batch_id and self.bank_line_id and self.bank_line.batch_id != self.batch_id:
            raise ValidationError({"bank_line": _("Bank line does not belong to the selected import batch.")})

    def save(self, *args, **kwargs) -> None:
        if self.bank_line_id and not self.batch_id:
            self.batch_id = self.bank_line.batch_id
        self.full_clean()
        super().save(*args, **kwargs)


class IncomeTransaction(Transaction):
    """后台菜单与权限拆分用代理模型，数据仍存于 Transaction 表。"""

    class Meta:
        proxy = True
        verbose_name = _("Income Transaction")
        verbose_name_plural = _("Income Transactions")


class ExpenseTransaction(Transaction):
    class Meta:
        proxy = True
        verbose_name = _("Expense Transaction")
        verbose_name_plural = _("Expense Transactions")
