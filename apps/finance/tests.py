from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import TestCase

from apps.finance.bank_import import import_csv_into_batch, parse_csv_rows
from apps.finance.bank_reconcile import apply_match, auto_match_lines, clear_match, find_auto_match
from apps.finance.bank_variance import create_adjustment_transaction
from apps.finance.dashboard import build_finance_dashboard
from apps.finance.reports import (
    build_balance_sheet_report,
    build_cash_flow_forecast_report,
    build_cash_flow_report,
    build_profit_loss_report,
)
from apps.finance.models import ReconciliationVarianceKind
from apps.finance.models import BankLineMatchStatus
from apps.finance.models import (
    APApprovalStatus,
    APInvoice,
    APInvoiceStatus,
    APPaymentAllocation,
    ARInvoice,
    ARInvoiceStatus,
    ARPaymentAllocation,
    BankStatementBatch,
    BankStatementBatchStatus,
    BankStatementLine,
    BankStatementSource,
    ReconciliationVariance,
    Category,
    CategoryKind,
    Counterparty,
    CounterpartyKind,
    Project,
    Tag,
    Transaction,
    TransactionType,
)
from apps.finance.admin import IncomeTransactionAdmin, TransactionCategoryListFilter
from apps.finance import db_backup
from apps.finance.visibility import visible_primary_keys


class ProjectTagSnapshotTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(email="fin@test.local", password="secret")
        self.cat = Category.objects.create(
            name="测试收入科目", kind=CategoryKind.INCOME, sort_order=0
        )
        self.project = Project.objects.create(code="demo-proj", name="演示项目")
        self.tag = Tag.objects.create(name="市场")

    def test_audit_snapshot_contains_project_tags_note(self):
        tx = Transaction.objects.create(
            date="2026-05-01",
            transaction_type=TransactionType.INCOME,
            category=self.cat,
            amount=Decimal("100.00"),
            account_name="基本户",
            note="季度回款",
            project=self.project,
            created_by=self.user,
        )
        tx.tags.add(self.tag)
        snap = tx.audit_snapshot()
        self.assertEqual(snap["note"], "季度回款")
        self.assertEqual(snap["project_id"], self.project.pk)
        self.assertEqual(snap["tag_ids"], [self.tag.pk])


class CounterpartyVisibilityTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.group_sales = Group.objects.create(name="test-sales-visibility")
        self.user_no_group = User.objects.create_user(
            email="nogroup@test.local", password="secret"
        )
        self.user_in_group = User.objects.create_user(
            email="ingroup@test.local", password="secret"
        )
        self.user_in_group.groups.add(self.group_sales)
        self.cp_public = Counterparty.objects.create(
            code="cp-public", name="公开", kind=CounterpartyKind.CUSTOMER
        )
        self.cp_group_only = Counterparty.objects.create(
            code="cp-group", name="仅销售组", kind=CounterpartyKind.VENDOR
        )
        self.cp_group_only.visibility_groups.add(self.group_sales)

    def test_user_without_shared_group_does_not_see_restricted(self):
        ids = visible_primary_keys(
            Counterparty.objects.all(),
            self.user_no_group,
            view_all_perm="finance.view_all_counterparties",
        )
        self.assertIn(self.cp_public.pk, ids)
        self.assertNotIn(self.cp_group_only.pk, ids)

    def test_user_in_visibility_group_sees_restricted(self):
        ids = visible_primary_keys(
            Counterparty.objects.all(),
            self.user_in_group,
            view_all_perm="finance.view_all_counterparties",
        )
        self.assertIn(self.cp_public.pk, ids)
        self.assertIn(self.cp_group_only.pk, ids)

    def test_view_all_counterparties_permission_bypasses_groups(self):
        perm = Permission.objects.get(
            content_type__app_label="finance",
            codename="view_all_counterparties",
        )
        self.user_no_group.user_permissions.add(perm)
        u = get_user_model().objects.get(pk=self.user_no_group.pk)
        ids = visible_primary_keys(
            Counterparty.objects.all(),
            u,
            view_all_perm="finance.view_all_counterparties",
        )
        self.assertIn(self.cp_group_only.pk, ids)


class ARInvoiceTests(TestCase):
    def setUp(self):
        self.customer = Counterparty.objects.create(
            code="cust-ar", name="客户 AR", kind=CounterpartyKind.CUSTOMER
        )
        self.vendor = Counterparty.objects.create(
            code="ven-ar", name="供应商 AR", kind=CounterpartyKind.VENDOR
        )

    def test_cannot_assign_pure_vendor_to_ar_invoice(self):
        inv = ARInvoice(
            number="AR-001",
            counterparty=self.vendor,
            issue_date="2026-01-10",
            amount_total=Decimal("500"),
            status=ARInvoiceStatus.OPEN,
        )
        with self.assertRaises(ValidationError):
            inv.full_clean()

    def test_status_becomes_paid_when_paid_matches_total(self):
        inv = ARInvoice.objects.create(
            number="AR-002",
            counterparty=self.customer,
            issue_date="2026-01-10",
            amount_total=Decimal("100.00"),
            amount_paid=Decimal("100.00"),
            status=ARInvoiceStatus.OPEN,
        )
        inv.refresh_from_db()
        self.assertEqual(inv.status, ARInvoiceStatus.PAID)

    def test_draft_not_overwritten_by_sync(self):
        inv = ARInvoice.objects.create(
            number="AR-DRAFT",
            counterparty=self.customer,
            issue_date="2026-01-10",
            amount_total=Decimal("100.00"),
            amount_paid=Decimal("0"),
            status=ARInvoiceStatus.DRAFT,
        )
        self.assertEqual(inv.status, ARInvoiceStatus.DRAFT)

    def test_balance_unpaid(self):
        inv = ARInvoice.objects.create(
            number="AR-003",
            counterparty=self.customer,
            issue_date="2026-01-10",
            amount_total=Decimal("200.00"),
            amount_paid=Decimal("50.00"),
            status=ARInvoiceStatus.OPEN,
        )
        self.assertEqual(inv.balance_unpaid, Decimal("150.00"))


class ARPaymentAllocationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(email="alloc@test.local", password="secret")
        self.cat = Category.objects.create(
            name="核销收入科目", kind=CategoryKind.INCOME, sort_order=0
        )
        self.customer = Counterparty.objects.create(
            code="cust-alloc", name="核销客户", kind=CounterpartyKind.CUSTOMER
        )
        self.inv = ARInvoice.objects.create(
            number="INV-ALLOC-1",
            counterparty=self.customer,
            issue_date="2026-02-01",
            amount_total=Decimal("500.00"),
            amount_paid=Decimal("0"),
            status=ARInvoiceStatus.OPEN,
        )
        self.tx = Transaction.objects.create(
            date="2026-02-02",
            transaction_type=TransactionType.INCOME,
            category=self.cat,
            amount=Decimal("300.00"),
            account_name="银行",
            counterparty=self.customer,
            created_by=self.user,
        )

    def test_allocation_updates_invoice_paid_and_partial_status(self):
        ARPaymentAllocation.objects.create(
            ar_invoice=self.inv, transaction=self.tx, amount=Decimal("300.00")
        )
        self.inv.refresh_from_db()
        self.assertEqual(self.inv.amount_paid, Decimal("300.00"))
        self.assertEqual(self.inv.status, ARInvoiceStatus.PARTIAL)

    def test_delete_allocation_recalcs_invoice(self):
        a = ARPaymentAllocation.objects.create(
            ar_invoice=self.inv, transaction=self.tx, amount=Decimal("200.00")
        )
        self.inv.refresh_from_db()
        self.assertEqual(self.inv.amount_paid, Decimal("200.00"))
        a.delete()
        self.inv.refresh_from_db()
        self.assertEqual(self.inv.amount_paid, Decimal("0"))

    def test_cannot_allocate_expense_transaction(self):
        cat_e = Category.objects.create(
            name="核销支出科目", kind=CategoryKind.EXPENSE, sort_order=0
        )
        tx_exp = Transaction.objects.create(
            date="2026-02-03",
            transaction_type=TransactionType.EXPENSE,
            category=cat_e,
            amount=Decimal("50.00"),
            account_name="现金",
            counterparty=self.customer,
            created_by=self.user,
        )
        alloc = ARPaymentAllocation(
            ar_invoice=self.inv, transaction=tx_exp, amount=Decimal("10.00")
        )
        with self.assertRaises(ValidationError):
            alloc.full_clean()

    def test_cannot_exceed_transaction_amount_across_allocations(self):
        inv2 = ARInvoice.objects.create(
            number="INV-ALLOC-2",
            counterparty=self.customer,
            issue_date="2026-02-01",
            amount_total=Decimal("1000.00"),
            amount_paid=Decimal("0"),
            status=ARInvoiceStatus.OPEN,
        )
        ARPaymentAllocation.objects.create(
            ar_invoice=self.inv, transaction=self.tx, amount=Decimal("200.00")
        )
        dup = ARPaymentAllocation(
            ar_invoice=inv2, transaction=self.tx, amount=Decimal("200.00")
        )
        with self.assertRaises(ValidationError):
            dup.full_clean()


class APInvoiceTests(TestCase):
    def setUp(self):
        self.vendor = Counterparty.objects.create(
            code="ven-ap", name="供应商 AP", kind=CounterpartyKind.VENDOR
        )
        self.customer = Counterparty.objects.create(
            code="cust-ap", name="客户 AP", kind=CounterpartyKind.CUSTOMER
        )

    def test_cannot_assign_pure_customer_to_ap_invoice(self):
        inv = APInvoice(
            number="AP-001",
            counterparty=self.customer,
            issue_date="2026-01-10",
            amount_total=Decimal("500"),
            approval_status=APApprovalStatus.APPROVED,
            status=APInvoiceStatus.OPEN,
        )
        with self.assertRaises(ValidationError):
            inv.full_clean()

    def test_paid_status_requires_approval(self):
        inv = APInvoice.objects.create(
            number="AP-002",
            counterparty=self.vendor,
            issue_date="2026-01-10",
            amount_total=Decimal("100.00"),
            amount_paid=Decimal("100.00"),
            approval_status=APApprovalStatus.APPROVED,
            status=APInvoiceStatus.OPEN,
        )
        inv.refresh_from_db()
        self.assertEqual(inv.status, APInvoiceStatus.PAID)

    def test_unapproved_does_not_sync_to_paid(self):
        inv = APInvoice.objects.create(
            number="AP-003",
            counterparty=self.vendor,
            issue_date="2026-01-10",
            amount_total=Decimal("100.00"),
            amount_paid=Decimal("100.00"),
            approval_status=APApprovalStatus.PENDING,
            status=APInvoiceStatus.OPEN,
        )
        self.assertEqual(inv.status, APInvoiceStatus.OPEN)


class APPaymentAllocationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(email="apalloc@test.local", password="secret")
        self.cat = Category.objects.create(
            name="核销支出科目", kind=CategoryKind.EXPENSE, sort_order=0
        )
        self.vendor = Counterparty.objects.create(
            code="ven-alloc", name="核销供应商", kind=CounterpartyKind.VENDOR
        )
        self.inv = APInvoice.objects.create(
            number="AP-ALLOC-1",
            counterparty=self.vendor,
            issue_date="2026-03-01",
            amount_total=Decimal("500.00"),
            amount_paid=Decimal("0"),
            approval_status=APApprovalStatus.APPROVED,
            status=APInvoiceStatus.OPEN,
        )
        self.tx = Transaction.objects.create(
            date="2026-03-02",
            transaction_type=TransactionType.EXPENSE,
            category=self.cat,
            amount=Decimal("300.00"),
            account_name="银行",
            counterparty=self.vendor,
            created_by=self.user,
        )

    def test_allocation_updates_invoice_paid(self):
        APPaymentAllocation.objects.create(
            ap_invoice=self.inv, transaction=self.tx, amount=Decimal("300.00")
        )
        self.inv.refresh_from_db()
        self.assertEqual(self.inv.amount_paid, Decimal("300.00"))
        self.assertEqual(self.inv.status, APInvoiceStatus.PARTIAL)

    def test_cannot_allocate_without_approval(self):
        self.inv.approval_status = APApprovalStatus.PENDING
        self.inv.save()
        alloc = APPaymentAllocation(
            ap_invoice=self.inv, transaction=self.tx, amount=Decimal("10.00")
        )
        with self.assertRaises(ValidationError):
            alloc.full_clean()

    def test_cannot_allocate_income_transaction(self):
        cat_i = Category.objects.create(
            name="误用收入科目", kind=CategoryKind.INCOME, sort_order=0
        )
        tx_in = Transaction.objects.create(
            date="2026-03-03",
            transaction_type=TransactionType.INCOME,
            category=cat_i,
            amount=Decimal("50.00"),
            account_name="现金",
            counterparty=self.vendor,
            created_by=self.user,
        )
        alloc = APPaymentAllocation(
            ap_invoice=self.inv, transaction=tx_in, amount=Decimal("10.00")
        )
        with self.assertRaises(ValidationError):
            alloc.full_clean()


class BankImportTests(TestCase):
    CSV_SAMPLE = (
        "交易日期,收入,支出,摘要,流水号\n"
        "2026-05-01,1000.00,,货款,X001\n"
        "2026-05-02,,200.50,手续费,X002\n"
    )

    def test_parse_csv_rows_income_and_expense(self):
        lines, errors = parse_csv_rows(self.CSV_SAMPLE)
        self.assertEqual(errors, [])
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0].transaction_type, TransactionType.INCOME)
        self.assertEqual(lines[0].amount, Decimal("1000.00"))
        self.assertEqual(lines[1].transaction_type, TransactionType.EXPENSE)
        self.assertEqual(lines[1].amount, Decimal("200.50"))

    def test_import_csv_into_batch(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        upload = SimpleUploadedFile(
            "bank.csv",
            self.CSV_SAMPLE.encode("utf-8-sig"),
            content_type="text/csv",
        )
        batch = BankStatementBatch.objects.create(
            account_name="对公户",
            source=BankStatementSource.BANK_CSV,
            file=upload,
        )
        result = import_csv_into_batch(batch)
        self.assertEqual(result.imported, 2)
        self.assertEqual(BankStatementLine.objects.filter(batch=batch).count(), 2)
        line = BankStatementLine.objects.get(batch=batch, reference="X001")
        self.assertEqual(line.description, "货款")


class BankReconcileTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            email="reconcile@test.local", password="secret"
        )
        self.cat_in = Category.objects.create(
            name="对账收入", kind=CategoryKind.INCOME, sort_order=0
        )
        self.cat_out = Category.objects.create(
            name="对账支出", kind=CategoryKind.EXPENSE, sort_order=0
        )
        upload = __import__(
            "django.core.files.uploadedfile", fromlist=["SimpleUploadedFile"]
        ).SimpleUploadedFile(
            "b.csv",
            (
                "交易日期,收入,支出,摘要,流水号\n"
                "2026-06-01,500.00,,回款,R1\n"
            ).encode("utf-8"),
            content_type="text/csv",
        )
        self.batch = BankStatementBatch.objects.create(
            account_name="对公户",
            source=BankStatementSource.BANK_CSV,
            file=upload,
        )
        import_csv_into_batch(self.batch)
        self.bank_line = BankStatementLine.objects.get(batch=self.batch, reference="R1")

    def test_auto_match_exact_transaction(self):
        tx = Transaction.objects.create(
            date="2026-06-01",
            transaction_type=TransactionType.INCOME,
            category=self.cat_in,
            amount=Decimal("500.00"),
            account_name="对公户",
            note="回款",
            created_by=self.user,
        )
        matched = find_auto_match(self.bank_line, self.user)
        self.assertEqual(matched.pk, tx.pk)
        result = auto_match_lines([self.bank_line], self.user)
        self.assertEqual(result.matched, 1)
        self.bank_line.refresh_from_db()
        tx.refresh_from_db()
        self.assertEqual(self.bank_line.match_status, BankLineMatchStatus.MATCHED)
        self.assertTrue(tx.is_reconciled)

    def test_clear_match_unmarks_transaction(self):
        tx = Transaction.objects.create(
            date="2026-06-01",
            transaction_type=TransactionType.INCOME,
            category=self.cat_in,
            amount=Decimal("500.00"),
            account_name="对公户",
            created_by=self.user,
        )
        apply_match(self.bank_line, tx)
        clear_match(self.bank_line)
        tx.refresh_from_db()
        self.assertFalse(tx.is_reconciled)
        self.assertEqual(self.bank_line.match_status, BankLineMatchStatus.UNMATCHED)


class BankVarianceTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            email="variance@test.local", password="secret"
        )
        self.cat_exp = Category.objects.create(
            name="银行手续费", kind=CategoryKind.EXPENSE, sort_order=0
        )
        upload = __import__(
            "django.core.files.uploadedfile", fromlist=["SimpleUploadedFile"]
        ).SimpleUploadedFile(
            "v.csv",
            "交易日期,收入,支出,摘要\n2026-07-01,,15.00,手续费\n".encode("utf-8"),
            content_type="text/csv",
        )
        self.batch = BankStatementBatch.objects.create(
            account_name="基本户",
            source=BankStatementSource.BANK_CSV,
            file=upload,
        )
        import_csv_into_batch(self.batch)
        self.bank_line = BankStatementLine.objects.get(batch=self.batch)

    def test_create_adjustment_matches_bank_line(self):
        var = ReconciliationVariance.objects.create(
            batch=self.batch,
            bank_line=self.bank_line,
            kind=ReconciliationVarianceKind.UNRECORDED_BANK,
            amount=self.bank_line.amount,
            adjustment_category=self.cat_exp,
            created_by=self.user,
        )
        tx = create_adjustment_transaction(var, self.user)
        self.bank_line.refresh_from_db()
        var.refresh_from_db()
        self.assertEqual(var.adjustment_transaction_id, tx.pk)
        self.assertTrue(var.is_resolved)
        self.assertEqual(self.bank_line.match_status, BankLineMatchStatus.MATCHED)
        self.assertEqual(self.bank_line.matched_transaction_id, tx.pk)


class ProfitLossReportTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(email="pl@test.local", password="secret")
        self.cat_in = Category.objects.create(
            name="PL测试收入", kind=CategoryKind.INCOME, sort_order=99
        )
        self.cat_out = Category.objects.create(
            name="PL测试支出", kind=CategoryKind.EXPENSE, sort_order=99
        )
        self.project = Project.objects.create(code="pl-p1", name="PL项目一")

    def test_profit_loss_totals(self):
        Transaction.objects.create(
            date="2026-08-01",
            transaction_type=TransactionType.INCOME,
            category=self.cat_in,
            amount=Decimal("1000.00"),
            account_name="A",
            project=self.project,
            created_by=self.user,
        )
        Transaction.objects.create(
            date="2026-08-02",
            transaction_type=TransactionType.EXPENSE,
            category=self.cat_out,
            amount=Decimal("300.00"),
            account_name="A",
            project=self.project,
            created_by=self.user,
        )
        report = build_profit_loss_report(
            self.user,
            date_from=__import__("datetime").date(2026, 8, 1),
            date_to=__import__("datetime").date(2026, 8, 31),
        )
        self.assertEqual(report.total_income, Decimal("1000.00"))
        self.assertEqual(report.total_expense, Decimal("300.00"))
        self.assertEqual(report.net_profit, Decimal("700.00"))
        self.assertEqual(len(report.income_rows), 1)
        self.assertEqual(len(report.expense_rows), 1)


class FinanceReportPageTests(TestCase):
    def test_reports_show_empty_project_guidance(self):
        User = get_user_model()
        user = User.objects.create_superuser(
            email="report-admin@test.local",
            password="secret",
        )
        self.client.force_login(user)

        response = self.client.get("/admin/finance/reports/profit-loss/")

        self.assertContains(response, "暂无项目基础资料")
        self.assertContains(response, "基础资料 → 项目")

    def test_expense_only_staff_can_access_reports(self):
        User = get_user_model()
        user = User.objects.create_user(
            email="expense-report@test.local",
            password="secret",
            is_staff=True,
            must_change_password=False,
        )
        perm = Permission.objects.get(
            content_type__app_label="finance",
            codename="view_expensetransaction",
        )
        user.user_permissions.add(perm)
        self.client.force_login(user)

        response = self.client.get("/admin/finance/reports/")

        self.assertEqual(response.status_code, 200)


class CashFlowBalanceSheetReportTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            email="cfbs@test.local", password="secret"
        )
        self.cat_in = Category.objects.create(
            name="CFBS测试收入", kind=CategoryKind.INCOME, sort_order=98
        )
        self.cat_out = Category.objects.create(
            name="CFBS测试支出", kind=CategoryKind.EXPENSE, sort_order=98
        )
        self.customer = Counterparty.objects.create(
            code="cfbs-c1",
            name="CFBS客户",
            kind=CounterpartyKind.CUSTOMER,
        )
        self.vendor = Counterparty.objects.create(
            code="cfbs-v1",
            name="CFBS供应商",
            kind=CounterpartyKind.VENDOR,
        )

    def test_cash_flow_and_balance_sheet(self):
        from datetime import date

        Transaction.objects.create(
            date="2026-09-01",
            transaction_type=TransactionType.INCOME,
            category=self.cat_in,
            amount=Decimal("1000.00"),
            account_name="主账户",
            counterparty=self.customer,
            created_by=self.user,
        )
        Transaction.objects.create(
            date="2026-09-05",
            transaction_type=TransactionType.EXPENSE,
            category=self.cat_out,
            amount=Decimal("300.00"),
            account_name="主账户",
            counterparty=self.vendor,
            created_by=self.user,
        )
        ARInvoice.objects.create(
            number="AR-CFBS-1",
            counterparty=self.customer,
            issue_date=date(2026, 9, 1),
            amount_total=Decimal("500.00"),
            amount_paid=Decimal("0"),
            status=ARInvoiceStatus.OPEN,
            created_by=self.user,
        )
        APInvoice.objects.create(
            number="AP-CFBS-1",
            counterparty=self.vendor,
            issue_date=date(2026, 9, 1),
            amount_total=Decimal("200.00"),
            amount_paid=Decimal("0"),
            approval_status=APApprovalStatus.APPROVED,
            status=APInvoiceStatus.OPEN,
            created_by=self.user,
        )

        period_from = date(2026, 9, 1)
        period_to = date(2026, 9, 30)
        cf = build_cash_flow_report(
            self.user, date_from=period_from, date_to=period_to
        )
        self.assertEqual(cf.total_inflow, Decimal("1000.00"))
        self.assertEqual(cf.total_outflow, Decimal("300.00"))
        self.assertEqual(cf.net_cash_flow, Decimal("700.00"))
        self.assertEqual(len(cf.account_rows), 1)
        self.assertEqual(cf.account_rows[0].account_name, "主账户")

        bs = build_balance_sheet_report(
            self.user, as_of_date=date(2026, 9, 30)
        )
        self.assertEqual(bs.total_cash, Decimal("700.00"))
        self.assertEqual(bs.accounts_receivable, Decimal("500.00"))
        self.assertEqual(bs.total_assets, Decimal("1200.00"))
        self.assertEqual(bs.accounts_payable, Decimal("200.00"))
        self.assertEqual(bs.retained_earnings, Decimal("700.00"))
        self.assertEqual(bs.balance_gap, Decimal("300.00"))


class CashFlowForecastReportTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            email="fcf@test.local", password="secret"
        )
        self.customer = Counterparty.objects.create(
            code="fcf-c1",
            name="FCF客户",
            kind=CounterpartyKind.CUSTOMER,
        )
        self.vendor = Counterparty.objects.create(
            code="fcf-v1",
            name="FCF供应商",
            kind=CounterpartyKind.VENDOR,
        )

    def test_forecast_by_due_date_buckets(self):
        from datetime import date

        period_from = date(2026, 10, 1)
        period_to = date(2026, 10, 31)

        ARInvoice.objects.create(
            number="AR-FCF-IN",
            counterparty=self.customer,
            issue_date=date(2026, 9, 1),
            due_date=date(2026, 10, 15),
            amount_total=Decimal("800.00"),
            amount_paid=Decimal("0"),
            status=ARInvoiceStatus.OPEN,
            created_by=self.user,
        )
        ARInvoice.objects.create(
            number="AR-FCF-OVER",
            counterparty=self.customer,
            issue_date=date(2026, 8, 1),
            due_date=date(2026, 9, 20),
            amount_total=Decimal("100.00"),
            amount_paid=Decimal("0"),
            status=ARInvoiceStatus.OPEN,
            created_by=self.user,
        )
        ARInvoice.objects.create(
            number="AR-FCF-UND",
            counterparty=self.customer,
            issue_date=date(2026, 9, 1),
            due_date=None,
            amount_total=Decimal("50.00"),
            amount_paid=Decimal("0"),
            status=ARInvoiceStatus.OPEN,
            created_by=self.user,
        )
        APInvoice.objects.create(
            number="AP-FCF-IN",
            counterparty=self.vendor,
            issue_date=date(2026, 9, 1),
            due_date=date(2026, 10, 20),
            amount_total=Decimal("200.00"),
            amount_paid=Decimal("0"),
            approval_status=APApprovalStatus.APPROVED,
            status=APInvoiceStatus.OPEN,
            created_by=self.user,
        )

        report = build_cash_flow_forecast_report(
            self.user, date_from=period_from, date_to=period_to
        )
        self.assertEqual(len(report.period_rows), 2)
        row_ar = next(r for r in report.period_rows if r.due_date == date(2026, 10, 15))
        row_ap = next(r for r in report.period_rows if r.due_date == date(2026, 10, 20))
        self.assertEqual(row_ar.expected_inflow, Decimal("800.00"))
        self.assertEqual(row_ap.expected_outflow, Decimal("200.00"))
        self.assertEqual(report.overdue_inflow, Decimal("100.00"))
        self.assertEqual(report.undated_inflow, Decimal("50.00"))
        self.assertEqual(report.total_expected_inflow, Decimal("950.00"))
        self.assertEqual(report.total_expected_outflow, Decimal("200.00"))
        self.assertEqual(report.in_period_net, Decimal("600.00"))


class FinanceDashboardTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            email="dash@test.local", password="secret"
        )
        self.cat_in_a = Category.objects.create(
            name="看板收入A", kind=CategoryKind.INCOME, sort_order=97
        )
        self.cat_in_b = Category.objects.create(
            name="看板收入B", kind=CategoryKind.INCOME, sort_order=96
        )
        self.cat_out = Category.objects.create(
            name="看板支出A", kind=CategoryKind.EXPENSE, sort_order=97
        )

    def test_dashboard_trends_and_shares(self):
        from datetime import date

        Transaction.objects.create(
            date="2026-07-10",
            transaction_type=TransactionType.INCOME,
            category=self.cat_in_a,
            amount=Decimal("600.00"),
            account_name="X",
            created_by=self.user,
        )
        Transaction.objects.create(
            date="2026-07-20",
            transaction_type=TransactionType.INCOME,
            category=self.cat_in_b,
            amount=Decimal("400.00"),
            account_name="X",
            created_by=self.user,
        )
        Transaction.objects.create(
            date="2026-08-05",
            transaction_type=TransactionType.EXPENSE,
            category=self.cat_out,
            amount=Decimal("250.00"),
            account_name="X",
            created_by=self.user,
        )

        dash = build_finance_dashboard(
            self.user,
            date_from=date(2026, 7, 1),
            date_to=date(2026, 8, 31),
        )
        self.assertEqual(dash.total_income, Decimal("1000.00"))
        self.assertEqual(dash.total_expense, Decimal("250.00"))
        self.assertEqual(dash.net_profit, Decimal("750.00"))
        july = next(r for r in dash.monthly_trends if r.month_start.month == 7)
        august = next(r for r in dash.monthly_trends if r.month_start.month == 8)
        self.assertEqual(july.income, Decimal("1000.00"))
        self.assertEqual(august.expense, Decimal("250.00"))
        self.assertEqual(len(dash.income_by_category), 2)
        self.assertEqual(
            sum((r.share_pct for r in dash.income_by_category), Decimal("0")),
            Decimal("100.00"),
        )
        self.assertEqual(dash.income_by_category[0].total, Decimal("600.00"))
        self.assertEqual(dash.expense_by_category[0].total, Decimal("250.00"))
        self.assertEqual(dash.profit_margin_pct, Decimal("75.00"))
        payload = dash.chart_payload()
        self.assertEqual(len(payload["trend"]["labels"]), len(dash.monthly_trends))
        self.assertEqual(payload["trend"]["income"][0], 1000.0)
        self.assertEqual(len(payload["income_by_category"]["labels"]), 2)


class TransactionCategoryFilterTests(TestCase):
    def setUp(self):
        self.income_cat = Category.objects.create(
            name="筛选用收入科目", kind=CategoryKind.INCOME, sort_order=0
        )
        self.expense_cat = Category.objects.create(
            name="筛选用支出科目", kind=CategoryKind.EXPENSE, sort_order=0
        )
        self.admin = IncomeTransactionAdmin(Transaction, None)

    def test_income_changelist_category_filter_only_income_kinds(self):
        request = None
        filt = TransactionCategoryListFilter(request, {}, Transaction, self.admin)
        lookups = dict(filt.lookups(request, self.admin))
        self.assertIn(str(self.income_cat.pk), lookups)
        self.assertNotIn(str(self.expense_cat.pk), lookups)
        self.assertEqual(lookups[str(self.income_cat.pk)], "筛选用收入科目")


class DatabaseBackupTests(TestCase):
    def setUp(self):
        self.backup_dir = db_backup.backup_directory()
        for path in self.backup_dir.glob(f"{db_backup.BACKUP_PREFIX}*"):
            path.unlink()

    def tearDown(self):
        for path in self.backup_dir.glob(f"{db_backup.BACKUP_PREFIX}*"):
            path.unlink()
        for path in self.backup_dir.glob("upload_*"):
            path.unlink()

    def test_resolve_backup_name_rejects_traversal(self):
        with self.assertRaises(ValueError):
            db_backup.resolve_backup_name("../db.sqlite3")

    def test_manage_database_permission_gate(self):
        User = get_user_model()
        staff = User.objects.create_user(email="staff@test.local", password="secret")
        staff.is_staff = True
        staff.save()
        superuser = User.objects.create_superuser(
            email="admin-gate@test.local",
            password="secret",
        )
        from apps.finance.views import _can_manage_system_settings

        self.assertFalse(_can_manage_system_settings(staff))
        self.assertTrue(_can_manage_system_settings(superuser))

    @patch("apps.finance.views.db_backup.create_backup")
    def test_superuser_can_backup_via_admin(self, mock_create_backup):
        mock_create_backup.return_value = self.backup_dir / "db_backup_mock.sqlite3"
        User = get_user_model()
        admin = User.objects.create_superuser(
            email="admin-backup@test.local",
            password="secret",
        )
        from django.test import Client

        client = Client()
        client.force_login(admin)
        response = client.post(
            "/admin/finance/system-settings/",
            {"action": "backup"},
        )
        self.assertEqual(response.status_code, 302)
        mock_create_backup.assert_called_once()
