"""按「可见分组」过滤数据范围；配合 Meta.permissions 中的 view_all_* 使用。"""
from __future__ import annotations

from typing import TYPE_CHECKING

from django.db.models import Count, Q, QuerySet

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


def visible_primary_keys(
    qs: QuerySet,
    user: AbstractUser,
    *,
    view_all_perm: str,
    m2m_field: str = "visibility_groups",
) -> list[int]:
    """
    返回当前用户可见的主键列表。
    - 超级用户或拥有 view_all_perm：全部主键。
    - 否则：M2M 为空（未限制）的记录，或与用户所在分组有交集的记录。
    - 用户未加入任何分组时：仅可见「未限制」的记录。
    """
    if not user.is_authenticated:
        return []
    if user.is_superuser or user.has_perm(view_all_perm):
        return list(qs.values_list("pk", flat=True))

    annotated = qs.annotate(_vis_cnt=Count(m2m_field, distinct=True))
    user_groups = user.groups.all()
    if user_groups.exists():
        flt = Q(_vis_cnt=0) | Q(**{f"{m2m_field}__in": user_groups})
    else:
        flt = Q(_vis_cnt=0)
    return list(annotated.filter(flt).values_list("pk", flat=True).distinct())


def transactions_visible_for_user(qs: QuerySet, user) -> QuerySet:
    """与收入/支出列表一致：按项目、往来单位的可见分组过滤流水 QuerySet。"""
    from apps.finance.models import Counterparty, Project

    if not getattr(user, "is_authenticated", False):
        return qs.none()
    if user.is_superuser or user.has_perm("finance.view_all_finance_transactions"):
        return qs
    proj_ids = visible_primary_keys(
        Project.objects.all(),
        user,
        view_all_perm="finance.view_all_projects",
    )
    cp_ids = visible_primary_keys(
        Counterparty.objects.all(),
        user,
        view_all_perm="finance.view_all_counterparties",
    )
    return qs.filter(
        Q(project__isnull=True) | Q(project_id__in=proj_ids),
        Q(counterparty__isnull=True) | Q(counterparty_id__in=cp_ids),
    )
