"""Til tanlash: asosiy til — ingliz tili; foydalanuvchi o‘zi tanlagan tilni ishlatamiz."""
from django.conf import settings
from django.utils import translation
from django.utils.cache import patch_vary_headers


def available_languages() -> set[str]:
    return {code for code, _name in settings.LANGUAGES}


class LanguageMiddleware:
    """Faol tilni aniqlaydi.

    Tartib: 1) brauzerdagi cookie (foydalanuvchi shu brauzerda tanlagan til),
    2) tizimga kirgan foydalanuvchining saqlangan tili (yangi qurilmada),
    3) `LANGUAGE_CODE` (ingliz tili).

    Brauzerning `Accept-Language` sarlavhasi ataylab e’tiborga olinmaydi: aks holda
    saytning asosiy tili brauzer sozlamasiga qarab o‘zgarib ketardi.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def pick(self, request) -> str:
        valid = available_languages()
        cookie = request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME)
        if cookie in valid:
            return cookie
        user = getattr(request, "user", None)
        saved = getattr(user, "language", "") if user is not None and user.is_authenticated else ""
        if saved in valid:
            return saved
        return settings.LANGUAGE_CODE

    def __call__(self, request):
        language = self.pick(request)
        translation.activate(language)
        request.LANGUAGE_CODE = language
        response = self.get_response(request)
        response.headers.setdefault("Content-Language", language)
        patch_vary_headers(response, ("Cookie",))
        return response
