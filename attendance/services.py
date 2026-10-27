from datetime import datetime, timedelta

from django.db.models import Q
from django.utils import timezone

from .models import AttendanceRecord, LeaveRequest, WorkSchedule


def schedule_for(employee, work_date):
    return (
        WorkSchedule.objects.filter(
            employee=employee,
            weekday=work_date.weekday(),
            effective_from__lte=work_date,
        )
        .filter(Q(effective_until__isnull=True) | Q(effective_until__gte=work_date))
        .order_by("-effective_from")
        .first()
    )


def has_approved_leave(employee, work_date):
    return LeaveRequest.objects.filter(
        employee=employee,
        status=LeaveRequest.Status.APPROVED,
        start_date__lte=work_date,
        end_date__gte=work_date,
    ).exists()


def classify_attendance(employee, work_date, check_in, *, is_remote=False):
    if has_approved_leave(employee, work_date):
        return AttendanceRecord.Status.ON_LEAVE
    if check_in is None:
        return AttendanceRecord.Status.PENDING_REVIEW

    schedule = schedule_for(employee, work_date)
    if schedule is None:
        return AttendanceRecord.Status.PRESENT

    local_check_in = timezone.localtime(check_in)
    expected_start = timezone.make_aware(
        datetime.combine(work_date, schedule.start_time),
        timezone.get_current_timezone(),
    )
    deadline = expected_start + timedelta(minutes=schedule.grace_period_minutes)
    return (
        AttendanceRecord.Status.LATE
        if local_check_in > deadline
        else AttendanceRecord.Status.PRESENT
    )
