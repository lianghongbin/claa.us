from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError(_("必须提供电子邮箱地址"))
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        extra_fields.setdefault("must_change_password", True)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields["must_change_password"] = False
        if not extra_fields.get("is_staff"):
            raise ValueError(_("超级用户必须 is_staff=True"))
        if not extra_fields.get("is_superuser"):
            raise ValueError(_("超级用户必须 is_superuser=True"))
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    username = None
    email = models.EmailField(_("电子邮箱"), unique=True)
    must_change_password = models.BooleanField(
        _("首次登录须修改密码"),
        default=True,
        help_text=_("由管理员新建用户时为 True；用户自行修改密码成功后清除。"),
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        verbose_name = _("用户")
        verbose_name_plural = _("用户")

    def __str__(self) -> str:
        return self.email
