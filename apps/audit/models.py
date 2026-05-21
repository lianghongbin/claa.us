from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class AuditLog(models.Model):
    """业务操作审计记录（独立于 django_admin_log）。"""

    class Action(models.TextChoices):
        CREATE = "create", "创建"
        UPDATE = "update", "修改"
        DELETE = "delete", "删除"
        RECONCILE_BULK = "reconcile_bulk", "批量对账"

    timestamp = models.DateTimeField("时间", auto_now_add=True, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="用户",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    action = models.CharField(
        "动作",
        max_length=32,
        choices=Action.choices,
        db_index=True,
    )
    content_type = models.ForeignKey(
        ContentType,
        verbose_name="对象类型",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    object_id = models.CharField("对象主键", max_length=64, blank=True)
    content_object = GenericForeignKey("content_type", "object_id")
    object_repr = models.CharField("对象摘要", max_length=500, blank=True)
    changes = models.JSONField("变更详情", null=True, blank=True)
    ip_address = models.GenericIPAddressField("IP", null=True, blank=True)

    class Meta:
        verbose_name = "操作日志"
        verbose_name_plural = "操作日志"
        ordering = ("-timestamp", "-pk")
        indexes = [
            models.Index(fields=("content_type", "object_id")),
        ]

    def __str__(self) -> str:
        return f"{self.timestamp} {self.get_action_display()} {self.object_repr}"
