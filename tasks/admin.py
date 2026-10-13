from django.contrib import admin

from .models import Notification, Task, TaskComment, User

admin.site.register(User)
admin.site.register(Task)
admin.site.register(TaskComment)
admin.site.register(Notification)
