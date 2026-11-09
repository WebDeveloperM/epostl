from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, ProtectedError, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.audit.services import log_action
from apps.core.files import protected_file_response
from apps.core.permissions import MentorRequiredMixin

from . import services
from .forms import AssignmentForm
from .models import Assignment, AssignmentAttachment, AssignmentTarget

Status = AssignmentTarget.Status


class AssignmentListView(LoginRequiredMixin, ListView):
    """Ustoz/administrator: topshiriqlar; talaba: o‘ziga berilgan topshiriqlar."""

    paginate_by = 20

    def get_template_names(self):
        if self.request.user.is_student:
            return ["student/assignments/list.html"]
        return ["mentor/assignments/list.html"]

    def get_queryset(self):
        user = self.request.user
        q = self.request.GET.get("q", "").strip()
        if user.is_student:
            qs = (AssignmentTarget.objects.filter(student=user, assignment__is_active=True)
                  .select_related("assignment", "assignment__subject", "assignment__created_by"))
            qs = services.filter_targets_by_status(qs, self.request.GET.get("status", ""))
            if q:
                qs = qs.filter(assignment__title__icontains=q)
            return qs.order_by("assignment__due_date")
        qs = (services.visible_assignments(user)
              .select_related("subject", "competency", "created_by")
              .annotate(
                  targets_total=Count("targets", distinct=True),
                  targets_submitted=Count("targets", filter=Q(targets__status=Status.SUBMITTED), distinct=True),
                  targets_approved=Count("targets", filter=Q(targets__status=Status.APPROVED), distinct=True),
              ).order_by("-created_at"))
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(subject__name__icontains=q))
        state = self.request.GET.get("state")
        if state == "active":
            qs = qs.filter(is_active=True)
        elif state == "archived":
            qs = qs.filter(is_active=False)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        if user.is_student:
            base = AssignmentTarget.objects.filter(student=user, assignment__is_active=True)
            ctx["status_tabs"] = [
                (code, label, services.filter_targets_by_status(base, code).count())
                for code, label in Status.choices
            ]
            ctx["total"] = base.count()
        return ctx


class AssignmentCreateView(MentorRequiredMixin, CreateView):
    template_name = "mentor/assignments/form.html"
    form_class = AssignmentForm

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "mentor": self.request.user}

    def get_initial(self):
        initial = super().get_initial()
        if student_id := self.request.GET.get("student"):
            initial["students"] = [student_id]
        return initial

    def form_valid(self, form):
        self.object = services.save_assignment(self.request, form)
        messages.success(self.request, _("Topshiriq yaratildi va talabalarga yuborildi."))
        return redirect("assignments:detail", pk=self.object.pk)


class AssignmentUpdateView(MentorRequiredMixin, UpdateView):
    template_name = "mentor/assignments/form.html"
    form_class = AssignmentForm

    def get_queryset(self):
        return Assignment.objects.filter(created_by=self.request.user)

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "mentor": self.request.user}

    def form_valid(self, form):
        self.object = services.save_assignment(self.request, form)
        messages.success(self.request, _("Topshiriq saqlandi."))
        return redirect("assignments:detail", pk=self.object.pk)


class AssignmentDetailView(LoginRequiredMixin, DetailView):
    context_object_name = "assignment"

    def get_queryset(self):
        return (services.visible_assignments(self.request.user)
                .select_related("subject", "competency", "created_by")
                .prefetch_related("attachments", "groups"))

    def get_template_names(self):
        if self.request.user.is_student:
            return ["student/assignments/detail.html"]
        return ["mentor/assignments/detail.html"]

    def get_context_data(self, **kwargs):
        from apps.portfolios.models import Portfolio

        ctx = super().get_context_data(**kwargs)
        assignment = self.object
        user = self.request.user
        ctx["criteria"] = assignment.effective_criteria()
        if user.is_student:
            ctx["target"] = get_object_or_404(AssignmentTarget, assignment=assignment, student=user)
            ctx["portfolio"] = Portfolio.objects.filter(assignment=assignment, student=user).first()
        else:
            targets = (assignment.targets.select_related("student", "student__group", "source_group")
                       .order_by("student__last_name"))
            targets = services.filter_targets_by_status(targets, self.request.GET.get("status", ""))
            works = {p.student_id: p for p in Portfolio.objects.filter(assignment=assignment)}
            ctx["targets"] = [(t, works.get(t.student_id)) for t in targets]
            all_targets = assignment.targets.all()
            ctx["status_summary"] = [
                (code, label, services.filter_targets_by_status(all_targets, code).count())
                for code, label in Status.choices
            ]
            ctx["can_manage"] = services.can_manage(user, assignment)
        return ctx


class AssignmentAcceptView(LoginRequiredMixin, View):
    def post(self, request, pk):
        target = get_object_or_404(AssignmentTarget, assignment_id=pk, student=request.user)
        if services.accept(request, target):
            messages.success(request, _("Topshiriq qabul qilindi."))
        return redirect("assignments:detail", pk=pk)


class AssignmentDeleteView(MentorRequiredMixin, View):
    def post(self, request, pk):
        assignment = get_object_or_404(Assignment, pk=pk, created_by=request.user)
        title = str(assignment)
        try:
            assignment_pk = assignment.pk
            assignment.delete()
            assignment.pk = assignment_pk
            log_action(request, "delete", assignment)
        except ProtectedError:
            messages.error(request, _("Topshiriq bo‘yicha ishlar yuklangan — o‘chirib bo‘lmaydi. "
                                      "Uni arxivlash uchun «Faol» belgisini olib tashlang."))
            return redirect("assignments:detail", pk=pk)
        messages.success(request, _("«%(t)s» topshirig‘i o‘chirildi.") % {"t": title})
        return redirect("assignments:list")


class AttachmentDownloadView(LoginRequiredMixin, View):
    def get(self, request, pk):
        attachment = get_object_or_404(AssignmentAttachment.objects.select_related("assignment"), pk=pk)
        if not services.visible_assignments(request.user).filter(pk=attachment.assignment_id).exists():
            raise Http404
        return protected_file_response(request, attachment.file, filename=attachment.original_name,
                                       content_type=attachment.mime_type)


class AttachmentDeleteView(MentorRequiredMixin, View):
    def post(self, request, pk):
        attachment = get_object_or_404(AssignmentAttachment, pk=pk, assignment__created_by=request.user)
        assignment_id = attachment.assignment_id
        log_action(request, "delete", attachment)
        attachment.file.delete(save=False)
        attachment.delete()
        messages.success(request, _("Fayl o‘chirildi."))
        return redirect("assignments:update", pk=assignment_id)
