from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import DetailView, ListView

from apps.core.files import protected_file_response
from apps.core.permissions import StudentRequiredMixin
from apps.portfolios.models import PortfolioVersion

from . import services
from .forms import ReflectionForm
from .frameworks import CHOOSABLE, DEFAULT_FRAMEWORK
from .models import Reflection, ReflectionEvidence


class ReflectionListView(LoginRequiredMixin, ListView):
    """Refleksiyalar tarixi (talaba) / talabalar refleksiyalari (ustoz)."""

    template_name = "student/reflections/list.html"
    context_object_name = "reflections"
    paginate_by = 20

    def get_queryset(self):
        qs = (services.visible_reflections(self.request.user)
              .select_related("student", "student__group", "portfolio_version__portfolio",
                              "portfolio_version__assessment"))
        flt = self.request.GET.get("filter")
        if flt == "new":
            qs = qs.filter(status=Reflection.Status.SUBMITTED, portfolio_version__assessment__isnull=True)
        elif flt in (Reflection.Status.DRAFT, Reflection.Status.SUBMITTED):
            qs = qs.filter(status=flt)
        if q := self.request.GET.get("q", "").strip():
            qs = qs.filter(Q(portfolio_version__portfolio__title__icontains=q)
                           | Q(student__last_name__icontains=q) | Q(answers__answer__icontains=q)).distinct()
        return qs


class ReflectionEditView(StudentRequiredMixin, View):
    template_name = "student/reflections/form.html"

    def _load(self, request, version_pk):
        version = get_object_or_404(
            PortfolioVersion.objects.select_related("portfolio", "portfolio__assignment", "portfolio__goal"),
            pk=version_pk, portfolio__student=request.user,
        )
        reflection = Reflection.objects.filter(portfolio_version=version).prefetch_related(
            "answers", "evidence").first()
        return version, reflection

    @staticmethod
    def _framework(request, reflection):
        """Model: refleksiya bo‘lsa — o‘zi; bo‘lmasa so‘rovdagi tanlov (faqat faol savoli bor modellardan)."""
        if reflection:
            return reflection.framework
        code = request.POST.get("framework") or request.GET.get("model") or ""
        return code if code in {f["info"].code for f in services.available_frameworks()} else None

    def _context(self, version, reflection, form):
        previous = (Reflection.objects.filter(student=version.portfolio.student,
                                              status=Reflection.Status.SUBMITTED)
                    .exclude(portfolio_version=version)
                    .select_related("portfolio_version__portfolio").order_by("-submitted_at")[:5])
        can_change = bool(reflection and services.can_change_framework(reflection))
        return {"version": version, "portfolio": version.portfolio, "reflection": reflection, "form": form,
                "framework": form.info, "progress": form.progress(), "previous_reflections": previous,
                "can_change_model": can_change,
                "other_frameworks": [f for f in services.available_frameworks()
                                     if f["info"].code != form.info.code] if can_change else []}

    def get(self, request, version_pk):
        version, reflection = self._load(request, version_pk)
        if reflection and reflection.is_locked:
            return redirect("reflections:detail", pk=reflection.pk)
        framework = self._framework(request, reflection)
        if framework is None:  # yangi refleksiya: avval modelni tanlash kerak
            return render(request, "student/reflections/choose.html", {
                "version": version, "portfolio": version.portfolio, "frameworks": services.available_frameworks(),
                "default_framework": DEFAULT_FRAMEWORK.value})
        answers = {a.question_id: a.answer for a in reflection.answers.all()} if reflection else {}
        form = ReflectionForm(questions=services.active_questions(framework), answers=answers,
                              framework=framework)
        return render(request, self.template_name, self._context(version, reflection, form))

    def post(self, request, version_pk):
        version, reflection = self._load(request, version_pk)
        framework = self._framework(request, reflection) or DEFAULT_FRAMEWORK.value
        questions = list(services.active_questions(framework))
        form = ReflectionForm(request.POST, request.FILES, questions=questions, framework=framework)
        if not form.is_valid():
            return render(request, self.template_name, self._context(version, reflection, form))
        submit = request.POST.get("action") == "submit"
        try:
            reflection = services.save_draft(
                request, version, questions, form.answers(),
                evidence_files=form.cleaned_data.get("evidence_files") or [],
                link=form.cleaned_data.get("evidence_link", ""),
                link_description=form.cleaned_data.get("evidence_description", ""),
                framework=framework,
            )
        except ValidationError as exc:
            form.add_error(None, exc)
            return render(request, self.template_name, self._context(version, reflection, form))

        if not submit:
            messages.success(request, _("Refleksiya qoralama sifatida saqlandi."))
            return redirect("reflections:edit", version_pk=version.pk)
        try:
            services.submit(request, reflection, questions)
        except ValidationError as exc:
            messages.warning(request, _("Qoralama saqlandi, lekin yuborilmadi: %(e)s") % {"e": " ".join(exc.messages)})
            return redirect("reflections:edit", version_pk=version.pk)
        messages.success(request, _("Refleksiya va ish ustozga tekshirish uchun yuborildi."))
        return redirect("portfolios:detail", pk=version.portfolio_id)


class ReflectionModelChangeView(StudentRequiredMixin, View):
    """Qoralama paytida modelni almashtirish: avval formadagi javoblar saqlanadi, so‘ng mos bosqichlarga ko‘chadi."""

    def post(self, request, version_pk):
        version = get_object_or_404(PortfolioVersion.objects.select_related("portfolio"), pk=version_pk,
                                    portfolio__student=request.user)
        target = request.POST.get("target_framework", "")
        reflection = Reflection.objects.filter(portfolio_version=version).first()
        if reflection is None:  # hali hech narsa saqlanmagan: yangi modelni shunchaki ochamiz
            url = reverse("reflections:edit", args=[version.pk])
            return redirect(f"{url}?model={target}" if target in CHOOSABLE else url)
        questions = list(services.active_questions(reflection.framework))
        form = ReflectionForm(request.POST, request.FILES, questions=questions, framework=reflection.framework)
        if not form.is_valid():
            messages.error(request, _("Avval formadagi xatolarni tuzating, keyin modelni almashtiring."))
            return redirect("reflections:edit", version_pk=version.pk)
        try:
            services.save_draft(
                request, version, questions, form.answers(),
                evidence_files=form.cleaned_data.get("evidence_files") or [],
                link=form.cleaned_data.get("evidence_link", ""),
                link_description=form.cleaned_data.get("evidence_description", ""),
                framework=reflection.framework)
            services.change_framework(request, reflection, target)
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        else:
            messages.success(request, _("Model almashtirildi. Javoblaringiz mos bosqichlarga ko‘chirildi — "
                                        "ularni tekshirib chiqing."))
        return redirect("reflections:edit", version_pk=version.pk)


class ReflectionDetailView(LoginRequiredMixin, DetailView):
    template_name = "shared/reflection_detail.html"
    context_object_name = "reflection"

    def get_queryset(self):
        return (services.visible_reflections(self.request.user)
                .select_related("student", "portfolio_version__portfolio")
                .prefetch_related("answers", "evidence"))


class EvidenceFileView(LoginRequiredMixin, View):
    def get(self, request, pk):
        evidence = get_object_or_404(ReflectionEvidence.objects.select_related("reflection"), pk=pk)
        if not evidence.file or not services.visible_reflections(request.user).filter(
                pk=evidence.reflection_id).exists():
            raise Http404
        return protected_file_response(request, evidence.file, filename=evidence.original_name,
                                       content_type=evidence.mime_type)


class EvidenceDeleteView(StudentRequiredMixin, View):
    def post(self, request, pk):
        evidence = get_object_or_404(ReflectionEvidence.objects.select_related("reflection"), pk=pk,
                                     reflection__student=request.user)
        version_pk = evidence.reflection.portfolio_version_id
        try:
            services.delete_evidence(request, evidence)
            messages.success(request, _("Dalil o‘chirildi."))
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        return redirect("reflections:edit", version_pk=version_pk)
