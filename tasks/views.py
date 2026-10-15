# pyright: reportMissingImports=false
from django.db.models import QuerySet
from django.db.models import Q
from django.utils import timezone
from rest_framework import permissions, serializers, viewsets  # type: ignore[import-not-found]
from rest_framework.decorators import action  # type: ignore[import-not-found]
from rest_framework.exceptions import PermissionDenied  # type: ignore[import-not-found]
from rest_framework.response import Response  # type: ignore[import-not-found]

from .access import is_administrator
from .models import Notification, Task, TaskComment, TaskCompletionReport, User
from .serializers import (
    NotificationSerializer,
    TaskCommentSerializer,
    TaskCompletionReportReviewSerializer,
    TaskCompletionReportSerializer,
    TaskSerializer,
    UserSerializer,
)

def can_manage_department_tasks(user):
    return is_administrator(user)


def can_view_task(user, task):
    return (
        is_administrator(user)
        or task.assignee_id == user.id
        or (
            user.role == User.Role.IT_MANAGER
            and task.assignee is not None
            and task.assignee.manager_id == user.id
        )
    )


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
                Q(assignee=user) | Q(assignee__manager=user)
            ).distinct().order_by("-updated_at")
        return qs.filter(assignee=user).order_by("-updated_at")

    @action(detail=False, methods=["get"], url_path="my-tasks")
    def my_tasks(self, request):
        tasks = Task.objects.select_related("assignee", "requester").filter(
            assignee=request.user
        ).order_by("-updated_at")
        return Response(self.get_serializer(tasks, many=True).data)

    def create(self, request, *args, **kwargs):
        user = operations_user(request.user)
        if not is_administrator(user):
            raise PermissionDenied("Only administrators can create and assign tasks.")
        payload = request.data.copy()
        if not payload.get("assignee"):
            raise serializers.ValidationError({"assignee": "Select an employee to assign this task to."})
        serializer = self.get_serializer(data=payload)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=201, headers=headers)

    def perform_create(self, serializer):
        task = serializer.save(requester=operations_user(self.request.user))
        if task.assignee_id:
            Notification.objects.create(
                user=task.assignee,
                task=task,
                message=f"New task assigned: {task.title}",
            )

    def update(self, request, *args, **kwargs):
        task = self.get_object()
        user = operations_user(request.user)
        if not is_administrator(user):
            raise PermissionDenied("Only administrators can edit task details.")
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        task = self.get_object()
        user = operations_user(request.user)
        if not is_administrator(user):
            raise PermissionDenied("Only administrators can update task details.")
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        user = operations_user(request.user)
        if not is_administrator(user):
            raise PermissionDenied("Only administrators can delete tasks.")
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["post"], url_path="comment")
    def add_comment(self, request, pk=None):
        if not is_administrator(request.user):
            raise PermissionDenied("Only administrators can add task comments.")
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


class TaskCompletionReportViewSet(viewsets.ModelViewSet):
    serializer_class = TaskCompletionReportSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self) -> QuerySet[TaskCompletionReport]:
        user = self.request.user
        reports = TaskCompletionReport.objects.select_related(
            "task", "employee", "reviewed_by"
        )
        if not isinstance(user, User):
            return TaskCompletionReport.objects.none()
        if is_administrator(user):
            return reports
        if user.role == User.Role.IT_MANAGER:
            return reports.filter(employee__manager=user)
        return reports.filter(employee=user)

    def create(self, request, *args, **kwargs):
        user = operations_user(request.user)
        if is_administrator(user) or user.role == User.Role.IT_MANAGER:
            raise PermissionDenied("Only employees can submit task completion reports.")
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task = serializer.validated_data["task"]
        if task.assignee_id != user.id:
            raise PermissionDenied("You can only report on a task assigned to you.")
        if task.status == Task.Status.COMPLETED:
            raise serializers.ValidationError(
                {"task": "This task has already been completed."}
            )
        report = serializer.save(employee=user)
        self._notify_reviewers(report)
        return Response(
            self.get_serializer(report).data,
            status=201,
            headers=self.get_success_headers(serializer.data),
        )

    def update(self, request, *args, **kwargs):
        raise PermissionDenied("Completion reports can only be resubmitted after changes are requested.")

    def partial_update(self, request, *args, **kwargs):
        report = self.get_object()
        user = operations_user(request.user)
        if report.employee_id != user.id:
            raise PermissionDenied("You can only resubmit your own completion report.")
        if report.status != TaskCompletionReport.Status.CHANGES_REQUESTED:
            raise serializers.ValidationError(
                {"status": "You can resubmit only after a manager requests changes."}
            )
        allowed_fields = {"summary", "issues", "time_spent_minutes"}
        if set(request.data.keys()) - allowed_fields:
            raise serializers.ValidationError(
                {"detail": "Only the report summary, issues, and time spent may be changed."}
            )
        serializer = self.get_serializer(report, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        report = serializer.save(
            status=TaskCompletionReport.Status.SUBMITTED,
            review_note="",
            reviewed_by=None,
            reviewed_at=None,
        )
        self._notify_reviewers(report)
        return Response(self.get_serializer(report).data)

    @action(detail=True, methods=["post"], url_path="review")
    def review(self, request, pk=None):
        report = self.get_object()
        user = operations_user(request.user)
        if not is_administrator(user) and (
            user.role != User.Role.IT_MANAGER
            or report.employee.manager_id != user.id
        ):
            raise PermissionDenied("Only the employee's manager or an administrator may review this report.")
        if report.status != TaskCompletionReport.Status.SUBMITTED:
            raise serializers.ValidationError(
                {"status": "Only submitted reports can be reviewed."}
            )
        serializer = TaskCompletionReportReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        report.status = serializer.validated_data["status"]
        report.review_note = serializer.validated_data.get("review_note", "").strip()
        report.reviewed_by = user
        report.reviewed_at = timezone.now()
        report.save(
            update_fields=[
                "status",
                "review_note",
                "reviewed_by",
                "reviewed_at",
                "updated_at",
            ]
        )
        if report.status == TaskCompletionReport.Status.APPROVED:
            report.task.status = Task.Status.COMPLETED
            report.task.save(update_fields=["status", "updated_at"])
        else:
            report.task.status = Task.Status.IN_PROGRESS
            report.task.save(update_fields=["status", "updated_at"])
        Notification.objects.create(
            user=report.employee,
            task=report.task,
            message=(
                f"Your completion report for {report.task.title} was approved."
                if report.status == TaskCompletionReport.Status.APPROVED
                else f"Changes were requested for your report on {report.task.title}: {report.review_note}"
            ),
        )
        return Response(self.get_serializer(report).data)

    def _notify_reviewers(self, report: TaskCompletionReport) -> None:
        if report.employee.manager_id:
            reviewers = User.objects.filter(pk=report.employee.manager_id)
        else:
            reviewers = User.objects.filter(
                Q(is_superuser=True) | Q(role=User.Role.ADMINISTRATOR),
                is_active=True,
            )
        for reviewer in reviewers:
            Notification.objects.create(
                user=reviewer,
                task=report.task,
                message=f"Completion report submitted for review: {report.task.title}",
            )


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
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self) -> QuerySet[TaskComment]:  # type: ignore[override]
        user = self.request.user
        if not isinstance(user, User):
            return TaskComment.objects.none()
        if is_administrator(user):
            return TaskComment.objects.select_related("task", "author").all()
        if user.role == User.Role.IT_MANAGER:
            return TaskComment.objects.select_related("task", "author").filter(
                Q(task__assignee=user) | Q(task__assignee__manager=user)
            ).distinct()
        return TaskComment.objects.select_related("task", "author").filter(task__assignee=user)

    def perform_create(self, serializer):
        task = serializer.validated_data["task"]
        user = operations_user(self.request.user)
        if not is_administrator(user):
            raise PermissionDenied("Only administrators can create task comments.")
        if not can_view_task(user, task):
            raise PermissionDenied("You may only comment on your own tasks or your direct reports' tasks.")
        serializer.save(author=user)
