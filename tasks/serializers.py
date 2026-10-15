from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Notification, Task, TaskComment

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
    assignee = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), allow_null=True, required=False)
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

    def get_assignee_name(self, obj):
        if obj.assignee:
            return obj.assignee.get_full_name() or obj.assignee.username
        return None

    def get_requester_name(self, obj):
        if obj.requester:
            return obj.requester.get_full_name() or obj.requester.username
        return None

    def validate(self, attrs):
        user = self.context["request"].user
        if (
            attrs.get("assignee")
            and attrs["assignee"].id != user.id
            and not user.is_superuser
            and user.role not in {"administrator", "it_manager"}
        ):
            raise serializers.ValidationError("Employees may only assign work to themselves.")
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
