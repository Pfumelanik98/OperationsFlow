from .models import User


def is_administrator(user):
    return user.is_superuser or user.role == User.Role.ADMINISTRATOR


def can_manage_employee(user, employee):
    return is_administrator(user) or (
        user.role == User.Role.IT_MANAGER and employee.manager_id == user.id
    )


def manageable_employee_ids(user):
    if is_administrator(user):
        return User.objects.filter(is_active=True).values("id")
    if user.role == User.Role.IT_MANAGER:
        return User.objects.filter(manager=user, is_active=True).values("id")
    return User.objects.filter(pk=user.pk).values("id")
