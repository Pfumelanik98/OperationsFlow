from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Notification, Task, TaskComment, TaskCompletionReport

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    manager_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "manager",
            "manager_name",
        ]

    def get_manager_name(self, obj):
        if obj.manager:
            return obj.manager.get_full_name() or obj.manager.username
        return None


class TaskSerializer(serializers.ModelSerializer):
    assignee = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(is_active=True))
    requester = serializers.PrimaryKeyRelatedField(read_only=True)
    assignee_name = serializers.SerializerMethodField()
    requester_name = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = [
            "id",
            "title",
            "description",
            "status",
            "priority",
            "due_date",
            "assignee",
            "assignee_name",
            "requester",
            "requester_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def validate_assignee(self, assignee):
        if assignee.role != User.Role.IT_EMPLOYEE:
            raise serializers.ValidationError("Tasks may only be assigned to IT employees.")
        return assignee

    def get_assignee_name(self, obj):
        if obj.assignee:
            return obj.assignee.get_full_name() or obj.assignee.username
        return None

    def get_requester_name(self, obj):
        if obj.requester:
            return obj.requester.get_full_name() or obj.requester.username
        return None

class TaskCompletionReportSerializer(serializers.ModelSerializer):
    task_title = serializers.CharField(source="task.title", read_only=True)
    employee = serializers.IntegerField(source="employee_id", read_only=True)
    employee_name = serializers.SerializerMethodField()
    reviewed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = TaskCompletionReport
        fields = [
            "id",
            "task",
            "task_title",
            "employee",
            "employee_name",
            "summary",
            "issues",
            "time_spent_minutes",
            "status",
            "review_note",
            "reviewed_by",
            "reviewed_by_name",
            "reviewed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "employee",
            "employee_name",
            "status",
            "review_note",
            "reviewed_by",
            "reviewed_by_name",
            "reviewed_at",
            "created_at",
            "updated_at",
        ]

    def get_employee_name(self, obj):
        return obj.employee.get_full_name() or obj.employee.username

    def get_reviewed_by_name(self, obj):
        if obj.reviewed_by:
            return obj.reviewed_by.get_full_name() or obj.reviewed_by.username
        return None


class TaskCompletionReportReviewSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=[
            TaskCompletionReport.Status.APPROVED,
            TaskCompletionReport.Status.CHANGES_REQUESTED,
        ]
    )
    review_note = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        if (
            attrs["status"] == TaskCompletionReport.Status.CHANGES_REQUESTED
            and not attrs.get("review_note", "").strip()
        ):
            raise serializers.ValidationError(
                {"review_note": "Provide a reason when requesting changes."}
            )
        return attrs


class TaskCommentSerializer(serializers.ModelSerializer):
    author = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = TaskComment
        fields = ["id", "task", "author", "body", "created_at"]
        read_only_fields = ["author", "created_at"]


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "user", "task", "message", "is_read", "created_at"]
        read_only_fields = ["user", "task", "message", "created_at"]
