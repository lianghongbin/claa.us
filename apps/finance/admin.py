from __future__ import annotations

from decimal import Decimal

from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.contrib.admin import DateFieldListFilter
from django.contrib.admin.views.main import IncorrectLookupParameters
from django.db.models import Sum
from django.utils.translation import gettext_lazy as _
from import_export.admin import ImportExportModelAdmin

from apps.admin_form_utils import CompactHelpTextMixin
from apps.audit.models import AuditLog
from apps.audit.services import (
    log_bulk_reconcile,
    log_model_change,
    log_model_deleted,
)
from apps.finance.permissions import can_approve_ap_invoice, is_finance_admin
from apps.finance.visibility import transactions_visible_for_user, visible_primary_keys
from apps.finance.bank_import import import_csv_into_batch
from apps.finance.bank_reconcile import (
    apply_match,
    auto_match_batch,
    auto_match_lines,
    candidate_transactions,
    clear_match,
    mark_ignored,
)
from apps.finance.bank_variance import (
    create_adjustment_transaction,
    resolve_without_adjustment,
)
from apps.finance.models import (
    APApprovalStatus,
    APInvoice,
    APInvoiceStatus,
    APPaymentAllocation,
    ARInvoice,
    ARInvoiceStatus,
    ARPaymentAllocation,
    BankLineMatchStatus,
    BankStatementBatch,
    BankStatementBatchStatus,
    BankStatementLine,
    Category,
    ReconciliationVariance,
    ReconciliationVarianceKind,
    Counterparty,
    CounterpartyKind,
    ExpenseTransaction,
    IncomeTransaction,
    Project,
    Tag,
    Transaction,
    TransactionAttachment,
    TransactionType,
)
from apps.finance.resources import (
    CategoryResource,
    ExpenseTransactionResource,
    IncomeTransactionResource,
)


def _tx_snapshot(tx: Transaction) -> dict:
    return tx.audit_snapshot()


class TransactionAttachmentInline(admin.TabularInline):
    model = TransactionAttachment
    extra = 0
    fields = ("file", "caption", "uploaded_at", "uploaded_by")
    readonly_fields = ("uploaded_at", "uploaded_by")


class ARPaymentAllocationByInvoiceInline(admin.TabularInline):
    """在应收账单上登记收款核销（标准做法），不在收入明细页维护。"""

    model = ARPaymentAllocation
    fk_name = "ar_invoice"
    extra = 0
    verbose_name = _("收款核销")
    verbose_name_plural = _("收款核销（关联收入流水）")
    fields = ("transaction", "amount", "note", "created_at", "created_by")
    readonly_fields = ("created_at", "created_by")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        obj = kwargs.get("obj")
        if db_field.name == "transaction" and obj is not None and obj.counterparty_id:
            base = Transaction.objects.filter(
                transaction_type=TransactionType.INCOME,
                counterparty_id=obj.counterparty_id,
            ).order_by("-date", "-pk")
            kwargs["queryset"] = transactions_visible_for_user(base, request.user)
        elif db_field.name == "transaction":
            kwargs["queryset"] = Transaction.objects.none()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class APPaymentAllocationByInvoiceInline(admin.TabularInline):
    """在应付账单上登记付款核销，不在支出明细页维护。"""

    model = APPaymentAllocation
    fk_name = "ap_invoice"
    extra = 0
    verbose_name = _("付款核销")
    verbose_name_plural = _("付款核销（关联支出流水）")
    fields = ("transaction", "amount", "note", "created_at", "created_by")
    readonly_fields = ("created_at", "created_by")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        obj = kwargs.get("obj")
        if db_field.name == "transaction" and obj is not None and obj.counterparty_id:
            if obj.approval_status != APApprovalStatus.APPROVED:
                kwargs["queryset"] = Transaction.objects.none()
            else:
                base = Transaction.objects.filter(
                    transaction_type=TransactionType.EXPENSE,
                    counterparty_id=obj.counterparty_id,
                ).order_by("-date", "-pk")
                kwargs["queryset"] = transactions_visible_for_user(base, request.user)
        elif db_field.name == "transaction":
            kwargs["queryset"] = Transaction.objects.none()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Category)
class CategoryAdmin(CompactHelpTextMixin, ImportExportModelAdmin):
    resource_classes = [CategoryResource]
    list_display = ("name", "kind", "sort_order", "is_active", "created_at")
    list_filter = ("kind", "is_active")
    search_fields = ("name",)
    ordering = ("kind", "sort_order", "name")

    def has_add_permission(self, request):
        return is_finance_admin(request)

    def has_change_permission(self, request, obj=None):
        return is_finance_admin(request)

    def has_delete_permission(self, request, obj=None):
        return is_finance_admin(request)


@admin.register(Counterparty)
class CounterpartyAdmin(CompactHelpTextMixin, admin.ModelAdmin):
    list_display = ("code", "name", "kind", "is_active", "created_at")
    list_filter = ("kind", "is_active")
    search_fields = ("code", "name", "tax_id", "contact_name", "contact_email")
    ordering = ("code",)
    filter_horizontal = ("visibility_groups",)
    fieldsets = (
        (None, {"fields": (("code", "name"), ("kind", "is_active"))}),
        (
            _("联系与开票"),
            {
                "fields": (
                    ("tax_id", "contact_name"),
                    ("contact_phone", "contact_email"),
                    "billing_address",
                )
            },
        ),
        (_("备注"), {"fields": ("remark",)}),
        (_("可见范围"), {"fields": ("visibility_groups",)}),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        ids = visible_primary_keys(
            Counterparty.objects.all(),
            request.user,
            view_all_perm="finance.view_all_counterparties",
        )
        return qs.filter(pk__in=ids)

    def has_add_permission(self, request):
        return is_finance_admin(request)

    def has_change_permission(self, request, obj=None):
        return is_finance_admin(request)

    def has_delete_permission(self, request, obj=None):
        return is_finance_admin(request)


@admin.register(Project)
class ProjectAdmin(CompactHelpTextMixin, admin.ModelAdmin):
    list_display = ("code", "name", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("code", "name")
    ordering = ("code",)
    filter_horizontal = ("visibility_groups",)
    fieldsets = (
        (None, {"fields": (("code", "name"), ("is_active", "remark"))}),
        (_("可见范围"), {"fields": ("visibility_groups",)}),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        ids = visible_primary_keys(
            Project.objects.all(),
            request.user,
            view_all_perm="finance.view_all_projects",
        )
        return qs.filter(pk__in=ids)

    def has_add_permission(self, request):
        return is_finance_admin(request)

    def has_change_permission(self, request, obj=None):
        return is_finance_admin(request)

    def has_delete_permission(self, request, obj=None):
        return is_finance_admin(request)


@admin.register(ARInvoice)
class ARInvoiceAdmin(CompactHelpTextMixin, admin.ModelAdmin):
    inlines = (ARPaymentAllocationByInvoiceInline,)
    list_display = (
        "number",
        "counterparty",
        "issue_date",
        "due_date",
        "amount_total",
        "amount_paid",
        "display_balance",
        "status",
        "created_by",
    )
    list_filter = (
        "status",
        ("issue_date", DateFieldListFilter),
        ("due_date", DateFieldListFilter),
        "counterparty",
    )
    search_fields = ("number", "title", "counterparty__name", "counterparty__code")
    autocomplete_fields = ("counterparty",)
    date_hierarchy = "issue_date"
    filter_horizontal = ("visibility_groups",)

    def get_readonly_fields(self, request, obj=None):
        ro = ("created_by", "created_at", "updated_at")
        if obj is not None:
            ro = ro + ("display_balance", "amount_paid")
            if not is_finance_admin(request):
                ro = ro + ("status",)
        return ro

    def get_fieldsets(self, request, obj=None):
        main = (None, {"fields": (("number", "counterparty"), ("title", "status"))})
        if obj is None:
            amount = (
                _("金额与日期"),
                {"fields": (("issue_date", "due_date"), "amount_total")},
            )
        else:
            amount = (
                _("金额与日期"),
                {
                    "fields": (
                        ("issue_date", "due_date"),
                        ("amount_total", "amount_paid"),
                        "display_balance",
                    )
                },
            )
        tail = (
            (_("备注"), {"fields": ("remark",)}),
            (_("可见范围"), {"fields": ("visibility_groups",)}),
        )
        if obj is None:
            return (main, amount) + tail
        audit = (
            _("审计"),
            {"fields": (("created_by", "created_at"), "updated_at")},
        )
        return (main, amount) + tail + (audit,)

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related("counterparty", "created_by")
        ids = visible_primary_keys(
            ARInvoice.objects.all(),
            request.user,
            view_all_perm="finance.view_all_arinvoices",
        )
        return qs.filter(pk__in=ids)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "counterparty":
            base = Counterparty.objects.filter(
                is_active=True,
                kind__in=(CounterpartyKind.CUSTOMER, CounterpartyKind.BOTH),
            ).order_by("code", "name")
            ids = visible_primary_keys(
                base,
                request.user,
                view_all_perm="finance.view_all_counterparties",
            )
            kwargs["queryset"] = base.filter(pk__in=ids)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    @admin.display(description=_("未收余额"))
    def display_balance(self, obj):
        if obj.pk:
            return obj.balance_unpaid
        return "—"

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        if formset.model is ARPaymentAllocation:
            instances = formset.save(commit=False)
            for obj in formset.deleted_objects:
                obj.delete()
            for obj in instances:
                if obj.created_by_id is None:
                    obj.created_by = request.user
                obj.save()
            formset.save_m2m()
        else:
            super().save_formset(request, form, formset, change)

    def has_delete_permission(self, request, obj=None):
        return is_finance_admin(request)


@admin.register(APInvoice)
class APInvoiceAdmin(CompactHelpTextMixin, admin.ModelAdmin):
    inlines = (APPaymentAllocationByInvoiceInline,)
    list_display = (
        "number",
        "counterparty",
        "issue_date",
        "due_date",
        "amount_total",
        "amount_paid",
        "display_balance",
        "approval_status",
        "status",
        "created_by",
    )
    list_filter = (
        "approval_status",
        "status",
        ("issue_date", DateFieldListFilter),
        ("due_date", DateFieldListFilter),
        "counterparty",
    )
    search_fields = ("number", "title", "counterparty__name", "counterparty__code")
    autocomplete_fields = ("counterparty",)
    date_hierarchy = "issue_date"
    filter_horizontal = ("visibility_groups",)

    def get_readonly_fields(self, request, obj=None):
        ro = ("created_by", "created_at", "updated_at")
        if obj is not None:
            ro = ro + ("display_balance", "amount_paid")
            if not can_approve_ap_invoice(request):
                ro = ro + ("approval_status",)
            if not is_finance_admin(request):
                ro = ro + ("status",)
        return ro

    def get_fieldsets(self, request, obj=None):
        main = (
            None,
            {
                "fields": (
                    ("number", "counterparty"),
                    ("title", "approval_status"),
                    "status",
                )
            },
        )
        if obj is None:
            amount = (
                _("金额与日期"),
                {"fields": (("issue_date", "due_date"), "amount_total")},
            )
        else:
            amount = (
                _("金额与日期"),
                {
                    "fields": (
                        ("issue_date", "due_date"),
                        ("amount_total", "amount_paid"),
                        "display_balance",
                    )
                },
            )
        tail = (
            (_("备注"), {"fields": ("remark",)}),
            (_("可见范围"), {"fields": ("visibility_groups",)}),
        )
        if obj is None:
            return (main, amount) + tail
        audit = (
            _("审计"),
            {"fields": (("created_by", "created_at"), "updated_at")},
        )
        return (main, amount) + tail + (audit,)

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related("counterparty", "created_by")
        ids = visible_primary_keys(
            APInvoice.objects.all(),
            request.user,
            view_all_perm="finance.view_all_apinvoices",
        )
        return qs.filter(pk__in=ids)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "counterparty":
            base = Counterparty.objects.filter(
                is_active=True,
                kind__in=(CounterpartyKind.VENDOR, CounterpartyKind.BOTH),
            ).order_by("code", "name")
            ids = visible_primary_keys(
                base,
                request.user,
                view_all_perm="finance.view_all_counterparties",
            )
            kwargs["queryset"] = base.filter(pk__in=ids)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    @admin.display(description=_("未付余额"))
    def display_balance(self, obj):
        if obj.pk:
            return obj.balance_unpaid
        return "—"

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        if formset.model is APPaymentAllocation:
            instances = formset.save(commit=False)
            for obj in formset.deleted_objects:
                obj.delete()
            for obj in instances:
                if obj.created_by_id is None:
                    obj.created_by = request.user
                obj.save()
            formset.save_m2m()
        else:
            super().save_formset(request, form, formset, change)

    def has_delete_permission(self, request, obj=None):
        return is_finance_admin(request)


@admin.register(Tag)
class TagAdmin(CompactHelpTextMixin, admin.ModelAdmin):
    list_display = ("name", "created_at")
    search_fields = ("name",)
    ordering = ("name",)

    def has_add_permission(self, request):
        return is_finance_admin(request)

    def has_change_permission(self, request, obj=None):
        return is_finance_admin(request)

    def has_delete_permission(self, request, obj=None):
        return is_finance_admin(request)


class TransactionCategoryListFilter(admin.SimpleListFilter):
    """列表筛选项：仅显示与当前收入/支出页一致的科目。"""

    title = _("科目")
    parameter_name = "category"

    def lookups(self, request, model_admin):
        kind = getattr(model_admin, "fixed_type", None)
        if not kind:
            return []
        categories = Category.objects.filter(is_active=True, kind=kind).order_by(
            "sort_order", "name"
        )
        return [(str(c.pk), c.name) for c in categories]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(category_id=self.value())
        return queryset


class BaseProxyTransactionAdmin(CompactHelpTextMixin, ImportExportModelAdmin):
    """收入/支出共用：列表按类型过滤；新增不写收支类型字段、不展示审计区。"""

    change_list_template = "admin/finance/transaction/change_list.html"
    fixed_type: str
    summary_scope: str

    inlines = (TransactionAttachmentInline,)
    filter_horizontal = ("tags",)

    list_display = (
        "date",
        "category",
        "project",
        "counterparty",
        "display_tags",
        "amount",
        "account_name",
        "is_reconciled",
        "created_by",
        "created_at",
    )
    list_filter = (
        ("date", DateFieldListFilter),
        TransactionCategoryListFilter,
        "project",
        "counterparty",
        "tags",
        "is_reconciled",
    )
    search_fields = (
        "account_name",
        "category__name",
        "note",
        "project__code",
        "project__name",
        "counterparty__code",
        "counterparty__name",
    )
    autocomplete_fields = ("category", "project", "counterparty")
    date_hierarchy = "date"
    actions = ("mark_reconciled",)

    # 标准收款/付款凭证：成对字段同一行，宽字段单独一行（布局见 admin_change_form.css）
    _main_fieldset_fields = (
        ("date", "amount"),
        ("category", "account_name"),
        ("counterparty", "project"),
        "note",
        "tags",
        "is_reconciled",
    )

    @admin.display(description=_("标签"))
    def display_tags(self, obj):
        names = list(obj.tags.values_list("name", flat=True)[:8])
        return ", ".join(names) if names else "—"

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return ()
        return ("created_by", "created_at", "updated_at")

    def get_fieldsets(self, request, obj=None):
        if self.fixed_type == TransactionType.INCOME:
            hint = _(
                "登记实际收款。核销应收账款请在「应收账单」中关联本笔收入，勿在本页维护。"
            )
        else:
            hint = _(
                "登记实际付款。核销应付账款请在「应付账单」中关联本笔支出，勿在本页维护。"
            )
        main = (None, {"fields": self._main_fieldset_fields, "description": hint})
        if obj is None:
            return (main,)
        return (main, (_("审计"), {"fields": ("created_by", "created_at", "updated_at")}))

    def get_inlines(self, request, obj=None):
        """新增页只录主表；附件在保存后的编辑页上传。"""
        if obj is None:
            return ()
        return self.inlines

    def get_queryset(self, request):
        qs = (
            super()
            .get_queryset(request)
            .filter(transaction_type=self.fixed_type)
            .select_related("category", "created_by", "project", "counterparty")
            .prefetch_related("tags")
        )
        return transactions_visible_for_user(qs, request.user)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "category":
            kwargs["queryset"] = Category.objects.filter(
                is_active=True, kind=self.fixed_type
            ).order_by("sort_order", "name")
        elif db_field.name == "project":
            base = Project.objects.filter(is_active=True).order_by("code", "name")
            ids = visible_primary_keys(
                base,
                request.user,
                view_all_perm="finance.view_all_projects",
            )
            kwargs["queryset"] = base.filter(pk__in=ids)
        elif db_field.name == "counterparty":
            base = Counterparty.objects.filter(is_active=True).order_by("code", "name")
            ids = visible_primary_keys(
                base,
                request.user,
                view_all_perm="finance.view_all_counterparties",
            )
            kwargs["queryset"] = base.filter(pk__in=ids)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_import_resource_kwargs(self, request, **kwargs):
        rk = super().get_import_resource_kwargs(request, **kwargs)
        rk["request"] = request
        rk["fixed_transaction_type"] = self.fixed_type
        return rk

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        summary = None
        try:
            cl = self.get_changelist_instance(request)
            qs = cl.get_queryset(request)
            if self.summary_scope == "income":
                income = qs.aggregate(s=Sum("amount"))["s"]
                summary = {
                    "scope": "income",
                    "total_income": income or Decimal("0"),
                }
            else:
                expense = qs.aggregate(s=Sum("amount"))["s"]
                summary = {
                    "scope": "expense",
                    "total_expense": expense or Decimal("0"),
                }
        except IncorrectLookupParameters:
            pass
        extra_context["finance_summary"] = summary
        return super().changelist_view(request, extra_context=extra_context)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.transaction_type = self.fixed_type
        old_snapshot = None
        if change and obj.pk:
            try:
                old = Transaction.objects.prefetch_related("tags").get(pk=obj.pk)
                old_snapshot = _tx_snapshot(old)
            except Transaction.DoesNotExist:
                pass
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
        request._tx_audit_old = old_snapshot
        request._tx_audit_change = change

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        obj = Transaction.objects.prefetch_related("tags").get(pk=form.instance.pk)
        new_snapshot = _tx_snapshot(obj)
        old_snapshot = getattr(request, "_tx_audit_old", None)
        is_change = getattr(request, "_tx_audit_change", False)
        if is_change:
            if old_snapshot != new_snapshot:
                log_model_change(
                    request,
                    action=AuditLog.Action.UPDATE,
                    instance=obj,
                    changes={"before": old_snapshot, "after": new_snapshot},
                )
        else:
            log_model_change(
                request,
                action=AuditLog.Action.CREATE,
                instance=obj,
                changes={"after": new_snapshot},
            )

    def save_formset(self, request, form, formset, change):
        if formset.model is TransactionAttachment:
            instances = formset.save(commit=False)
            for obj in formset.deleted_objects:
                obj.delete()
            for obj in instances:
                if obj.uploaded_by_id is None:
                    obj.uploaded_by = request.user
                obj.save()
            formset.save_m2m()
        else:
            super().save_formset(request, form, formset, change)

    def delete_model(self, request, obj):
        snap = _tx_snapshot(obj)
        oid = obj.pk
        repr_str = str(obj)
        super().delete_model(request, obj)
        log_model_deleted(
            request,
            model_class=self.model,
            pk=oid,
            object_repr=repr_str,
            changes={"before": snap},
        )

    @admin.action(description=_("将选中记录标记为已对账"))
    def mark_reconciled(self, request, queryset):
        ids = list(queryset.values_list("pk", flat=True))
        updated = queryset.update(is_reconciled=True)
        log_bulk_reconcile(request, transaction_ids=ids)
        self.message_user(
            request,
            _("已标记 %(count)s 条为已对账。") % {"count": updated},
            messages.SUCCESS,
        )

    def has_delete_permission(self, request, obj=None):
        return is_finance_admin(request)


@admin.register(ReconciliationVariance)
class ReconciliationVarianceAdmin(CompactHelpTextMixin, admin.ModelAdmin):
    list_display = (
        "kind",
        "amount",
        "batch",
        "bank_line",
        "transaction",
        "is_resolved",
        "adjustment_transaction",
        "created_by",
        "created_at",
    )
    list_filter = ("kind", "is_resolved", "batch")
    search_fields = ("note", "batch__account_name")
    raw_id_fields = ("bank_line", "transaction", "adjustment_transaction")
    autocomplete_fields = ("adjustment_category", "batch")
    readonly_fields = ("adjustment_transaction", "created_by", "created_at")
    actions = ("action_create_adjustment", "action_mark_resolved")

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "batch",
                    "bank_line",
                    "transaction",
                    "kind",
                    "amount",
                    "note",
                )
            },
        ),
        (
            _("调整流水"),
            {"fields": ("adjustment_category", "adjustment_transaction", "is_resolved")},
        ),
        (_("审计"), {"fields": ("created_by", "created_at")}),
    )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    @admin.action(description=_("生成调整流水并完成对账关联"))
    def action_create_adjustment(self, request, queryset):
        created = 0
        for var in queryset.filter(adjustment_transaction__isnull=True):
            try:
                create_adjustment_transaction(var, request.user)
                created += 1
            except ValidationError as exc:
                self.message_user(
                    request,
                    _("差异 #%(id)s: %(err)s") % {"id": var.pk, "err": exc},
                    messages.ERROR,
                )
        if created:
            self.message_user(
                request,
                _("已为 %(n)s 条差异生成调整流水。") % {"n": created},
                messages.SUCCESS,
            )

    @admin.action(description=_("标记为已处理（不生成流水）"))
    def action_mark_resolved(self, request, queryset):
        for var in queryset.filter(is_resolved=False):
            resolve_without_adjustment(var)
        self.message_user(request, _("已标记为已处理。"), messages.SUCCESS)

    def has_add_permission(self, request):
        return request.user.has_perm("finance.add_reconciliationvariance")

    def has_change_permission(self, request, obj=None):
        return request.user.has_perm("finance.change_reconciliationvariance")

    def has_delete_permission(self, request, obj=None):
        return is_finance_admin(request)


class BankStatementLineInline(admin.TabularInline):
    model = BankStatementLine
    extra = 0
    can_delete = False
    show_change_link = True
    fields = (
        "line_date",
        "transaction_type",
        "amount",
        "description",
        "reference",
        "counterparty_hint",
        "match_status",
        "matched_transaction",
        "source_row_number",
    )
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(BankStatementLine)
class BankStatementLineAdmin(CompactHelpTextMixin, admin.ModelAdmin):
    list_display = (
        "line_date",
        "batch",
        "transaction_type",
        "amount",
        "description",
        "match_status",
        "matched_transaction",
    )
    list_filter = (
        "match_status",
        "transaction_type",
        "batch",
        ("line_date", DateFieldListFilter),
    )
    search_fields = ("description", "reference", "counterparty_hint", "batch__account_name")
    raw_id_fields = ("matched_transaction",)
    readonly_fields = (
        "batch",
        "line_date",
        "transaction_type",
        "amount",
        "description",
        "reference",
        "counterparty_hint",
        "source_row_number",
        "match_status",
    )

    actions = (
        "action_auto_match",
        "action_mark_ignored",
        "action_clear_match",
        "action_register_unrecorded_bank",
    )

    def get_fields(self, request, obj=None):
        return (
            "batch",
            "line_date",
            "transaction_type",
            "amount",
            "description",
            "reference",
            "counterparty_hint",
            "match_status",
            "matched_transaction",
            "source_row_number",
        )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        obj = kwargs.get("obj")
        if db_field.name == "matched_transaction" and obj is not None:
            ids = [t.pk for t in candidate_transactions(obj, request.user)]
            if obj.matched_transaction_id:
                ids.append(obj.matched_transaction_id)
            kwargs["queryset"] = (
                Transaction.objects.filter(pk__in=ids)
                if ids
                else Transaction.objects.none()
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        prev_tx_id = None
        if change and obj.pk:
            prev_tx_id = (
                BankStatementLine.objects.filter(pk=obj.pk)
                .values_list("matched_transaction_id", flat=True)
                .first()
            )
        super().save_model(request, obj, form, change)
        if obj.matched_transaction_id:
            try:
                apply_match(obj, obj.matched_transaction)
            except ValueError as exc:
                messages.error(request, str(exc))
                if prev_tx_id:
                    obj.matched_transaction_id = prev_tx_id
                else:
                    obj.matched_transaction = None
                    obj.match_status = BankLineMatchStatus.UNMATCHED
                obj.save(update_fields=["matched_transaction", "match_status"])
        elif prev_tx_id and not obj.matched_transaction_id:
            clear_match(obj)

    @admin.action(description=_("自动匹配选中明细"))
    def action_auto_match(self, request, queryset):
        result = auto_match_lines(queryset, request.user)
        self.message_user(
            request,
            _("自动匹配成功 %(m)s 条；无候选 %(n)s 条；多候选 %(a)s 条。")
            % {"m": result.matched, "n": result.no_candidate, "a": result.ambiguous},
            messages.SUCCESS if result.matched else messages.INFO,
        )

    @admin.action(description=_("标记为忽略（不参与对账）"))
    def action_mark_ignored(self, request, queryset):
        for line in queryset:
            mark_ignored(line)
        self.message_user(request, _("已标记为忽略。"), messages.SUCCESS)

    @admin.action(description=_("登记为「有账未记账」差异"))
    def action_register_unrecorded_bank(self, request, queryset):
        created = 0
        for line in queryset.filter(match_status=BankLineMatchStatus.UNMATCHED):
            ReconciliationVariance.objects.create(
                batch=line.batch,
                bank_line=line,
                kind=ReconciliationVarianceKind.UNRECORDED_BANK,
                amount=line.amount,
                note=line.description or "",
                created_by=request.user,
            )
            created += 1
        self.message_user(
            request,
            _("已登记 %(n)s 条差异，请在「对账差异」中指定科目并生成调整流水。") % {"n": created},
            messages.SUCCESS if created else messages.INFO,
        )

    @admin.action(description=_("清除匹配"))
    def action_clear_match(self, request, queryset):
        for line in queryset:
            if line.match_status == BankLineMatchStatus.MATCHED:
                clear_match(line)
            elif line.match_status == BankLineMatchStatus.IGNORED:
                line.match_status = BankLineMatchStatus.UNMATCHED
                line.save(update_fields=["match_status"])
        self.message_user(request, _("已清除匹配。"), messages.SUCCESS)

    def has_change_permission(self, request, obj=None):
        return request.user.has_perm("finance.change_bankstatementline")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return is_finance_admin(request)


@admin.register(BankStatementBatch)
class BankStatementBatchAdmin(CompactHelpTextMixin, admin.ModelAdmin):
    list_display = (
        "account_name",
        "source",
        "status",
        "display_match_progress",
        "imported_rows",
        "error_rows",
        "created_by",
        "created_at",
    )
    list_filter = ("status", "source", ("created_at", DateFieldListFilter))
    search_fields = ("account_name",)
    readonly_fields = (
        "status",
        "total_rows",
        "imported_rows",
        "error_rows",
        "error_log",
        "created_by",
        "created_at",
    )
    inlines = (BankStatementLineInline,)
    actions = ("action_auto_match_batch",)

    @admin.display(description=_("对账进度"))
    def display_match_progress(self, obj):
        if not obj.pk:
            return "—"
        total = obj.lines.count()
        if not total:
            return "—"
        matched = obj.lines.filter(match_status=BankLineMatchStatus.MATCHED).count()
        return f"{matched}/{total}"

    @admin.action(description=_("对本批次未匹配明细执行自动匹配"))
    def action_auto_match_batch(self, request, queryset):
        total_matched = 0
        for batch in queryset:
            result = auto_match_batch(batch, request.user)
            total_matched += result.matched
        self.message_user(
            request,
            _("共自动匹配 %(n)s 条。") % {"n": total_matched},
            messages.SUCCESS if total_matched else messages.INFO,
        )

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            return (
                (
                    None,
                    {
                        "fields": (
                            "account_name",
                            "source",
                            "file",
                        )
                    },
                ),
            )
        return (
            (None, {"fields": ("account_name", "source", "file")}),
            (
                _("导入结果"),
                {
                    "fields": (
                        "status",
                        "total_rows",
                        "imported_rows",
                        "error_rows",
                        "error_log",
                        "created_by",
                        "created_at",
                    )
                },
            ),
        )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
            obj.status = BankStatementBatchStatus.PENDING
        super().save_model(request, obj, form, change)
        if not change and obj.file:
            result = import_csv_into_batch(obj)
            obj.imported_rows = result.imported
            obj.error_rows = len(result.errors)
            obj.total_rows = result.imported + obj.error_rows
            obj.error_log = "\n".join(result.errors[:500])
            if result.imported and not result.errors:
                obj.status = BankStatementBatchStatus.SUCCESS
            elif result.imported and result.errors:
                obj.status = BankStatementBatchStatus.PARTIAL
            else:
                obj.status = BankStatementBatchStatus.FAILED
            obj.save(
                update_fields=[
                    "status",
                    "total_rows",
                    "imported_rows",
                    "error_rows",
                    "error_log",
                ]
            )
            if result.imported:
                self.message_user(
                    request,
                    _("成功导入 %(n)s 条账单明细。") % {"n": result.imported},
                    messages.SUCCESS,
                )
            if result.errors:
                self.message_user(
                    request,
                    _("有 %(n)s 行解析失败，详见错误日志。") % {"n": len(result.errors)},
                    messages.WARNING,
                )
            if not result.imported and not result.errors:
                self.message_user(request, _("未解析到有效数据行。"), messages.ERROR)

    def get_readonly_fields(self, request, obj=None):
        ro = list(self.readonly_fields)
        if obj is not None:
            ro.extend(["account_name", "source", "file"])
        return ro

    def has_add_permission(self, request):
        return is_finance_admin(request)

    def has_change_permission(self, request, obj=None):
        return (
            request.user.has_perm("finance.change_bankstatementline")
            or is_finance_admin(request)
        )

    def has_delete_permission(self, request, obj=None):
        return is_finance_admin(request)

    def has_view_permission(self, request, obj=None):
        return request.user.has_perm("finance.view_bankstatementbatch")


@admin.register(IncomeTransaction)
class IncomeTransactionAdmin(BaseProxyTransactionAdmin):
    inlines = (TransactionAttachmentInline,)
    fixed_type = TransactionType.INCOME
    summary_scope = "income"
    resource_classes = [IncomeTransactionResource]


@admin.register(ExpenseTransaction)
class ExpenseTransactionAdmin(BaseProxyTransactionAdmin):
    inlines = (TransactionAttachmentInline,)
    fixed_type = TransactionType.EXPENSE
    summary_scope = "expense"
    resource_classes = [ExpenseTransactionResource]
