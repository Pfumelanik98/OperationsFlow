from django.contrib.auth import get_user_model
from rest_framework import permissions, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Notification, Task, TaskComment, User
from .serializers import NotificationSerializer, TaskCommentSerializer, TaskSerializer, UserSerializer

UserModel = get_user_model()
ADMIN_ACTION_ROLES = {UserModel.Role.ADMINISTRATOR, UserModel.Role.IT_MANAGER}


class IsAuthenticatedUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)


class TaskViewSet(viewsets.ModelViewSet):
    queryset = Task.objects.select_related("assignee", "requester").all()
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticatedUser]

    def get_queryset(self):
        user = self.request.user
        qs = Task.objects.select_related("assignee", "requester").all()
        if user.role in ADMIN_ACTION_ROLES:
            return qs.order_by("-updated_at")
        return qs.filter(assignee=user).order_by("-updated_at")

    def create(self, request, *args, **kwargs):
        user = request.user
        payload = request.data.copy()
        if "assignee" in payload and payload["assignee"] and user.role not in ADMIN_ACTION_ROLES:
            assignee_id = int(payload["assignee"])
            if assignee_id != user.id:
                raise serializers.ValidationError({"assignee": "Employees can only assign tasks to themselves."})
        if "requester" not in payload:
            payload["requester"] = user.id
        serializer = self.get_serializer(data=payload)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=201, headers=headers)

    def update(self, request, *args, **kwargs):
        task = self.get_object()
        user = request.user
        if user.role not in ADMIN_ACTION_ROLES and task.assignee_id != user.id:
            raise permissions.PermissionDenied("You can only update your own assigned tasks.")
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        task = self.get_object()
        user = request.user
        if user.role not in ADMIN_ACTION_ROLES and task.assignee_id != user.id:
            raise permissions.PermissionDenied("You can only update your own assigned tasks.")
        return super().partial_update(request, *args, **kwargs)

    @action(detail=True, methods=["post"], url_path="comment")
    def add_comment(self, request, pk=None):
        task = self.get_object()
        body = request.data.get("body", "").strip()
        if not body:
            raise serializers.ValidationError({"body": "A comment cannot be empty."})
        comment = TaskComment.objects.create(task=task, author=request.user, body=body)
        return Response(TaskCommentSerializer(comment).data, status=201)


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = UserModel.objects.order_by("username")
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticatedUser]


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticatedUser]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user).order_by("-created_at")


class TaskCommentViewSet(viewsets.ModelViewSet):
    serializer_class = TaskCommentSerializer
    permission_classes = [IsAuthenticatedUser]

    def get_queryset(self):
        user = self.request.user
        if user.role in ADMIN_ACTION_ROLES:
            return TaskComment.objects.select_related("task", "author").all()
        return TaskComment.objects.select_related("task", "author").filter(task__assignee=user)

    def perform_create(self, serializer):
        task = serializer.validated_data["task"]
        user = self.request.user
        if user.role not in ADMIN_ACTION_ROLES and task.assignee_id != user.id:
            raise permissions.PermissionDenied("You can only comment on tasks assigned to you.")
        serializer.save(author=user)
