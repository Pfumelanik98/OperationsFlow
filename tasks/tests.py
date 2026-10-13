from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Task

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
