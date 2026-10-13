from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AttendanceCheckInView,
    AttendanceCheckOutView,
    AttendanceViewSet,
    LeaveRequestViewSet,
    PublicHolidayViewSet,
    WorkScheduleViewSet,
    attendance_report,
)

router = DefaultRouter()
router.register("leave-requests", LeaveRequestViewSet, basename="leave-request")
router.register("schedules", WorkScheduleViewSet, basename="work-schedule")
router.register("holidays", PublicHolidayViewSet, basename="public-holiday")
router.register("", AttendanceViewSet, basename="attendance-record")

urlpatterns = [
    path("check-in/", AttendanceCheckInView.as_view(), name="attendance-check-in"),
    path("check-out/", AttendanceCheckOutView.as_view(), name="attendance-check-out"),
    path("reports/", attendance_report, name="attendance-report"),
    path("", include(router.urls)),
]
