from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.translation import gettext_lazy as _


class AuditLog(models.Model):
    """Business audit trail (separate from django_admin_log)."""

    class Action(models.TextChoices):
        CREATE = "create", _("Create")
        UPDATE = "update", _("Update")
        DELETE = "delete", _("Delete")
        RECONCILE_BULK = "reconcile_bulk", _("Bulk reconcile")

    timestamp = models.DateTimeField(_("Timestamp"), auto_now_add=True, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("User"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    action = models.CharField(
        _("Action"),
        max_length=32,
        choices=Action.choices,
        db_index=True,
    )
    content_type = models.ForeignKey(
        ContentType,
        verbose_name=_("Content type"),
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    object_id = models.CharField(_("Object ID"), max_length=64, blank=True)
    content_object = GenericForeignKey("content_type", "object_id")
    object_repr = models.CharField(_("Object summary"), max_length=500, blank=True)
    changes = models.JSONField(_("Changes"), null=True, blank=True)
    ip_address = models.GenericIPAddressField(_("IP address"), null=True, blank=True)

    class Meta:
        verbose_name = _("Audit log")
        verbose_name_plural = _("Audit log")
        ordering = ("-timestamp", "-pk")
        indexes = [
            models.Index(fields=("content_type", "object_id")),
        ]

    def __str__(self) -> str:
        return f"{self.timestamp} {self.get_action_display()} {self.object_repr}"
