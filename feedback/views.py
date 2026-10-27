from django.utils import timezone
from rest_framework import permissions, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from tasks.access import is_administrator
from tasks.models import Notification, User

from .models import EmployeeFeedback, FeedbackActionItem
from .serializers import (
    EmployeeFeedbackSerializer,
    FeedbackActionCreateSerializer,
    FeedbackActionSerializer,
    FeedbackActionStatusSerializer,
    FeedbackResponseSerializer,
)


class EmployeeFeedbackViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = EmployeeFeedbackSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        feedback = EmployeeFeedback.objects.select_related(
            "employee", "author", "task"
        ).prefetch_related("action_items")
        if is_administrator(user):
            return feedback
        if user.role == User.Role.IT_MANAGER:
            return feedback.none()
        return feedback.filter(employee=user)

    def create(self, request, *args, **kwargs):
        if not is_administrator(request.user):
            raise PermissionDenied("Only administrators can publish employee feedback.")
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        raise PermissionDenied("Published feedback is retained as an immutable record.")

    def partial_update(self, request, *args, **kwargs):
        raise PermissionDenied("Published feedback is retained as an immutable record.")

    def perform_create(self, serializer):
        employee = serializer.validated_data["employee"]
        if not is_administrator(self.request.user):
            raise PermissionDenied("Only administrators can publish employee feedback.")
        feedback = serializer.save(author=self.request.user)
        Notification.objects.create(
            user=employee,
            task=feedback.task,
            message="New private employee feedback is available for you.",
        )

    @action(detail=False, methods=["get"], url_path="me")
    def me(self, request):
        feedback = self.get_queryset().filter(employee=request.user)
        return Response(self.get_serializer(feedback, many=True).data)

    @action(detail=True, methods=["post"], url_path="acknowledge")
    def acknowledge(self, request, pk=None):
        feedback = self.get_object()
        if feedback.employee_id != request.user.id:
            raise PermissionDenied("Only the feedback recipient can acknowledge it.")
        if feedback.acknowledged_at is None:
            feedback.acknowledged_at = timezone.now()
            feedback.save(update_fields=["acknowledged_at"])
        return Response(self.get_serializer(feedback).data)

    @action(detail=True, methods=["post"], url_path="responses")
    def responses(self, request, pk=None):
        feedback = self.get_object()
        if feedback.employee_id != request.user.id:
            raise PermissionDenied("Only the feedback recipient can respond.")
        serializer = FeedbackResponseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        feedback.employee_response = serializer.validated_data["response"]
        feedback.save(update_fields=["employee_response"])
        return Response(self.get_serializer(feedback).data)

    @action(detail=True, methods=["post"], url_path="actions")
    def create_action(self, request, pk=None):
        if not is_administrator(request.user):
            raise PermissionDenied("Only administrators can create feedback follow-up actions.")
        feedback = self.get_object()
        serializer = FeedbackActionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        assigned_to = serializer.validated_data["assigned_to"]
        if assigned_to.id not in {feedback.employee_id, feedback.author_id}:
            raise serializers.ValidationError(
                {"assigned_to": "Assign the action to the employee or the feedback author."}
            )
        action_item = serializer.save(feedback=feedback)
        Notification.objects.create(
            user=assigned_to,
            task=feedback.task,
            message=f"New feedback follow-up action: {action_item.title}",
        )
        return Response(
            FeedbackActionSerializer(action_item).data,
            status=status.HTTP_201_CREATED,
        )


class FeedbackActionViewSet(viewsets.ModelViewSet):
    serializer_class = FeedbackActionSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        user = self.request.user
        actions = FeedbackActionItem.objects.select_related(
            "feedback", "feedback__employee", "feedback__author", "assigned_to"
        )
        if is_administrator(user):
            return actions
        if user.role == User.Role.IT_MANAGER:
            return actions.none()
        return actions.filter(assigned_to=user)

    def partial_update(self, request, *args, **kwargs):
        action_item = self.get_object()
        if (
            action_item.assigned_to_id != request.user.id
            and not is_administrator(request.user)
        ):
            raise PermissionDenied("Only the action owner or an administrator can update it.")
        serializer = FeedbackActionStatusSerializer(
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        if "status" not in serializer.validated_data:
            raise serializers.ValidationError({"status": "A status is required."})
        action_item.status = serializer.validated_data["status"]
        action_item.completed_at = (
            timezone.now()
            if action_item.status == FeedbackActionItem.Status.COMPLETED
            else None
        )
        action_item.save(update_fields=["status", "completed_at"])
        return Response(self.get_serializer(action_item).data)
