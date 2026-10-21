from django.contrib import admin
from django.urls import include, path
from .health import readiness

urlpatterns = [path('healthz', readiness), path('admin/', admin.site.urls), path('api/', include('core.urls'))]
