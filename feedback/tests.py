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
        self.administrator = User.objects.create_user(
            username="feedback-admin",
            password="test-password",
            role=User.Role.ADMINISTRATOR,
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

    def test_employee_feedback_list_and_detail_are_private(self):
        other_feedback = EmployeeFeedback.objects.create(
            employee=self.unrelated,
            author=self.manager,
            category=EmployeeFeedback.Category.COACHING,
            content="Private feedback for another employee.",
            feedback_date=date(2026, 10, 13),
        )
        self.client.force_authenticate(user=self.employee)

        listing = self.client.get(reverse("feedback-me"))
        hidden = self.client.get(
            reverse("feedback-detail", args=[other_feedback.id])
        )

        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        self.assertEqual([item["id"] for item in listing.data], [self.feedback.id])
        self.assertEqual(hidden.status_code, status.HTTP_404_NOT_FOUND)

    def test_employee_action_list_contains_only_actions_assigned_to_them(self):
        own_action = FeedbackActionItem.objects.create(
            feedback=self.feedback,
            assigned_to=self.employee,
            title="Prepare troubleshooting notes",
        )
        FeedbackActionItem.objects.create(
            feedback=self.feedback,
            assigned_to=self.manager,
            title="Review troubleshooting notes",
        )
        self.client.force_authenticate(user=self.employee)

        listing = self.client.get(reverse("feedback-action-list"))
        feedback = self.client.get(reverse("feedback-me"))

        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        self.assertEqual([item["id"] for item in listing.data], [own_action.id])
        self.assertEqual(
            [item["id"] for item in feedback.data[0]["action_items"]],
            [own_action.id],
        )

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

    def test_administrator_publishing_feedback_notifies_employee(self):
        self.client.force_authenticate(user=self.administrator)
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

    def test_manager_cannot_publish_feedback(self):
        self.client.force_authenticate(user=self.manager)
        response = self.client.post(
            reverse("feedback-list"),
            {
                "employee": self.employee.id,
                "category": EmployeeFeedback.Category.COACHING,
                "content": "Feedback should be administrator-managed.",
                "feedback_date": "2026-10-13",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_administrator_can_create_a_private_follow_up(self):
        self.client.force_authenticate(user=self.administrator)

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

    def test_manager_cannot_view_direct_report_feedback(self):
        self.client.force_authenticate(user=self.manager)

        listing = self.client.get(reverse("feedback-list"))
        hidden = self.client.get(
            reverse("feedback-detail", args=[self.feedback.id])
        )

        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        self.assertEqual(listing.data, [])
        self.assertEqual(hidden.status_code, status.HTTP_404_NOT_FOUND)

    def test_manager_cannot_create_follow_up_actions(self):
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

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(self.feedback.action_items.exists())

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
