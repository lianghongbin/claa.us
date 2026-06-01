"""Shared admin form UX: help_text as placeholder, compact textareas."""
from __future__ import annotations

from django import forms
from django.contrib import admin
from django.utils.html import strip_tags
from django.utils.translation import gettext_lazy as _

PLACEHOLDER_WIDGETS = (
    forms.TextInput,
    forms.NumberInput,
    forms.Textarea,
    forms.EmailInput,
    forms.URLInput,
)

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

EXTRA_PLACEHOLDERS: dict[str, str] = {
    "account_name": _("e.g. Main checking, Petty cash"),
    "note": _("Memo (optional)"),
    "remark": _("Notes (optional)"),
    "number": _("Document no. (unique)"),
    "title": _("Title (optional)"),
}


class CompactHelpTextMixin:
    """Use help_text as placeholder; hide help text below the field."""

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
            widget.attrs.setdefault("placeholder", str(EXTRA_PLACEHOLDERS[db_field.name]))

        if db_field.name == "date" and isinstance(widget, forms.DateInput):
            widget.attrs.setdefault("placeholder", _("Transaction date"))

        return formfield


class CompactAdmin(CompactHelpTextMixin, admin.ModelAdmin):
    """ModelAdmin with compact form layout."""
