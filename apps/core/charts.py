"""Chart.js uchun grafik spetsifikatsiyalari (static/js/charts.js o‘qiydi).

Kategorik ranglar tekshirilgan tartibda (CVD-xavfsiz), hech qachon aylantirilmaydi:
1 — ko‘k, 2 — to‘q sariq, 3 — zangori.
"""
from django.utils.translation import gettext as _

SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]


def comparison_bar(labels, initial, latest, *, max_value=100, suffix="%",
                   initial_label=None, latest_label=None, horizontal=False):
    """Dastlabki va keyingi natijani taqqoslash."""
    return {
        "type": "bar",
        "labels": labels,
        "horizontal": horizontal,
        "max": max_value,
        "suffix": suffix,
        "datasets": [
            {"label": initial_label or _("Boshlang‘ich"), "data": initial, "color": SERIES[1]},
            {"label": latest_label or _("Keyingi natija"), "data": latest, "color": SERIES[0]},
        ],
    }


def line_chart(labels, series, *, max_value=None, suffix="", fill=False):
    return {
        "type": "line",
        "labels": labels,
        "max": max_value,
        "suffix": suffix,
        "datasets": [
            {"label": label, "data": data, "color": SERIES[i], "fill": fill and len(series) == 1}
            for i, (label, data) in enumerate(series)
        ],
    }


def bar_chart(labels, series, *, stacked=False, suffix="", horizontal=False):
    return {
        "type": "bar",
        "labels": labels,
        "stacked": stacked,
        "suffix": suffix,
        "horizontal": horizontal,
        "datasets": [{"label": label, "data": data, "color": SERIES[i]} for i, (label, data) in enumerate(series)],
    }


def doughnut(labels, values, label=""):
    return {
        "type": "doughnut",
        "labels": labels,
        "datasets": [{"label": label, "data": values, "colors": SERIES[: len(values)]}],
    }
