# pyright: reportMissingImports=false
from django.db.models import QuerySet
from django.db.models import Q
from rest_framework import permissions, serializers, viewsets  # type: ignore[import-not-found]
from rest_framework.decorators import action  # type: ignore[import-not-found]
from rest_framework.exceptions import PermissionDenied  # type: ignore[import-not-found]
from rest_framework.response import Response  # type: ignore[import-not-found]

from .access import can_manage_employee, is_administrator
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
        if is_administrator(user):
            return qs.order_by("-updated_at")
        if user.role == User.Role.IT_MANAGER:
            return qs.filter(
                Q(assignee=user)
                | Q(assignee__manager=user)
                | Q(requester=user)
            ).distinct().order_by("-updated_at")
        return qs.filter(assignee=user).order_by("-updated_at")

    @action(detail=False, methods=["get"], url_path="my-tasks")
    def my_tasks(self, request):
        tasks = self.get_queryset().filter(assignee=request.user)
        return Response(self.get_serializer(tasks, many=True).data)

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
        assignee = serializer.validated_data.get("assignee")
        if (
            assignee
            and user.role == User.Role.IT_MANAGER
            and not is_administrator(user)
            and assignee.id != user.id
            and not can_manage_employee(user, assignee)
        ):
            raise serializers.ValidationError(
                {"assignee": "Managers may only assign tasks to their direct reports."}
            )
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
        if not can_manage_department_tasks(user):
            if request.method != "PATCH":
                raise PermissionDenied("Employees may update task status only.")
            if set(request.data.keys()) - {"status"}:
                raise serializers.ValidationError(
                    {"detail": "Employees may update task status only."}
                )
        return super().update(request, *args, **kwargs)

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
        if is_administrator(user):
            return TaskComment.objects.select_related("task", "author").all()
        if user.role == User.Role.IT_MANAGER:
            return TaskComment.objects.select_related("task", "author").filter(
                Q(task__assignee=user)
                | Q(task__assignee__manager=user)
                | Q(task__requester=user)
            ).distinct()
        return TaskComment.objects.select_related("task", "author").filter(task__assignee=user)

    def perform_create(self, serializer):
        task = serializer.validated_data["task"]
        user = operations_user(self.request.user)
        if (
            not is_administrator(user)
            and task.assignee_id != user.pk
            and task.requester_id != user.pk
            and not (
                task.assignee and can_manage_employee(user, task.assignee)
            )
        ):
            raise PermissionDenied("You may only comment on tasks you own or manage.")
        serializer.save(author=user)
