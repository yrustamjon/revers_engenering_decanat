import hashlib
import json
import math
from datetime import date
from pathlib import Path
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.core.cache import cache
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import URLValidator
from django.db import transaction
from django.db.models import Q
from django.http import FileResponse, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from .models import Activity, Attachment, History, Notification, Report, ReportTemplate, WorkItem
from .serializers import ActivitySerializer, AttachmentSerializer, NotificationSerializer, ProfileSerializer, ReportSerializer, WorkItemSerializer, effective_role, is_administrator, user_data
from .admin_api import TemplateSerializer


@ensure_csrf_cookie
@require_GET
def session_view(request):
    if not request.user.is_authenticated:
        return JsonResponse({'detail': 'Tizimga kiring.'}, status=401)
    return JsonResponse({'user': user_data(request.user)})


def json_body(request):
    try:
        value = json.loads(request.body or '{}')
        return value if isinstance(value, dict) else {}
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}


@require_POST
@csrf_protect
def demo_login(request):
    if not settings.DEBUG:
        return JsonResponse({'detail': 'Topilmadi.'}, status=404)
    role = json_body(request).get('role', 'employee')
    if role not in ['employee', 'reviewer', 'administrator']:
        return JsonResponse({'role': ['Noto‘g‘ri rol.']}, status=400)
    user = get_user_model().objects.filter(username=f'demo_{role}', is_active=True).first()
    if not user:
        return JsonResponse({'detail': 'Demo ma’lumotlari o‘rnatilmagan. seed_demo buyrug‘ini bajaring.'}, status=503)
    login(request, user)
    return JsonResponse({'user': user_data(user)})


@require_POST
@csrf_protect
def login_view(request):
    body = json_body(request)
    ip = request.META.get('REMOTE_ADDR', 'unknown')
    username = body.get('username', '')
    password = body.get('password', '')
    ip_key = 'login-ip:' + hashlib.sha256(ip.encode()).hexdigest()
    if cache.get(ip_key, 0) >= 100:
        return JsonResponse({'detail': 'Urinishlar ko‘p. 5 daqiqadan keyin qayta urinib ko‘ring.'}, status=429)
    if cache.add(ip_key, 1, timeout=300) is False:
        cache.incr(ip_key)
    if not isinstance(username, str) or len(username) > 150 or not isinstance(password, str) or len(password) > 128:
        return JsonResponse({'detail': 'Login yoki parol formati noto‘g‘ri.'}, status=400)
    username = username.strip()
    key = 'login-attempt:' + hashlib.sha256(f'{ip}\0{username.casefold()}'.encode()).hexdigest()
    if cache.get(key, 0) >= 10:
        return JsonResponse({'detail': 'Urinishlar ko‘p. 5 daqiqadan keyin qayta urinib ko‘ring.'}, status=429)
    user = authenticate(request, username=username, password=password)
    if user is None:
        if cache.add(key, 1, timeout=300) is False:
            cache.incr(key)
        return JsonResponse({'detail': 'Login yoki parol noto‘g‘ri.'}, status=401)
    cache.delete(key)
    login(request, user)
    return JsonResponse({'user': user_data(user)})


@require_POST
@csrf_protect
def logout_view(request):
    logout(request)
    return HttpResponse(status=204)


def reviewer_reports(user):
    if is_administrator(user):
        return Report.objects.filter(status__in=['submitted', 'returned', 'approved']).exclude(owner=user)
    if user.profile.role != 'reviewer' or not user.profile.department:
        return Report.objects.none()
    return Report.objects.filter(owner__profile__department=user.profile.department, status__in=['submitted', 'returned', 'approved']).exclude(owner=user)


def accessible_reports(user):
    if is_administrator(user):
        return Report.objects.all()
    # Keep the outer query free of DISTINCT: PostgreSQL cannot lock a DISTINCT
    # result when an employee submits a report with SELECT ... FOR UPDATE.
    return Report.objects.filter(Q(owner=user) | Q(pk__in=reviewer_reports(user).values('pk')))


def validate_report_extra_data(report):
    schema = report.template_snapshot.get('form_schema', [])
    values = report.extra_data
    errors = {}
    allowed = {field['key'] for field in schema}
    for key in values.keys() - allowed:
        errors[key] = ['Bu maydon hisobot shablonida mavjud emas.']
    for field in schema:
        key, label, kind = field['key'], field['label'], field['type']
        value = values.get(key)
        missing = value is None or (isinstance(value, str) and not value.strip())
        if missing:
            if field.get('required', False):
                errors[key] = [f'{label}: bu maydonni to‘ldiring.']
            continue
        if kind in ['text', 'textarea'] and not isinstance(value, str):
            errors[key] = [f'{label}: matn kiriting.']
        elif kind == 'number':
            try:
                valid = not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)
            except OverflowError:
                valid = False
            if not valid:
                errors[key] = [f'{label}: son kiriting.']
        elif kind == 'date':
            try:
                if not isinstance(value, str):
                    raise ValueError()
                if date.fromisoformat(value).isoformat() != value:
                    raise ValueError()
            except (ValueError, TypeError):
                errors[key] = [f'{label}: sanani YYYY-MM-DD formatida kiriting.']
        elif kind == 'url':
            try:
                if not isinstance(value, str):
                    raise DjangoValidationError('Invalid URL')
                URLValidator(schemes=['http', 'https'])(value)
            except DjangoValidationError:
                errors[key] = [f'{label}: http yoki https havola kiriting.']
    return errors


@api_view(['GET'])
def workspace(request):
    user = request.user
    reports = accessible_reports(user).select_related('owner').prefetch_related('activities', 'history__actor')
    if is_administrator(user):
        activities = Activity.objects.all()
    elif user.profile.role == 'reviewer':
        activities = Activity.objects.filter(Q(reports__in=reports) | Q(owner=user)).distinct()
    else:
        activities = Activity.objects.filter(owner=user)
    return Response({
        'user': user_data(user),
        'profile': ProfileSerializer(user.profile).data,
        'activities': ActivitySerializer(activities.select_related('owner', 'attachment').distinct(), many=True).data,
        'reports': ReportSerializer(reports, many=True).data,
        'work_items': WorkItemSerializer(user.work_items.all(), many=True).data,
        'notifications': NotificationSerializer(user.notifications.all()[:50], many=True).data,
        'templates': TemplateSerializer(ReportTemplate.objects.filter(is_active=True), many=True).data,
    })


@api_view(['GET', 'PATCH'])
def profile(request):
    serializer = ProfileSerializer(request.user.profile, data=request.data, partial=True) if request.method == 'PATCH' else ProfileSerializer(request.user.profile)
    if request.method == 'PATCH':
        serializer.is_valid(raise_exception=True)
        serializer.save()
    return Response(serializer.data)


class ActivityViewSet(viewsets.ModelViewSet):
    serializer_class = ActivitySerializer
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        return Activity.objects.filter(owner=self.request.user).select_related('owner', 'attachment')

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user, status='draft')

    def ensure_editable(self, instance):
        if instance.reports.filter(status__in=['submitted', 'approved']).exists():
            raise ValidationError({'detail': 'Faoliyat tekshiruvdagi yoki tasdiqlangan hisobotga biriktirilgan. Uni o‘zgartirib bo‘lmaydi.'})

    @transaction.atomic
    def perform_update(self, serializer):
        instance = Activity.objects.select_for_update().get(pk=serializer.instance.pk)
        self.ensure_editable(instance)
        serializer.save(status='draft')

    @transaction.atomic
    def perform_destroy(self, instance):
        instance = Activity.objects.select_for_update().get(pk=instance.pk)
        self.ensure_editable(instance)
        instance.delete()


class ReportViewSet(viewsets.ModelViewSet):
    serializer_class = ReportSerializer
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        return accessible_reports(self.request.user).select_related('owner').prefetch_related('activities', 'history__actor')

    def perform_create(self, serializer):
        report = serializer.save(owner=self.request.user, status='draft')
        History.objects.create(report=report, actor=self.request.user, action='created', comment='Hisobot qoralamasi yaratildi.')

    def check_owner_editable(self, report):
        if report.owner_id != self.request.user.pk:
            raise PermissionDenied('Faqat muallif hisobotni tahrirlashi mumkin.')
        if report.status not in ['draft', 'returned']:
            raise ValidationError({'status': 'Tekshiruvdagi yoki tasdiqlangan hisobotni o‘zgartirib bo‘lmaydi.'})

    @transaction.atomic
    def perform_update(self, serializer):
        report = Report.objects.select_for_update().get(pk=serializer.instance.pk)
        self.check_owner_editable(report)
        serializer.save()
        History.objects.create(report=report, actor=self.request.user, action='updated', comment='Hisobot ma’lumotlari yangilandi.')

    @transaction.atomic
    def perform_destroy(self, instance):
        report = Report.objects.select_for_update().get(pk=instance.pk)
        self.check_owner_editable(report)
        report.delete()

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def submit(self, request, pk=None):
        report = get_object_or_404(self.get_queryset().select_for_update(), pk=pk)
        self.check_owner_editable(report)
        activities = list(report.activities.select_for_update().all())
        errors = {}
        if not report.title.strip():
            errors['title'] = ['Hisobot nomini kiriting.']
        if not report.period.strip():
            errors['period'] = ['Hisobot davrini kiriting.']
        if not activities:
            errors['activity_ids'] = ['Kamida bitta faoliyatni biriktiring.']
        without_evidence = [a.title for a in activities if not a.attachment_id and not a.link]
        if without_evidence:
            errors['activity_ids'] = ['Tasdiqlovchi fayl yoki havola yetishmaydi: ' + ', '.join(without_evidence)]
        if not report.template_version or not isinstance(report.template_snapshot, dict) or not report.template_snapshot:
            errors['template_id'] = ['Hisobot shabloni saqlanmagan. Faol shablon asosida yangi qoralama yarating.']
        else:
            extra_errors = validate_report_extra_data(report)
            if extra_errors:
                errors['extra_data'] = extra_errors
        if errors:
            raise ValidationError(errors)
        report.status = 'submitted'
        report.submitted_at = timezone.now()
        report.save(update_fields=['status', 'submitted_at', 'updated_at'])
        History.objects.create(report=report, actor=request.user, action='submitted', comment='Hisobot tekshiruvga yuborildi.')
        reviewers = get_user_model().objects.filter(is_active=True).filter(Q(profile__role='reviewer', profile__department=request.user.profile.department) | Q(profile__role='administrator') | Q(is_staff=True) | Q(is_superuser=True)).exclude(pk=request.user.pk).distinct()
        Notification.objects.bulk_create([Notification(owner=u, report=report, title='Yangi hisobot tekshiruvga keldi', message=f'{request.user.get_full_name()}: {report.title}') for u in reviewers])
        return Response(ReportSerializer(report).data)

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def review(self, request, pk=None):
        if effective_role(request.user) not in ['reviewer', 'administrator']:
            raise PermissionDenied('Tekshiruvchi vakolati kerak.')
        report = get_object_or_404(reviewer_reports(request.user).select_for_update(), pk=pk)
        if report.status != 'submitted':
            raise ValidationError({'status': 'Faqat tekshiruvdagi hisobot bo‘yicha qaror berish mumkin.'})
        decision = request.data.get('decision')
        comment = str(request.data.get('comment', '')).strip()
        if decision not in ['approved', 'returned']:
            raise ValidationError({'decision': 'approved yoki returned qiymatini tanlang.'})
        if decision == 'returned' and len(comment) < 5:
            raise ValidationError({'comment': 'Qaytarish sababini kamida 5 belgi bilan tushuntiring.'})
        if len(comment) > 5000:
            raise ValidationError({'comment': 'Izoh 5000 belgidan oshmasin.'})
        report.status = decision
        report.comment = comment
        report.save(update_fields=['status', 'comment', 'updated_at'])
        History.objects.create(report=report, actor=request.user, action=decision, comment=comment)
        if decision == 'approved':
            report.activities.update(status='verified')
        Notification.objects.create(owner=report.owner, report=report, title='Hisobot tasdiqlandi' if decision == 'approved' else 'Hisobot tuzatishga qaytarildi', message=comment or report.title)
        return Response(ReportSerializer(report).data)


class WorkItemViewSet(viewsets.ModelViewSet):
    serializer_class = WorkItemSerializer
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        return WorkItem.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


@api_view(['POST'])
def upload_attachment(request):
    if not settings.UPLOADS_ENABLED:
        return Response({'detail': 'Fayl saqlash xizmati hali sozlanmagan. Hozircha manba havolasidan foydalaning.'}, status=503)
    file = request.FILES.get('file')
    if file is None:
        raise ValidationError({'file': 'Faylni tanlang.'})
    if not file.size or file.size > 20 * 1024 * 1024:
        raise ValidationError({'file': 'Fayl bo‘sh bo‘lmasin va 20 MB dan oshmasin.'})
    if Path(file.name).suffix.lower() not in ['.pdf', '.doc', '.docx', '.xlsx', '.png', '.jpg', '.jpeg', '.txt']:
        raise ValidationError({'file': 'PDF, Word, Excel, JPG, PNG yoki TXT fayl yuklang.'})
    attachment = Attachment.objects.create(owner=request.user, file=file, name=Path(file.name).name[:255], size=file.size)
    return Response(AttachmentSerializer(attachment).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
def download_attachment(request, pk):
    attachment = get_object_or_404(Attachment, pk=pk)
    can_review = is_administrator(request.user) or Activity.objects.filter(attachment=attachment, reports__in=reviewer_reports(request.user)).exists()
    if attachment.owner_id != request.user.pk and not can_review:
        raise PermissionDenied('Bu faylni ko‘rishga ruxsat yo‘q.')
    try:
        response = FileResponse(attachment.file.open('rb'), as_attachment=True, filename=attachment.name)
    except FileNotFoundError:
        return Response({'detail': 'Fayl saqlash joyida topilmadi.'}, status=404)
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@api_view(['POST'])
def read_notification(request, pk):
    notification = get_object_or_404(Notification, pk=pk, owner=request.user)
    notification.read = True
    notification.save(update_fields=['read'])
    return Response(NotificationSerializer(notification).data)
