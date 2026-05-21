from django.contrib import admin
from django.contrib.admin import DateFieldListFilter

from apps.audit.models import AuditLog
from apps.finance.permissions import GROUP_FINANCE_ADMIN


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = (
        "timestamp",
        "user",
        "action",
        "content_type",
        "object_id",
        "object_repr",
        "ip_address",
    )
    list_filter = (
        "action",
        "content_type",
        ("timestamp", DateFieldListFilter),
    )
    search_fields = ("object_repr", "object_id", "user__username")
    readonly_fields = (
        "timestamp",
        "user",
        "action",
        "content_type",
        "object_id",
        "object_repr",
        "changes",
        "ip_address",
    )

    def has_module_permission(self, request):
        return request.user.is_active and (
            request.user.is_superuser
            or request.user.groups.filter(name=GROUP_FINANCE_ADMIN).exists()
        )

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
