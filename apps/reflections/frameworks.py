"""Refleksiya modellari: Gibbs va Kolb sikllari (bosqichlari bilan).

Talaba refleksiya yozishdan oldin modelni tanlaydi. Har bir model — tayyor savollar to‘plami;
savollar bosqichlarga bo‘lingan. Bosqich kodlari modellar orasida takrorlanmaydi, shuning uchun
`ReflectionQuestion.stage` bitta ro‘yxatdan tanlanadi.

Matnlar o‘zbekcha yoziladi (loyiha qoidasi), inglizchasi `locale/en` katalogida.
"""
from dataclasses import dataclass

from django.db import models
from django.utils.translation import gettext_lazy as _


class Framework(models.TextChoices):
    GIBBS = "gibbs", _("Gibbs refleksiya sikli")
    KOLB = "kolb", _("Kolb tajriba orqali o‘rganish sikli")
    SIMPLE = "simple", _("Qisqa refleksiya")


DEFAULT_FRAMEWORK = Framework.GIBBS


@dataclass(frozen=True)
class Stage:
    code: str
    label: object  # lazy matn
    hint: object


@dataclass(frozen=True)
class FrameworkInfo:
    code: str
    label: object
    summary: object
    best_for: object
    icon: str
    stages: tuple = ()
    insight_stages: tuple = ()  # «asosiy xulosalar» shu bosqichlar javobidan olinadi

    @property
    def stage_codes(self):
        return [s.code for s in self.stages]

    def stage(self, code):
        return next((s for s in self.stages if s.code == code), None)


FRAMEWORKS = {
    Framework.GIBBS.value: FrameworkInfo(
        code="gibbs", label=Framework.GIBBS.label, icon="bi-arrow-repeat",
        summary=_("Tajriba yoki faoliyat bosqichlari haqida ketma-ket, tizimli o‘ylashga yordam beradigan keng "
                  "tarqalgan model. Olti bosqichdan iborat: tasvir, his-tuyg‘ular, baholash, tahlil, xulosa "
                  "va harakat rejasi."),
        best_for=_("Tuzilmasi aniq: muvaffaqiyat va xatolardan to‘liq o‘rganish uchun qulay."),
        stages=(
            Stage("description", _("Tasvir"), _("Nima bo‘lganini aytib bering.")),
            Stage("feelings", _("His-tuyg‘ular"), _("Nimalarni his qilganingizni yozing.")),
            Stage("evaluation", _("Voqeani baholash"), _("Nima yaxshi, nima yomon bo‘ldi?")),
            Stage("analysis", _("Tahlil"), _("Nima uchun shunday bo‘lganini tushuntiring.")),
            Stage("conclusion", _("Xulosa"), _("Nimani o‘rganganingizni yozing.")),
            Stage("action_plan", _("Harakat rejasi"), _("Keyingi safar nima qilishingizni yozing.")),
        ),
        insight_stages=("conclusion", "action_plan"),
    ),
    Framework.KOLB.value: FrameworkInfo(
        code="kolb", label=Framework.KOLB.label, icon="bi-diagram-3",
        summary=_("Tajriba va undan o‘rganishga tayanadigan model. To‘rt bosqichdan iborat: aniq tajriba, "
                  "mulohazali kuzatish, mavhum tushunchalash va faol tajriba qilish."),
        best_for=_("Tajribani amalda qo‘llasa bo‘ladigan xulosalarga aylantirish uchun qulay."),
        stages=(
            Stage("concrete_experience", _("Aniq tajriba"), _("Nima qilganingizni tasvirlang.")),
            Stage("reflective_observation", _("Mulohazali kuzatish"),
                  _("Voqeaga yon tomondan qarang: nimani payqadingiz?")),
            Stage("abstract_conceptualization", _("Mavhum tushunchalash"),
                  _("Tajribani nazariya yoki qoida bilan bog‘lang.")),
            Stage("active_experimentation", _("Faol tajriba qilish"), _("Yangi g‘oyani sinab ko‘ring.")),
        ),
        insight_stages=("abstract_conceptualization", "active_experimentation"),
    ),
    Framework.SIMPLE.value: FrameworkInfo(
        code="simple", label=Framework.SIMPLE.label, icon="bi-lightning-charge",
        summary=_("Tez refleksiya uchun beshta oddiy savol."),
        best_for=_("Vaqt kam bo‘lganda qulay."),
        stages=(),
    ),
}

# Modelni almashtirganda javoblar mos bosqichga ko‘chadi (hech narsa yo‘qolmasin): eski bosqich -> yangi bosqich.
# Bir necha bosqich bitta bosqichga tushsa, matnlar ketma-ket birlashtiriladi.
CARRY_OVER = {
    ("gibbs", "kolb"): {
        "description": "concrete_experience",
        "feelings": "reflective_observation",
        "evaluation": "reflective_observation",
        "analysis": "abstract_conceptualization",
        "conclusion": "abstract_conceptualization",
        "action_plan": "active_experimentation",
    },
    ("kolb", "gibbs"): {
        "concrete_experience": "description",
        "reflective_observation": "evaluation",
        "abstract_conceptualization": "analysis",
        "active_experimentation": "action_plan",
    },
}

# Tanlash ekranida ko‘rsatiladigan modellar (qisqa refleksiya faqat eski ma’lumotlar uchun)
CHOOSABLE = (Framework.GIBBS.value, Framework.KOLB.value)

# Bosqichlar ro‘yxati (guruhlangan tanlov): savol formasi uchun
STAGE_CHOICES = [("", "—")] + [
    (info.label, [(s.code, s.label) for s in info.stages])
    for info in (FRAMEWORKS["gibbs"], FRAMEWORKS["kolb"])
]


def get_framework(code, default=DEFAULT_FRAMEWORK) -> FrameworkInfo:
    """Noma’lum kod kelsa — standart model (foydalanuvchi kiritmasiga ishonmaymiz)."""
    return FRAMEWORKS.get(code) or FRAMEWORKS[default.value if hasattr(default, "value") else default]


def stage_of(code):
    """Bosqich kodi bo‘yicha (model, bosqich) juftligi."""
    for info in FRAMEWORKS.values():
        if (stage := info.stage(code)):
            return info, stage
    return None, None
