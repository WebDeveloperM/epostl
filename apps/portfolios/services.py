"""Portfolio, versiyalar va fayllar bo‘yicha biznes-logika."""
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.accounts.services import is_mentor_of, mentor_student_ids, student_mentors
from apps.assignments.models import AssignmentTarget
from apps.assignments.services import update_target_status
from apps.audit.services import log_action
from apps.core.models import SystemSettings
from apps.goals.services import mark_in_progress
from apps.notifications.models import Notification
from apps.notifications.services import notify

from .models import Portfolio, PortfolioFile, PortfolioVersion

Status = Portfolio.Status


# --- Ko‘rinish va ruxsatlar ----------------------------------------------
def visible_portfolios(user):
    if user.is_platform_admin:
        return Portfolio.objects.all()
    if user.is_mentor:
        return Portfolio.objects.filter(
            Q(student_id__in=mentor_student_ids(user)) | Q(assignment__created_by=user)
        )
    if user.is_student:
        return Portfolio.objects.filter(student=user)
    return Portfolio.objects.none()


def can_assess(user, portfolio: Portfolio) -> bool:
    if not user.is_mentor:
        return False
    if portfolio.assignment_id and portfolio.assignment.created_by_id == user.pk:
        return True
    return is_mentor_of(user, portfolio.student)


def reviewers(portfolio: Portfolio):
    """Ish haqida xabardor qilinadigan ustozlar."""
    people = {m.pk: m for m in student_mentors(portfolio.student)}
    if portfolio.assignment_id:
        creator = portfolio.assignment.created_by
        people.setdefault(creator.pk, creator)
    return list(people.values())


def upload_state(portfolio: Portfolio) -> dict:
    """Talaba hozir fayl yuklay oladimi va bu qanday amal bo‘ladi."""
    latest = portfolio.latest_version
    if portfolio.status == Status.SUBMITTED:
        return {"allowed": False, "mode": None, "reason": _("Ish tekshirilmoqda. Ustoz bahosini kuting.")}
    if portfolio.status == Status.APPROVED:
        return {"allowed": False, "mode": None, "reason": _("Ish tasdiqlangan.")}
    if latest is None or latest.is_submitted:
        return {"allowed": True, "mode": "new_version", "reason": ""}
    return {"allowed": True, "mode": "add_to_draft", "reason": ""}


def check_deadline(assignment):
    if assignment and assignment.is_past_due and not SystemSettings.get_solo().allow_late_submission:
        raise ValidationError(_("Topshiriq muddati o‘tgan. Muddatdan keyin topshirishga ruxsat berilmagan."))


# --- Yaratish va yuklash --------------------------------------------------
def _store_files(version: PortfolioVersion, files) -> list[PortfolioFile]:
    stored = []
    for uploaded, info in files:
        stored.append(PortfolioFile.objects.create(
            version=version, file=uploaded, original_name=info.original_name, file_size=info.size,
            mime_type=info.mime_type, category=info.category,
        ))
    return stored


def _new_version(portfolio: Portfolio, user, note: str) -> PortfolioVersion:
    number = portfolio.current_version + 1
    version = PortfolioVersion.objects.create(portfolio=portfolio, version_number=number, note=note,
                                              created_by=user)
    portfolio.current_version = number
    if portfolio.status == Status.REVISION:
        portfolio.status = Status.DRAFT
    portfolio.save(update_fields=["current_version", "status", "updated_at"])
    portfolio._latest_version_cache = version
    return version


@transaction.atomic
def create_portfolio(request, form) -> Portfolio:
    student = request.user
    assignment = form.cleaned_data.get("assignment")
    check_deadline(assignment)
    portfolio = form.save(commit=False)
    portfolio.student = student
    portfolio.save()
    version = _new_version(portfolio, student, form.cleaned_data.get("note", ""))
    stored = _store_files(version, form.cleaned_data["files"])
    if assignment:
        update_target_status(assignment.pk, student.pk, AssignmentTarget.Status.IN_PROGRESS)
    mark_in_progress(portfolio.goal)
    log_action(request, "upload", version, files=[f.original_name for f in stored])
    return portfolio


@transaction.atomic
def upload_files(request, portfolio: Portfolio, files, note: str = "") -> PortfolioVersion:
    """Qoralama versiyaga fayl qo‘shadi yoki (qayta ishlashdan keyin) yangi versiya yaratadi.

    Oldingi versiyalar va ularning fayllari o‘zgarishsiz saqlanadi.
    """
    portfolio = Portfolio.objects.select_for_update().get(pk=portfolio.pk)
    state = upload_state(portfolio)
    if not state["allowed"]:
        raise ValidationError(state["reason"])
    check_deadline(portfolio.assignment)
    if state["mode"] == "new_version":
        version = _new_version(portfolio, request.user, note)
        if portfolio.assignment_id:
            update_target_status(portfolio.assignment_id, portfolio.student_id, AssignmentTarget.Status.IN_PROGRESS)
    else:
        version = portfolio.latest_version
        if note:
            version.note = f"{version.note}\n{note}".strip() if version.note else note
            version.save(update_fields=["note"])
    stored = _store_files(version, files)
    Portfolio.objects.filter(pk=portfolio.pk).update(updated_at=timezone.now())
    log_action(request, "upload", version, files=[f.original_name for f in stored])
    return version


def delete_draft_file(request, pfile: PortfolioFile):
    version = pfile.version
    if version.is_submitted:
        raise ValidationError(_("Yuborilgan versiya fayllarini o‘chirib bo‘lmaydi."))
    log_action(request, "delete", pfile, version=version.version_number)
    pfile.file.delete(save=False)
    pfile.delete()


@transaction.atomic
def submit_version(request, version: PortfolioVersion):
    """Versiyani (refleksiya bilan birga) ustozga tekshirishga yuboradi."""
    from apps.reflections.models import Reflection

    portfolio = Portfolio.objects.select_for_update(of=("self",)).select_related("assignment", "student").get(
        pk=version.portfolio_id)
    if version.version_number != portfolio.current_version:
        raise ValidationError(_("Faqat oxirgi versiyani yuborish mumkin."))
    if version.is_submitted:
        raise ValidationError(_("Bu versiya allaqachon yuborilgan."))
    if not version.files.exists():
        raise ValidationError(_("Yuborishdan oldin kamida bitta fayl yuklang."))
    check_deadline(portfolio.assignment)
    reflection = Reflection.objects.filter(portfolio_version=version).first()
    if reflection is None:
        raise ValidationError(_("Ishni yuborishdan oldin refleksiya yozing."))

    now = timezone.now()
    version.submitted_at = now
    version.save(update_fields=["submitted_at"])
    portfolio.status = Status.SUBMITTED
    portfolio.submitted_at = now
    portfolio.save(update_fields=["status", "submitted_at", "updated_at"])
    if portfolio.assignment_id:
        update_target_status(portfolio.assignment_id, portfolio.student_id, AssignmentTarget.Status.SUBMITTED)

    notify(
        reviewers(portfolio),
        type=Notification.Type.WORK_SUBMITTED,
        title=lambda: _("%(s)s ish yukladi: %(t)s (v%(v)s)") % {
            "s": portfolio.student.short_name, "t": portfolio.title, "v": version.version_number},
        message=lambda: _("Ish va refleksiya tekshirishga yuborildi."),
        url=reverse("portfolios:detail", args=[portfolio.pk]),
        actor=request.user,
    )
    log_action(request, "submit", version)
    return version
