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

# Hosts always permitted (Cloudflare Tunnel public domain).
_TUNNEL_HOSTS = ("fin.skyvl.com",)

ALLOWED_HOSTS = [
    h.strip()
    for h in os.getenv(
        "ALLOWED_HOSTS",
        "127.0.0.1,localhost,fin.skyvl.com",
    ).split(",")
    if h.strip()
]
for host in _TUNNEL_HOSTS:
    if host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(host)

CSRF_TRUSTED_ORIGINS = [
    o.strip()
    for o in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",")
    if o.strip()
]
if not CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS = [f"https://{host}" for host in _TUNNEL_HOSTS]

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
    "config.middleware.AdminFinanceStaticNoCacheMiddleware",
    "config.middleware.AdminLocaleNoCacheMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.accounts.middleware.SessionInactivityMiddleware",
    "apps.accounts.middleware.ForcePasswordChangeMiddleware",
    "config.middleware.RefreshSimpleuiMenusMiddleware",
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
                "django.template.context_processors.i18n",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "config.context_processors.finance_asset_version",
                "config.context_processors.language_switcher",
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

from django.utils.translation import gettext_lazy as _

LANGUAGE_CODE = "en"
LANGUAGES = [
    ("en", "English"),
    ("zh-hans", "简体中文"),
]
LOCALE_PATHS = [BASE_DIR / "locale"]
# Business reporting uses Los Angeles time.
TIME_ZONE = "America/Los_Angeles"
USE_I18N = True
USE_L10N = True
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

# 会话：连续 1 小时无服务端请求则需重新登录（见 SessionInactivityMiddleware）
SESSION_COOKIE_AGE = int(os.getenv("SESSION_COOKIE_AGE", "3600"))
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
# HTTPS（Cloudflare Tunnel）下应设为 True，可在 .env 中覆盖
_session_secure = os.getenv("SESSION_COOKIE_SECURE", "").strip().lower()
if _session_secure in ("1", "true", "yes"):
    SESSION_COOKIE_SECURE = True
elif _session_secure in ("0", "false", "no"):
    SESSION_COOKIE_SECURE = False
else:
    SESSION_COOKIE_SECURE = not DEBUG

# django-simpleui：统一后台入口；菜单顺序；首页标题
from config.simpleui_menus import SIMPLEUI_MENU_DISPLAY, get_simpleui_menus

SIMPLEUI_HOME_INFO = False
SIMPLEUI_HOME_QUICK = False
SIMPLEUI_ANALYSIS = False
SIMPLEUI_DEFAULT_THEME = "admin.lte.css"
SIMPLEUI_HOME_PAGE = "/admin/finance/dashboard/?home=1"
SIMPLEUI_HOME_TITLE = _("Dashboard")
SIMPLEUI_HOME_ICON = "el-icon-s-home"
SIMPLEUI_DEFAULT_ICON = False

# 自定义菜单（按业务分组 + 权限过滤）；见 config/simpleui_menus.py
SIMPLEUI_CONFIG = {
    "system_keep": False,
    "menu_display": SIMPLEUI_MENU_DISPLAY,
    "menus": get_simpleui_menus(),
}

# Fallback icons by menu label (menus already set icon per item).
SIMPLEUI_ICON = {
    "Overview": "fas fa-chart-pie",
    "Reports": "fas fa-chart-bar",
    "Transactions": "fas fa-book",
    "Master data": "fas fa-database",
    "AR / AP": "fas fa-handshake",
    "Bank reconciliation": "fas fa-university",
    "Audit": "fas fa-clipboard-list",
    "System": "fas fa-cogs",
}

# Python 3.14+：修复 Django 5.0 BaseContext.__copy__ 与 copy(super()) 不兼容（3.11 不加载）
from config.django_py314_context_patch import apply as _apply_django_context_copy_patch

_apply_django_context_copy_patch()
