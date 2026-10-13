from django.contrib import admin

from .models import EmployeeFeedback, FeedbackActionItem

admin.site.register(EmployeeFeedback)
admin.site.register(FeedbackActionItem)
