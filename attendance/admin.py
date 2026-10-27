from django.contrib import admin

from .models import (
    AttendanceCorrection,
    AttendanceRecord,
    LeaveRequest,
    PublicHoliday,
    WorkSchedule,
)

admin.site.register(AttendanceRecord)
admin.site.register(AttendanceCorrection)
admin.site.register(LeaveRequest)
admin.site.register(PublicHoliday)
admin.site.register(WorkSchedule)
