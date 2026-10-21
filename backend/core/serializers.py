from django.contrib.auth import get_user_model
from rest_framework import serializers
from .models import Activity, Attachment, History, Notification, Profile, Report, ReportTemplate, WorkItem


DEMO_USERNAMES = {'demo_employee', 'demo_reviewer', 'demo_administrator'}


def effective_role(user):
    return 'administrator' if user.is_staff or user.is_superuser or user.profile.role == 'administrator' else user.profile.role


def is_administrator(user):
    return user.is_authenticated and effective_role(user) == 'administrator'


def user_data(user):
    role = effective_role(user)
    return {'id': user.pk, 'name': user.get_full_name() or user.username, 'email': user.email, 'role': role, 'initials': user.profile.initials, 'is_demo': user.username in DEMO_USERNAMES, 'capabilities': {'manage_users': role == 'administrator', 'manage_templates': role == 'administrator', 'review_reports': role in ['reviewer', 'administrator']}}


class ProfileSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='user.get_full_name')
    email = serializers.EmailField(source='user.email')
    initials = serializers.CharField(read_only=True)

    class Meta:
        model = Profile
        fields = ['id', 'full_name', 'email', 'phone', 'department', 'faculty', 'position', 'degree', 'bio', 'employee_id', 'initials', 'experience_years', 'employment_type']
        read_only_fields = ['id', 'department', 'faculty', 'position', 'degree', 'employee_id', 'experience_years', 'employment_type']

    def validate_full_name(self, value):
        if len(value.strip()) < 3 or len(value) > 150:
            raise serializers.ValidationError('Ism kamida 3, ko‘pi bilan 150 belgidan iborat bo‘lsin.')
        return value.strip()

    def update(self, instance, validated_data):
        user_fields = validated_data.pop('user', {})
        full_name = user_fields.pop('get_full_name', None)
        if full_name is not None:
            parts = full_name.split(maxsplit=1)
            instance.user.first_name = parts[0]
            instance.user.last_name = parts[1] if len(parts) > 1 else ''
        if 'email' in user_fields:
            instance.user.email = user_fields['email']
        instance.user.save(update_fields=['first_name', 'last_name', 'email'])
        return super().update(instance, validated_data)


class AttachmentSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = Attachment
        fields = ['id', 'name', 'url', 'size']

    def get_url(self, obj):
        return f'/api/attachments/{obj.pk}/download/'


class ActivitySerializer(serializers.ModelSerializer):
    attachment = AttachmentSerializer(read_only=True)
    attachment_id = serializers.PrimaryKeyRelatedField(source='attachment', queryset=Attachment.objects.all(), allow_null=True, required=False, write_only=True)
    owner_name = serializers.CharField(source='owner.get_full_name', read_only=True)
    owner_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Activity
        fields = ['id', 'title', 'category', 'date', 'description', 'link', 'status', 'attachment', 'attachment_id', 'created_at', 'owner_name', 'owner_id']
        read_only_fields = ['id', 'status', 'created_at', 'owner_name']

    def validate_attachment_id(self, value):
        if value and value.owner_id != self.context['request'].user.pk:
            raise serializers.ValidationError('Faqat o‘zingiz yuklagan faylni tanlang.')
        return value


class HistorySerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source='actor.get_full_name', read_only=True)

    class Meta:
        model = History
        fields = ['id', 'action', 'actor_name', 'comment', 'created_at']


class ReportSerializer(serializers.ModelSerializer):
    activity_ids = serializers.PrimaryKeyRelatedField(source='activities', queryset=Activity.objects.all(), many=True, required=False)
    history = HistorySerializer(many=True, read_only=True)
    owner_name = serializers.CharField(source='owner.get_full_name', read_only=True)
    owner_id = serializers.IntegerField(read_only=True)
    template_id = serializers.SlugRelatedField(queryset=ReportTemplate.objects.filter(is_active=True), slug_field='id', write_only=True, required=False)

    class Meta:
        model = Report
        fields = ['id', 'title', 'type', 'period', 'status', 'activity_ids', 'comment', 'due_date', 'submitted_at', 'created_at', 'updated_at', 'owner_name', 'owner_id', 'history', 'template_id', 'template_version', 'template_snapshot', 'extra_data']
        read_only_fields = ['id', 'status', 'comment', 'submitted_at', 'created_at', 'updated_at', 'owner_name', 'history', 'template_version', 'template_snapshot']

    def validate_activity_ids(self, values):
        if len({v.pk for v in values}) != len(values):
            raise serializers.ValidationError('Bir faoliyatni ikki marta tanlab bo‘lmaydi.')
        if any(value.owner_id != self.context['request'].user.pk for value in values):
            raise serializers.ValidationError('Faqat o‘zingizning faoliyatlaringizni tanlang.')
        return values

    def validate_extra_data(self, value):
        if not isinstance(value, dict) or len(value) > 20:
            raise serializers.ValidationError('Qo‘shimcha maydonlar ko‘pi bilan 20 ta kalitli obyekt bo‘lsin.')
        if any(not isinstance(key, str) or not (val is None or isinstance(val, (str, int, float, bool))) for key, val in value.items()):
            raise serializers.ValidationError('Qo‘shimcha maydonlarda oddiy matn yoki son qiymatlarini kiriting.')
        if any(isinstance(val, str) and len(val) > 5000 for val in value.values()):
            raise serializers.ValidationError('Maydon qiymati 5000 belgidan oshmasin.')
        return value

    def validate(self, attrs):
        template = attrs.get('template_id')
        report_type = attrs.get('type', self.instance.type if self.instance else None)
        if template and template.type != report_type:
            raise serializers.ValidationError({'template_id': 'Shablon turi hisobot turiga mos kelmaydi.'})
        if self.instance and template:
            raise serializers.ValidationError({'template_id': 'Yaratilgan hisobot shablonini almashtirib bo‘lmaydi.'})
        if self.instance and report_type != self.instance.type:
            raise serializers.ValidationError({'type': 'Hisobot turini almashtirish uchun yangi qoralama yarating.'})
        if self.instance is None:
            if template is None:
                template = ReportTemplate.objects.filter(type=report_type, is_active=True).first()
            if template is None:
                raise serializers.ValidationError({'template_id': 'Bu hisobot turi uchun faol shablon mavjud emas. Administratorga murojaat qiling.'})
            attrs['template_id'] = template
        return attrs

    def create(self, validated_data):
        template = validated_data.pop('template_id')
        validated_data['template_version'] = template.version
        validated_data['template_snapshot'] = {'id': template.pk, 'title': template.title, 'description': template.description, 'type': template.type, 'version': template.version, 'fields': template.fields, 'form_schema': template.form_schema}
        return super().create(validated_data)


class WorkItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkItem
        fields = ['id', 'title', 'category', 'target', 'completed', 'due_date']

    def validate(self, attrs):
        target = attrs.get('target', self.instance.target if self.instance else 1)
        completed = attrs.get('completed', self.instance.completed if self.instance else 0)
        if target < 1:
            raise serializers.ValidationError({'target': 'Reja kamida 1 bo‘lishi kerak.'})
        if completed > target:
            raise serializers.ValidationError({'completed': 'Bajarilgan ish reja miqdoridan oshmasin.'})
        return attrs


class NotificationSerializer(serializers.ModelSerializer):
    report_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Notification
        fields = ['id', 'title', 'message', 'read', 'created_at', 'report_id']
