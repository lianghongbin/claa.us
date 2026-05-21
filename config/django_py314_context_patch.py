"""
Django 模板上下文在 Python 3.14 下的兼容性修复。

Django 5.0/5.1 中 BaseContext.__copy__ 使用 ``copy(super())``，在 CPython 3.14
中会触发 ``AttributeError: 'super' object has no attribute 'dicts'``（渲染
admin changelist 时，与 import_export / simpleui 组合易复现）。

Django 主分支已改为基于实例 __dict__ 的浅拷贝实现，此处对齐该逻辑。
"""
from __future__ import annotations

from copy import copy as copy_fn


def apply() -> None:
    import sys

    if sys.version_info < (3, 14):
        return

    from django.template.context import BaseContext

    def __copy__(self):  # noqa: ANN001
        duplicate = BaseContext()
        duplicate.__class__ = self.__class__
        duplicate.__dict__ = copy_fn(self.__dict__)
        duplicate.dicts = self.dicts[:]
        return duplicate

    BaseContext.__copy__ = __copy__
