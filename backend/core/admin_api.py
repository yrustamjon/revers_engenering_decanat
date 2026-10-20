from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Q
from rest_framework import serializers, viewsets
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from .models import Department, Profile, ReportTemplate
from .serializers import DEMO_USERNAMES, effective_role, is_administrator


class IsInstitutionAdministrator(BasePermission):
    message = 'Administrator vakolati kerak.'

    def has_permission(self, request, view):
        return is_administrator(request.user)


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ['id', 'name', 'faculty', 'head_name']

    def validate_name(self, value):
        value = value.strip()
        matches = Department.objects.filter(name__iexact=value)
        if self.instance:
            matches = matches.exclude(pk=self.instance.pk)
        if matches.exists():
            raise serializers.ValidationError('Bu nomdagi bo‘lim mavjud.')
        return value

    @transaction.atomic
    def update(self, instance, validated_data):
        old_name = instance.name
        instance = super().update(instance, validated_data)
        Profile.objects.filter(department=old_name).update(department=instance.name, faculty=instance.faculty)
        return instance


class SchemaFieldSerializer(serializers.Serializer):
    key = serializers.RegexField(r'^[a-z][a-z0-9_]{0,49}$')
    label = serializers.CharField(max_length=120)
    type = serializers.ChoiceField(choices=['text', 'textarea', 'number', 'date', 'url'])
    required = serializers.BooleanField(default=False)


class TemplateSerializer(serializers.ModelSerializer):
    fields = serializers.ListField(child=serializers.CharField(max_length=120), min_length=1, max_length=20)
    form_schema = SchemaFieldSerializer(many=True, required=False)

    class Meta:
        model = ReportTemplate
        fields = ['id', 'title', 'description', 'type', 'version', 'fields', 'form_schema', 'icon', 'is_active']

    def validate(self, attrs):
        if self.instance:
            if 'id' in attrs and attrs['id'] != self.instance.pk:
                raise serializers.ValidationError({'id': 'Shablon identifikatorini o‘zgartirib bo‘lmaydi.'})
            content_changed = any(key in attrs and attrs[key] != getattr(self.instance, key) for key in ['title', 'description', 'type', 'fields', 'form_schema', 'icon'])
            if content_changed and attrs.get('version', self.instance.version) == self.instance.version:
                raise serializers.ValidationError({'version': 'Shablon mazmuni o‘zgarsa, yangi versiyani kiriting.'})
        if len(set(attrs.get('fields', []))) != len(attrs.get('fields', [])):
            raise serializers.ValidationError({'fields': 'Maydon nomlari takrorlanmasin.'})
        schema = attrs.get('form_schema', [])
        if len(schema) > 20:
            raise serializers.ValidationError({'form_schema': 'Ko‘pi bilan 20 ta qo‘shimcha maydon kiriting.'})
        keys = [field['key'] for field in schema]
        if len(set(keys)) != len(keys):
            raise serializers.ValidationError({'form_schema': 'Qo‘shimcha maydon kalitlari takrorlanmasin.'})
        return attrs


class InstitutionUserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='get_full_name', max_length=150)
    email = serializers.EmailField(max_length=254)
    role = serializers.ChoiceField(source='profile.role', choices=['employee', 'reviewer', 'administrator'], default='employee')
    department = serializers.CharField(source='profile.department', max_length=180, allow_blank=True, required=False)
    faculty = serializers.CharField(source='profile.faculty', read_only=True)
    position = serializers.CharField(source='profile.position', max_length=120, allow_blank=True, required=False)
    degree = serializers.CharField(source='profile.degree', max_length=120, allow_blank=True, required=False)
    employee_id = serializers.CharField(source='profile.employee_id', max_length=30, allow_blank=True, required=False)
    employment_type = serializers.CharField(source='profile.employment_type', max_length=80, allow_blank=True, required=False)
    experience_years = serializers.IntegerField(source='profile.experience_years', min_value=0, max_value=70, required=False)
    password = serializers.CharField(write_only=True, required=False, trim_whitespace=False, max_length=128)
    is_demo = serializers.SerializerMethodField()

    class Meta:
        model = get_user_model()
        fields = ['id', 'username', 'full_name', 'email', 'role', 'department', 'faculty', 'position', 'degree', 'employee_id', 'employment_type', 'experience_years', 'is_active', 'password', 'is_demo']
        read_only_fields = ['id']

    def get_is_demo(self, obj):
        return obj.username in DEMO_USERNAMES

    def to_representation(self, instance):
        result = super().to_representation(instance)
        result['role'] = effective_role(instance)
        return result

    def validate_full_name(self, value):
        if len(value.strip()) < 3:
            raise serializers.ValidationError('Ism kamida 3 belgidan iborat bo‘lsin.')
        return value.strip()

    def validate(self, attrs):
        profile_data = attrs.get('profile', {})
        role = profile_data.get('role', effective_role(self.instance) if self.instance else 'employee')
        department = profile_data.get('department', self.instance.profile.department if self.instance else '')
        if department and not Department.objects.filter(name=department).exists():
            raise serializers.ValidationError({'department': 'Mavjud bo‘limni tanlang.'})
        if role == 'reviewer' and not department:
            raise serializers.ValidationError({'department': 'Tekshiruvchi uchun bo‘limni tanlang.'})
        employee_id = profile_data.get('employee_id', '')
        if employee_id:
            others = Profile.objects.filter(employee_id__iexact=employee_id)
            if self.instance:
                others = others.exclude(user=self.instance)
            if others.exists():
                raise serializers.ValidationError({'employee_id': 'Bu xodim raqami band.'})
        if not self.instance and 'password' not in attrs:
            raise serializers.ValidationError({'password': 'Yangi hisob uchun parol kiriting.'})
        if self.instance and self.instance.username in DEMO_USERNAMES:
            if 'username' in attrs and attrs['username'] != self.instance.username:
                raise serializers.ValidationError({'username': 'Demo hisob loginini o‘zgartirib bo‘lmaydi.'})
            if 'password' in attrs:
                raise serializers.ValidationError({'password': 'Demo hisob uchun parol o‘rnatilmaydi. Yangi haqiqiy hisob yarating.'})
        if 'password' in attrs:
            prospective = get_user_model()(username=attrs.get('username', self.instance.username if self.instance else ''), email=attrs.get('email', self.instance.email if self.instance else ''))
            try:
                validate_password(attrs['password'], prospective)
            except DjangoValidationError as error:
                raise serializers.ValidationError({'password': error.messages})
        if self.instance and self.instance.is_superuser and role != 'administrator':
            raise serializers.ValidationError({'role': 'Superuser vakolati ushbu interfeysdan o‘zgartirilmaydi.'})
        if self.instance and effective_role(self.instance) == 'administrator' and (role != 'administrator' or not attrs.get('is_active', self.instance.is_active)):
            admins = get_user_model().objects.filter(is_active=True).filter(Q(is_staff=True) | Q(is_superuser=True) | Q(profile__role='administrator')).exclude(pk=self.instance.pk)
            if not admins.exists():
                raise serializers.ValidationError({'role': 'Oxirgi faol administratorni o‘chirib yoki lavozimini pasaytirib bo‘lmaydi.'})
        return attrs

    def apply_profile(self, user, data):
        profile = user.profile
        profile.role = effective_role(user)
        for key, value in data.items():
            setattr(profile, key, value)
        if 'department' in data:
            department = Department.objects.filter(name=data['department']).first()
            profile.faculty = department.faculty if department else ''
        profile.save()
        user.is_staff = profile.role == 'administrator' or user.is_superuser
        user.save(update_fields=['is_staff'])

    @transaction.atomic
    def create(self, validated_data):
        profile_data = validated_data.pop('profile', {})
        full_name = validated_data.pop('get_full_name')
        password = validated_data.pop('password')
        parts = full_name.split(maxsplit=1)
        user = get_user_model().objects.create_user(first_name=parts[0], last_name=parts[1] if len(parts) > 1 else '', password=password, **validated_data)
        self.apply_profile(user, profile_data)
        return user

    @transaction.atomic
    def update(self, instance, validated_data):
        profile_data = validated_data.pop('profile', {})
        full_name = validated_data.pop('get_full_name', None)
        password = validated_data.pop('password', None)
        if full_name is not None:
            parts = full_name.split(maxsplit=1)
            instance.first_name = parts[0]
            instance.last_name = parts[1] if len(parts) > 1 else ''
        for key, value in validated_data.items():
            setattr(instance, key, value)
        if password is not None:
            instance.set_password(password)
        instance.save()
        self.apply_profile(instance, profile_data)
        return instance


class InstitutionUserViewSet(viewsets.ModelViewSet):
    permission_classes = [IsInstitutionAdministrator]
    serializer_class = InstitutionUserSerializer
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_queryset(self):
        return get_user_model().objects.select_related('profile').order_by('last_name', 'first_name', 'id')

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        # Serialize privilege changes so two concurrent updates cannot remove the last administrator.
        list(get_user_model().objects.select_for_update().filter(is_active=True).values_list('pk', flat=True))
        return super().update(request, *args, **kwargs)


class DepartmentViewSet(viewsets.ModelViewSet):
    permission_classes = [IsInstitutionAdministrator]
    serializer_class = DepartmentSerializer
    queryset = Department.objects.all()
    http_method_names = ['get', 'post', 'patch', 'head', 'options']


class TemplateViewSet(viewsets.ModelViewSet):
    permission_classes = [IsInstitutionAdministrator]
    serializer_class = TemplateSerializer
    queryset = ReportTemplate.objects.all()
    http_method_names = ['get', 'post', 'patch', 'head', 'options']


@api_view(['POST'])
def change_password(request):
    if request.user.username in DEMO_USERNAMES:
        raise PermissionDenied('Demo hisob parolini o‘zgartirib bo‘lmaydi. Haqiqiy hisob yarating.')
    current = request.data.get('current_password', '')
    password = request.data.get('new_password', '')
    if not isinstance(current, str) or not request.user.check_password(current):
        raise ValidationError({'current_password': 'Joriy parol noto‘g‘ri.'})
    if not isinstance(password, str) or len(password) > 128:
        raise ValidationError({'new_password': 'Parol 128 belgidan oshmasin.'})
    if password == current:
        raise ValidationError({'new_password': 'Yangi parol joriy paroldan farq qilsin.'})
    try:
        validate_password(password, request.user)
    except DjangoValidationError as error:
        raise ValidationError({'new_password': error.messages})
    request.user.set_password(password)
    request.user.save(update_fields=['password'])
    update_session_auth_hash(request, request.user)
    return Response(status=204)
