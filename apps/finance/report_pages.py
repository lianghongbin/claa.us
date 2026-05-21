"""报表分页与布局约定。

- 同一页不要上下堆叠多张表：若第一张表行数很多，下面的表很难用。
- 仅当两张表行数都固定且很少时，才允许同页上下摆放。
- 否则：拆成独立子页，或同页用 Tab 切换（每次只显示一张表）。
- 行数不固定的明细：子页 + 分页；不要把多张可变长表拼成一张大表。
"""
from __future__ import annotations

from django.core.paginator import Paginator
from django.http import HttpRequest

# 明细类报表默认每页行数
REPORT_DETAIL_PAGE_SIZE = 50

# 主表内「按日/按账户」等次级汇总，超过此行数则分页（仍留在同一页）
REPORT_INLINE_PAGE_SIZE = 31


def paginate_sequence(request: HttpRequest, items, *, per_page: int, page_param: str = "page"):
    paginator = Paginator(items, per_page)
    return paginator.get_page(request.GET.get(page_param) or 1)


def parse_report_tab(request: HttpRequest, allowed: tuple[str, ...], default: str) -> str:
    tab = (request.GET.get("tab") or default).strip()
    return tab if tab in allowed else default


def query_string(request: HttpRequest, **extra) -> str:
    """保留当前 GET 筛选参数，用于分页与子页链接。"""
    q = request.GET.copy()
    for key in ("page", "period_page", "income_page", "expense_page", "project_page"):
        q.pop(key, None)
    for k, v in extra.items():
        if v is None:
            q.pop(k, None)
        elif v != "":
            q[k] = v
        else:
            q.pop(k, None)
    return q.urlencode()
