from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import DetailView, ListView

from apps.accounts.services import mentor_students
from apps.competencies.models import AssessmentCriterion
from apps.core import charts
from apps.core.permissions import MentorRequiredMixin
from apps.core.utils import tr
from apps.portfolios.models import Portfolio, PortfolioVersion
from apps.portfolios.services import can_assess

from . import services
from .forms import AssessmentForm, FeedbackForm
from .models import Assessment, AssessmentDetail


class ReviewQueueView(MentorRequiredMixin, ListView):
    template_name = "mentor/review_queue.html"
    context_object_name = "pending"

    def get_queryset(self):
        return services.pending_reviews(self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["recent"] = (Assessment.objects.filter(mentor=self.request.user, kind=Assessment.Kind.WORK)
                         .select_related("student", "portfolio_version__portfolio")[:10])
        return ctx


class AssessView(MentorRequiredMixin, View):
    template_name = "mentor/assess_form.html"

    def _load(self, request, version_pk):
        version = get_object_or_404(
            PortfolioVersion.objects.select_related("portfolio__student", "portfolio__assignment",
                                                    "portfolio__goal"), pk=version_pk)
        if not can_assess(request.user, version.portfolio):
            raise PermissionDenied
        return version

    def _context(self, version, form):
        portfolio = version.portfolio
        reflection = getattr(version, "reflection", None)
        previous = (Assessment.objects.filter(portfolio_version__portfolio=portfolio)
                    .exclude(portfolio_version=version).select_related("portfolio_version")
                    .prefetch_related("details__criterion").order_by("-created_at").first())
        return {"version": version, "portfolio": portfolio, "form": form, "reflection": reflection,
                "files": version.files.all(), "previous": previous,
                "previous_details": {d.criterion_id: d for d in previous.details.all()} if previous else {}}

    def get(self, request, version_pk):
        version = self._load(request, version_pk)
        existing = Assessment.objects.filter(portfolio_version=version).prefetch_related("details").first()
        details = {d.criterion_id: d for d in existing.details.all()} if existing else {}
        initial = {"decision": existing.decision, "overall_comment": existing.overall_comment} if existing else None
        form = AssessmentForm(criteria=services.criteria_for_version(version), details=details, initial=initial)
        return render(request, self.template_name, self._context(version, form))

    def post(self, request, version_pk):
        version = self._load(request, version_pk)
        form = AssessmentForm(request.POST, criteria=services.criteria_for_version(version))
        if form.is_valid():
            try:
                services.assess_version(request, version, decision=form.cleaned_data["decision"],
                                        overall_comment=form.cleaned_data.get("overall_comment", ""),
                                        details=form.details_data())
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                if form.cleaned_data["decision"] == Assessment.Decision.APPROVED:
                    messages.success(request, _("Ish baholandi va tasdiqlandi."))
                else:
                    messages.success(request, _("Ish baholandi va qayta ishlash uchun talabaga qaytarildi."))
                return redirect("portfolios:detail", pk=version.portfolio_id)
        return render(request, self.template_name, self._context(version, form))


class BaselineCreateView(MentorRequiredMixin, View):
    template_name = "mentor/baseline_form.html"

    def _student(self, request, student_pk):
        return get_object_or_404(mentor_students(request.user), pk=student_pk)

    def _criteria(self):
        return AssessmentCriterion.objects.filter(is_active=True).select_related("competency")

    def get(self, request, student_pk):
        student = self._student(request, student_pk)
        form = AssessmentForm(criteria=self._criteria(), baseline=True, student=student)
        return render(request, self.template_name, {"student": student, "form": form})

    def post(self, request, student_pk):
        student = self._student(request, student_pk)
        form = AssessmentForm(request.POST, criteria=self._criteria(), baseline=True, student=student)
        if form.is_valid():
            assessment = services.create_baseline(
                request, student, goal=form.cleaned_data.get("goal"),
                overall_comment=form.cleaned_data.get("overall_comment", ""), details=form.details_data())
            messages.success(request, _("Boshlang‘ich baholash saqlandi."))
            return redirect("assessments:detail", pk=assessment.pk)
        return render(request, self.template_name, {"student": student, "form": form})


class AssessmentListView(LoginRequiredMixin, ListView):
    template_name = "student/assessments/list.html"
    context_object_name = "assessments"
    paginate_by = 20

    def get_queryset(self):
        qs = (services.visible_assessments(self.request.user)
              .select_related("student", "student__group", "mentor", "portfolio_version__portfolio", "goal"))
        if kind := self.request.GET.get("kind"):
            qs = qs.filter(kind=kind)
        if student_id := self.request.GET.get("student"):
            if student_id.isdigit():
                qs = qs.filter(student_id=student_id)
        if q := self.request.GET.get("q", "").strip():
            qs = qs.filter(Q(student__last_name__icontains=q) | Q(portfolio_version__portfolio__title__icontains=q))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["kinds"] = Assessment.Kind.choices
        return ctx


class AssessmentDetailView(LoginRequiredMixin, DetailView):
    template_name = "shared/assessment_detail.html"
    context_object_name = "assessment"

    def get_queryset(self):
        return (services.visible_assessments(self.request.user)
                .select_related("student", "mentor", "portfolio_version__portfolio", "goal")
                .prefetch_related(Prefetch("details", queryset=AssessmentDetail.objects.select_related(
                    "criterion__competency"))))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        a = self.object
        prev = (Assessment.objects.filter(student=a.student, created_at__lt=a.created_at)
                .prefetch_related("details").order_by("-created_at").first())
        ctx["previous"] = prev
        ctx["previous_details"] = {d.criterion_id: d for d in prev.details.all()} if prev else {}
        details = list(a.details.all())
        prev_map = ctx["previous_details"]
        ctx["chart"] = charts.comparison_bar(
            [tr(d.criterion.name) for d in details],
            [prev_map[d.criterion_id].score if d.criterion_id in prev_map else None for d in details],
            [d.score for d in details],
            max_value=max([d.max_score for d in details] or [20]), suffix="",
            initial_label=_("Oldingi baho"), latest_label=_("Ushbu baho"),
        )
        return ctx


class FeedbackCreateView(MentorRequiredMixin, View):
    def post(self, request, portfolio_pk):
        portfolio = get_object_or_404(Portfolio.objects.select_related("assignment", "student"), pk=portfolio_pk)
        form = FeedbackForm(request.POST)
        if form.is_valid():
            services.add_feedback(request, portfolio, kind=form.cleaned_data["kind"], text=form.cleaned_data["text"])
            messages.success(request, _("Izoh talabaga yuborildi."))
        else:
            messages.error(request, _("Izoh matnini kiriting."))
        return redirect(reverse("portfolios:detail", args=[portfolio.pk]) + "#feedback")
