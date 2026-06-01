"""财务后台报表视图（需登录且具备流水查看权限）。"""
from __future__ import annotations

from datetime import date, timedelta

from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import UploadedFile
from django.http import FileResponse, Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.finance import db_backup
from apps.finance.dashboard import build_finance_dashboard
from apps.finance.report_pages import (
    REPORT_DETAIL_PAGE_SIZE,
    REPORT_INLINE_PAGE_SIZE,
    paginate_sequence,
    parse_report_tab,
    query_string,
)
from apps.finance.reports import (
    build_balance_sheet_report,
    build_cash_flow_forecast_report,
    build_cash_flow_report,
    build_profit_loss_report,
    visible_projects_for_user,
)


def _default_period():
    today = timezone.localdate()
    return date(today.year, today.month, 1), today


def _default_forecast_period():
    today = timezone.localdate()
    return today, today + timedelta(days=90)


def _default_dashboard_period():
    today = timezone.localdate()
    months_back = 5
    y, m = today.year, today.month - months_back
    while m <= 0:
        m += 12
        y -= 1
    return date(y, m, 1), today


def _parse_date(raw: str | None) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def _can_view_finance_reports(user) -> bool:
    return user.is_active and (
        user.is_superuser
        or user.has_perm("finance.view_incometransaction")
        or user.has_perm("finance.view_expensetransaction")
    )


def _can_manage_system_settings(user) -> bool:
    return user.is_active and (
        user.is_superuser or user.has_perm("finance.manage_database")
    )


def _validate_sqlite_upload(uploaded: UploadedFile) -> None:
    header = uploaded.read(16)
    uploaded.seek(0)
    if header != b"SQLite format 3\x00":
        raise ValueError(_("The uploaded file is not a valid SQLite database."))


def _parse_project_filter(request, projects):
    project_raw = request.GET.get("project", "").strip()
    project_id = int(project_raw) if project_raw.isdigit() else None
    if project_id and not projects.filter(pk=project_id).exists():
        project_id = None
    return project_id


def reports_index(request):
    if not _can_view_finance_reports(request.user):
        raise PermissionDenied
    return render(
        request,
        "admin/finance/reports/index.html",
        {
            **admin.site.each_context(request),
            "title": _("Report center"),
        },
    )


def profit_loss_report(request):
    if not _can_view_finance_reports(request.user):
        raise PermissionDenied

    default_from, default_to = _default_period()
    date_from = _parse_date(request.GET.get("date_from")) or default_from
    date_to = _parse_date(request.GET.get("date_to")) or default_to
    projects = visible_projects_for_user(request.user)
    project_id = _parse_project_filter(request, projects)

    report = build_profit_loss_report(
        request.user,
        date_from=date_from,
        date_to=date_to,
        project_id=project_id,
    )

    show_projects_tab = not project_id and bool(report.project_rows)
    allowed_tabs = ("income", "expense", "projects") if show_projects_tab else ("income", "expense")
    active_tab = parse_report_tab(request, allowed_tabs, "income")
    income_page = paginate_sequence(
        request,
        report.income_rows,
        per_page=REPORT_DETAIL_PAGE_SIZE,
        page_param="income_page",
    )
    expense_page = paginate_sequence(
        request,
        report.expense_rows,
        per_page=REPORT_DETAIL_PAGE_SIZE,
        page_param="expense_page",
    )
    project_page = None
    if show_projects_tab:
        project_page = paginate_sequence(
            request,
            report.project_rows,
            per_page=REPORT_DETAIL_PAGE_SIZE,
            page_param="project_page",
        )
    q = query_string(request, tab=active_tab)
    return render(
        request,
        "admin/finance/reports/profit_loss.html",
        {
            **admin.site.each_context(request),
            "title": _("Profit & loss"),
            "report": report,
            "projects": projects,
            "selected_project_id": project_id,
            "filter_date_from": date_from.isoformat(),
            "filter_date_to": date_to.isoformat(),
            "filter_query": q,
            "active_tab": active_tab,
            "show_projects_tab": show_projects_tab,
            "tab_income_url": query_string(request, tab="income"),
            "tab_expense_url": query_string(request, tab="expense"),
            "tab_projects_url": query_string(request, tab="projects"),
            "income_page": income_page,
            "expense_page": expense_page,
            "project_page": project_page,
        },
    )


def _profit_loss_filters(request):
    default_from, default_to = _default_period()
    date_from = _parse_date(request.GET.get("date_from")) or default_from
    date_to = _parse_date(request.GET.get("date_to")) or default_to
    projects = visible_projects_for_user(request.user)
    project_id = _parse_project_filter(request, projects)
    report = build_profit_loss_report(
        request.user,
        date_from=date_from,
        date_to=date_to,
        project_id=project_id,
    )
    return date_from, date_to, projects, project_id, report


def _redirect_profit_loss_tab(request, tab: str):
    q = request.GET.copy()
    q["tab"] = tab
    for key in ("page", "income_page", "expense_page", "project_page"):
        q.pop(key, None)
    return redirect(f"{reverse('finance:profit_loss')}?{q.urlencode()}")


def profit_loss_income_report(request):
    if not _can_view_finance_reports(request.user):
        raise PermissionDenied
    return _redirect_profit_loss_tab(request, "income")


def profit_loss_expense_report(request):
    if not _can_view_finance_reports(request.user):
        raise PermissionDenied
    return _redirect_profit_loss_tab(request, "expense")


def profit_loss_projects_report(request):
    if not _can_view_finance_reports(request.user):
        raise PermissionDenied
    return _redirect_profit_loss_tab(request, "projects")


def cash_flow_report(request):
    if not _can_view_finance_reports(request.user):
        raise PermissionDenied

    default_from, default_to = _default_period()
    date_from = _parse_date(request.GET.get("date_from")) or default_from
    date_to = _parse_date(request.GET.get("date_to")) or default_to
    projects = visible_projects_for_user(request.user)
    project_id = _parse_project_filter(request, projects)

    report = build_cash_flow_report(
        request.user,
        date_from=date_from,
        date_to=date_to,
        project_id=project_id,
    )

    page_obj = paginate_sequence(
        request, report.account_rows, per_page=REPORT_DETAIL_PAGE_SIZE
    )
    return render(
        request,
        "admin/finance/reports/cash_flow.html",
        {
            **admin.site.each_context(request),
            "title": _("Cash flow statement"),
            "report": report,
            "page_obj": page_obj,
            "projects": projects,
            "selected_project_id": project_id,
            "filter_date_from": date_from.isoformat(),
            "filter_date_to": date_to.isoformat(),
            "filter_query": query_string(request),
        },
    )


def balance_sheet_report(request):
    if not _can_view_finance_reports(request.user):
        raise PermissionDenied

    today = timezone.localdate()
    as_of_date = _parse_date(request.GET.get("as_of_date")) or today
    projects = visible_projects_for_user(request.user)
    project_id = _parse_project_filter(request, projects)

    report = build_balance_sheet_report(
        request.user,
        as_of_date=as_of_date,
        project_id=project_id,
    )

    active_tab = parse_report_tab(request, ("assets", "liabilities", "equity"), "assets")
    q = query_string(request, tab=active_tab)
    return render(
        request,
        "admin/finance/reports/balance_sheet.html",
        {
            **admin.site.each_context(request),
            "title": _("Balance sheet"),
            "report": report,
            "projects": projects,
            "selected_project_id": project_id,
            "filter_as_of_date": as_of_date.isoformat(),
            "filter_query": q,
            "active_tab": active_tab,
            "tab_assets_url": query_string(request, tab="assets"),
            "tab_liabilities_url": query_string(request, tab="liabilities"),
            "tab_equity_url": query_string(request, tab="equity"),
            "cash_filter_query": query_string(request, tab=None),
            "cash_account_count": len(report.cash_rows),
        },
    )


def balance_sheet_cash_report(request):
    if not _can_view_finance_reports(request.user):
        raise PermissionDenied

    today = timezone.localdate()
    as_of_date = _parse_date(request.GET.get("as_of_date")) or today
    projects = visible_projects_for_user(request.user)
    project_id = _parse_project_filter(request, projects)

    report = build_balance_sheet_report(
        request.user,
        as_of_date=as_of_date,
        project_id=project_id,
    )
    page_obj = paginate_sequence(
        request, report.cash_rows, per_page=REPORT_DETAIL_PAGE_SIZE
    )

    return render(
        request,
        "admin/finance/reports/balance_sheet_cash.html",
        {
            **admin.site.each_context(request),
            "title": _("Balance sheet · cash detail"),
            "report": report,
            "page_obj": page_obj,
            "filter_as_of_date": as_of_date.isoformat(),
            "filter_query": query_string(request),
        },
    )


def cash_flow_forecast_report(request):
    if not _can_view_finance_reports(request.user):
        raise PermissionDenied

    default_from, default_to = _default_forecast_period()
    date_from = _parse_date(request.GET.get("date_from")) or default_from
    date_to = _parse_date(request.GET.get("date_to")) or default_to

    report = build_cash_flow_forecast_report(
        request.user,
        date_from=date_from,
        date_to=date_to,
    )

    period_page = paginate_sequence(
        request,
        report.period_rows,
        per_page=REPORT_INLINE_PAGE_SIZE,
        page_param="period_page",
    )
    active_tab = parse_report_tab(request, ("period", "other", "details"), "period")
    q = query_string(request, tab=active_tab)
    return render(
        request,
        "admin/finance/reports/cash_flow_forecast.html",
        {
            **admin.site.each_context(request),
            "title": _("Cash flow forecast"),
            "report": report,
            "period_page": period_page,
            "filter_date_from": date_from.isoformat(),
            "filter_date_to": date_to.isoformat(),
            "filter_query": q,
            "active_tab": active_tab,
            "tab_period_url": query_string(request, tab="period"),
            "tab_other_url": query_string(request, tab="other"),
            "tab_details_url": query_string(request, tab="details"),
            "detail_filter_query": query_string(request, tab=None),
            "detail_count": len(report.detail_rows),
        },
    )


def cash_flow_forecast_details_report(request):
    if not _can_view_finance_reports(request.user):
        raise PermissionDenied

    default_from, default_to = _default_forecast_period()
    date_from = _parse_date(request.GET.get("date_from")) or default_from
    date_to = _parse_date(request.GET.get("date_to")) or default_to

    report = build_cash_flow_forecast_report(
        request.user,
        date_from=date_from,
        date_to=date_to,
    )
    page_obj = paginate_sequence(
        request, report.detail_rows, per_page=REPORT_DETAIL_PAGE_SIZE
    )

    return render(
        request,
        "admin/finance/reports/cash_flow_forecast_details.html",
        {
            **admin.site.each_context(request),
            "title": _("Cash flow forecast · invoice details"),
            "report": report,
            "page_obj": page_obj,
            "filter_date_from": date_from.isoformat(),
            "filter_date_to": date_to.isoformat(),
            "filter_query": query_string(request),
        },
    )


def finance_dashboard(request):
    if not _can_view_finance_reports(request.user):
        raise PermissionDenied

    default_from, default_to = _default_dashboard_period()
    date_from = _parse_date(request.GET.get("date_from")) or default_from
    date_to = _parse_date(request.GET.get("date_to")) or default_to
    projects = visible_projects_for_user(request.user)
    project_id = _parse_project_filter(request, projects)

    dashboard = build_finance_dashboard(
        request.user,
        date_from=date_from,
        date_to=date_to,
        project_id=project_id,
    )
    max_monthly = int(dashboard.max_monthly_value) or 1

    return render(
        request,
        "admin/finance/dashboard.html",
        {
            **admin.site.each_context(request),
            "title": _("Finance dashboard"),
            "dashboard": dashboard,
            "max_monthly": max_monthly,
            "projects": projects,
            "selected_project_id": project_id,
            "filter_date_from": date_from.isoformat(),
            "filter_date_to": date_to.isoformat(),
        },
    )


def system_settings(request):
    if not _can_manage_system_settings(request.user):
        raise PermissionDenied

    settings_url = reverse("finance:system_settings")
    sqlite_enabled = db_backup.is_sqlite_backend()

    download_name = request.GET.get("download", "").strip()
    if download_name:
        if not sqlite_enabled:
            raise Http404
        try:
            backup_path = db_backup.resolve_backup_name(download_name)
        except ValueError as exc:
            raise Http404 from exc
        return FileResponse(
            backup_path.open("rb"),
            as_attachment=True,
            filename=backup_path.name,
        )

    backups = []
    if sqlite_enabled:
        backups = [
            {
                "name": path.name,
                "label": db_backup.format_backup_label(path),
                "size_kb": max(1, path.stat().st_size // 1024),
            }
            for path in db_backup.list_backups()
        ]

    if request.method == "POST":
        if not sqlite_enabled:
            messages.error(
                request,
                _("PostgreSQL is in use. Use pg_dump/pg_restore on the server for backups."),
            )
            return redirect(settings_url)

        action = request.POST.get("action", "").strip()
        if action == "backup":
            try:
                path = db_backup.create_backup()
            except RuntimeError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(
                    request,
                    _("Database backed up: %(name)s") % {"name": path.name},
                )
            return redirect(settings_url)

        if action == "restore":
            if request.POST.get("confirm") != "yes":
                messages.error(request, _("Check the confirmation box before restoring the database."))
                return redirect(settings_url)

            backup_path = None
            uploaded = request.FILES.get("backup_file")
            selected = request.POST.get("backup_name", "").strip()

            try:
                if uploaded:
                    _validate_sqlite_upload(uploaded)
                    temp_name = db_backup.backup_filename()
                    temp_path = db_backup.backup_directory() / f"upload_{temp_name}"
                    with temp_path.open("wb") as dest:
                        for chunk in uploaded.chunks():
                            dest.write(chunk)
                    backup_path = temp_path
                elif selected:
                    backup_path = db_backup.resolve_backup_name(selected)
                else:
                    messages.error(request, _("Select a backup file or upload a .sqlite3 file."))
                    return redirect(settings_url)

                db_backup.restore_from_path(backup_path)
            except (ValueError, FileNotFoundError) as exc:
                messages.error(request, str(exc))
            except RuntimeError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(
                    request,
                    _("Database restored. Refresh the page or restart the service if data looks stale."),
                )
            return redirect(settings_url)

        messages.error(request, _("Unknown action."))
        return redirect(settings_url)

    return render(
        request,
        "admin/finance/system_settings.html",
        {
            **admin.site.each_context(request),
            "title": _("System settings"),
            "sqlite_enabled": sqlite_enabled,
            "database_name": db_backup.database_path().name if sqlite_enabled else "",
            "backups": backups,
        },
    )
