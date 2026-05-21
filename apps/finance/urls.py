from django.contrib import admin
from django.urls import path

from apps.finance import views

app_name = "finance"

urlpatterns = [
    path(
        "dashboard/",
        admin.site.admin_view(views.finance_dashboard),
        name="dashboard",
    ),
    path(
        "reports/",
        admin.site.admin_view(views.reports_index),
        name="reports_index",
    ),
    path(
        "reports/profit-loss/",
        admin.site.admin_view(views.profit_loss_report),
        name="profit_loss",
    ),
    path(
        "reports/cash-flow/",
        admin.site.admin_view(views.cash_flow_report),
        name="cash_flow",
    ),
    path(
        "reports/balance-sheet/",
        admin.site.admin_view(views.balance_sheet_report),
        name="balance_sheet",
    ),
    path(
        "reports/balance-sheet/cash/",
        admin.site.admin_view(views.balance_sheet_cash_report),
        name="balance_sheet_cash",
    ),
    path(
        "reports/cash-flow-forecast/",
        admin.site.admin_view(views.cash_flow_forecast_report),
        name="cash_flow_forecast",
    ),
    path(
        "reports/cash-flow-forecast/details/",
        admin.site.admin_view(views.cash_flow_forecast_details_report),
        name="cash_flow_forecast_details",
    ),
    path(
        "reports/profit-loss/income/",
        admin.site.admin_view(views.profit_loss_income_report),
        name="profit_loss_income",
    ),
    path(
        "reports/profit-loss/expense/",
        admin.site.admin_view(views.profit_loss_expense_report),
        name="profit_loss_expense",
    ),
    path(
        "reports/profit-loss/projects/",
        admin.site.admin_view(views.profit_loss_projects_report),
        name="profit_loss_projects",
    ),
    path(
        "system-settings/",
        admin.site.admin_view(views.system_settings),
        name="system_settings",
    ),
]
