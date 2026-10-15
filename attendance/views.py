from datetime import date, datetime, timedelta
import calendar

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, serializers, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from tasks.access import can_manage_employee, is_administrator, manageable_employee_ids
from tasks.models import Notification, User

from .models import (
    AttendanceCorrection,
    AttendanceRecord,
    LeaveRequest,
    PublicHoliday,
    WorkSchedule,
)
from .serializers import (
    AttendanceCorrectionHistorySerializer,
    AttendanceCorrectionSerializer,
    AttendanceManualCreateSerializer,
    AttendanceSerializer,
    LeaveRequestSerializer,
    LeaveReviewSerializer,
    PublicHolidaySerializer,
    WorkScheduleSerializer,
)
from .services import classify_attendance, has_approved_leave, schedule_for


class AttendanceViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        user = self.request.user
        records = AttendanceRecord.objects.select_related("employee", "recorded_by")
        if is_administrator(user):
            return records
        if user.role == User.Role.IT_MANAGER:
            return records.filter(Q(employee=user) | Q(employee__manager=user))
        return records.filter(employee=user)

    def get_serializer_class(self):
        if self.action == "create":
            return AttendanceManualCreateSerializer
        if self.action == "partial_update":
            return AttendanceCorrectionSerializer
        return AttendanceSerializer

    @action(detail=False, methods=["get"], url_path="me")
    def me(self, request):
        records = self.get_queryset().filter(employee=request.user)
        return Response(self.get_serializer(records, many=True).data)

    def create(self, request, *args, **kwargs):
        if not is_administrator(request.user):
            raise PermissionDenied("Only administrators can create manual attendance records.")
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        employee = serializer.validated_data["employee"]
        if not can_manage_employee(request.user, employee):
            raise PermissionDenied("You may only record attendance for yourself or an employee you manage.")
        validated = serializer.validated_data
        reason = validated.pop("correction_reason")
        validated["source"] = AttendanceRecord.Source.MANAGER
        validated["recorded_by"] = request.user
        try:
            with transaction.atomic():
                record = AttendanceRecord.objects.create(**validated)
                AttendanceCorrection.objects.create(
                    attendance=record,
                    corrected_by=request.user,
                    reason=reason,
                    previous_values={},
                )
        except IntegrityError as exc:
            raise serializers.ValidationError(
                {"work_date": "An attendance record already exists for this employee and date."}
            ) from exc
        return Response(AttendanceSerializer(record).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        record = self.get_object()
        if not is_administrator(request.user):
            raise PermissionDenied("Only administrators can correct attendance records.")

        serializer = self.get_serializer(record, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        validated = dict(serializer.validated_data)
        reason = validated.pop("correction_reason", "").strip()
        if not reason:
            raise serializers.ValidationError(
                {"correction_reason": "A reason is required for attendance corrections."}
            )
        previous = {
            "check_in": record.check_in.isoformat() if record.check_in else None,
            "check_out": record.check_out.isoformat() if record.check_out else None,
            "status": record.status,
            "is_remote": record.is_remote,
        }
        new_check_in = validated.get("check_in", record.check_in)
        if "status" not in validated and "check_in" in validated:
            validated["status"] = classify_attendance(
                record.employee,
                record.work_date,
                new_check_in,
                is_remote=validated.get("is_remote", record.is_remote),
            )
        with transaction.atomic():
            updated = serializer.save(
                recorded_by=request.user,
                approved_by=None,
                approved_at=None,
                **validated,
            )
            AttendanceCorrection.objects.create(
                attendance=updated,
                corrected_by=request.user,
                reason=reason,
                previous_values=previous,
            )
        return Response(AttendanceSerializer(updated).data)

    @action(detail=True, methods=["get"], url_path="corrections")
    def corrections(self, request, pk=None):
        record = self.get_object()
        history = record.corrections.select_related("corrected_by")
        return Response(AttendanceCorrectionHistorySerializer(history, many=True).data)

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        record = self.get_object()
        if not can_manage_employee(request.user, record.employee):
            raise PermissionDenied("Only the employee's manager or an administrator can approve attendance.")
        if not record.check_in:
            raise serializers.ValidationError(
                {"attendance": "Attendance needs a check-in before it can be approved."}
            )
        if record.approved_at:
            raise serializers.ValidationError(
                {"attendance": "This attendance record is already approved."}
            )
        record.approved_by = request.user
        record.approved_at = timezone.now()
        record.save(update_fields=["approved_by", "approved_at", "updated_at"])
        Notification.objects.create(
            user=record.employee,
            message=f"Your attendance for {record.work_date} was approved.",
        )
        return Response(AttendanceSerializer(record).data)


class AttendanceCheckInView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        work_date = timezone.localdate()
        if has_approved_leave(request.user, work_date):
            raise serializers.ValidationError("You have approved leave for today.")
        now = timezone.now()
        try:
            with transaction.atomic():
                record, created = AttendanceRecord.objects.get_or_create(
                    employee=request.user,
                    work_date=work_date,
                    defaults={
                        "check_in": now,
                        "status": classify_attendance(request.user, work_date, now),
                        "source": AttendanceRecord.Source.SELF_SERVICE,
                        "recorded_by": request.user,
                    },
                )
                if not created:
                    if record.check_in:
                        raise serializers.ValidationError("You have already checked in today.")
                    record.check_in = now
                    record.status = classify_attendance(request.user, work_date, now)
                    record.source = AttendanceRecord.Source.SELF_SERVICE
                    record.recorded_by = request.user
                    record.save(
                        update_fields=["check_in", "status", "source", "recorded_by", "updated_at"]
                    )
        except IntegrityError as exc:
            raise serializers.ValidationError("Unable to record check-in; please try again.") from exc
        return Response(AttendanceSerializer(record).data, status=status.HTTP_201_CREATED)


class AttendanceCheckOutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        work_date = timezone.localdate()
        with transaction.atomic():
            record = get_object_or_404(
                AttendanceRecord.objects.select_for_update(),
                employee=request.user,
                work_date=work_date,
            )
            if not record.check_in:
                raise serializers.ValidationError("Check in before checking out.")
            if record.check_out:
                raise serializers.ValidationError("You have already checked out today.")
            record.check_out = timezone.now()
            record.save(update_fields=["check_out", "updated_at"])
        return Response(AttendanceSerializer(record).data)


class WorkScheduleViewSet(viewsets.ModelViewSet):
    serializer_class = WorkScheduleSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        schedules = WorkSchedule.objects.select_related("employee")
        if is_administrator(user):
            return schedules
        if user.role == User.Role.IT_MANAGER:
            return schedules.filter(Q(employee=user) | Q(employee__manager=user))
        return schedules.filter(employee=user)

    def perform_create(self, serializer):
        employee = serializer.validated_data["employee"]
        if not is_administrator(self.request.user):
            raise PermissionDenied("Only administrators can create employee schedules.")
        serializer.save()

    def perform_update(self, serializer):
        if not is_administrator(self.request.user):
            raise PermissionDenied("Only administrators can update employee schedules.")
        serializer.save()

    def perform_destroy(self, instance):
        if not is_administrator(self.request.user):
            raise PermissionDenied("Only administrators can delete employee schedules.")
        instance.delete()


class PublicHolidayViewSet(viewsets.ModelViewSet):
    queryset = PublicHoliday.objects.all()
    serializer_class = PublicHolidaySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        if self.action in {"create", "update", "partial_update", "destroy"}:
            return [IsOperationsAdministrator()]
        return super().get_permissions()


class IsOperationsAdministrator(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (
                request.user.is_superuser
                or request.user.role == User.Role.ADMINISTRATOR
            )
        )


class LeaveRequestViewSet(viewsets.ModelViewSet):
    serializer_class = LeaveRequestSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        user = self.request.user
        requests = LeaveRequest.objects.select_related("employee", "reviewed_by")
        if is_administrator(user):
            return requests
        if user.role == User.Role.IT_MANAGER:
            return requests.filter(Q(employee=user) | Q(employee__manager=user))
        return requests.filter(employee=user)

    def perform_create(self, serializer):
        serializer.save(employee=self.request.user)

    @action(detail=True, methods=["post"], url_path="review")
    def review(self, request, pk=None):
        leave_request = self.get_object()
        if not can_manage_employee(request.user, leave_request.employee):
            raise PermissionDenied("You may only review leave for your direct reports.")
        if leave_request.status != LeaveRequest.Status.PENDING:
            raise serializers.ValidationError("Only pending leave requests can be reviewed.")
        serializer = LeaveReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_status = serializer.validated_data["status"]
        if new_status == LeaveRequest.Status.APPROVED:
            conflict = LeaveRequest.objects.filter(
                employee=leave_request.employee,
                status=LeaveRequest.Status.APPROVED,
                start_date__lte=leave_request.end_date,
                end_date__gte=leave_request.start_date,
            ).exists()
            if conflict:
                raise serializers.ValidationError("The requested dates overlap approved leave.")
        leave_request.status = new_status
        leave_request.reviewed_by = request.user
        leave_request.review_note = serializer.validated_data.get("review_note", "")
        leave_request.save(
            update_fields=["status", "reviewed_by", "review_note", "updated_at"]
        )
        Notification.objects.create(
            user=leave_request.employee,
            message=f"Your {leave_request.leave_type} leave request was {new_status}.",
        )
        return Response(LeaveRequestSerializer(leave_request).data)

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        leave_request = self.get_object()
        if leave_request.employee_id != request.user.id:
            raise PermissionDenied("You can only cancel your own leave request.")
        if leave_request.status != LeaveRequest.Status.PENDING:
            raise serializers.ValidationError("Only pending leave requests can be cancelled.")
        leave_request.status = LeaveRequest.Status.CANCELLED
        leave_request.save(update_fields=["status", "updated_at"])
        return Response(LeaveRequestSerializer(leave_request).data)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def attendance_report(request):
    period = request.query_params.get("period", "daily")
    try:
        requested_date = date.fromisoformat(
            request.query_params.get("date", timezone.localdate().isoformat())
        )
    except ValueError as exc:
        raise serializers.ValidationError({"date": "Use a valid YYYY-MM-DD date."}) from exc

    if period == "daily":
        start_date = end_date = requested_date
    elif period == "weekly":
        start_date = requested_date - timedelta(days=requested_date.weekday())
        end_date = start_date + timedelta(days=6)
    elif period == "monthly":
        start_date = requested_date.replace(day=1)
        end_date = requested_date.replace(
            day=calendar.monthrange(requested_date.year, requested_date.month)[1]
        )
    else:
        raise serializers.ValidationError(
            {"period": "Period must be daily, weekly or monthly."}
        )

    user = request.user
    employees = User.objects.filter(pk__in=manageable_employee_ids(user))
    if user.role == User.Role.IT_MANAGER:
        employees = User.objects.filter(Q(pk=user.pk) | Q(manager=user), is_active=True)
    records = AttendanceRecord.objects.filter(
        employee__in=employees,
        work_date__range=(start_date, end_date),
    ).select_related("employee", "recorded_by")
    approved_leave = LeaveRequest.objects.filter(
        employee__in=employees,
        status=LeaveRequest.Status.APPROVED,
        start_date__lte=end_date,
        end_date__gte=start_date,
    ).select_related("employee")
    expected_days = {}
    now = timezone.localtime()
    today = timezone.localdate()
    for employee in employees:
        for day_offset in range((end_date - start_date).days + 1):
            work_date = start_date + timedelta(days=day_offset)
            schedule = schedule_for(employee, work_date)
            if schedule is None:
                continue
            if PublicHoliday.objects.filter(date=work_date, is_active=True).exists():
                continue
            if has_approved_leave(employee, work_date):
                continue
            expected_start = timezone.make_aware(
                datetime.combine(work_date, schedule.start_time),
                timezone.get_current_timezone(),
            )
            check_in_due_at = expected_start + timedelta(
                minutes=schedule.grace_period_minutes
            )
            if work_date > today or (
                work_date == today and now < check_in_due_at
            ):
                continue
            expected_days[(employee.id, work_date)] = employee
    records_by_day = {
        (record.employee_id, record.work_date): record for record in records
    }
    missing_check_ins = [
        {
            "employee": employee.id,
            "employee_name": employee.get_full_name() or employee.username,
            "work_date": work_date.isoformat(),
            "status": AttendanceRecord.Status.PENDING_REVIEW,
        }
        for (employee_id, work_date), employee in expected_days.items()
        if (employee_id, work_date) not in records_by_day
        or (
            records_by_day[(employee_id, work_date)].check_in is None
            and records_by_day[(employee_id, work_date)].status
            == AttendanceRecord.Status.PENDING_REVIEW
        )
    ]
    missing_check_outs = []
    for record in records:
        if not record.check_in or record.check_out:
            continue
        schedule = schedule_for(record.employee, record.work_date)
        if schedule is None:
            continue
        expected_end = timezone.make_aware(
            datetime.combine(record.work_date, schedule.end_time),
            timezone.get_current_timezone(),
        )
        if record.work_date < today or now >= expected_end:
            missing_check_outs.append(
                {
                    "employee": record.employee_id,
                    "employee_name": record.employee.get_full_name()
                    or record.employee.username,
                    "work_date": record.work_date.isoformat(),
                    "status": "missing_check_out",
                }
            )
    return Response(
        {
            "period": period,
            "start_date": start_date,
            "end_date": end_date,
            "records": AttendanceSerializer(records, many=True).data,
            "approved_leave_requests": [
                {
                    "id": leave.id,
                    "employee": leave.employee_id,
                    "employee_name": leave.employee.get_full_name()
                    or leave.employee.username,
                    "start_date": leave.start_date,
                    "end_date": leave.end_date,
                    "leave_type": leave.leave_type,
                }
                for leave in approved_leave
            ],
            "missing_check_ins": missing_check_ins,
            "missing_check_outs": missing_check_outs,
        }
    )
