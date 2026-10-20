from django.contrib import admin
from .models import Activity, Attachment, Department, History, Notification, Profile, Report, ReportTemplate, WorkItem

admin.site.register([Profile, Activity, Attachment, History, Notification, Report, WorkItem, Department, ReportTemplate])
