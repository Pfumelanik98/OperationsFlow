from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Notification, Task

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

    def test_manager_can_list_all_tasks(self):
        self.client.force_authenticate(user=self.manager)
        response = self.client.get(reverse("task-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)

    def test_employee_cannot_assign_task_to_someone_else(self):
        self.client.force_authenticate(user=self.employee)
        response = self.client.post(
            reverse("task-list"),
            {
                "title": "Install software",
                "description": "Install a standard office suite.",
                "assignee": self.manager.id,
                "requester": self.admin.id,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_task_requester_is_always_the_authenticated_creator(self):
        self.client.force_authenticate(user=self.manager)

        response = self.client.post(
            reverse("task-list"),
            {
                "title": "Prepare employee laptop",
                "description": "Install the standard image.",
                "requester": self.admin.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        task = Task.objects.get(id=response.data["id"])
        self.assertEqual(task.requester, self.manager)

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
