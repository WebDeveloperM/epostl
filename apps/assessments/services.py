"""Baholash va ustoz fikri bo‘yicha biznes-logika."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import gettext_noop

from apps.accounts.services import is_mentor_of, mentor_student_ids
from apps.assignments.models import AssignmentTarget
from apps.assignments.services import update_target_status
from apps.audit.services import log_action
from apps.competencies.models import AssessmentCriterion
from apps.notifications.models import Notification
from apps.notifications.services import notify
from apps.portfolios.models import Portfolio, PortfolioVersion
from apps.portfolios.services import can_assess

from .models import Assessment, AssessmentDetail, MentorFeedback


def visible_assessments(user):
    if user.is_platform_admin:
        return Assessment.objects.all()
    if user.is_mentor:
        return Assessment.objects.filter(
            Q(student_id__in=mentor_student_ids(user)) | Q(mentor=user)
            | Q(portfolio_version__portfolio__assignment__created_by=user)
        )
    if user.is_student:
        return Assessment.objects.filter(student=user)
    return Assessment.objects.none()


def criteria_for_version(version: PortfolioVersion):
    assignment = version.portfolio.assignment
    if assignment:
        return list(assignment.effective_criteria())
    return list(AssessmentCriterion.objects.filter(is_active=True).select_related("competency"))


def pending_reviews(mentor):
    """Ustoz tekshirishi kutilayotgan ishlar."""
    return (Portfolio.objects.filter(status=Portfolio.Status.SUBMITTED)
            .filter(Q(student_id__in=mentor_student_ids(mentor)) | Q(assignment__created_by=mentor))
            .select_related("student", "student__group", "assignment").order_by("submitted_at"))


def _save_details(assessment: Assessment, details):
    assessment.details.all().delete()
    rows = [
        AssessmentDetail(
            assessment=assessment, criterion=d["criterion"], score=d["score"], max_score=d["criterion"].max_score,
            comment=d["comment"], weaknesses=d["weaknesses"], recommendations=d["recommendations"],
        )
        for d in details
    ]
    for row in rows:
        row.full_clean(exclude=["assessment"])
    AssessmentDetail.objects.bulk_create(rows)
    assessment.total_score = sum(r.score for r in rows)
    assessment.max_score = sum(r.max_score for r in rows)
    assessment.save(update_fields=["total_score", "max_score", "updated_at"])


@transaction.atomic
def assess_version(request, version: PortfolioVersion, *, decision, overall_comment, details) -> Assessment:
    """Ish versiyasini mezonlar bo‘yicha baholaydi va qaror qabul qiladi."""
    mentor = request.user
    portfolio = Portfolio.objects.select_for_update(of=("self",)).select_related("assignment", "student").get(
        pk=version.portfolio_id)
    if not can_assess(mentor, portfolio):
        raise PermissionDenied
    if version.version_number != portfolio.current_version:
        raise ValidationError(_("Faqat ishning oxirgi versiyasini baholash mumkin."))
    if not version.is_submitted:
        raise ValidationError(_("Bu versiya hali tekshirishga yuborilmagan."))

    assessment = Assessment.objects.filter(portfolio_version=version).first()
    is_new = assessment is None
    if is_new:
        assessment = Assessment(kind=Assessment.Kind.WORK, portfolio_version=version, student=portfolio.student,
                                goal=portfolio.goal)
    assessment.mentor = mentor
    assessment.decision = decision
    assessment.overall_comment = overall_comment
    assessment.save()
    _save_details(assessment, details)

    now = timezone.now()
    url = reverse("portfolios:detail", args=[portfolio.pk])
    if decision == Assessment.Decision.APPROVED:
        portfolio.status = Portfolio.Status.APPROVED
        portfolio.approved_at = now
        target_status = AssignmentTarget.Status.APPROVED
        n_type, title_text = Notification.Type.APPROVED, gettext_noop("Ishingiz tasdiqlandi: %(t)s")
    else:
        portfolio.status = Portfolio.Status.REVISION
        portfolio.approved_at = None
        target_status = AssignmentTarget.Status.REVISION
        n_type, title_text = Notification.Type.REVISION, gettext_noop("Ish qayta ishlashga qaytarildi: %(t)s")
    portfolio.save(update_fields=["status", "approved_at", "updated_at"])
    update_target_status(portfolio.assignment_id, portfolio.student_id, target_status)

    notify(portfolio.student, type=n_type, title=lambda: _(title_text) % {"t": portfolio.title},
           message=lambda: _("Ball: %(s)s/%(m)s. %(c)s") % {"s": assessment.total_score, "m": assessment.max_score,
                                                            "c": overall_comment[:200]},
           url=url, actor=mentor)
    log_action(request, "assess", assessment, decision=decision, total=assessment.total_score,
               version=version.version_number, updated=not is_new)
    return assessment


@transaction.atomic
def create_baseline(request, student, *, goal, overall_comment, details) -> Assessment:
    mentor = request.user
    if not is_mentor_of(mentor, student):
        raise PermissionDenied
    assessment = Assessment.objects.create(kind=Assessment.Kind.BASELINE, student=student, mentor=mentor,
                                           goal=goal, overall_comment=overall_comment)
    _save_details(assessment, details)
    notify(student, type=Notification.Type.FEEDBACK,
           title=lambda: _("Boshlang‘ich baholash natijasi: %(s)s/%(m)s") % {"s": assessment.total_score,
                                                                              "m": assessment.max_score},
           url=reverse("assessments:detail", args=[assessment.pk]), actor=mentor)
    log_action(request, "assess", assessment, kind="baseline", total=assessment.total_score)
    return assessment


def add_feedback(request, portfolio: Portfolio, *, kind, text) -> MentorFeedback:
    if not can_assess(request.user, portfolio):
        raise PermissionDenied
    feedback = MentorFeedback.objects.create(
        portfolio=portfolio, version=portfolio.latest_version, mentor=request.user, kind=kind, text=text)
    notify(portfolio.student, type=Notification.Type.FEEDBACK,
           title=lambda: _("Ustoz izoh qoldirdi: %(t)s") % {"t": portfolio.title},
           message=text[:300], url=reverse("portfolios:detail", args=[portfolio.pk]) + "#feedback",
           actor=request.user)
    log_action(request, "create", feedback)
    return feedback
