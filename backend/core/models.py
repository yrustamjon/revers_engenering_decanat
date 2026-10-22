import uuid
from pathlib import Path
from django.conf import settings
from django.db import models
from django.db.models.functions import Lower


class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=[('employee', 'Employee'), ('reviewer', 'Reviewer'), ('administrator', 'Administrator')], default='employee')
    phone = models.CharField(max_length=40, blank=True)
    department = models.CharField(max_length=180, blank=True)
    faculty = models.CharField(max_length=180, blank=True)
    position = models.CharField(max_length=120, blank=True)
    degree = models.CharField(max_length=120, blank=True)
    bio = models.TextField(blank=True, max_length=2000)
    employee_id = models.CharField(max_length=30, blank=True)
    experience_years = models.PositiveSmallIntegerField(default=0)
    employment_type = models.CharField(max_length=80, default="Asosiy ish joyi · 1 stavka")

    class Meta:
        constraints = [models.UniqueConstraint(Lower('employee_id'), condition=~models.Q(employee_id=''), name='unique_nonblank_employee_id')]

    @property
    def initials(self):
        return ''.join(p[0] for p in (self.user.get_full_name() or self.user.username).split()[:2]).upper()


def attachment_path(instance, filename):
    return f'{instance.owner_id}/{uuid.uuid4().hex}{Path(filename).suffix.lower()}'


class Attachment(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    file = models.FileField(upload_to=attachment_path)
    name = models.CharField(max_length=255)
    size = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)


class Activity(models.Model):
    CATEGORIES = [('article', 'Maqola'), ('conference', 'Konferensiya'), ('certificate', 'Sertifikat'), ('teaching', "O‘quv-uslubiy ish"), ('project', 'Loyiha')]
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='activities')
    title = models.CharField(max_length=240)
    category = models.CharField(max_length=20, choices=CATEGORIES)
    date = models.DateField()
    description = models.TextField(blank=True, max_length=5000)
    link = models.URLField(blank=True, max_length=600)
    status = models.CharField(max_length=20, choices=[('draft', 'Draft'), ('verified', 'Verified')], default='draft')
    attachment = models.ForeignKey(Attachment, on_delete=models.PROTECT, null=True, blank=True, related_name='activities')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-id']


class Report(models.Model):
    TYPES = [('scientific', 'Ilmiy faoliyat'), ('annual', 'Yillik hisobot'), ('teaching', "O‘quv-uslubiy"), ('qualification', 'Malaka oshirish')]
    STATUSES = [('draft', 'Qoralama'), ('submitted', 'Tekshiruvda'), ('returned', 'Tuzatish kerak'), ('approved', 'Tasdiqlangan')]
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reports')
    title = models.CharField(max_length=240)
    type = models.CharField(max_length=20, choices=TYPES)
    period = models.CharField(max_length=80)
    status = models.CharField(max_length=20, choices=STATUSES, default='draft')
    activities = models.ManyToManyField(Activity, related_name='reports', blank=True)
    comment = models.TextField(blank=True)
    due_date = models.DateField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    template_version = models.CharField(max_length=30, blank=True)
    template_snapshot = models.JSONField(default=dict, blank=True)
    extra_data = models.JSONField(default=dict, blank=True)
    review_department = models.CharField(max_length=180, blank=True)

    class Meta:
        ordering = ['-updated_at', '-id']


class History(models.Model):
    report = models.ForeignKey(Report, on_delete=models.CASCADE, related_name='history')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=30)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'id']


class Submission(models.Model):
    report = models.ForeignKey(Report, on_delete=models.PROTECT, related_name='submissions')
    number = models.PositiveIntegerField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    snapshot = models.JSONField()
    attachments = models.ManyToManyField(Attachment, related_name='submissions', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['number']
        constraints = [models.UniqueConstraint(fields=['report', 'number'], name='unique_report_submission')]


class AuditEvent(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=40)
    resource = models.CharField(max_length=80)
    object_id = models.CharField(max_length=100)
    before = models.JSONField(default=dict)
    after = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at', '-id']


class WorkItem(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='work_items')
    title = models.CharField(max_length=240)
    category = models.CharField(max_length=20, choices=Activity.CATEGORIES)
    target = models.PositiveIntegerField(default=1)
    completed = models.PositiveIntegerField(default=0)
    due_date = models.DateField()

    class Meta:
        ordering = ['due_date', 'id']


class Notification(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    report = models.ForeignKey(Report, on_delete=models.CASCADE, null=True, blank=True)
    title = models.CharField(max_length=180)
    message = models.TextField()
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']


class Department(models.Model):
    name = models.CharField(max_length=180, unique=True)
    faculty = models.CharField(max_length=180)
    head_name = models.CharField(max_length=150, blank=True)

    class Meta:
        ordering = ['name', 'id']
        constraints = [models.UniqueConstraint(Lower('name'), name='unique_department_name_casefold')]


class ReportTemplate(models.Model):
    id = models.SlugField(primary_key=True, max_length=80)
    title = models.CharField(max_length=160)
    description = models.TextField(max_length=1000)
    type = models.CharField(max_length=20, choices=Report.TYPES)
    version = models.CharField(max_length=30, default='1.0')
    fields = models.JSONField(default=list)
    form_schema = models.JSONField(default=list, blank=True)
    icon = models.CharField(max_length=60, default='BookOpen')
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at', 'id']
