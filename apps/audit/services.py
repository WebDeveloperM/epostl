import logging

from django.core.serializers.json import DjangoJSONEncoder
import json

from apps.core.utils import client_ip

from .models import AuditLog

logger = logging.getLogger("apps.audit")


def _jsonable(data):
    try:
        return json.loads(json.dumps(data, cls=DjangoJSONEncoder, default=str))
    except (TypeError, ValueError):
        return {"raw": str(data)}


def log_action(request, action, obj=None, message="", *, user=None, **extra):
    """Muhim amalni audit log'ga yozadi. Xatolik asosiy jarayonni to‘xtatmaydi."""
    try:
        if user is None and request is not None and getattr(request, "user", None) is not None:
            user = request.user if request.user.is_authenticated else None
        entry = AuditLog(
            user=user,
            action=action,
            message=message,
            extra=_jsonable(extra),
            ip_address=client_ip(request),
            user_agent=(request.META.get("HTTP_USER_AGENT", "")[:255] if request else ""),
        )
        if obj is not None:
            entry.object_type = obj._meta.label
            entry.object_id = str(obj.pk or "")
            entry.object_repr = str(obj)[:255]
        entry.save()
        return entry
    except Exception:  # pragma: no cover
        logger.exception("Audit log yozib bo‘lmadi")
        return None
