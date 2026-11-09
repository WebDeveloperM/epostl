from django import template
from django.utils.html import format_html

from apps.core.files import CATEGORY_ICONS, CATEGORY_LABELS
from apps.core.files import human_size as _human_size

register = template.Library()


@register.simple_tag
def admin_link():
    """`{% admin_link as admin %}` — «Administratorga» (Telegram havolasi bilan, sozlangan bo‘lsa)."""
    from apps.core.utils import admin_link as _admin_link

    return _admin_link()


@register.filter
def tr(value):
    """Bazadagi standart nom/savol matnini joriy tilda ko‘rsatadi (`{{ x.name|tr }}`)."""
    from apps.core.utils import tr as _tr

    return _tr(value)

STATUS_COLORS = {
    # umumiy
    "new": "secondary",
    "draft": "secondary",
    "accepted": "info",
    "in_progress": "primary",
    "submitted": "warning",
    "revision": "danger",
    "approved": "success",
    "completed": "success",
    "overdue": "dark",
    "cancelled": "light",
    # baholash
    "baseline": "info",
    "work": "primary",
}


@register.simple_tag
def status_badge(code, label=None):
    color = STATUS_COLORS.get(code, "secondary")
    text_class = " text-dark border" if color == "light" else ""
    return format_html('<span class="badge rounded-pill text-bg-{}{} status-badge">{}</span>',
                       color, text_class, label or code)


@register.simple_tag(takes_context=True)
def url_replace(context, **kwargs):
    query = context["request"].GET.copy()
    for key, value in kwargs.items():
        if value in (None, ""):
            query.pop(key, None)
        else:
            query[key] = value
    return query.urlencode()


@register.filter
def human_size(value):
    return _human_size(value)


@register.filter
def file_icon(category):
    return CATEGORY_ICONS.get(category, "bi-file-earmark")


@register.filter
def file_category_label(category):
    return CATEGORY_LABELS.get(category, category)


@register.filter
def initials(user):
    if not user:
        return "?"
    first = (getattr(user, "first_name", "") or "")[:1]
    last = (getattr(user, "last_name", "") or "")[:1]
    return (last + first).upper() or (getattr(user, "username", "?")[:2]).upper()


@register.filter
def get_item(mapping, key):
    try:
        return mapping.get(key)
    except AttributeError:
        return None


@register.filter
def score_color(percent_value):
    if percent_value is None:
        return "secondary"
    if percent_value >= 85:
        return "success"
    if percent_value >= 60:
        return "primary"
    if percent_value >= 40:
        return "warning"
    return "danger"


@register.filter
def signed(value):
    if value is None:
        return "—"
    from django.utils.formats import number_format

    text = number_format(value, decimal_pos=1 if isinstance(value, float) else None)
    return f"+{text}" if value > 0 else text


@register.filter
def css_pct(value):
    """CSS uchun foiz qiymati (lokalizatsiyasiz, 0–100 oralig‘ida)."""
    try:
        number = max(0.0, min(100.0, float(value)))
    except (TypeError, ValueError):
        return "0"
    return f"{number:.1f}"
