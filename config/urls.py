"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from apps.accounts.views import staff_password_change, staff_password_change_done

admin.site.site_header = "轻量财务管理系统"
admin.site.site_title = "财务管理"

urlpatterns = [
    path("", RedirectView.as_view(url="/admin/", permanent=False), name="home"),
    path(
        "admin/password_change/",
        admin.site.admin_view(staff_password_change),
    ),
    path(
        "admin/password_change/done/",
        admin.site.admin_view(staff_password_change_done),
    ),
    path("admin/finance/", include("apps.finance.urls")),
    path("admin/", admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
