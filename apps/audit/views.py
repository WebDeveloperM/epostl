from datetime import datetime, time

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone
from django.views.generic import ListView

from apps.core.permissions import AdminRequiredMixin

from .models import AuditLog


def _parse_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


class AuditLogListView(AdminRequiredMixin, ListView):
    template_name = "admin/audit_logs.html"
    paginate_by = 50
    context_object_name = "logs"

    def get_queryset(self):
        qs = AuditLog.objects.select_related("user")
        params = self.request.GET
        if q := params.get("q", "").strip():
            qs = qs.filter(
                Q(user__username__icontains=q) | Q(user__last_name__icontains=q)
                | Q(object_repr__icontains=q) | Q(message__icontains=q) | Q(ip_address__icontains=q)
            )
        if action := params.get("action"):
            qs = qs.filter(action=action)
        if user_id := params.get("user"):
            if user_id.isdigit():
                qs = qs.filter(user_id=int(user_id))
        tz = timezone.get_current_timezone()
        if date_from := _parse_date(params.get("from")):
            qs = qs.filter(created_at__gte=timezone.make_aware(datetime.combine(date_from, time.min), tz))
        if date_to := _parse_date(params.get("to")):
            qs = qs.filter(created_at__lte=timezone.make_aware(datetime.combine(date_to, time.max), tz))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["actions"] = AuditLog.Action.choices
        ctx["filter_user"] = None
        user_id = self.request.GET.get("user")
        if user_id and user_id.isdigit():
            ctx["filter_user"] = get_user_model().objects.filter(pk=user_id).first()
        return ctx
