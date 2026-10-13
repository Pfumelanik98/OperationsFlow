from django.db.models import Q
from django.utils import timezone
from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from attendance.models import AttendanceRecord, LeaveRequest
from feedback.models import FeedbackActionItem
from tasks.access import is_administrator
from tasks.models import Task, User


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def employee_operations_dashboard(request):
    user = request.user
    today = timezone.localdate()
    month_start = today.replace(day=1)
    if is_administrator(user):
        employees = User.objects.filter(is_active=True)
    elif user.role == User.Role.IT_MANAGER:
        employees = User.objects.filter(Q(pk=user.pk) | Q(manager=user), is_active=True)
    else:
        employees = User.objects.filter(pk=user.pk)

    summary = []
    for employee in employees.order_by("last_name", "first_name", "username"):
        task_set = Task.objects.filter(assignee=employee)
        attendance_set = AttendanceRecord.objects.filter(
            employee=employee,
            work_date__gte=month_start,
            work_date__lte=today,
        )
        action_set = FeedbackActionItem.objects.filter(assigned_to=employee)
        summary.append(
            {
                "employee_id": employee.id,
                "employee_name": employee.get_full_name() or employee.username,
                "task_summary": {
                    "active": task_set.exclude(status=Task.Status.COMPLETED).count(),
                    "completed": task_set.filter(status=Task.Status.COMPLETED).count(),
                    "overdue": task_set.exclude(status=Task.Status.COMPLETED)
                    .filter(due_date__lt=today)
                    .count(),
                },
                "attendance_month_to_date": {
                    "present": attendance_set.filter(
                        status=AttendanceRecord.Status.PRESENT
                    ).count(),
                    "late": attendance_set.filter(
                        status=AttendanceRecord.Status.LATE
                    ).count(),
                    "absent": attendance_set.filter(
                        status=AttendanceRecord.Status.ABSENT
                    ).count(),
                    "pending_review": attendance_set.filter(
                        status=AttendanceRecord.Status.PENDING_REVIEW
                    ).count(),
                    "on_leave": attendance_set.filter(
                        status=AttendanceRecord.Status.ON_LEAVE
                    ).count(),
                    "approved_leave_requests": LeaveRequest.objects.filter(
                        employee=employee,
                        status=LeaveRequest.Status.APPROVED,
                        start_date__lte=today,
                        end_date__gte=month_start,
                    ).count(),
                },
                "feedback_actions": {
                    "outstanding": action_set.exclude(
                        status=FeedbackActionItem.Status.COMPLETED
                    ).count(),
                    "overdue": action_set.exclude(
                        status=FeedbackActionItem.Status.COMPLETED
                    )
                    .filter(due_date__lt=today)
                    .count(),
                },
            }
        )
    return Response({"as_of": today, "employees": summary})
