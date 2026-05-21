"""
Shared Django settings. Override via environment variables or local.py.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "django-insecure-dev-only-change-in-production",
)

DEBUG = os.getenv("DEBUG", "True").lower() in ("1", "true", "yes")

ALLOWED_HOSTS = [
    h.strip()
    for h in os.getenv("ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
    if h.strip()
]

INSTALLED_APPS = [
    "simpleui",
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "apps.accounts",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.admin",
    "import_export",
    "apps.finance",
    "apps.audit",
]

AUTH_USER_MODEL = "accounts.User"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.accounts.middleware.ForcePasswordChangeMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Database: SQLite by default; optional PostgreSQL via POSTGRES_* env vars
if os.getenv("POSTGRES_DB"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ["POSTGRES_DB"],
            "USER": os.getenv("POSTGRES_USER", "postgres"),
            "PASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
            "HOST": os.getenv("POSTGRES_HOST", "localhost"),
            "PORT": os.getenv("POSTGRES_PORT", "5432"),
        }
    }
else:
    sqlite_name = os.getenv("SQLITE_PATH", str(BASE_DIR / "db.sqlite3"))
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": sqlite_name,
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "zh-hans"
# 业务记账与报表默认按洛杉矶时间（与运营地一致）
TIME_ZONE = "America/Los_Angeles"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
# 优先于各 app 内 static/，用于覆盖 simpleui 同名资源（如 menu.js）
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# 邮件（新建用户发送初始密码）。开发环境默认打印到控制台。
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True").lower() in ("1", "true", "yes")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "noreply@localhost")
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# django-import-export：导入需 add，导出需 view（与 Django 权限码一致）
IMPORT_EXPORT_IMPORT_PERMISSION_CODE = "add"
IMPORT_EXPORT_EXPORT_PERMISSION_CODE = "view"

LOGIN_REDIRECT_URL = "/admin/"
LOGIN_URL = "/admin/login/"

# django-simpleui：统一后台入口；菜单顺序；首页标题
from config.simpleui_menus import SIMPLEUI_MENU_DISPLAY, get_simpleui_menus

SIMPLEUI_HOME_INFO = False
SIMPLEUI_ANALYSIS = False
SIMPLEUI_DEFAULT_THEME = "admin.lte.css"
SIMPLEUI_HOME_TITLE = "工作台"
SIMPLEUI_HOME_ICON = "el-icon-s-home"
SIMPLEUI_DEFAULT_ICON = False

# 自定义菜单（按业务分组 + 权限过滤）；见 config/simpleui_menus.py
SIMPLEUI_CONFIG = {
    "system_keep": False,
    "menu_display": SIMPLEUI_MENU_DISPLAY,
    "menus": get_simpleui_menus(),
}

# 备用：菜单名 / 模型名 → 图标（自定义 menus 已在各项上指定 icon）
SIMPLEUI_ICON = {
    "财务概览": "fas fa-chart-pie",
    "财务报表": "fas fa-chart-bar",
    "日常记账": "fas fa-book",
    "基础资料": "fas fa-database",
    "应收应付": "fas fa-handshake",
    "银行对账": "fas fa-university",
    "审计中心": "fas fa-clipboard-list",
    "系统管理": "fas fa-cogs",
}

# Python 3.14+：修复 Django 5.0 BaseContext.__copy__ 与 copy(super()) 不兼容（3.11 不加载）
from config.django_py314_context_patch import apply as _apply_django_context_copy_patch

_apply_django_context_copy_patch()
