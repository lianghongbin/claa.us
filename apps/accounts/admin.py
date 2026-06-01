import secrets

from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.contrib.admin.options import ModelAdmin
from django.contrib.admin.utils import unquote
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.html import escape, format_html, strip_tags
from django.utils.translation import gettext, gettext_lazy as _
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.debug import sensitive_post_parameters

from apps.admin_form_utils import CompactHelpTextMixin
from apps.accounts.forms import (
    EmailUserChangeForm,
    StaffUserAddForm,
    StaffUserAddFormSuperuser,
)
from apps.accounts.mail import send_initial_password_email
from apps.accounts.models import User

csrf_protect_m = method_decorator(csrf_protect)
sensitive_post_parameters_m = method_decorator(sensitive_post_parameters())


class CustomUserAdmin(CompactHelpTextMixin, BaseUserAdmin):
    """
    邮箱登录用户管理：新建用户时生成密码并发邮件；管理员重置他人密码后要求其再次修改。
    在模块末尾从 AdminSite 卸载默认 UserAdmin 后注册本类（见 INSTALLED_APPS 中 accounts 位于 auth 之后）。
    """

    add_form_template = "admin/auth/user/add_form.html"
    change_form_template = "admin/accounts/user/change_form.html"
    add_form = StaffUserAddForm
    form = EmailUserChangeForm
    ordering = ("email",)
    list_display = ("email", "first_name", "last_name", "is_staff", "must_change_password")
    list_filter = ("is_staff", "is_superuser", "is_active", "groups", "must_change_password")
    search_fields = ("email", "first_name", "last_name")
    readonly_fields = ("password_actions", "last_login", "date_joined")

    fieldsets = (
        (
            _("Account"),
            {"classes": ("accounts-card", "accounts-two-cols"), "fields": ("email", "password_actions")},
        ),
        (
            _("Personal info"),
            {"classes": ("accounts-card", "accounts-two-cols"), "fields": ("first_name", "last_name")},
        ),
        (
            _("Status"),
            {
                "classes": ("accounts-card", "accounts-status-card"),
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "must_change_password",
                ),
            },
        ),
        (
            _("Roles & permissions"),
            {
                "classes": ("accounts-card", "accounts-permission-card"),
                "fields": (
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        (
            _("Important dates"),
            {"classes": ("accounts-card", "accounts-two-cols"), "fields": ("last_login", "date_joined")},
        ),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("accounts-card", "accounts-add-grid"),
                "fields": (
                    "email",
                    "first_name",
                    "last_name",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                ),
            },
        ),
        (
            _("Roles & permissions"),
            {
                "classes": ("accounts-card", "accounts-permission-card"),
                "fields": ("groups", "user_permissions"),
            },
        ),
    )

    def get_fieldsets(self, request, obj=None):
        if obj is None and not request.user.is_superuser:
            return (
                (
                    None,
                    {
                        "classes": ("accounts-card", "accounts-add-grid"),
                        "fields": (
                            "email",
                            "first_name",
                            "last_name",
                            "is_active",
                            "is_staff",
                        ),
                    },
                ),
                (
                    _("Roles"),
                    {
                        "classes": ("accounts-card", "accounts-permission-card"),
                        "fields": ("groups",),
                    },
                ),
            )
        if obj is None:
            return self.add_fieldsets
        return super().get_fieldsets(request, obj)

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        if formfield is None:
            return formfield
        if db_field.name in {
            "is_active",
            "is_staff",
            "is_superuser",
            "must_change_password",
        }:
            text = strip_tags(str(formfield.help_text or "")).strip()
            if text:
                formfield.widget.attrs.setdefault("title", text)
            formfield.help_text = ""
        return formfield

    def get_form(self, request, obj=None, **kwargs):
        if obj is None:
            base = StaffUserAddFormSuperuser if request.user.is_superuser else StaffUserAddForm

            class AddWithUser(base):
                def __init__(self, *args, **kw):
                    super().__init__(*args, user=request.user, **kw)

            kwargs["form"] = AddWithUser
        else:
            kwargs["form"] = EmailUserChangeForm
        return ModelAdmin.get_form(self, request, obj, **kwargs)

    @admin.display(description=_("Password"))
    def password_actions(self, obj):
        if not obj or not obj.pk:
            return "—"
        url = reverse("admin:auth_user_password_change", args=(obj.pk,))
        return format_html('<a class="button accounts-password-button" href="{}">' + str(_("Change password")) + '</a>', url)

    def save_model(self, request, obj, form, change):
        if not change:
            raw = secrets.token_urlsafe(14)
            obj.set_password(raw)
            obj.must_change_password = True
            super().save_model(request, obj, form, change)
            try:
                send_initial_password_email(user=obj, raw_password=raw, request=request)
                messages.success(
                    request,
                    _("User created. Initial password sent to %(email)s.") % {"email": obj.email},
                )
            except Exception as exc:
                messages.warning(
                    request,
                    _("User created but email failed: %(err)s") % {"err": exc},
                )
        else:
            super().save_model(request, obj, form, change)

    @sensitive_post_parameters_m
    def user_change_password(self, request, id, form_url=""):
        user = self.get_object(request, unquote(id))
        if not self.has_change_permission(request, user):
            raise PermissionDenied
        if user is None:
            raise Http404(
                gettext("%(name)s object with primary key %(key)r does not exist.")
                % {
                    "name": self.opts.verbose_name,
                    "key": escape(id),
                }
            )
        if request.method == "POST":
            form = self.change_password_form(user, request.POST)
            if form.is_valid():
                form.save()
                if user.pk != request.user.pk:
                    User.objects.filter(pk=user.pk).update(must_change_password=True)
                change_message = self.construct_change_message(request, form, None)
                self.log_change(request, user, change_message)
                messages.success(request, gettext("Password changed successfully."))
                update_session_auth_hash(request, form.user)
                return HttpResponseRedirect(
                    reverse(
                        "%s:%s_%s_change"
                        % (
                            self.admin_site.name,
                            user._meta.app_label,
                            user._meta.model_name,
                        ),
                        args=(user.pk,),
                    )
                )
        else:
            form = self.change_password_form(user)

        fieldsets = [(None, {"fields": list(form.base_fields)})]
        admin_form = helpers.AdminForm(form, fieldsets, {})

        from django.contrib.admin.options import IS_POPUP_VAR

        context = {
            "title": _("Change password: %s") % escape(user.get_username()),
            "adminForm": admin_form,
            "form_url": form_url,
            "form": form,
            "is_popup": (IS_POPUP_VAR in request.POST or IS_POPUP_VAR in request.GET),
            "is_popup_var": IS_POPUP_VAR,
            "add": True,
            "change": False,
            "has_delete_permission": False,
            "has_change_permission": True,
            "has_absolute_url": False,
            "opts": self.opts,
            "original": user,
            "save_as": False,
            "show_save": True,
            **self.admin_site.each_context(request),
        }

        request.current_app = self.admin_site.name

        return TemplateResponse(
            request,
            self.change_user_password_template
            or "admin/auth/user/change_password.html",
            context,
        )


from django.contrib.auth import get_user_model as _get_user_model

_User = _get_user_model()
try:
    admin.site.unregister(_User)
except admin.sites.NotRegistered:
    pass
admin.site.register(_User, CustomUserAdmin)
