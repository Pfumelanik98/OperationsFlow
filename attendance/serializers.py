from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import serializers

from .models import (
    AttendanceCorrection,
    AttendanceRecord,
    LeaveRequest,
    PublicHoliday,
    WorkSchedule,
)

User = get_user_model()


class AttendanceSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    recorded_by_name = serializers.SerializerMethodField()
    approved_by_name = serializers.SerializerMethodField()
    worked_minutes = serializers.SerializerMethodField()

    class Meta:
        model = AttendanceRecord
        fields = [
            "id",
            "employee",
            "employee_name",
            "work_date",
            "check_in",
            "check_out",
            "worked_minutes",
            "status",
            "is_remote",
            "source",
            "recorded_by",
            "recorded_by_name",
            "approved_by",
            "approved_by_name",
            "approved_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_employee_name(self, obj):
        return obj.employee.get_full_name() or obj.employee.username

    def get_recorded_by_name(self, obj):
        if obj.recorded_by:
            return obj.recorded_by.get_full_name() or obj.recorded_by.username
        return None

    def get_approved_by_name(self, obj):
        if obj.approved_by:
            return obj.approved_by.get_full_name() or obj.approved_by.username
        return None

    def get_worked_minutes(self, obj):
        if obj.check_in and obj.check_out:
            return int((obj.check_out - obj.check_in).total_seconds() // 60)
        return None


class AttendanceManualCreateSerializer(serializers.ModelSerializer):
    employee = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    correction_reason = serializers.CharField(write_only=True, allow_blank=False)

    class Meta:
        model = AttendanceRecord
        fields = [
            "employee",
            "work_date",
            "check_in",
            "check_out",
            "status",
            "is_remote",
            "correction_reason",
        ]

    def validate(self, attrs):
        check_in = attrs.get("check_in")
        check_out = attrs.get("check_out")
        if check_in and check_out and check_out <= check_in:
            raise serializers.ValidationError(
                {"check_out": "Check-out must be later than check-in."}
            )
        return attrs


class AttendanceCorrectionSerializer(serializers.ModelSerializer):
    correction_reason = serializers.CharField(write_only=True, allow_blank=False)

    class Meta:
        model = AttendanceRecord
        fields = [
            "check_in",
            "check_out",
            "status",
            "is_remote",
            "correction_reason",
        ]

    def validate(self, attrs):
        check_in = attrs.get("check_in", self.instance.check_in)
        check_out = attrs.get("check_out", self.instance.check_out)
        if check_in and check_out and check_out <= check_in:
            raise serializers.ValidationError(
                {"check_out": "Check-out must be later than check-in."}
            )
        return attrs


class AttendanceCorrectionHistorySerializer(serializers.ModelSerializer):
    corrected_by_name = serializers.SerializerMethodField()

    class Meta:
        model = AttendanceCorrection
        fields = ["id", "corrected_by", "corrected_by_name", "reason", "previous_values", "corrected_at"]
        read_only_fields = fields

    def get_corrected_by_name(self, obj):
        return obj.corrected_by.get_full_name() or obj.corrected_by.username


class WorkScheduleSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()

    class Meta:
        model = WorkSchedule
        fields = [
            "id",
            "employee",
            "employee_name",
            "weekday",
            "start_time",
            "end_time",
            "grace_period_minutes",
            "effective_from",
            "effective_until",
        ]

    def get_employee_name(self, obj):
        return obj.employee.get_full_name() or obj.employee.username

    def validate(self, attrs):
        employee = attrs.get("employee", getattr(self.instance, "employee", None))
        weekday = attrs.get("weekday", getattr(self.instance, "weekday", None))
        start_time = attrs.get("start_time", getattr(self.instance, "start_time", None))
        end_time = attrs.get("end_time", getattr(self.instance, "end_time", None))
        effective_from = attrs.get(
            "effective_from", getattr(self.instance, "effective_from", None)
        )
        effective_until = attrs.get(
            "effective_until", getattr(self.instance, "effective_until", None)
        )
        user = self.context["request"].user
        if employee and not (
            employee.id == user.id
            or user.is_superuser
            or user.role == User.Role.ADMINISTRATOR
            or (
                user.role == User.Role.IT_MANAGER
                and employee.manager_id == user.id
            )
        ):
            raise serializers.ValidationError(
                {"employee": "You may only manage schedules for yourself or your direct reports."}
            )
        if start_time and end_time and end_time <= start_time:
            raise serializers.ValidationError(
                {"end_time": "End time must be later than start time; overnight shifts are not supported."}
            )
        if effective_from and effective_until and effective_until < effective_from:
            raise serializers.ValidationError(
                {"effective_until": "End date must be on or after the effective start date."}
            )
        if employee and weekday is not None and effective_from is not None:
            overlapping = WorkSchedule.objects.filter(
                employee=employee,
                weekday=weekday,
                effective_from__lte=effective_until or effective_from,
            ).filter(
                Q(effective_until__isnull=True)
                | Q(effective_until__gte=effective_from)
            )
            if self.instance:
                overlapping = overlapping.exclude(pk=self.instance.pk)
            if overlapping.exists():
                raise serializers.ValidationError(
                    {"effective_from": "This schedule overlaps another schedule for that employee and weekday."}
                )
        return attrs


class LeaveRequestSerializer(serializers.ModelSerializer):
    employee = serializers.PrimaryKeyRelatedField(read_only=True)
    employee_name = serializers.SerializerMethodField()
    reviewed_by = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = LeaveRequest
        fields = [
            "id",
            "employee",
            "employee_name",
            "start_date",
            "end_date",
            "leave_type",
            "status",
            "reviewed_by",
            "review_note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "employee",
            "employee_name",
            "status",
            "reviewed_by",
            "review_note",
            "created_at",
            "updated_at",
        ]

    def get_employee_name(self, obj):
        return obj.employee.get_full_name() or obj.employee.username

    def validate(self, attrs):
        start_date = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end_date = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError({"end_date": "End date must be on or after start date."})
        if self.instance is None and start_date and end_date:
            overlaps = LeaveRequest.objects.filter(
                employee=self.context["request"].user,
                status=LeaveRequest.Status.APPROVED,
                start_date__lte=end_date,
                end_date__gte=start_date,
            ).exists()
            if overlaps:
                raise serializers.ValidationError(
                    {"start_date": "The requested dates overlap approved leave."}
                )
        return attrs


class LeaveReviewSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=[LeaveRequest.Status.APPROVED, LeaveRequest.Status.REJECTED]
    )
    review_note = serializers.CharField(required=False, allow_blank=True)


class PublicHolidaySerializer(serializers.ModelSerializer):
    class Meta:
        model = PublicHoliday
        fields = ["id", "date", "name", "is_active"]
