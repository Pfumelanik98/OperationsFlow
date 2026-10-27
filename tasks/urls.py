from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework.authtoken.views import obtain_auth_token

from .views import (
    NotificationViewSet,
    TaskCommentViewSet,
    TaskCompletionReportViewSet,
    TaskViewSet,
    UserViewSet,
)

router = DefaultRouter()
router.register(r"tasks", TaskViewSet, basename="task")
router.register(r"task-reports", TaskCompletionReportViewSet, basename="task-report")
router.register(r"users", UserViewSet, basename="user")
router.register(r"notifications", NotificationViewSet, basename="notification")
router.register(r"comments", TaskCommentViewSet, basename="comment")

urlpatterns = [
    path("auth/login/", obtain_auth_token, name="api-token-auth"),
    path("", include(router.urls)),
]
