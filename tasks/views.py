# pyright: reportMissingImports=false
from django.db.models import QuerySet
from django.db.models import Q
from rest_framework import permissions, serializers, viewsets  # type: ignore[import-not-found]
from rest_framework.decorators import action  # type: ignore[import-not-found]
from rest_framework.exceptions import PermissionDenied  # type: ignore[import-not-found]
from rest_framework.response import Response  # type: ignore[import-not-found]

from .access import is_administrator
from .models import Notification, Task, TaskComment, User
from .serializers import NotificationSerializer, TaskCommentSerializer, TaskSerializer, UserSerializer

def can_manage_department_tasks(user):
    return is_administrator(user) or user.role == User.Role.IT_MANAGER


def operations_user(candidate):
    if not isinstance(candidate, User):
        raise PermissionDenied("An authenticated OperationsFlow user is required.")
    return candidate


class TaskViewSet(viewsets.ModelViewSet):
    queryset = Task.objects.select_related("assignee", "requester").all()
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self) -> QuerySet[Task]:  # type: ignore[override]
        user = self.request.user
        if not isinstance(user, User):
            return Task.objects.none()
        qs = Task.objects.select_related("assignee", "requester").all()
        if can_manage_department_tasks(user):
            return qs.order_by("-updated_at")
        return qs.filter(assignee=user).order_by("-updated_at")

    def create(self, request, *args, **kwargs):
        user = operations_user(request.user)
        payload = request.data.copy()
        if "assignee" in payload and payload["assignee"] and not can_manage_department_tasks(user):
            try:
                assignee_id = int(payload["assignee"])
            except (TypeError, ValueError):
                assignee_id = None
            if assignee_id is not None and assignee_id != user.pk:
                raise serializers.ValidationError({"assignee": "Employees can only assign tasks to themselves."})
        serializer = self.get_serializer(data=payload)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=201, headers=headers)

    def perform_create(self, serializer):
        serializer.save(requester=operations_user(self.request.user))

    def update(self, request, *args, **kwargs):
        task = self.get_object()
        user = operations_user(request.user)
        if not can_manage_department_tasks(user) and task.assignee_id != user.pk:
            raise PermissionDenied("You can only update your own assigned tasks.")
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        task = self.get_object()
        user = operations_user(request.user)
        if not can_manage_department_tasks(user) and task.assignee_id != user.pk:
            raise PermissionDenied("You can only update your own assigned tasks.")
        return super().partial_update(request, *args, **kwargs)

    @action(detail=True, methods=["post"], url_path="comment")
    def add_comment(self, request, pk=None):
        task = self.get_object()
        body = request.data.get("body", "").strip()
        if not body:
            raise serializers.ValidationError({"body": "A comment cannot be empty."})
        comment = TaskComment.objects.create(
            task=task,
            author=operations_user(request.user),
            body=body,
        )
        return Response(TaskCommentSerializer(comment).data, status=201)


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = User.objects.order_by("username")
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self) -> QuerySet[User]:  # type: ignore[override]
        user = self.request.user
        if not isinstance(user, User):
            return User.objects.none()
        if is_administrator(user):
            return User.objects.filter(is_active=True).order_by("username")
        if user.role == User.Role.IT_MANAGER:
            return User.objects.filter(
                Q(pk=user.pk) | Q(manager=user),
                is_active=True,
            ).order_by("username")
        return User.objects.filter(pk=user.pk)


class NotificationViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self) -> QuerySet[Notification]:  # type: ignore[override]
        user = self.request.user
        if not isinstance(user, User):
            return Notification.objects.none()
        return Notification.objects.filter(user=user).order_by("-created_at")


class TaskCommentViewSet(viewsets.ModelViewSet):
    serializer_class = TaskCommentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self) -> QuerySet[TaskComment]:  # type: ignore[override]
        user = self.request.user
        if not isinstance(user, User):
            return TaskComment.objects.none()
        if can_manage_department_tasks(user):
            return TaskComment.objects.select_related("task", "author").all()
        return TaskComment.objects.select_related("task", "author").filter(task__assignee=user)

    def perform_create(self, serializer):
        task = serializer.validated_data["task"]
        user = operations_user(self.request.user)
        if not can_manage_department_tasks(user) and task.assignee_id != user.pk:
            raise PermissionDenied("You can only comment on tasks assigned to you.")
        serializer.save(author=user)
