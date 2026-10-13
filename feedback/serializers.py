from django.contrib.auth import get_user_model
from rest_framework import serializers

from tasks.models import Task

from .models import EmployeeFeedback, FeedbackActionItem

User = get_user_model()


class EmployeeFeedbackSerializer(serializers.ModelSerializer):
    employee = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    employee_name = serializers.SerializerMethodField()
    author_name = serializers.SerializerMethodField()
    task_title = serializers.CharField(source="task.title", read_only=True)
    action_items = serializers.SerializerMethodField()

    class Meta:
        model = EmployeeFeedback
        fields = [
            "id",
            "employee",
            "employee_name",
            "author",
            "author_name",
            "task",
            "task_title",
            "category",
            "content",
            "feedback_date",
            "acknowledged_at",
            "employee_response",
            "created_at",
            "action_items",
        ]
        read_only_fields = [
            "id",
            "employee_name",
            "author",
            "author_name",
            "acknowledged_at",
            "employee_response",
            "created_at",
        ]

    def get_employee_name(self, obj):
        return obj.employee.get_full_name() or obj.employee.username

    def get_author_name(self, obj):
        return obj.author.get_full_name() or obj.author.username

    def get_action_items(self, obj):
        return [
            {
                "id": item.id,
                "assigned_to": item.assigned_to_id,
                "title": item.title,
                "due_date": item.due_date,
                "status": item.status,
                "completed_at": item.completed_at,
            }
            for item in obj.action_items.all()
        ]

    def validate(self, attrs):
        task = attrs.get("task")
        employee = attrs.get("employee")
        if task and employee and task.assignee_id != employee.id:
            raise serializers.ValidationError(
                {"task": "Related tasks must be assigned to the feedback recipient."}
            )
        return attrs


class FeedbackActionCreateSerializer(serializers.ModelSerializer):
    assigned_to = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())

    class Meta:
        model = FeedbackActionItem
        fields = ["id", "assigned_to", "title", "due_date"]
        read_only_fields = ["id"]


class FeedbackActionSerializer(serializers.ModelSerializer):
    feedback_employee = serializers.IntegerField(source="feedback.employee_id", read_only=True)
    feedback_title = serializers.CharField(source="feedback.content", read_only=True)

    class Meta:
        model = FeedbackActionItem
        fields = [
            "id",
            "feedback",
            "feedback_employee",
            "feedback_title",
            "assigned_to",
            "title",
            "due_date",
            "status",
            "completed_at",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "feedback",
            "feedback_employee",
            "feedback_title",
            "assigned_to",
            "title",
            "due_date",
            "completed_at",
            "created_at",
        ]


class FeedbackResponseSerializer(serializers.Serializer):
    response = serializers.CharField(allow_blank=False, trim_whitespace=True)


class FeedbackActionStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=FeedbackActionItem.Status.choices)
