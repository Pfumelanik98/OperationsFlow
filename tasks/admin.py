from django.contrib import admin

from .models import Notification, Task, TaskComment, TaskCompletionReport, User

admin.site.register(User)
admin.site.register(Task)
admin.site.register(TaskComment)
admin.site.register(TaskCompletionReport)
admin.site.register(Notification)
