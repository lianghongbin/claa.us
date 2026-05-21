from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q, Sum


class CategoryKind(models.TextChoices):
    INCOME = "income", "收入"
    EXPENSE = "expense", "支出"


class TransactionType(models.TextChoices):
    INCOME = "income", "收入"
    EXPENSE = "expense", "支出"


class Category(models.Model):
    name = models.CharField("名称", max_length=100)
    kind = models.CharField(
        "类型",
        max_length=20,
        choices=CategoryKind.choices,
        db_index=True,
    )
    sort_order = models.PositiveSmallIntegerField("排序", default=0)
    is_active = models.BooleanField("启用", default=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "科目分类"
        verbose_name_plural = "科目分类"
        ordering = ("kind", "sort_order", "name")
        permissions = [
            ("manage_database", "备份与还原数据库"),
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
    CUSTOMER = "customer", "客户"
    VENDOR = "vendor", "供应商"
    BOTH = "both", "客户与供应商"


class Counterparty(models.Model):
    """客户/供应商等往来单位（应收应付将挂接于此）。"""

    code = models.SlugField("单位编码", max_length=50, unique=True, db_index=True)
    name = models.CharField("名称", max_length=200)
    kind = models.CharField(
        "类型",
        max_length=20,
        choices=CounterpartyKind.choices,
        db_index=True,
    )
    tax_id = models.CharField("税号/统一社会信用代码", max_length=40, blank=True)
    contact_name = models.CharField("联系人", max_length=100, blank=True)
    contact_phone = models.CharField("电话", max_length=40, blank=True)
    contact_email = models.EmailField("邮箱", blank=True)
    billing_address = models.TextField("地址", blank=True)
    remark = models.CharField("备注", max_length=500, blank=True)
    is_active = models.BooleanField("启用", default=True, db_index=True)
    visibility_groups = models.ManyToManyField(
        Group,
        blank=True,
        related_name="finance_counterparties_visible",
        verbose_name="可见分组",
        help_text="不选则所有可查看往来单位的用户均可见；选择后仅所选分组内的用户可见。",
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "往来单位"
        verbose_name_plural = "往来单位"
        ordering = ("code",)
        permissions = [
            ("view_all_counterparties", "可查看全部往来单位（忽略可见分组）"),
        ]

    def __str__(self) -> str:
        return f"{self.code} · {self.name}"


class Project(models.Model):
    """项目/成本对象核算（流水可选关联）。"""

    code = models.SlugField("项目编码", max_length=50, unique=True, db_index=True)
    name = models.CharField("项目名称", max_length=200)
    is_active = models.BooleanField("启用", default=True, db_index=True)
    remark = models.CharField("备注", max_length=500, blank=True)
    visibility_groups = models.ManyToManyField(
        Group,
        blank=True,
        related_name="finance_projects_visible",
        verbose_name="可见分组",
        help_text="不选则所有可查看项目的用户均可见；选择后仅所选分组内的用户可见。",
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "项目"
        verbose_name_plural = "项目"
        ordering = ("code",)
        permissions = [
            ("view_all_projects", "可查看全部项目（忽略可见分组）"),
        ]

    def __str__(self) -> str:
        return f"{self.code} · {self.name}"


class Tag(models.Model):
    name = models.CharField("标签", max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        verbose_name = "流水标签"
        verbose_name_plural = "流水标签"
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class Transaction(models.Model):
    date = models.DateField("日期", db_index=True)
    transaction_type = models.CharField(
        "收支类型",
        max_length=20,
        choices=TransactionType.choices,
        db_index=True,
    )
    category = models.ForeignKey(
        Category,
        verbose_name="科目",
        on_delete=models.PROTECT,
        related_name="transactions",
    )
    amount = models.DecimalField(
        "金额",
        max_digits=12,
        decimal_places=2,
        help_text="正数，单位与记账本位币一致",
    )
    account_name = models.CharField("账户名称", max_length=200)
    note = models.TextField("摘要/备注", blank=True)
    project = models.ForeignKey(
        Project,
        verbose_name="项目",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
    )
    counterparty = models.ForeignKey(
        Counterparty,
        verbose_name="往来单位",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="transactions",
    )
    tags = models.ManyToManyField(
        Tag,
        verbose_name="标签",
        blank=True,
        related_name="transactions",
    )
    is_reconciled = models.BooleanField("已对账", default=False, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="创建人",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="finance_transactions_created",
        editable=False,
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "收支明细"
        verbose_name_plural = "收支明细"
        ordering = ("-date", "-pk")
        permissions = [
            (
                "view_all_finance_transactions",
                "可查看全部财务流水（忽略项目/往来可见范围）",
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
                    {"category": "所选科目的类型必须与收支类型一致。"}
                )
        if self.amount is not None and self.amount <= Decimal("0"):
            raise ValidationError({"amount": "金额必须大于 0。"})


class TransactionAttachment(models.Model):
    """单笔流水的凭证、合同、回单等附件。"""

    transaction = models.ForeignKey(
        Transaction,
        verbose_name="流水",
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    file = models.FileField("文件", upload_to="finance_attachments/%Y/%m/")
    caption = models.CharField("说明", max_length=200, blank=True)
    uploaded_at = models.DateTimeField("上传时间", auto_now_add=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="上传人",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
    )

    class Meta:
        verbose_name = "流水凭证附件"
        verbose_name_plural = "流水凭证附件"
        ordering = ("pk",)

    def __str__(self) -> str:
        return self.caption or self.file.name


class ARInvoiceStatus(models.TextChoices):
    DRAFT = "draft", "草稿"
    OPEN = "open", "待收款"
    PARTIAL = "partial", "部分收款"
    PAID = "paid", "已结清"
    VOID = "void", "已作废"


class ARInvoice(models.Model):
    """应收账单：记录对客户应收金额、账期与结清状态（收款核销在后续任务中对接）。"""

    number = models.CharField("应收单号", max_length=40, unique=True, db_index=True)
    counterparty = models.ForeignKey(
        Counterparty,
        verbose_name="客户",
        on_delete=models.PROTECT,
        related_name="ar_invoices",
    )
    title = models.CharField("摘要", max_length=200, blank=True)
    issue_date = models.DateField("立账/开票日期", db_index=True)
    due_date = models.DateField(
        "约定收款日",
        null=True,
        blank=True,
        db_index=True,
    )
    amount_total = models.DecimalField("应收金额", max_digits=14, decimal_places=2)
    amount_paid = models.DecimalField(
        "已收金额",
        max_digits=14,
        decimal_places=2,
        default=Decimal("0"),
        help_text="由收款核销明细自动汇总；不在此手工改数。",
    )
    status = models.CharField(
        "状态",
        max_length=20,
        choices=ARInvoiceStatus.choices,
        default=ARInvoiceStatus.DRAFT,
        db_index=True,
    )
    remark = models.TextField("备注", blank=True)
    visibility_groups = models.ManyToManyField(
        Group,
        blank=True,
        related_name="finance_ar_invoices_visible",
        verbose_name="可见分组",
        help_text="不选则所有可查看应收的用户均可见；选择后仅所选分组内的用户可见。",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="创建人",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ar_invoices_created",
        editable=False,
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "应收账单"
        verbose_name_plural = "应收账单"
        ordering = ("-issue_date", "-pk")
        permissions = [
            ("view_all_arinvoices", "可查看全部应收账单（忽略可见分组）"),
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
                    {"counterparty": "应收账单只能关联「客户」或「客户与供应商」类型的往来单位。"}
                )
        if (
            self.amount_total is not None
            and self.amount_paid is not None
            and self.amount_paid > self.amount_total
        ):
            raise ValidationError({"amount_paid": "已收金额不能大于应收金额。"})

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        self._sync_status_from_amounts()
        super().save(*args, **kwargs)


class ARPaymentAllocation(models.Model):
    """一笔收入流水核销到某张应收账单上的金额。"""

    ar_invoice = models.ForeignKey(
        ARInvoice,
        verbose_name="应收账单",
        on_delete=models.CASCADE,
        related_name="payment_allocations",
    )
    transaction = models.ForeignKey(
        "Transaction",
        verbose_name="收款流水",
        on_delete=models.CASCADE,
        related_name="ar_payment_allocations",
    )
    amount = models.DecimalField("核销金额", max_digits=14, decimal_places=2)
    note = models.CharField("备注", max_length=200, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="创建人",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ar_payment_allocations_created",
        editable=False,
    )

    class Meta:
        verbose_name = "应收核销记录"
        verbose_name_plural = "应收核销记录"
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
        return f"#{self.pk} 核销 {self.amount}"

    def clean(self) -> None:
        super().clean()
        if self.transaction_id:
            if self.transaction.transaction_type != TransactionType.INCOME:
                raise ValidationError(
                    {"transaction": "仅收入流水可参与应收核销。"}
                )
            if (
                self.ar_invoice_id
                and self.transaction.counterparty_id != self.ar_invoice.counterparty_id
            ):
                raise ValidationError(
                    {"transaction": "流水的往来单位必须与应收账单的客户一致。"}
                )
        if self.ar_invoice_id and self.amount is not None:
            qs = ARPaymentAllocation.objects.filter(ar_invoice_id=self.ar_invoice_id)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            other = qs.aggregate(s=Sum("amount"))["s"] or Decimal("0")
            if other + self.amount > self.ar_invoice.amount_total:
                raise ValidationError({"amount": "核销金额之和不能超过应收总额。"})
        if self.transaction_id and self.amount is not None:
            qs = ARPaymentAllocation.objects.filter(transaction_id=self.transaction_id)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            other = qs.aggregate(s=Sum("amount"))["s"] or Decimal("0")
            if other + self.amount > self.transaction.amount:
                raise ValidationError({"amount": "该流水已核销金额超过流水本身金额。"})


class APApprovalStatus(models.TextChoices):
    DRAFT = "draft", "草稿"
    PENDING = "pending", "待审批"
    APPROVED = "approved", "已批准"
    REJECTED = "rejected", "已驳回"


class APInvoiceStatus(models.TextChoices):
    DRAFT = "draft", "草稿"
    OPEN = "open", "待付款"
    PARTIAL = "partial", "部分付款"
    PAID = "paid", "已结清"
    VOID = "void", "已作废"


class APInvoice(models.Model):
    """应付账单：记录对供应商应付金额、账期、审批与付款状态。"""

    number = models.CharField("应付单号", max_length=40, unique=True, db_index=True)
    counterparty = models.ForeignKey(
        Counterparty,
        verbose_name="供应商",
        on_delete=models.PROTECT,
        related_name="ap_invoices",
    )
    title = models.CharField("摘要", max_length=200, blank=True)
    issue_date = models.DateField("立账日期", db_index=True)
    due_date = models.DateField(
        "约定付款日",
        null=True,
        blank=True,
        db_index=True,
    )
    amount_total = models.DecimalField("应付金额", max_digits=14, decimal_places=2)
    amount_paid = models.DecimalField(
        "已付金额",
        max_digits=14,
        decimal_places=2,
        default=Decimal("0"),
        help_text="由付款核销明细自动汇总；不在此手工改数。",
    )
    approval_status = models.CharField(
        "审批状态",
        max_length=20,
        choices=APApprovalStatus.choices,
        default=APApprovalStatus.DRAFT,
        db_index=True,
    )
    status = models.CharField(
        "付款状态",
        max_length=20,
        choices=APInvoiceStatus.choices,
        default=APInvoiceStatus.DRAFT,
        db_index=True,
    )
    remark = models.TextField("备注", blank=True)
    visibility_groups = models.ManyToManyField(
        Group,
        blank=True,
        related_name="finance_ap_invoices_visible",
        verbose_name="可见分组",
        help_text="不选则所有可查看应付的用户均可见；选择后仅所选分组内的用户可见。",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="创建人",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ap_invoices_created",
        editable=False,
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "应付账单"
        verbose_name_plural = "应付账单"
        ordering = ("-issue_date", "-pk")
        permissions = [
            ("view_all_apinvoices", "可查看全部应付账单（忽略可见分组）"),
            ("approve_apinvoice", "可审批应付账单"),
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
                    {"counterparty": "应付账单只能关联「供应商」或「客户与供应商」类型的往来单位。"}
                )
        if (
            self.amount_total is not None
            and self.amount_paid is not None
            and self.amount_paid > self.amount_total
        ):
            raise ValidationError({"amount_paid": "已付金额不能大于应付金额。"})

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        self._sync_status_from_amounts()
        super().save(*args, **kwargs)


class APPaymentAllocation(models.Model):
    """一笔支出流水核销到某张应付账单上的金额。"""

    ap_invoice = models.ForeignKey(
        APInvoice,
        verbose_name="应付账单",
        on_delete=models.CASCADE,
        related_name="payment_allocations",
    )
    transaction = models.ForeignKey(
        "Transaction",
        verbose_name="付款流水",
        on_delete=models.CASCADE,
        related_name="ap_payment_allocations",
    )
    amount = models.DecimalField("核销金额", max_digits=14, decimal_places=2)
    note = models.CharField("备注", max_length=200, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="创建人",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ap_payment_allocations_created",
        editable=False,
    )

    class Meta:
        verbose_name = "应付核销记录"
        verbose_name_plural = "应付核销记录"
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
        return f"#{self.pk} 核销 {self.amount}"

    def clean(self) -> None:
        super().clean()
        if self.ap_invoice_id:
            if self.ap_invoice.approval_status != APApprovalStatus.APPROVED:
                raise ValidationError(
                    {"ap_invoice": "仅「已批准」的应付账单可登记付款核销。"}
                )
        if self.transaction_id:
            if self.transaction.transaction_type != TransactionType.EXPENSE:
                raise ValidationError(
                    {"transaction": "仅支出流水可参与应付核销。"}
                )
            if (
                self.ap_invoice_id
                and self.transaction.counterparty_id != self.ap_invoice.counterparty_id
            ):
                raise ValidationError(
                    {"transaction": "流水的往来单位必须与应付账单的供应商一致。"}
                )
        if self.ap_invoice_id and self.amount is not None:
            qs = APPaymentAllocation.objects.filter(ap_invoice_id=self.ap_invoice_id)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            other = qs.aggregate(s=Sum("amount"))["s"] or Decimal("0")
            if other + self.amount > self.ap_invoice.amount_total:
                raise ValidationError({"amount": "核销金额之和不能超过应付总额。"})
        if self.transaction_id and self.amount is not None:
            qs = APPaymentAllocation.objects.filter(transaction_id=self.transaction_id)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            other = qs.aggregate(s=Sum("amount"))["s"] or Decimal("0")
            if other + self.amount > self.transaction.amount:
                raise ValidationError({"amount": "该流水已核销金额超过流水本身金额。"})


class BankStatementSource(models.TextChoices):
    BANK_CSV = "bank_csv", "银行 CSV"
    ALIPAY = "alipay", "支付宝账单"
    WECHAT = "wechat", "微信支付账单"
    OTHER = "other", "其他"


class BankStatementBatchStatus(models.TextChoices):
    PENDING = "pending", "待导入"
    SUCCESS = "success", "导入成功"
    PARTIAL = "partial", "部分成功"
    FAILED = "failed", "导入失败"


class BankLineMatchStatus(models.TextChoices):
    UNMATCHED = "unmatched", "未匹配"
    MATCHED = "matched", "已匹配"
    IGNORED = "ignored", "已忽略"


class BankStatementBatch(models.Model):
    """一次银行/渠道账单文件导入批次。"""

    account_name = models.CharField(
        "账户名称",
        max_length=200,
        help_text="与系统内收支流水的「账户名称」一致，便于后续对账匹配。",
    )
    source = models.CharField(
        "来源",
        max_length=20,
        choices=BankStatementSource.choices,
        default=BankStatementSource.BANK_CSV,
        db_index=True,
    )
    file = models.FileField("账单文件", upload_to="bank_statements/%Y/%m/")
    status = models.CharField(
        "导入状态",
        max_length=20,
        choices=BankStatementBatchStatus.choices,
        default=BankStatementBatchStatus.PENDING,
        db_index=True,
    )
    total_rows = models.PositiveIntegerField("文件行数", default=0)
    imported_rows = models.PositiveIntegerField("成功导入", default=0)
    error_rows = models.PositiveIntegerField("解析失败", default=0)
    error_log = models.TextField("错误日志", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="导入人",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bank_statement_batches",
        editable=False,
    )
    created_at = models.DateTimeField("导入时间", auto_now_add=True)

    class Meta:
        verbose_name = "银行账单导入"
        verbose_name_plural = "银行账单导入"
        ordering = ("-created_at", "-pk")

    def __str__(self) -> str:
        return f"{self.account_name} · {self.created_at:%Y-%m-%d %H:%M}"


class BankStatementLine(models.Model):
    """导入的单条银行/渠道流水（待与系统 Transaction 对账匹配）。"""

    batch = models.ForeignKey(
        BankStatementBatch,
        verbose_name="导入批次",
        on_delete=models.CASCADE,
        related_name="lines",
    )
    line_date = models.DateField("交易日期", db_index=True)
    transaction_type = models.CharField(
        "方向",
        max_length=20,
        choices=TransactionType.choices,
        db_index=True,
    )
    amount = models.DecimalField("金额", max_digits=14, decimal_places=2)
    description = models.CharField("摘要", max_length=500, blank=True)
    reference = models.CharField("流水号/参考号", max_length=100, blank=True, db_index=True)
    counterparty_hint = models.CharField("对方户名", max_length=200, blank=True)
    source_row_number = models.PositiveIntegerField("源文件行号", default=0)
    match_status = models.CharField(
        "匹配状态",
        max_length=20,
        choices=BankLineMatchStatus.choices,
        default=BankLineMatchStatus.UNMATCHED,
        db_index=True,
    )
    matched_transaction = models.ForeignKey(
        Transaction,
        verbose_name="已匹配系统流水",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bank_statement_lines",
    )

    class Meta:
        verbose_name = "银行账单明细"
        verbose_name_plural = "银行账单明细"
        ordering = ("-line_date", "-pk")
        indexes = [
            models.Index(fields=["batch", "match_status"]),
        ]

    def __str__(self) -> str:
        return f"{self.line_date} {self.get_transaction_type_display()} {self.amount}"


class ReconciliationVarianceKind(models.TextChoices):
    BANK_FEE = "bank_fee", "银行手续费"
    ROUNDING = "rounding", "尾差"
    UNRECORDED_BANK = "unrecorded_bank", "有账未记账（银行有、系统无）"
    UNRECORDED_BOOK = "unrecorded_book", "已记账未到账（系统有、银行无）"
    OTHER = "other", "其他"


class ReconciliationVariance(models.Model):
    """对账差异登记；可生成调整流水以补齐账目。"""

    batch = models.ForeignKey(
        BankStatementBatch,
        verbose_name="导入批次",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="variances",
    )
    bank_line = models.ForeignKey(
        BankStatementLine,
        verbose_name="银行明细",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="variances",
    )
    transaction = models.ForeignKey(
        Transaction,
        verbose_name="系统流水",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="reconciliation_variances",
    )
    kind = models.CharField(
        "差异类型",
        max_length=30,
        choices=ReconciliationVarianceKind.choices,
        db_index=True,
    )
    amount = models.DecimalField(
        "差异金额",
        max_digits=14,
        decimal_places=2,
        help_text="正数，表示需调整或说明的金额规模。",
    )
    note = models.TextField("说明", blank=True)
    adjustment_category = models.ForeignKey(
        Category,
        verbose_name="调整科目",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reconciliation_variances",
        help_text="生成调整流水时使用的科目；保存后若勾选「生成调整流水」则必填。",
    )
    adjustment_transaction = models.ForeignKey(
        Transaction,
        verbose_name="调整流水",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="source_variance",
        editable=False,
    )
    is_resolved = models.BooleanField("已处理", default=False, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="登记人",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reconciliation_variances_created",
        editable=False,
    )
    created_at = models.DateTimeField("登记时间", auto_now_add=True)

    class Meta:
        verbose_name = "对账差异"
        verbose_name_plural = "对账差异"
        ordering = ("-created_at", "-pk")

    def __str__(self) -> str:
        return f"{self.get_kind_display()} {self.amount}"

    def clean(self) -> None:
        super().clean()
        if not self.bank_line_id and not self.transaction_id and not self.batch_id:
            raise ValidationError("请至少关联导入批次、银行明细或系统流水中的一项。")
        if self.amount is not None and self.amount <= Decimal("0"):
            raise ValidationError({"amount": "差异金额必须大于 0。"})
        if self.bank_line_id and not self.batch_id:
            self.batch_id = self.bank_line.batch_id
        elif self.batch_id and self.bank_line_id and self.bank_line.batch_id != self.batch_id:
            raise ValidationError({"bank_line": "银行明细不属于所选导入批次。"})

    def save(self, *args, **kwargs) -> None:
        if self.bank_line_id and not self.batch_id:
            self.batch_id = self.bank_line.batch_id
        self.full_clean()
        super().save(*args, **kwargs)


class IncomeTransaction(Transaction):
    """后台菜单与权限拆分用代理模型，数据仍存于 Transaction 表。"""

    class Meta:
        proxy = True
        verbose_name = "收入明细"
        verbose_name_plural = "收入明细"


class ExpenseTransaction(Transaction):
    class Meta:
        proxy = True
        verbose_name = "支出明细"
        verbose_name_plural = "支出明细"
