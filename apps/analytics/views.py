from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import TemplateView

from apps.accounts.models import User
from apps.accounts.services import mentor_students, student_mentors
from apps.assessments.models import Assessment
from apps.assignments.models import AssignmentTarget
from apps.assignments.services import maybe_process_deadlines
from apps.core import charts
from apps.core.utils import tr
from apps.core.permissions import StaffRequiredMixin
from apps.goals.models import Goal
from apps.portfolios.models import Portfolio
from apps.reflections.models import Reflection

from . import services


class DashboardView(LoginRequiredMixin, View):
    """Har bir rol uchun o‘z dashboardi."""

    def get(self, request):
        user = request.user
        maybe_process_deadlines()
        if user.is_student:
            return render(request, "student/dashboard.html", services.student_dashboard(user))
        if user.is_mentor:
            return render(request, "mentor/dashboard.html", services.mentor_dashboard(user))
        if user.is_platform_admin:
            return render(request, "admin/dashboard.html", services.admin_dashboard())
        return render(request, "base/no_role.html")


def student_analytics_context(student) -> dict:
    comparison = services.competency_comparison(student)
    timeline = services.score_timeline(student)
    dynamics = services.monthly_dynamics(student)
    criteria_rows = services.criteria_comparison(student)
    return {
        "student": student,
        "summary": services.student_summary(student),
        "comparison": comparison,
        "comparison_chart": services.comparison_chart(comparison),
        "criteria_rows": criteria_rows,
        "criteria_chart": charts.comparison_bar(
            [tr(r["criterion"].name) for r in criteria_rows], [r["initial"] for r in criteria_rows],
            [r["latest"] for r in criteria_rows],
            max_value=max([r["max"] for r in criteria_rows] or [20]), suffix=""),
        "timeline": timeline,
        "timeline_chart": charts.line_chart(timeline["labels"], [(_("Umumiy natija"), timeline["values"])],
                                            max_value=100, suffix="%", fill=True),
        "dynamics": dynamics,
        "dynamics_chart": charts.bar_chart(dynamics["labels"], [
            (_("Tasdiqlangan topshiriqlar"), dynamics["approved"]),
            (_("Yuklangan versiyalar"), dynamics["versions"]),
            (_("Refleksiyalar"), dynamics["reflections"]),
        ]),
        "repeat_results": services.repeat_work_results(student),
        "model_stats": services.reflection_model_stats(Reflection.objects.filter(student=student)),
        "assessments": (Assessment.objects.filter(student=student)
                        .select_related("mentor", "portfolio_version__portfolio").order_by("-created_at")[:20]),
    }


class AnalyticsView(LoginRequiredMixin, View):
    """Talaba: «Mening rivojlanishim»; ustoz: talabalar ro‘yxati; administrator: umumiy analitika."""

    def get(self, request):
        user = request.user
        if user.is_student:
            return render(request, "student/analytics.html", student_analytics_context(user))
        if user.is_mentor:
            return redirect("analytics:students")
        if user.is_platform_admin:
            ctx = services.admin_dashboard()
            ctx["platform"] = services.platform_competency_averages()
            ctx["model_stats"] = services.reflection_model_stats()
            return render(request, "admin/analytics.html", ctx)
        return render(request, "base/no_role.html")


class StudentListView(StaffRequiredMixin, TemplateView):
    """Ustoz: «Mening talabalarim» — rivojlanish ko‘rsatkichlari bilan."""

    template_name = "mentor/students/list.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        students = mentor_students(user) if user.is_mentor else User.objects.students().select_related("group")
        q = self.request.GET.get("q", "").strip()
        if q:
            students = students.filter(Q(last_name__icontains=q) | Q(first_name__icontains=q)
                                       | Q(group__name__icontains=q) | Q(external_id__icontains=q))
        if group := self.request.GET.get("group"):
            if group.isdigit():
                students = students.filter(group_id=group)
        students = students.order_by("group__name", "last_name")[:300]
        ctx["rows"] = services.mentor_overview(user, students)
        ctx["model_stats"] = services.reflection_model_stats(
            Reflection.objects.filter(student_id__in=[s.pk for s in students]))
        ctx["q"] = q
        base = mentor_students(user) if user.is_mentor else User.objects.students()
        ctx["groups"] = sorted({s.group for s in base.select_related("group") if s.group}, key=lambda g: g.name)
        return ctx


class StudentDetailView(StaffRequiredMixin, View):
    template_name = "mentor/students/detail.html"

    def get(self, request, pk):
        user = request.user
        qs = mentor_students(user) if user.is_mentor else User.objects.students()
        student = get_object_or_404(qs.select_related("group__direction__faculty"), pk=pk)
        ctx = student_analytics_context(student)
        ctx.update(
            mentors=student_mentors(student),
            goals=Goal.objects.filter(student=student).select_related("competency")[:10],
            portfolios=(Portfolio.objects.filter(student=student)
                        .select_related("assignment", "goal").order_by("-updated_at")[:10]),
            targets=(AssignmentTarget.objects.filter(student=student)
                     .select_related("assignment").order_by("-assignment__due_date")[:10]),
            reflections=(Reflection.objects.filter(student=student, status=Reflection.Status.SUBMITTED)
                         .select_related("portfolio_version__portfolio").order_by("-submitted_at")[:5]),
            has_baseline=Assessment.objects.filter(student=student, kind=Assessment.Kind.BASELINE).exists(),
        )
        return render(request, self.template_name, ctx)
