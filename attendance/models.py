from django.conf import settings
from django.db import models
from django.db.models import F, Q


class PublicHoliday(models.Model):
    date = models.DateField(unique=True)
    name = models.CharField(max_length=150)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["date"]

    def __str__(self):
        return f"{self.date}: {self.name}"


class WorkSchedule(models.Model):
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="work_schedules",
    )
    weekday = models.PositiveSmallIntegerField(
        choices=[
            (0, "Monday"),
            (1, "Tuesday"),
            (2, "Wednesday"),
            (3, "Thursday"),
            (4, "Friday"),
            (5, "Saturday"),
            (6, "Sunday"),
        ]
    )
    start_time = models.TimeField()
    end_time = models.TimeField()
    grace_period_minutes = models.PositiveSmallIntegerField(default=0)
    effective_from = models.DateField()
    effective_until = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["employee_id", "weekday", "-effective_from"]
        constraints = [
            models.UniqueConstraint(
                fields=["employee", "weekday", "effective_from"],
                name="unique_employee_schedule_start",
            ),
            models.CheckConstraint(
                condition=Q(end_time__gt=F("start_time")),
                name="schedule_end_after_start",
            ),
            models.CheckConstraint(
                condition=Q(effective_until__isnull=True)
                | Q(effective_until__gte=F("effective_from")),
                name="schedule_valid_effective_range",
            ),
        ]

    def __str__(self):
        return f"{self.employee} schedule on weekday {self.weekday}"


class LeaveRequest(models.Model):
    class LeaveType(models.TextChoices):
        ANNUAL = "annual", "Annual"
        SICK = "sick", "Sick"
        PERSONAL = "personal", "Personal"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="leave_requests",
    )
    start_date = models.DateField()
    end_date = models.DateField()
    leave_type = models.CharField(max_length=20, choices=LeaveType.choices)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_leave_requests",
    )
    review_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(end_date__gte=F("start_date")),
                name="leave_end_on_or_after_start",
            )
        ]

    def __str__(self):
        return f"{self.employee} leave {self.start_date} to {self.end_date}"


class AttendanceRecord(models.Model):
    class Status(models.TextChoices):
        PRESENT = "present", "Present"
        LATE = "late", "Late"
        ABSENT = "absent", "Absent"
        ON_LEAVE = "on_leave", "On leave"
        HALF_DAY = "half_day", "Half day"
        PENDING_REVIEW = "pending_review", "Pending review"

    class Source(models.TextChoices):
        SELF_SERVICE = "self_service", "Self service"
        MANAGER = "manager", "Manager entry"

    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="attendance_records",
    )
    work_date = models.DateField()
    check_in = models.DateTimeField(null=True, blank=True)
    check_out = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING_REVIEW,
    )
    is_remote = models.BooleanField(default=False)
    source = models.CharField(
        max_length=20,
        choices=Source.choices,
        default=Source.SELF_SERVICE,
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recorded_attendance",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-work_date", "employee_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["employee", "work_date"],
                name="unique_attendance_employee_work_date",
            ),
            models.CheckConstraint(
                condition=Q(check_out__isnull=True)
                | Q(check_in__isnull=True)
                | Q(check_out__gt=F("check_in")),
                name="attendance_checkout_after_checkin",
            ),
        ]

    def __str__(self):
        return f"{self.employee} attendance on {self.work_date}"


class AttendanceCorrection(models.Model):
    attendance = models.ForeignKey(
        AttendanceRecord,
        on_delete=models.PROTECT,
        related_name="corrections",
    )
    corrected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="attendance_corrections",
    )
    reason = models.TextField()
    previous_values = models.JSONField()
    corrected_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-corrected_at"]

    def __str__(self):
        return f"Correction for attendance {self.attendance_id}"
