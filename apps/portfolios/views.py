from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db.models import Count, Prefetch, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import CreateView, DetailView, FormView, ListView, UpdateView

from apps.audit.services import log_action
from apps.core import charts
from apps.core.files import protected_file_response
from apps.core.permissions import StudentRequiredMixin

from . import services
from .forms import PortfolioCreateForm, PortfolioUpdateForm, UploadForm
from .models import Portfolio, PortfolioFile, PortfolioVersion


class PortfolioListView(LoginRequiredMixin, ListView):
    template_name = "student/portfolio/list.html"
    context_object_name = "portfolios"
    paginate_by = 20

    def get_queryset(self):
        qs = (services.visible_portfolios(self.request.user)
              .select_related("student", "student__group", "assignment", "goal")
              .annotate(files_count=Count("versions__files", distinct=True))
              .order_by("-updated_at"))
        params = self.request.GET
        if status := params.get("status"):
            qs = qs.filter(status=status)
        if material := params.get("type"):
            qs = qs.filter(material_type=material)
        if student_id := params.get("student"):
            if student_id.isdigit():
                qs = qs.filter(student_id=student_id)
        if q := params.get("q", "").strip():
            qs = qs.filter(Q(title__icontains=q) | Q(student__last_name__icontains=q)
                           | Q(student__first_name__icontains=q) | Q(assignment__title__icontains=q))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["statuses"] = Portfolio.Status.choices
        ctx["material_types"] = Portfolio.MaterialType.choices
        return ctx


class PortfolioCreateView(StudentRequiredMixin, CreateView):
    template_name = "student/portfolio/create.html"
    form_class = PortfolioCreateForm

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "student": self.request.user}

    def get_initial(self):
        initial = super().get_initial()
        for key in ("assignment", "goal"):
            if value := self.request.GET.get(key):
                initial[key] = value
        return initial

    def form_valid(self, form):
        try:
            self.object = services.create_portfolio(self.request, form)
        except ValidationError as exc:
            form.add_error(None, exc)
            return self.form_invalid(form)
        messages.success(self.request, _("Ish yuklandi (1-versiya). Endi refleksiya yozib, ustozga yuboring."))
        return redirect("portfolios:detail", pk=self.object.pk)


class PortfolioUpdateView(StudentRequiredMixin, UpdateView):
    template_name = "student/portfolio/edit.html"
    form_class = PortfolioUpdateForm

    def get_queryset(self):
        return Portfolio.objects.filter(student=self.request.user)

    def form_valid(self, form):
        self.object = form.save()
        log_action(self.request, "update", self.object, changed=form.changed_data)
        messages.success(self.request, _("Ish ma’lumotlari saqlandi."))
        return redirect("portfolios:detail", pk=self.object.pk)


class PortfolioDetailView(LoginRequiredMixin, DetailView):
    template_name = "shared/portfolio_detail.html"
    context_object_name = "portfolio"

    def get_queryset(self):
        from apps.assessments.models import AssessmentDetail

        versions = PortfolioVersion.objects.prefetch_related(
            "files",
            "reflection__answers",
            "reflection__evidence",
            Prefetch("assessment__details",
                     queryset=AssessmentDetail.objects.select_related("criterion").order_by("criterion__order")),
        ).select_related("assessment__mentor", "reflection")
        return (services.visible_portfolios(self.request.user)
                .select_related("student", "student__group", "assignment", "assignment__created_by", "goal")
                .prefetch_related(Prefetch("versions", queryset=versions)))

    def get_context_data(self, **kwargs):
        from apps.assessments.forms import FeedbackForm
        from apps.assessments.models import MentorFeedback

        ctx = super().get_context_data(**kwargs)
        portfolio = self.object
        user = self.request.user
        versions = list(portfolio.versions.all())  # oxirgisi birinchi
        selected = versions[0] if versions else None
        if v := self.request.GET.get("v"):
            selected = next((x for x in versions if str(x.version_number) == v), selected)
        ctx.update(
            versions=versions,
            selected=selected,
            latest=versions[0] if versions else None,
            is_owner=user.pk == portfolio.student_id,
            can_assess=services.can_assess(user, portfolio),
            upload_state=services.upload_state(portfolio),
            upload_form=UploadForm(),
            feedback_list=MentorFeedback.objects.filter(portfolio=portfolio).select_related("mentor", "version"),
            feedback_form=FeedbackForm(),
        )
        # Versiyalar bo‘yicha natijalar dinamikasi
        history = []
        for version in reversed(versions):
            assessment = getattr(version, "assessment", None)
            history.append({"version": version, "assessment": assessment})
        # Asosiy xulosalar: yuborilgan refleksiyalardan (eskisidan yangisiga — o‘sish ko‘rinsin)
        insights = []
        for version in reversed(versions):
            reflection = getattr(version, "reflection", None)
            if reflection is not None and reflection.status == "submitted" and (items := reflection.insights()):
                insights.append({"version": version, "reflection": reflection, "items": items})
        ctx["insights"] = insights
        ctx["history"] = history
        assessed = [h for h in history if h["assessment"]]
        ctx["history_chart"] = charts.line_chart(
            [f"v{h['version'].version_number}" for h in assessed],
            [(_("Natija"), [h["assessment"].percent for h in assessed])], max_value=100, suffix="%",
        ) if len(assessed) >= 2 else None
        return ctx


class PortfolioUploadView(StudentRequiredMixin, FormView):
    template_name = "student/portfolio/upload.html"
    form_class = UploadForm

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            self.portfolio = get_object_or_404(Portfolio, pk=kwargs["pk"], student=request.user)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["portfolio"] = self.portfolio
        ctx["upload_state"] = services.upload_state(self.portfolio)
        return ctx

    def form_valid(self, form):
        try:
            version = services.upload_files(self.request, self.portfolio, form.cleaned_data["files"],
                                            form.cleaned_data.get("note", ""))
        except ValidationError as exc:
            form.add_error(None, exc)
            return self.form_invalid(form)
        messages.success(self.request, _("Fayllar %(v)s-versiyaga yuklandi.") % {"v": version.version_number})
        return redirect("portfolios:detail", pk=self.portfolio.pk)


class PortfolioFileView(LoginRequiredMixin, View):
    """Faylni ruxsat tekshirilgandan keyin uzatadi (video uchun Range qo‘llab-quvvatlanadi)."""

    def get(self, request, pk):
        pfile = get_object_or_404(PortfolioFile.objects.select_related("version__portfolio"), pk=pk)
        if not services.visible_portfolios(request.user).filter(pk=pfile.version.portfolio_id).exists():
            raise Http404
        download = request.GET.get("download") == "1"
        if download:
            log_action(request, "download", pfile)
        return protected_file_response(request, pfile.file, filename=pfile.original_name,
                                       content_type=pfile.mime_type, force_download=download)


class PortfolioFileDeleteView(StudentRequiredMixin, View):
    def post(self, request, pk):
        pfile = get_object_or_404(PortfolioFile.objects.select_related("version__portfolio"), pk=pk,
                                  version__portfolio__student=request.user)
        portfolio_id = pfile.version.portfolio_id
        try:
            services.delete_draft_file(request, pfile)
            messages.success(request, _("Fayl o‘chirildi."))
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        return redirect("portfolios:detail", pk=portfolio_id)
