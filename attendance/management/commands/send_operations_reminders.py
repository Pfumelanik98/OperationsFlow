from datetime import datetime, timedelta

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from attendance.models import (
    AttendanceRecord,
    PublicHoliday,
    WorkSchedule,
)
from attendance.services import has_approved_leave
from feedback.models import FeedbackActionItem
from tasks.models import Notification


class Command(BaseCommand):
    help = "Create idempotent in-app reminders for due actions and attendance exceptions."

    def handle(self, *args, **options):
        today = timezone.localdate()
        notifications_created = self._notify_due_feedback_actions(today)
        notifications_created += self._notify_missing_attendance(today)
        self.stdout.write(
            self.style.SUCCESS(f"Created {notifications_created} operations reminder(s).")
        )

    def _create_once_today(self, user, message, task=None):
        exists = Notification.objects.filter(
            user=user,
            task=task,
            message=message,
            created_at__date=timezone.localdate(),
        ).exists()
        if exists:
            return False
        Notification.objects.create(user=user, task=task, message=message)
        return True

    def _notify_due_feedback_actions(self, today):
        count = 0
        due_actions = FeedbackActionItem.objects.exclude(
            status=FeedbackActionItem.Status.COMPLETED
        ).filter(due_date__lte=today).select_related("assigned_to", "feedback")
        for action in due_actions:
            state = "due today" if action.due_date == today else "overdue"
            message = f"Feedback follow-up action is {state}: {action.title}"
            count += self._create_once_today(
                action.assigned_to,
                message,
                action.feedback.task,
            )
        return count

    def _notify_missing_attendance(self, today):
        if PublicHoliday.objects.filter(date=today, is_active=True).exists():
            return 0

        now = timezone.localtime()
        count = 0
        schedules = WorkSchedule.objects.filter(
            weekday=today.weekday(),
            effective_from__lte=today,
            employee__is_active=True,
        ).filter(Q(effective_until__isnull=True) | Q(effective_until__gte=today))
        for schedule in schedules.select_related("employee", "employee__manager"):
            employee = schedule.employee
            if has_approved_leave(employee, today):
                continue
            expected_start = timezone.make_aware(
                datetime.combine(today, schedule.start_time),
                timezone.get_current_timezone(),
            )
            threshold = expected_start + timedelta(
                minutes=schedule.grace_period_minutes
            )
            if now <= threshold:
                continue
            record = AttendanceRecord.objects.filter(
                employee=employee,
                work_date=today,
            ).first()
            if record and record.check_in:
                continue

            message = (
                f"No attendance check-in is recorded for {employee.username} on "
                f"{today.isoformat()}; review required."
            )
            count += self._create_once_today(employee, message)
            if employee.manager_id:
                count += self._create_once_today(employee.manager, message)
        return count
