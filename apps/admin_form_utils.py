"""后台表单通用：help_text 作 placeholder、紧凑多行框等。"""
from __future__ import annotations

from django import forms
from django.contrib import admin
from django.utils.html import strip_tags

PLACEHOLDER_WIDGETS = (
    forms.TextInput,
    forms.NumberInput,
    forms.Textarea,
    forms.EmailInput,
    forms.URLInput,
)

# 备注类字段默认 2 行高
COMPACT_TEXTAREA_NAMES = frozenset(
    {
        "note",
        "remark",
        "title",
        "caption",
        "billing_address",
        "error_log",
    }
)

# 无 help_text 时仍给 placeholder 的字段
EXTRA_PLACEHOLDERS: dict[str, str] = {
    "account_name": "如：工商银行基本户、库存现金",
    "note": "摘要或备注，选填",
    "remark": "备注，选填",
    "number": "单号，需唯一",
    "title": "摘要，选填",
}


class CompactHelpTextMixin:
    """将字段 help_text 写入 placeholder，去掉输入框下方说明文字。"""

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        if formfield is None:
            return formfield

        widget = formfield.widget
        if isinstance(widget, forms.Textarea) and db_field.name in COMPACT_TEXTAREA_NAMES:
            widget.attrs["rows"] = 2
            widget.attrs.setdefault("style", "overflow-y: auto; resize: none;")

        if formfield.help_text:
            text = strip_tags(str(formfield.help_text)).strip()
            if text and isinstance(widget, PLACEHOLDER_WIDGETS):
                widget.attrs.setdefault("placeholder", text)
                formfield.help_text = ""

        if db_field.name in EXTRA_PLACEHOLDERS and isinstance(
            widget, (forms.TextInput, forms.Textarea)
        ):
            widget.attrs.setdefault("placeholder", EXTRA_PLACEHOLDERS[db_field.name])

        if db_field.name == "date" and isinstance(widget, forms.DateInput):
            widget.attrs.setdefault("placeholder", "选择交易日期")

        return formfield


class CompactAdmin(CompactHelpTextMixin, admin.ModelAdmin):
    """带紧凑表单行为的 ModelAdmin 基类。"""
