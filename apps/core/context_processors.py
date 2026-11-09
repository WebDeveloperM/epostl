from django.conf import settings

from .models import SystemSettings
from .permissions import ADMIN, MENTOR, STUDENT, role_of
from .utils import tr


def platform(request):
    role = role_of(getattr(request, "user", None))
    try:
        system = SystemSettings.get_solo()
    except Exception:  # migratsiyalar qo‘llanmagan bo‘lsa
        system = None
    return {
        "system_settings": system,
        # Platforma nomi standart bo‘lsa — joriy tilda; administrator o‘zgartirgan bo‘lsa — o‘zgarishsiz
        "platform_name": tr(system.platform_name if system and system.platform_name else "Refleksiv portfolio"),
        # Til nomlari tarjima qilinmaydi: har bir til o‘z nomi bilan ko‘rinadi
        "language_choices": settings.LANGUAGES,
        "user_role": role,
        "is_admin_role": role == ADMIN,
        "is_mentor_role": role == MENTOR,
        "is_student_role": role == STUDENT,
    }
