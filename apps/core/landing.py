"""Landing (bosh) sahifa mazmuni.

Matnlar o‘zbekcha yoziladi (loyiha qoidasi); inglizchasi `locale/en` katalogida (oddiy so‘zlar bilan).
Funksiya har bir so‘rovda chaqiriladi, shuning uchun matnlar joriy tilda chiqadi.
"""
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _

from .utils import admin_link

from apps.reflections.frameworks import FRAMEWORKS


def landing_content(system) -> dict:
    doc_mb = system.max_upload_size_mb if system else 50
    video_mb = system.max_video_size_mb if system else 1024
    return {
        "nav": [
            ("about", _("Umumiy ma'lumot")), ("cycle", _("Qanday ishlaydi")), ("models", _("Modellar")),
            ("features", _("Imkoniyatlar")), ("roles", _("Rollar")), ("faq", _("Savol-javob")),
        ],
        "stats": [
            ("8", _("bosqichli rivojlanish sikli")),
            ("2", _("refleksiya modeli: Gibbs va Kolb")),
            ("3", _("foydalanuvchi roli")),
            ("2", _("til: English va O‘zbekcha")),
        ],
        "pillars": [
            ("bi-folder2-open", _("Saqlang"),
             _("Muhim tajribalaringizni va ish versiyalaringizni bir joyda saqlang.")),
            ("bi-lightbulb", _("O‘ylang"),
             _("Gibbs va Kolb modellari bilan o‘z faoliyatingizni tahlil qiling.")),
            ("bi-graph-up-arrow", _("O‘sing"),
             _("Ustoz fikri va natijalar taqqoslashi bilan oldinga siljing.")),
        ],
        "steps": [
            ("bi-clipboard-data", _("Boshlang‘ich baholash"), _("Ustoz sizning boshlang‘ich darajangizni baholaydi.")),
            ("bi-bullseye", _("Maqsad"), _("O‘zingiz uchun aniq va o‘lchasa bo‘ladigan maqsad qo‘ying.")),
            ("bi-calendar-check", _("Rejalashtirish"),
             _("Maqsadga erishish uchun topshiriq va muddatlarni rejalashtiring.")),
            ("bi-cloud-arrow-up", _("Amaliy ish"), _("Dars ishlanmasi, video va boshqa ishlaringizni yuklang.")),
            ("bi-chat-square-quote", _("Refleksiya"), _("Gibbs yoki Kolb modeli bilan o‘z ishingiz haqida o‘ylang.")),
            ("bi-person-check", _("Ustoz fikri"), _("Ustoz mezonlar bo‘yicha ball qo‘yadi va tavsiya beradi.")),
            ("bi-arrow-repeat", _("Takomillashtirish"),
             _("Tavsiyalar asosida ishni yaxshilab, yangi versiya yuklang.")),
            ("bi-bar-chart-line", _("Taqqoslash"), _("Boshlang‘ich va oxirgi natijani yonma-yon ko‘ring.")),
        ],
        "slides": [
            {"image": "images/landing/slide-goals.svg", "tone": "indigo", "kicker": _("Maqsad va reja"),
             "title": _("Maqsad qo‘ying va yo‘lingizni rejalashtiring"),
             "text": _("Har bir maqsadda kompetensiya, muddat va kutilgan natija bo‘ladi. Ustozlar topshiriq beradi, "
                       "muddatlardan oldin esa eslatma kelib turadi."),
             "points": [_("Maqsadlar va topshiriqlar bir joyda"), _("Muddatlar haqida eslatmalar"),
                        _("Holatingizni har doim ko‘rasiz")]},
            {"image": "images/landing/slide-versions.svg", "tone": "teal", "kicker": _("Portfolio ishlari"),
             "title": _("Ishlaringizni versiyalari bilan saqlang"),
             "text": _("Dars ishlanmasi, video, audio, rasm va taqdimotlarni yuklang. Har bir versiya saqlanadi va "
                       "hech qachon o‘chirilmaydi."),
             "points": [_("Hujjat, video, audio, rasm va taqdimot"), _("Har bir yangi versiya alohida saqlanadi"),
                        _("Fayllar yopiq va xavfsiz")]},
            {"image": "images/landing/slide-models.svg", "tone": "violet", "kicker": _("Refleksiya"),
             "title": _("Gibbs yoki Kolb modeli bilan o‘ylang"),
             "text": _("Model refleksiyani aniq bosqichlarga bo‘lib beradi. Javob yozgan sari progressni ko‘rasiz."),
             "points": [_("Gibbs: 6 bosqich"), _("Kolb: 4 bosqich"),
                        _("Ustozga yuborguncha modelni almashtirish mumkin")]},
            {"image": "images/landing/slide-analysis.svg", "tone": "amber", "kicker": _("Tahlil va natijalar"),
             "title": _("O‘sishingizni raqamlarda ko‘ring"),
             "text": _("Boshlang‘ich va oxirgi natija, mezonlar bo‘yicha ballar va ustoz fikrlari tarixi bitta "
                       "sahifada."),
             "points": [_("Boshlang‘ich va oxirgi natija taqqoslanadi"), _("Mezonlar bo‘yicha ballar"),
                        _("Ustoz fikrlari tarixi")]},
        ],
        "features": [
            ("bi-files", _("Versiyali portfolio"),
             _("Ishning har bir versiyasi saqlanadi, shuning uchun o‘sish tarixi to‘liq ko‘rinadi.")),
            ("bi-diagram-3", _("Refleksiya modellari"),
             _("Gibbs va Kolb sikllari: savollar bosqichlarga bo‘lingan, to‘ldirilish darajasi ko‘rinib turadi.")),
            ("bi-clipboard-check", _("Aniq baholash mezonlari"),
             _("Ustoz har bir mezon bo‘yicha ball va izoh beradi, nimani yaxshilash kerakligi aniq bo‘ladi.")),
            ("bi-bullseye", _("Maqsadlar va topshiriqlar"),
             _("Maqsad qo‘ying, topshiriqni qabul qiling, muddatni kuzating.")),
            ("bi-bar-chart-line", _("Tahlil va taqqoslash"),
             _("Boshlang‘ich va oxirgi natija, dinamika grafiklari va modellar bo‘yicha tahlil.")),
            ("bi-bell", _("Bildirishnomalar"),
             _("Yangi topshiriq, ustoz fikri va muddat eslatmalari o‘z tilingizda keladi.")),
            ("bi-translate", _("Ikki til"),
             _("Sayt ingliz va o‘zbek tillarida ishlaydi. Tanlovingiz eslab qolinadi.")),
            ("bi-shield-lock", _("Xavfsizlik"),
             _("Fayllar yopiq, har bir amal jurnalga yoziladi, ruxsatlar rolga qarab beriladi.")),
            ("bi-file-earmark-excel", _("Excel orqali import"),
             _("Administrator foydalanuvchilarni Excel fayldan birdaniga qo‘shadi.")),
        ],
        "roles": [
            ("bi-mortarboard", _("Talaba"), [
                _("Maqsad qo‘yadi va topshiriqlarni bajaradi"), _("Ish yuklaydi va refleksiya yozadi"),
                _("Baholarini va o‘sishini ko‘radi")]),
            ("bi-person-workspace", _("Ustoz"), [
                _("Topshiriq beradi va ishlarni ko‘radi"), _("Mezonlar bo‘yicha baholaydi va tavsiya yozadi"),
                _("Talabalar o‘sishini kuzatadi")]),
            ("bi-gear", _("Administrator"), [
                _("Foydalanuvchilar va tuzilmani boshqaradi"), _("Mezonlar va refleksiya savollarini sozlaydi"),
                _("Umumiy analitikani ko‘radi")]),
        ],
        "faq": [
            (_("Platformaga kim kira oladi?"),
             _("Administrator yaratgan talaba, ustoz va administrator hisoblari. O‘zingiz ro‘yxatdan o‘ta olmaysiz.")),
            (_("Parolimni unutsam, nima qilaman?"),
             mark_safe(_("%(admin)s murojaat qiling. U sizga yangi vaqtinchalik parol beradi.")
                      % {"admin": conditional_escape(admin_link())})),
            (_("Qanday fayllarni yuklash mumkin?"),
             _("Hujjat, rasm, audio, video va taqdimot. Hajm: hujjat, rasm va audio %(doc)s MB gacha, "
               "video %(video)s MB gacha.") % {"doc": doc_mb, "video": video_mb}),
            (_("Refleksiya modelini almashtirsam bo‘ladimi?"),
             _("Ha, ustozga yuborguncha. Javoblaringiz mos bosqichlarga ko‘chiriladi, hech narsa yo‘qolmaydi.")),
            (_("Ishimni kimlar ko‘ra oladi?"),
             _("Faqat siz, sizga biriktirilgan ustoz va administrator.")),
            (_("Sayt qaysi tillarda ishlaydi?"),
             _("Ingliz va o‘zbek tillarida. Tilni yuqoridagi tugma bilan almashtirasiz, tanlovingiz saqlanadi.")),
        ],
        "frameworks": [FRAMEWORKS["gibbs"], FRAMEWORKS["kolb"]],
    }
