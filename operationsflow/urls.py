from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("tasks.urls")),
    path("api/v1/attendance/", include("attendance.urls")),
    path("api/v1/feedback/", include("feedback.urls")),
    path("api/v1/", include("operationsflow.api_urls")),
    path("api-auth/", include("rest_framework.urls")),
]
