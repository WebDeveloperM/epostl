from django.utils import timezone
from django.utils.translation import gettext as _

from apps.accounts.services import mentor_student_ids

from .models import Goal


def visible_goals(user):
    if user.is_platform_admin:
        return Goal.objects.all()
    if user.is_mentor:
        return Goal.objects.filter(student_id__in=mentor_student_ids(user))
    if user.is_student:
        return Goal.objects.filter(student=user)
    return Goal.objects.none()


def set_status(goal: Goal, status: str):
    goal.status = status
    goal.completed_at = timezone.now() if status == Goal.Status.COMPLETED else None
    goal.save(update_fields=["status", "completed_at", "updated_at"])


def mark_in_progress(goal: Goal | None):
    if goal and goal.status == Goal.Status.NEW:
        set_status(goal, Goal.Status.IN_PROGRESS)


def goal_cycle(goal: Goal) -> dict:
    """Rivojlanish siklining 8 bosqichi bo‘yicha holat (TZ, 4-bo‘lim)."""
    from apps.assessments.models import Assessment
    from apps.portfolios.models import Portfolio, PortfolioVersion
    from apps.reflections.models import Reflection

    portfolios = Portfolio.objects.filter(goal=goal)
    versions = PortfolioVersion.objects.filter(portfolio__goal=goal)
    assessments = Assessment.objects.filter(student=goal.student).filter(
        models_q_goal_or_portfolio(goal)
    )
    baseline = Assessment.objects.filter(student=goal.student, kind=Assessment.Kind.BASELINE)
    reflections = Reflection.objects.filter(portfolio_version__portfolio__goal=goal,
                                            status=Reflection.Status.SUBMITTED)
    work_assessments = assessments.filter(kind=Assessment.Kind.WORK)
    steps = [
        (_("Boshlang‘ich baholash"), baseline.exists()),
        (_("Maqsad belgilash"), True),
        (_("Rejalashtirish"), portfolios.filter(assignment__isnull=False).exists() or portfolios.exists()),
        (_("Amaliy ishni bajarish"), versions.filter(files__isnull=False).exists()),
        (_("Refleksiya yozish"), reflections.exists()),
        (_("Ustoz fikri va baholash"), work_assessments.exists()),
        (_("Ishni takomillashtirish"), versions.filter(version_number__gte=2).exists()),
        (_("Natijalarni taqqoslash"), assessments.count() >= 2),
    ]
    done = sum(1 for _label, ok in steps if ok)
    current = next((i for i, (_l, ok) in enumerate(steps) if not ok), len(steps))
    return {
        "steps": [{"index": i + 1, "label": label, "done": ok, "current": i == current}
                  for i, (label, ok) in enumerate(steps)],
        "done": done,
        "percent": round(done * 100 / len(steps)),
        "is_complete": done == len(steps),
    }


def models_q_goal_or_portfolio(goal):
    from django.db.models import Q

    return Q(goal=goal) | Q(portfolio_version__portfolio__goal=goal)
