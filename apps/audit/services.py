"""审计写入辅助函数。"""
from __future__ import annotations

from typing import Any

from django.contrib.contenttypes.models import ContentType
from django.http import HttpRequest

from apps.audit.models import AuditLog


def get_client_ip(request: HttpRequest | None) -> str | None:
    if not request:
        return None
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def log_model_change(
    request: HttpRequest | None,
    *,
    action: str,
    instance: Any,
    changes: dict | None = None,
) -> None:
    ct = ContentType.objects.get_for_model(instance.__class__)
    AuditLog.objects.create(
        user=request.user if request and request.user.is_authenticated else None,
        action=action,
        content_type=ct,
        object_id=str(instance.pk),
        object_repr=str(instance)[:500],
        changes=changes,
        ip_address=get_client_ip(request),
    )


def log_model_deleted(
    request: HttpRequest | None,
    *,
    model_class: type,
    pk: int,
    object_repr: str,
    changes: dict | None = None,
) -> None:
    AuditLog.objects.create(
        user=request.user if request and request.user.is_authenticated else None,
        action=AuditLog.Action.DELETE,
        content_type=ContentType.objects.get_for_model(model_class),
        object_id=str(pk),
        object_repr=object_repr[:500],
        changes=changes,
        ip_address=get_client_ip(request),
    )


def log_bulk_reconcile(
    request: HttpRequest | None,
    *,
    transaction_ids: list[int],
) -> None:
    AuditLog.objects.create(
        user=request.user if request and request.user.is_authenticated else None,
        action=AuditLog.Action.RECONCILE_BULK,
        content_type=None,
        object_id="",
        object_repr=f"批量对账 {len(transaction_ids)} 条",
        changes={"transaction_ids": transaction_ids},
        ip_address=get_client_ip(request),
    )
