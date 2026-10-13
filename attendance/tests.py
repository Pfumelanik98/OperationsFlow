from datetime import time, timedelta

from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .models import AttendanceCorrection, AttendanceRecord, LeaveRequest, WorkSchedule

User = get_user_model()


class AttendanceApiTests(APITestCase):
    def setUp(self):
        self.manager = User.objects.create_user(
            username="attendance-manager",
            password="Password123!",
            role=User.Role.IT_MANAGER,
        )
        self.employee = User.objects.create_user(
            username="attendance-employee",
            password="Password123!",
            role=User.Role.IT_EMPLOYEE,
            manager=self.manager,
        )
        self.other_employee = User.objects.create_user(
            username="other-employee",
            password="Password123!",
            role=User.Role.IT_EMPLOYEE,
        )
        self.today = timezone.localdate()

    def test_employee_can_check_in_once_and_check_out(self):
        self.client.force_authenticate(user=self.employee)
        check_in = self.client.post(reverse("attendance-check-in"))
        self.assertEqual(check_in.status_code, status.HTTP_201_CREATED)

        duplicate = self.client.post(reverse("attendance-check-in"))
        self.assertEqual(duplicate.status_code, status.HTTP_400_BAD_REQUEST)

        check_out = self.client.post(reverse("attendance-check-out"))
        self.assertEqual(check_out.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(check_out.data["check_out"])

    def test_late_status_uses_schedule_and_grace_period(self):
        local_now = timezone.localtime(timezone.now())
        start_time = (local_now - timedelta(minutes=10)).time().replace(tzinfo=None)
        WorkSchedule.objects.create(
            employee=self.employee,
            weekday=self.today.weekday(),
            start_time=start_time,
            end_time=(local_now + timedelta(hours=4)).time().replace(tzinfo=None),
            grace_period_minutes=0,
            effective_from=self.today,
        )
        self.client.force_authenticate(user=self.employee)

        response = self.client.post(reverse("attendance-check-in"))

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], AttendanceRecord.Status.LATE)

    def test_manager_correction_requires_reason_and_writes_audit_history(self):
        record = AttendanceRecord.objects.create(
            employee=self.employee,
            work_date=self.today,
            status=AttendanceRecord.Status.PENDING_REVIEW,
            source=AttendanceRecord.Source.MANAGER,
            recorded_by=self.manager,
        )
        self.client.force_authenticate(user=self.manager)
        detail = reverse("attendance-record-detail", args=[record.id])

        denied = self.client.patch(
            detail,
            {"status": AttendanceRecord.Status.ABSENT},
            format="json",
        )
        self.assertEqual(denied.status_code, status.HTTP_400_BAD_REQUEST)

        corrected = self.client.patch(
            detail,
            {
                "status": AttendanceRecord.Status.PRESENT,
                "correction_reason": "Employee confirmed arrival with supervisor.",
            },
            format="json",
        )
        self.assertEqual(corrected.status_code, status.HTTP_200_OK)
        correction = AttendanceCorrection.objects.get(attendance=record)
        self.assertEqual(correction.corrected_by, self.manager)
        self.assertEqual(correction.previous_values["status"], AttendanceRecord.Status.PENDING_REVIEW)

    def test_manager_cannot_view_or_edit_unrelated_attendance(self):
        record = AttendanceRecord.objects.create(
            employee=self.other_employee,
            work_date=self.today,
            status=AttendanceRecord.Status.PENDING_REVIEW,
        )
        self.client.force_authenticate(user=self.manager)

        response = self.client.get(reverse("attendance-record-detail", args=[record.id]))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_attendance_me_endpoint_only_returns_the_current_employee_records(self):
        own_record = AttendanceRecord.objects.create(
            employee=self.employee,
            work_date=self.today,
            status=AttendanceRecord.Status.PRESENT,
        )
        AttendanceRecord.objects.create(
            employee=self.other_employee,
            work_date=self.today,
            status=AttendanceRecord.Status.PRESENT,
        )
        self.client.force_authenticate(user=self.employee)

        response = self.client.get(reverse("attendance-record-me"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([row["id"] for row in response.data], [own_record.id])

    def test_report_flags_missing_record_for_review_not_absence(self):
        WorkSchedule.objects.create(
            employee=self.employee,
            weekday=self.today.weekday(),
            start_time=time(8, 0),
            end_time=time(16, 0),
            effective_from=self.today,
        )
        self.client.force_authenticate(user=self.manager)

        response = self.client.get(
            reverse("attendance-report"),
            {"period": "daily", "date": self.today.isoformat()},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["missing_check_ins"]), 1)
        self.assertEqual(
            response.data["missing_check_ins"][0]["status"],
            AttendanceRecord.Status.PENDING_REVIEW,
        )
        self.assertEqual(response.data["missing_check_outs"], [])

    def test_past_record_without_checkout_is_reported_for_review(self):
        work_date = self.today - timedelta(days=1)
        WorkSchedule.objects.create(
            employee=self.employee,
            weekday=work_date.weekday(),
            start_time=time(8, 0),
            end_time=time(16, 0),
            effective_from=work_date,
        )
        AttendanceRecord.objects.create(
            employee=self.employee,
            work_date=work_date,
            check_in=timezone.now() - timedelta(days=1),
            status=AttendanceRecord.Status.PRESENT,
        )
        self.client.force_authenticate(user=self.manager)

        response = self.client.get(
            reverse("attendance-report"),
            {"period": "daily", "date": work_date.isoformat()},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["missing_check_outs"]), 1)

    def test_approved_leave_appears_in_reports_without_creating_absence(self):
        LeaveRequest.objects.create(
            employee=self.employee,
            start_date=self.today,
            end_date=self.today,
            leave_type=LeaveRequest.LeaveType.ANNUAL,
            status=LeaveRequest.Status.APPROVED,
            reviewed_by=self.manager,
        )
        self.client.force_authenticate(user=self.manager)

        response = self.client.get(
            reverse("attendance-report"),
            {"period": "daily", "date": self.today.isoformat()},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["approved_leave_requests"]), 1)
        self.assertEqual(response.data["missing_check_ins"], [])

    def test_approved_leave_blocks_check_in(self):
        LeaveRequest.objects.create(
            employee=self.employee,
            start_date=self.today,
            end_date=self.today,
            leave_type=LeaveRequest.LeaveType.ANNUAL,
            status=LeaveRequest.Status.APPROVED,
            reviewed_by=self.manager,
        )
        self.client.force_authenticate(user=self.employee)

        response = self.client.post(reverse("attendance-check-in"))

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_manager_reviewing_leave_sends_employee_notification(self):
        leave_request = LeaveRequest.objects.create(
            employee=self.employee,
            start_date=self.today,
            end_date=self.today + timedelta(days=1),
            leave_type=LeaveRequest.LeaveType.ANNUAL,
        )
        self.client.force_authenticate(user=self.manager)

        response = self.client.post(
            reverse("leave-request-review", args=[leave_request.id]),
            {"status": LeaveRequest.Status.APPROVED, "review_note": "Approved."},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(
            self.employee.notifications.filter(message__contains="was approved").exists()
        )

    def test_public_holiday_is_not_reported_as_a_missing_check_in(self):
        from .models import PublicHoliday

        WorkSchedule.objects.create(
            employee=self.employee,
            weekday=self.today.weekday(),
            start_time=time(8, 0),
            end_time=time(16, 0),
            effective_from=self.today,
        )
        PublicHoliday.objects.create(date=self.today, name="Configured public holiday")
        self.client.force_authenticate(user=self.manager)

        response = self.client.get(
            reverse("attendance-report"),
            {"period": "daily", "date": self.today.isoformat()},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["missing_check_ins"], [])

    def test_reminder_command_notifies_missing_checkin_once_per_day(self):
        WorkSchedule.objects.create(
            employee=self.employee,
            weekday=self.today.weekday(),
            start_time=time(0, 0),
            end_time=time(23, 59),
            effective_from=self.today,
        )

        call_command("send_operations_reminders")
        first_count = self.employee.notifications.count()
        call_command("send_operations_reminders")

        self.assertEqual(first_count, 1)
        self.assertEqual(self.employee.notifications.count(), 1)
