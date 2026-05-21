from django import forms
from django.contrib.admin.forms import AdminAuthenticationForm, AdminPasswordChangeForm
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserChangeForm
from django.utils.translation import gettext_lazy as _

User = get_user_model()


class EmailAdminAuthenticationForm(AdminAuthenticationForm):
    """后台登录：字段名仍为 username，标签为「邮箱」，值为邮箱地址。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = _("邮箱")


class ClearMustChangePasswordForm(AdminPasswordChangeForm):
    """用户修改自身密码成功后，清除「须修改密码」标记。"""

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit and user.must_change_password:
            user.must_change_password = False
            user.save(update_fields=["must_change_password"])
        return user


class StaffUserAddForm(forms.ModelForm):
    """管理员新建用户：仅需邮箱与基本信息，密码由系统生成并发邮件。"""

    class Meta:
        model = User
        fields = (
            "email",
            "first_name",
            "last_name",
            "is_active",
            "is_staff",
            "groups",
        )

    def __init__(self, *args, user=None, **kwargs):
        self._current_user = user
        super().__init__(*args, **kwargs)


class StaffUserAddFormSuperuser(StaffUserAddForm):
    class Meta(StaffUserAddForm.Meta):
        fields = StaffUserAddForm.Meta.fields + ("is_superuser", "user_permissions")

    def clean_email(self):
        email = User.objects.normalize_email(self.cleaned_data.get("email", ""))
        if not email:
            raise forms.ValidationError(_("请输入有效邮箱。"))
        return email


class EmailUserChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "username" in self.fields:
            del self.fields["username"]
