from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Notification, Task, TaskCompletionReport

User = get_user_model()


class OperationsFlowApiTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="Password123!",
            role=User.Role.ADMINISTRATOR,
        )
        self.manager = User.objects.create_user(
            username="manager",
            email="manager@example.com",
            password="Password123!",
            role=User.Role.IT_MANAGER,
        )
        self.employee = User.objects.create_user(
            username="employee",
            email="employee@example.com",
            password="Password123!",
            role=User.Role.IT_EMPLOYEE,
            manager=self.manager,
        )
        self.task = Task.objects.create(
            title="Reset VPN access",
            description="Provide access to the new user.",
            status=Task.Status.NEW,
            priority=Task.Priority.HIGH,
            assignee=self.employee,
            requester=self.manager,
        )

    def test_employee_can_list_only_assigned_tasks(self):
        self.client.force_authenticate(user=self.employee)
        response = self.client.get(reverse("task-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_employee_my_tasks_endpoint_and_detail_are_private(self):
        unrelated = User.objects.create_user(
            username="unrelated-task-owner",
            email="unrelated@example.com",
            password="test-password",
            role=User.Role.IT_EMPLOYEE,
        )
        other_task = Task.objects.create(
            title="Private task",
            description="Belongs to another employee.",
            assignee=unrelated,
            requester=self.manager,
        )
        self.client.force_authenticate(user=self.employee)

        listing = self.client.get(reverse("task-my-tasks"))
        hidden = self.client.get(reverse("task-detail", args=[other_task.id]))

        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        self.assertEqual([item["id"] for item in listing.data], [self.task.id])
        self.assertEqual(hidden.status_code, status.HTTP_404_NOT_FOUND)

    def test_employee_cannot_edit_task(self):
        self.client.force_authenticate(user=self.employee)
        detail = reverse("task-detail", args=[self.task.id])

        response = self.client.patch(
            detail,
            {"status": Task.Status.IN_PROGRESS},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, Task.Status.NEW)
        self.assertEqual(self.task.title, "Reset VPN access")

    def test_employee_cannot_delete_assigned_task(self):
        self.client.force_authenticate(user=self.employee)

        response = self.client.delete(
            reverse("task-detail", args=[self.task.id])
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Task.objects.filter(pk=self.task.id).exists())

    def test_manager_can_list_all_tasks(self):
        self.client.force_authenticate(user=self.manager)
        response = self.client.get(reverse("task-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)

    def test_manager_task_list_excludes_another_managers_team(self):
        other_manager = User.objects.create_user(
            username="other-manager",
            email="other-manager@example.com",
            password="test-password",
            role=User.Role.IT_MANAGER,
        )
        unrelated = User.objects.create_user(
            username="unrelated-task-owner",
            email="unrelated@example.com",
            password="test-password",
            role=User.Role.IT_EMPLOYEE,
            manager=other_manager,
        )
        other_task = Task.objects.create(
            title="Unrelated task",
            description="Belongs to another manager's team.",
            assignee=unrelated,
            requester=other_manager,
        )
        self.client.force_authenticate(user=self.manager)

        listing = self.client.get(reverse("task-list"))
        hidden = self.client.get(reverse("task-detail", args=[other_task.id]))

        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        self.assertNotIn(other_task.id, {item["id"] for item in listing.data})
        self.assertEqual(hidden.status_code, status.HTTP_404_NOT_FOUND)

    def test_employee_cannot_create_a_task(self):
        self.client.force_authenticate(user=self.employee)
        response = self.client.post(
            reverse("task-list"),
            {
                "title": "Install software",
                "description": "Install a standard office suite.",
                "assignee": self.employee.id,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_cannot_create_or_assign_a_task(self):
        self.client.force_authenticate(user=self.manager)

        response = self.client.post(
            reverse("task-list"),
            {
                "title": "Out-of-team task",
                "description": "This assignment should be denied.",
                "assignee": self.employee.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_manager_cannot_delete_task(self):
        self.client.force_authenticate(user=self.manager)

        response = self.client.delete(
            reverse("task-detail", args=[self.task.id])
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Task.objects.filter(pk=self.task.id).exists())

    def test_employee_cannot_add_task_comments(self):
        self.client.force_authenticate(user=self.employee)

        response = self.client.post(
            reverse("task-add-comment", args=[self.task.id]),
            {"body": "Please update the due date."},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(self.task.comments.exists())

    def test_administrator_must_assign_task_to_an_employee(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(
            reverse("task-list"),
            {
                "title": "Prepare workstation",
                "description": "Set up the assigned workstation.",
                "assignee": self.employee.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["assignee"], self.employee.id)

    def test_administrator_cannot_assign_task_to_a_manager(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(
            reverse("task-list"),
            {
                "title": "Prepare workstation",
                "description": "Set up the assigned workstation.",
                "assignee": self.manager.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_employee_can_submit_report_and_manager_can_approve(self):
        self.client.force_authenticate(user=self.employee)
        submitted = self.client.post(
            reverse("task-report-list"),
            {
                "task": self.task.id,
                "summary": "Completed the VPN configuration.",
                "issues": "",
                "time_spent_minutes": 30,
            },
            format="json",
        )
        self.assertEqual(submitted.status_code, status.HTTP_201_CREATED)
        self.assertEqual(submitted.data["status"], TaskCompletionReport.Status.SUBMITTED)

        self.client.force_authenticate(user=self.manager)
        approved = self.client.post(
            reverse("task-report-review", args=[submitted.data["id"]]),
            {"status": TaskCompletionReport.Status.APPROVED},
            format="json",
        )
        self.assertEqual(approved.status_code, status.HTTP_200_OK)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, Task.Status.COMPLETED)

    def test_manager_cannot_review_report_from_another_team(self):
        other_manager = User.objects.create_user(
            username="other-manager",
            email="other-manager@example.com",
            password="test-password",
            role=User.Role.IT_MANAGER,
        )
        report = TaskCompletionReport.objects.create(
            task=self.task,
            employee=self.employee,
            summary="Work completed.",
        )
        self.client.force_authenticate(user=other_manager)

        response = self.client.post(
            reverse("task-report-review", args=[report.id]),
            {"status": TaskCompletionReport.Status.APPROVED},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_manager_can_request_changes_and_employee_can_resubmit_report(self):
        report = TaskCompletionReport.objects.create(
            task=self.task,
            employee=self.employee,
            summary="Work completed.",
        )
        self.client.force_authenticate(user=self.manager)
        review = self.client.post(
            reverse("task-report-review", args=[report.id]),
            {
                "status": TaskCompletionReport.Status.CHANGES_REQUESTED,
                "review_note": "Please include the verification results.",
            },
            format="json",
        )
        self.assertEqual(review.status_code, status.HTTP_200_OK)

        self.client.force_authenticate(user=self.employee)
        resubmitted = self.client.patch(
            reverse("task-report-detail", args=[report.id]),
            {
                "summary": "Work completed and verified.",
                "issues": "",
                "time_spent_minutes": 45,
            },
            format="json",
        )
        self.assertEqual(resubmitted.status_code, status.HTTP_200_OK)
        self.assertEqual(resubmitted.data["status"], TaskCompletionReport.Status.SUBMITTED)

    def test_employee_dashboard_contains_only_the_authenticated_employee(self):
        self.client.force_authenticate(user=self.employee)

        response = self.client.get(reverse("employee-operations-dashboard"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [entry["employee_id"] for entry in response.data["employees"]],
            [self.employee.id],
        )

    def test_task_requester_is_always_the_authenticated_creator(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(
            reverse("task-list"),
            {
                "title": "Prepare employee laptop",
                "description": "Install the standard image.",
                "assignee": self.employee.id,
                "requester": self.manager.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        task = Task.objects.get(id=response.data["id"])
        self.assertEqual(task.requester, self.admin)

    def test_notifications_are_private_and_only_read_state_is_mutable(self):
        notification = Notification.objects.create(
            user=self.employee,
            message="A private workflow update.",
        )
        self.client.force_authenticate(user=self.admin)

        hidden = self.client.get(
            reverse("notification-detail", args=[notification.id])
        )
        self.assertEqual(hidden.status_code, status.HTTP_404_NOT_FOUND)

        self.client.force_authenticate(user=self.employee)
        updated = self.client.patch(
            reverse("notification-detail", args=[notification.id]),
            {"is_read": True, "message": "Tampered"},
            format="json",
        )
        self.assertEqual(updated.status_code, status.HTTP_200_OK)
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)
        self.assertEqual(notification.message, "A private workflow update.")

    def test_superuser_role_can_manage_tasks_even_when_user_role_is_employee(self):
        superuser = User.objects.create_superuser(
            username="root",
            email="root@example.com",
            password="Password123!",
        )
        self.client.force_authenticate(user=superuser)

        listing = self.client.get(reverse("task-list"))
        created = self.client.post(
            reverse("task-list"),
            {
                "title": "Assign an employee task",
                "assignee": self.employee.id,
            },
            format="json",
        )

        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        self.assertEqual(len(listing.data), 1)
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)

    def test_user_directory_is_scoped_to_direct_reports_for_managers(self):
        self.client.force_authenticate(user=self.manager)

        response = self.client.get(reverse("user-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            {user["id"] for user in response.data},
            {self.manager.id, self.employee.id},
        )
