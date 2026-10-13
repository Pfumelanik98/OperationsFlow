from django.urls import path
from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .dashboard import employee_operations_dashboard


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def current_user(request):
    user = request.user
    return Response(
        {
            "id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role": user.role,
            "is_superuser": user.is_superuser,
            "manager": user.manager_id,
        }
    )


urlpatterns = [
    path("accounts/me/", current_user, name="current-user"),
    path(
        "dashboard/employee-operations/",
        employee_operations_dashboard,
        name="employee-operations-dashboard",
    ),
]
