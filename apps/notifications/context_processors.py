from .models import Notification


def notifications(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}
    unread = Notification.objects.filter(recipient=user, is_read=False)
    return {
        "unread_notifications_count": unread.count(),
        "latest_notifications": list(unread.order_by("-created_at")[:6]),
    }
