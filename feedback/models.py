from django.conf import settings
from django.db import models

from tasks.models import Task


class EmployeeFeedback(models.Model):
    class Category(models.TextChoices):
        POSITIVE = "positive_recognition", "Positive recognition"
        TECHNICAL = "technical_skills", "Technical skills"
        TEAMWORK = "communication_teamwork", "Communication and teamwork"
        QUALITY = "task_quality", "Task quality"
        TIME = "time_management", "Time management"
        IMPROVEMENT = "areas_for_improvement", "Areas for improvement"
        COACHING = "coaching_development", "Coaching and development"

    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="received_feedback",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="authored_feedback",
    )
    task = models.ForeignKey(
        Task,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employee_feedback",
    )
    category = models.CharField(max_length=40, choices=Category.choices)
    content = models.TextField()
    feedback_date = models.DateField()
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    employee_response = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-feedback_date", "-created_at"]

    def __str__(self):
        return f"{self.get_category_display()} for {self.employee}"


class FeedbackActionItem(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"

    feedback = models.ForeignKey(
        EmployeeFeedback,
        on_delete=models.PROTECT,
        related_name="action_items",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="feedback_action_items",
    )
    title = models.CharField(max_length=300)
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["status", "due_date", "created_at"]

    def __str__(self):
        return self.title
