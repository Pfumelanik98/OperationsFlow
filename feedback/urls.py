from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import EmployeeFeedbackViewSet, FeedbackActionViewSet

router = DefaultRouter()
router.register("actions", FeedbackActionViewSet, basename="feedback-action")
router.register("", EmployeeFeedbackViewSet, basename="feedback")

urlpatterns = [
    path("", include(router.urls)),
]
