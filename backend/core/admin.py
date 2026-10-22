from django.contrib import admin
from .models import Activity, Attachment, Department, History, Notification, Profile, Report, ReportTemplate, WorkItem
from .models import AuditEvent, Submission


@admin.register(AuditEvent, Submission)
class ReadOnlyEvidenceAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

admin.site.register([Profile, Activity, Attachment, History, Notification, Report, WorkItem, Department, ReportTemplate])
