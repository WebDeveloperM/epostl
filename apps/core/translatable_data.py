"""Bazaga yozilgan standart (seed) matnlar — tarjima kataloglari uchun.

Bu matnlar migratsiyalar orqali bazaga o‘zbek tilida yoziladi. Ekranda ular
`tr()` / `|tr` orqali joriy tilga o‘giriladi, shuning uchun katalogga tushishi kerak.
`gettext_noop` — matnni faqat «tarjima qilinadi» deb belgilaydi (`makemessages` ko‘radi),
ishga tushganda hech narsa o‘zgartirmaydi.

Administrator bu nomlarni o‘zgartirsa, yangi matn tarjimasiz, yozilganidek ko‘rsatiladi.
"""
from django.utils.translation import gettext_noop as _

SEED_TEXTS = [
    # platforma nomi (SystemSettings.platform_name standart qiymati)
    _("Refleksiv portfolio"),
    # kompetensiyalar (competencies/migrations/0002_seed_competencies.py)
    _("Darsni rejalashtirish"),
    _("Mavzuni tushuntirish"),
    _("Savol berish"),
    _("O‘quvchilar bilan muloqot"),
    _("Refleksiya"),
    _("Dars maqsadi, tuzilmasi, vaqt va resurslarni rejalashtirish"),
    _("Mavzuni aniq, izchil va tushunarli bayon qilish"),
    _("Turli darajadagi savollar bilan o‘quvchilarni fikrlashga undash"),
    _("Hamkorlik, qayta aloqa va ijobiy muhit yaratish"),
    _("O‘z faoliyatini tahlil qilish va takomillashtirish"),
    # baholash mezonlari
    _("Mavzuni tushuntirish aniqligi"),
    _("Savol berish ko‘nikmasi"),
    _("Refleksiya va o‘zini tahlil qilish"),
    # refleksiya savollari (reflections/migrations/0002_seed_questions.py)
    _("Men nimaga erishmoqchi edim?"),
    _("Amalda nima sodir bo‘ldi?"),
    _("Nima yaxshi chiqdi? Buni qaysi dalil ko‘rsatadi?"),
    _("Qayerda qiyinchilik bo‘ldi va nima sababdan?"),
    _("Keyingi safar nimani o‘zgartiraman?"),
    _("Dars yoki faoliyat oldidan qo‘ygan maqsadingizni yozing."),
    _("Jarayonni ketma-ket, faktlarga tayanib tasvirlang."),
    _("Video lavha, o‘quvchilar javoblari, kuzatuv natijalari kabi dalillarni keltiring."),
    _("Qiyinchilik sabablarini tahlil qiling."),
    _("Aniq va amalga oshirsa bo‘ladigan qadamlarni yozing."),
    # refleksiya modellari savollari (reflections/migrations/0003_reflection_frameworks.py)
    _("Nima sodir bo‘ldi?"),
    _("Voqeani ketma-ket, faqat faktlarga tayanib hikoya qiling."),
    _("Qanday his-tuyg‘ularni his qildingiz?"),
    _("Voqea paytida va undan keyin o‘zingizni qanday his qilganingizni yozing."),
    _("Nima yaxshi, nima yomon chiqdi?"),
    _("Yaxshi va yomon tomonlarni dalillar bilan ko‘rsating."),
    _("Nima uchun bunday bo‘ldi?"),
    _("Sabablarni toping: nima yordam berdi, nima xalaqit qildi?"),
    _("Bundan nimani o‘rgandingiz?"),
    _("Boshqacha nima qilish mumkin edi?"),
    _("Keyingi safar nima qilasiz?"),
    _("Haqiqatan bajara oladigan aniq qadamlarni yozing."),
    _("Nima qildingiz?"),
    _("Tajribani tasvirlang: qayerda, kim bilan va nima bo‘ldi?"),
    _("Nimani payqadingiz?"),
    _("Voqeaga yon tomondan qarang. Nimani ko‘rdingiz va nimani o‘yladingiz?"),
    _("Bu tajriba sizga nimani o‘rgatdi?"),
    _("Tajribani biror nazariya yoki qoida bilan bog‘lang."),
    _("Keyingi safar nimani sinab ko‘rasiz?"),
    _("Yangi g‘oyani ishda qo‘llash uchun aniq reja yozing."),
]
