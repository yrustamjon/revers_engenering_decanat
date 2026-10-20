from django.urls import include, path
from rest_framework.routers import DefaultRouter
from . import admin_api, views

router = DefaultRouter()
router.register('activities', views.ActivityViewSet, basename='activity')
router.register('reports', views.ReportViewSet, basename='report')
router.register('work-items', views.WorkItemViewSet, basename='work-item')
router.register('admin/users', admin_api.InstitutionUserViewSet, basename='admin-user')
router.register('admin/departments', admin_api.DepartmentViewSet, basename='admin-department')
router.register('admin/templates', admin_api.TemplateViewSet, basename='admin-template')
urlpatterns = [
    path('auth/session/', views.session_view),
    path('auth/demo/', views.demo_login),
    path('auth/login/', views.login_view),
    path('auth/logout/', views.logout_view),
    path('auth/password/', admin_api.change_password),
    path('workspace/', views.workspace),
    path('profile/', views.profile),
    path('attachments/', views.upload_attachment),
    path('attachments/<int:pk>/download/', views.download_attachment),
    path('notifications/<int:pk>/read/', views.read_notification),
    path('', include(router.urls)),
]
