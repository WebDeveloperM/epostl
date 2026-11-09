"""Topshiriqlar bo‘yicha biznes-logika."""
from datetime import timedelta

from django.core.cache import cache
from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.accounts.models import User
from apps.audit.services import log_action
from apps.core.models import SystemSettings
from apps.notifications.models import Notification
from apps.notifications.services import notify

from .models import Assignment, AssignmentAttachment, AssignmentTarget

Status = AssignmentTarget.Status
ACTIVE_WORK_STATUSES = (Status.NEW, Status.ACCEPTED, Status.IN_PROGRESS, Status.REVISION, Status.OVERDUE)


# --- Ko‘rinish va ruxsatlar ----------------------------------------------
def visible_assignments(user):
    if user.is_platform_admin:
        return Assignment.objects.all()
    if user.is_mentor:
        return Assignment.objects.filter(created_by=user)
    if user.is_student:
        return Assignment.objects.filter(targets__student=user, is_active=True).distinct()
    return Assignment.objects.none()


def can_manage(user, assignment: Assignment) -> bool:
    return user.is_mentor and assignment.created_by_id == user.pk


def overdue_q(prefix: str = "") -> Q:
    """Muddati o‘tgan (va hali bajarilmagan) ijrochilar filtri."""
    return Q(**{f"{prefix}status__in": ACTIVE_WORK_STATUSES,
                f"{prefix}assignment__due_date__lt": timezone.now()})


def filter_targets_by_status(qs, status: str):
    if not status:
        return qs
    if status == Status.OVERDUE:
        return qs.filter(overdue_q())
    if status in ACTIVE_WORK_STATUSES:
        return qs.filter(status=status).exclude(overdue_q())
    return qs.filter(status=status)


# --- Yaratish / yangilash -------------------------------------------------
def _target_url(assignment):
    return reverse("assignments:detail", args=[assignment.pk])


def sync_targets(assignment: Assignment, groups, students) -> list[int]:
    """Guruh va talabalar bo‘yicha ijrochilar ro‘yxatini yangilaydi.

    Ishni boshlagan ijrochilar hech qachon o‘chirilmaydi. Yangi qo‘shilgan
    talabalar ID lari qaytariladi.
    """
    from apps.portfolios.models import Portfolio

    desired: dict[int, int | None] = {}
    for group in groups:
        for student_id in User.objects.students().filter(is_active=True, group=group).values_list("pk", flat=True):
            desired.setdefault(student_id, group.pk)
    for student in students:
        desired[student.pk] = None

    existing = {t.student_id: t for t in assignment.targets.all()}
    new_targets = [
        AssignmentTarget(assignment=assignment, student_id=sid, source_group_id=gid)
        for sid, gid in desired.items() if sid not in existing
    ]
    AssignmentTarget.objects.bulk_create(new_targets)

    started = set(Portfolio.objects.filter(assignment=assignment).values_list("student_id", flat=True))
    removable = [
        t.pk for sid, t in existing.items()
        if sid not in desired and t.status in (Status.NEW, Status.ACCEPTED) and sid not in started
    ]
    if removable:
        AssignmentTarget.objects.filter(pk__in=removable).delete()
    return [t.student_id for t in new_targets]


@transaction.atomic
def save_assignment(request, form) -> Assignment:
    is_new = form.instance.pk is None
    assignment = form.save(commit=False)
    if is_new:
        assignment.created_by = request.user
    assignment.save()
    form.save_m2m()

    for uploaded, info in form.cleaned_data.get("attachments") or []:
        AssignmentAttachment.objects.create(
            assignment=assignment, file=uploaded, original_name=info.original_name,
            file_size=info.size, mime_type=info.mime_type, category=info.category,
        )

    new_ids = sync_targets(assignment, form.cleaned_data.get("groups") or [],
                           form.cleaned_data.get("students") or [])
    if new_ids and assignment.is_active:
        notify(
            User.objects.filter(pk__in=new_ids),
            type=Notification.Type.ASSIGNMENT_NEW,
            title=lambda: _("Yangi topshiriq: %(t)s") % {"t": assignment.title},
            message=lambda: _("Muddat: %(d)s") % {
                "d": timezone.localtime(assignment.due_date).strftime("%d.%m.%Y %H:%M")},
            url=_target_url(assignment),
            actor=request.user,
        )
    log_action(request, "create" if is_new else "update", assignment, new_targets=len(new_ids))
    return assignment


def ensure_group_targets(student: User):
    """Talaba guruhga qo‘shilganda, shu guruhga berilgan faol topshiriqlarni unga ham biriktiradi."""
    if not student.is_student or not student.group_id or not student.is_active:
        return
    assignments = Assignment.objects.filter(groups=student.group_id, is_active=True,
                                            due_date__gt=timezone.now()).exclude(targets__student=student)
    created = []
    for assignment in assignments:
        AssignmentTarget.objects.get_or_create(assignment=assignment, student=student,
                                               defaults={"source_group_id": student.group_id})
        created.append(assignment)
    for assignment in created:
        notify(student, type=Notification.Type.ASSIGNMENT_NEW,
               title=lambda: _("Yangi topshiriq: %(t)s") % {"t": assignment.title},
               url=_target_url(assignment), actor=assignment.created_by)


# --- Holatlar -------------------------------------------------------------
def accept(request, target: AssignmentTarget) -> bool:
    if target.status != Status.NEW:
        return False
    target.status = Status.ACCEPTED
    target.accepted_at = timezone.now()
    target.save(update_fields=["status", "accepted_at", "updated_at"])
    log_action(request, "update", target, status=target.status)
    return True


def update_target_status(assignment_id, student_id, status: str):
    if not assignment_id:
        return
    fields = {"status": status, "updated_at": timezone.now()}
    if status == Status.SUBMITTED:
        fields["submitted_at"] = timezone.now()
    elif status == Status.APPROVED:
        fields["completed_at"] = timezone.now()
    AssignmentTarget.objects.filter(assignment_id=assignment_id, student_id=student_id).update(**fields)


# --- Muddatlar ------------------------------------------------------------
def send_deadline_reminders() -> int:
    now = timezone.now()
    hours = SystemSettings.get_solo().deadline_reminder_hours
    targets = list(
        AssignmentTarget.objects.filter(
            status__in=(Status.NEW, Status.ACCEPTED, Status.IN_PROGRESS, Status.REVISION),
            deadline_reminder_sent=False,
            assignment__is_active=True,
            assignment__due_date__gt=now,
            assignment__due_date__lte=now + timedelta(hours=hours),
        ).select_related("assignment", "student")
    )
    for target in targets:
        due = timezone.localtime(target.assignment.due_date).strftime("%d.%m.%Y %H:%M")
        notify(target.student, type=Notification.Type.DEADLINE_SOON,
               title=lambda: _("Muddat yaqinlashmoqda: %(t)s") % {"t": target.assignment.title},
               message=lambda: _("Topshiriqni %(d)s gacha topshiring.") % {"d": due},
               url=_target_url(target.assignment))
    AssignmentTarget.objects.filter(pk__in=[t.pk for t in targets]).update(deadline_reminder_sent=True)
    return len(targets)


def maybe_process_deadlines():
    """Cron sozlanmagan bo‘lsa ham eslatmalar ishlashi uchun: 10 daqiqada ko‘pi bilan bir marta."""
    if cache.add("assignments:deadline-check", 1, 600):
        try:
            send_deadline_reminders()
        except Exception:  # pragma: no cover
            import logging

            logging.getLogger("apps.assignments").exception("Muddat eslatmalarini yuborib bo‘lmadi")
