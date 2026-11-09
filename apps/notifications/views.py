from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import ListView

from .models import Notification


class NotificationListView(LoginRequiredMixin, ListView):
    template_name = "base/notifications.html"
    context_object_name = "notifications"
    paginate_by = 30

    def get_queryset(self):
        qs = Notification.objects.filter(recipient=self.request.user).select_related("actor")
        if self.request.GET.get("filter") == "unread":
            qs = qs.filter(is_read=False)
        return qs


class NotificationOpenView(LoginRequiredMixin, View):
    def get(self, request, pk):
        n = get_object_or_404(Notification, pk=pk, recipient=request.user)
        if not n.is_read:
            n.is_read = True
            n.read_at = timezone.now()
            n.save(update_fields=["is_read", "read_at"])
        if n.url and url_has_allowed_host_and_scheme(n.url, allowed_hosts={request.get_host()}):
            return redirect(n.url)
        return redirect("notifications:list")


class NotificationMarkAllView(LoginRequiredMixin, View):
    def post(self, request):
        Notification.objects.filter(recipient=request.user, is_read=False).update(
            is_read=True, read_at=timezone.now())
        messages.success(request, _("Barcha bildirishnomalar o‘qilgan deb belgilandi."))
        return redirect("notifications:list")
