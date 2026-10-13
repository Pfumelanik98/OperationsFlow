from datetime import date

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from tasks.models import Notification

from .models import EmployeeFeedback, FeedbackActionItem

User = get_user_model()


class FeedbackApiTests(APITestCase):
    def setUp(self):
        self.manager = User.objects.create_user(
            username="feedback-manager",
            password="Password123!",
            role=User.Role.IT_MANAGER,
        )
        self.employee = User.objects.create_user(
            username="feedback-employee",
            password="Password123!",
            role=User.Role.IT_EMPLOYEE,
            manager=self.manager,
        )
        self.unrelated = User.objects.create_user(
            username="unrelated-employee",
            password="Password123!",
            role=User.Role.IT_EMPLOYEE,
        )
        self.feedback = EmployeeFeedback.objects.create(
            employee=self.employee,
            author=self.manager,
            category=EmployeeFeedback.Category.COACHING,
            content="Document the troubleshooting steps.",
            feedback_date=date(2026, 10, 13),
        )

    def test_unrelated_employee_cannot_read_feedback(self):
        self.client.force_authenticate(user=self.unrelated)
        response = self.client.get(reverse("feedback-detail", args=[self.feedback.id]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_employee_can_acknowledge_without_changing_feedback(self):
        self.client.force_authenticate(user=self.employee)
        response = self.client.post(
            reverse("feedback-acknowledge", args=[self.feedback.id])
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.feedback.refresh_from_db()
        self.assertIsNotNone(self.feedback.acknowledged_at)
        self.assertEqual(self.feedback.employee_response, "")

    def test_employee_can_submit_a_response(self):
        self.client.force_authenticate(user=self.employee)

        response = self.client.post(
            reverse("feedback-responses", args=[self.feedback.id]),
            {"response": "I will prepare the notes this week."},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.feedback.refresh_from_db()
        self.assertEqual(
            self.feedback.employee_response,
            "I will prepare the notes this week.",
        )

    def test_manager_publishing_feedback_notifies_employee(self):
        self.client.force_authenticate(user=self.manager)
        response = self.client.post(
            reverse("feedback-list"),
            {
                "employee": self.employee.id,
                "category": EmployeeFeedback.Category.POSITIVE,
                "content": "Thank you for resolving the issue.",
                "feedback_date": "2026-10-13",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            Notification.objects.filter(
                user=self.employee,
                message="New private employee feedback is available for you.",
            ).exists()
        )

    def test_manager_cannot_publish_feedback_for_an_unrelated_employee(self):
        self.client.force_authenticate(user=self.manager)
        response = self.client.post(
            reverse("feedback-list"),
            {
                "employee": self.unrelated.id,
                "category": EmployeeFeedback.Category.COACHING,
                "content": "Private information.",
                "feedback_date": "2026-10-13",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_can_create_a_private_follow_up_for_a_direct_report(self):
        self.client.force_authenticate(user=self.manager)

        response = self.client.post(
            reverse("feedback-create-action", args=[self.feedback.id]),
            {
                "title": "Document troubleshooting steps",
                "assigned_to": self.employee.id,
                "due_date": "2026-10-20",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            Notification.objects.filter(
                user=self.employee,
                message__contains="Document troubleshooting steps",
            ).exists()
        )

    def test_employee_can_update_status_of_assigned_action(self):
        action_item = FeedbackActionItem.objects.create(
            feedback=self.feedback,
            assigned_to=self.employee,
            title="Write troubleshooting notes",
        )
        self.client.force_authenticate(user=self.employee)

        response = self.client.patch(
            reverse("feedback-action-detail", args=[action_item.id]),
            {"status": FeedbackActionItem.Status.COMPLETED},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        action_item.refresh_from_db()
        self.assertIsNotNone(action_item.completed_at)

    def test_reminder_command_notifies_due_action_once_per_day(self):
        action_item = FeedbackActionItem.objects.create(
            feedback=self.feedback,
            assigned_to=self.employee,
            title="Prepare a follow-up plan",
            due_date=timezone.localdate(),
        )

        call_command("send_operations_reminders")
        first_count = self.employee.notifications.count()
        call_command("send_operations_reminders")

        self.assertEqual(first_count, 1)
        self.assertEqual(self.employee.notifications.count(), 1)
