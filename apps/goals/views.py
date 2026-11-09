from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, ProtectedError, Q
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.audit.services import log_action
from apps.core.permissions import StudentRequiredMixin

from . import services
from .forms import GoalForm, GoalStatusForm
from .models import Goal


class GoalListView(LoginRequiredMixin, ListView):
    template_name = "student/goals/list.html"
    context_object_name = "goals"
    paginate_by = 20

    def get_queryset(self):
        qs = (services.visible_goals(self.request.user)
              .select_related("competency", "student", "student__group")
              .annotate(works_count=Count("portfolios", distinct=True))
              .order_by("-created_at"))
        if status := self.request.GET.get("status"):
            qs = qs.filter(status=status)
        if q := self.request.GET.get("q", "").strip():
            qs = qs.filter(Q(title__icontains=q) | Q(student__last_name__icontains=q)
                           | Q(student__first_name__icontains=q))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        base = services.visible_goals(self.request.user)
        ctx["statuses"] = Goal.Status.choices
        ctx["status_counts"] = {row["status"]: row["n"] for row in base.values("status").annotate(n=Count("id"))}
        ctx["total"] = base.count()
        return ctx


class GoalCreateView(StudentRequiredMixin, CreateView):
    template_name = "student/goals/form.html"
    form_class = GoalForm

    def form_valid(self, form):
        form.instance.student = self.request.user
        self.object = form.save()
        log_action(self.request, "create", self.object)
        messages.success(self.request, _("Rivojlanish maqsadi belgilandi."))
        return redirect("goals:detail", pk=self.object.pk)


class GoalOwnerMixin(StudentRequiredMixin):
    def get_queryset(self):
        return Goal.objects.filter(student=self.request.user)


class GoalUpdateView(GoalOwnerMixin, UpdateView):
    template_name = "student/goals/form.html"
    form_class = GoalForm

    def form_valid(self, form):
        self.object = form.save()
        log_action(self.request, "update", self.object, changed=form.changed_data)
        messages.success(self.request, _("Maqsad saqlandi."))
        return redirect("goals:detail", pk=self.object.pk)


class GoalStatusView(GoalOwnerMixin, View):
    def post(self, request, pk):
        goal = get_object_or_404(self.get_queryset(), pk=pk)
        form = GoalStatusForm(request.POST)
        if form.is_valid():
            services.set_status(goal, form.cleaned_data["status"])
            log_action(request, "update", goal, status=goal.status)
            messages.success(request, _("Maqsad holati: %(s)s") % {"s": goal.get_status_display()})
        return redirect("goals:detail", pk=goal.pk)


class GoalDeleteView(GoalOwnerMixin, View):
    def post(self, request, pk):
        goal = get_object_or_404(self.get_queryset(), pk=pk)
        title = str(goal)
        try:
            goal_pk = goal.pk
            goal.delete()
            goal.pk = goal_pk
            log_action(request, "delete", goal)
        except ProtectedError:
            messages.error(request, _("Maqsadga ishlar bog‘langan — uni o‘chirib bo‘lmaydi. "
                                      "Kerak bo‘lsa, «Bekor qilindi» holatiga o‘tkazing."))
            return redirect("goals:detail", pk=pk)
        messages.success(request, _("«%(t)s» maqsadi o‘chirildi.") % {"t": title})
        return redirect("goals:list")


class GoalDetailView(LoginRequiredMixin, DetailView):
    template_name = "student/goals/detail.html"
    context_object_name = "goal"

    def get_queryset(self):
        return services.visible_goals(self.request.user).select_related("competency", "student")

    def get_context_data(self, **kwargs):
        from apps.analytics.services import comparison_chart, competency_comparison
        from apps.assessments.models import Assessment

        ctx = super().get_context_data(**kwargs)
        goal = self.object
        ctx["cycle"] = services.goal_cycle(goal)
        ctx["portfolios"] = (goal.portfolios.select_related("assignment")
                             .prefetch_related("versions__assessment", "versions__reflection"))
        goal_assessments = Assessment.objects.filter(student=goal.student).filter(
            services.models_q_goal_or_portfolio(goal))
        baseline = Assessment.objects.filter(student=goal.student, kind=Assessment.Kind.BASELINE)
        ctx["assessments"] = (goal_assessments | baseline).distinct().select_related(
            "mentor", "portfolio_version__portfolio").order_by("created_at")
        ctx["comparison"] = competency_comparison(goal.student, (goal_assessments | baseline).distinct())
        ctx["comparison_chart"] = comparison_chart(ctx["comparison"])
        ctx["statuses"] = Goal.Status.choices
        ctx["is_owner"] = self.request.user.pk == goal.student_id
        return ctx
