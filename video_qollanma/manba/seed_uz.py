"""Video uchun o'zbekcha demo ma'lumotlar (faqat video bazasi uchun: settings_video)."""
import os
import sys
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings_video")
django.setup()

from django.core.files.uploadedfile import SimpleUploadedFile  # noqa: E402
from django.db import transaction  # noqa: E402
from django.utils import timezone  # noqa: E402
from django.utils.datastructures import MultiValueDict  # noqa: E402

from apps.accounts.models import MentorAssignment, Role, User  # noqa: E402
from apps.assessments.models import Assessment, MentorFeedback  # noqa: E402
from apps.assessments.services import assess_version, create_baseline  # noqa: E402
from apps.assignments.models import Assignment, AssignmentTarget  # noqa: E402
from apps.assignments.services import sync_targets  # noqa: E402
from apps.competencies.models import AssessmentCriterion, Competency  # noqa: E402
from apps.core.models import SystemSettings  # noqa: E402
from apps.goals.models import Goal  # noqa: E402
from apps.organization.models import Department, Direction, Faculty, StudyGroup  # noqa: E402
from apps.portfolios.forms import PortfolioCreateForm, UploadForm  # noqa: E402
from apps.portfolios.services import create_portfolio, upload_files  # noqa: E402
from apps.reflections import services as rs  # noqa: E402
from apps.subjects.models import Subject  # noqa: E402

SAMPLES = Path(__file__).resolve().parent / "samples"
REAL_NOW = timezone.now
BASE = REAL_NOW()


@contextmanager
def at(days_ago, hour_shift=0):
    """Shu blok ichida yaratilgan yozuvlar `days_ago` kun oldingi sana bilan saqlanadi."""
    fake = BASE - timedelta(days=days_ago, hours=hour_shift)
    with mock.patch("django.utils.timezone.now", lambda: fake):
        yield fake


def req(user):
    return SimpleNamespace(user=user, META={"REMOTE_ADDR": "10.0.0.15", "HTTP_USER_AGENT": "Mozilla/5.0"})


def pdf(name):
    return SimpleUploadedFile(name, (SAMPLES / "dars_ishlanmasi_v1.pdf").read_bytes(), "application/pdf")


def user(username, password, role, **fields):
    u, created = User.objects.get_or_create(username=username, defaults={**fields, "role": Role.objects.get(code=role),
                                                                          "language": "uz"})
    if created:
        u.set_password(password)
        u.save()
    return u


def details(scores):
    crit = list(AssessmentCriterion.objects.filter(is_active=True).order_by("order"))
    return [{"criterion": c, "score": s, "comment": cm, "weaknesses": w, "recommendations": r}
            for c, (s, cm, w, r) in zip(crit, scores)]


def work(student, assignment, goal, title, desc, framework, answers, days):
    with at(days):
        form = PortfolioCreateForm(
            data={"title": title, "assignment": assignment.pk, "goal": goal.pk if goal else "",
                  "material_type": "lesson_plan", "description": desc, "note": ""},
            files=MultiValueDict({"files": [pdf("dars_ishlanmasi_v1.pdf")]}), student=student)
        assert form.is_valid(), form.errors
        p = create_portfolio(req(student), form)
    with at(days, -2):
        qs = list(rs.active_questions(framework))
        r = rs.save_draft(req(student), p.latest_version, qs, {q.pk: a for q, a in zip(qs, answers)},
                          framework=framework)
        rs.submit(req(student), r, qs)
    p.refresh_from_db()
    return p


GIBBS_AZIZ = [
    "3-sinfda 45 daqiqalik dars o‘tdim. Barcha o‘quvchilarni savol-javobga jalb qilmoqchi edim, lekin faqat 6–7 nafari javob berdi.",
    "Avvaliga hayajonlandim. Keyin ko‘pchilik jim o‘tirgani uchun xavotir oldim.",
    "Yaxshi tomoni: darsni muammoli savol bilan boshladim va o‘quvchilar qiziqdi. Kamchiligi: savollarim asosan yopiq edi.",
    "Javob uchun yetarli kutmadim, shuning uchun uyatchan o‘quvchilar o‘ylashga ulgurmadi.",
    "Ochiq savollar va uzoqroq kutish ko‘proq o‘quvchini gapirishga undashini tushundim.",
    "Keyingi darsda ochiq savollar va «o‘yla — juftlikda muhokama qil» usulini qo‘llayman.",
]
KOLB_AZIZ = [
    "Darsni ochiq savollar bilan qayta o‘tdim. Har savoldan keyin 5–7 soniya kutdim.",
    "Juftlikda muhokamadan keyin 20 nafardan 17 nafari javob berdi, javoblar to‘liqroq bo‘ldi.",
    "Kutish vaqti va juftlikda ishlash uyatchan o‘quvchilarga o‘ylash imkonini beradi.",
    "Oxirgi bosqichga 5 daqiqa ajrataman va bu usulni boshqa fanlarda ham sinab ko‘raman.",
]
GIBBS_DILNOZA = [
    "4-sinfda «Ona tili» darsini savol-javob metodi bilan o‘tdim.",
    "Dars boshida ishonchim yuqori edi, oxirida vaqt yetmay qolganidan biroz tushkunlandim.",
    "O‘quvchilar faol qatnashdi, lekin savollar bir xil darajada bo‘ldi.",
    "Savollarni oldindan darajalar bo‘yicha tayyorlamagan edim.",
    "Savollarni Blum taksonomiyasi bo‘yicha rejalashtirish kerakligini angladim.",
    "Keyingi darsga uch darajali savollar ro‘yxatini tayyorlab boraman.",
]
KOLB_SARDOR = [
    "2-sinfda matematika darsida savol-javob va o‘yin usulini birlashtirdim.",
    "O‘quvchilar o‘yin paytida savollarga tez va quvonib javob berishdi.",
    "O‘yin elementlari motivatsiyani oshiradi va savol berishni tabiiy qiladi.",
    "Keyingi darsda guruhlarga bo‘lib, musobaqa shaklini sinab ko‘raman.",
]
GIBBS_MADINA = [
    "3-sinfda «Atrofimizdagi olam» darsini o‘tdim.",
    "Dars davomida o‘zimni xotirjam his qildim.",
    "Dars rejasi bo‘yicha ishladim, lekin savollar kam bo‘ldi.",
    "Ko‘proq o‘zim gapirdim, o‘quvchilarga imkon kam berdim.",
    "O‘quvchilarga ko‘proq so‘z berish kerak.",
    "Keyingi safar har bosqichda kamida ikkita savol beraman.",
]


@transaction.atomic
def main():
    s = SystemSettings.objects.first() or SystemSettings()
    s.organization_name = "Pedagogika instituti"
    s.save()

    fac, _ = Faculty.objects.get_or_create(name="Pedagogika fakulteti", defaults={"short_name": "PF"})
    Faculty.objects.get_or_create(name="Xorijiy tillar fakulteti", defaults={"short_name": "XTF"})
    dep, _ = Department.objects.get_or_create(faculty=fac, name="Pedagogika va psixologiya kafedrasi")
    Department.objects.get_or_create(faculty=fac, name="Boshlang‘ich ta’lim metodikasi kafedrasi")
    direction, _ = Direction.objects.get_or_create(
        code="60110500", defaults={"faculty": fac, "department": dep, "name": "Boshlang‘ich ta’lim"})
    g1, _ = StudyGroup.objects.get_or_create(name="BT-21", defaults={"direction": direction, "course": 3,
                                                                      "academic_year": "2026-2027"})
    g2, _ = StudyGroup.objects.get_or_create(name="BT-22", defaults={"direction": direction, "course": 3,
                                                                      "academic_year": "2026-2027"})
    subj, _ = Subject.objects.get_or_create(code="PA-301", defaults={"name": "Pedagogik amaliyot", "department": dep})
    subj2, _ = Subject.objects.get_or_create(code="TM-205", defaults={"name": "Ta’lim metodikasi", "department": dep})

    admin = user("admin", "Admin12345!", Role.Code.ADMIN, last_name="Administrator", first_name="Tizim",
                 is_staff=True, is_superuser=True, email="admin@example.uz")
    mentor = user("ustoz", "Ustoz12345!", Role.Code.MENTOR, last_name="Saidova", first_name="Malika",
                  middle_name="Akramovna", department=dep, email="ustoz@example.uz", external_id="EMP-0001")
    mentor2 = user("ustoz2", "Ustoz12345!", Role.Code.MENTOR, last_name="Qodirov", first_name="Bekzod",
                   middle_name="Anvarovich", department=dep, external_id="EMP-0002")
    names = [("Karimov", "Aziz", "Rustamovich", g1), ("Toshmatova", "Dilnoza", "Baxtiyorovna", g1),
             ("Ergashev", "Sardor", "Alisherovich", g1), ("Yusupova", "Madina", "Shavkatovna", g1),
             ("Nazarov", "Otabek", "Ilhomovich", g1), ("Abdullayeva", "Zarina", "Komilovna", g2),
             ("Xolmatov", "Doniyor", "Baxromovich", g2)]
    st = [user(f"talaba{i}", "Talaba12345!", Role.Code.STUDENT, last_name=ln, first_name=fn, middle_name=mn,
               group=g, external_id=f"ST-00{i}") for i, (ln, fn, mn, g) in enumerate(names, start=1)]
    aziz, dilnoza, sardor, madina, otabek = st[:5]
    with at(25):
        MentorAssignment.objects.get_or_create(mentor=mentor, group=g1, is_active=True, defaults={"assigned_by": admin})
        MentorAssignment.objects.get_or_create(mentor=mentor2, group=g2, is_active=True,
                                               defaults={"assigned_by": admin})

    q = Competency.objects.get(code="questioning")
    with at(20):
        a1 = Assignment.objects.create(
            title="Savol-javob metodi asosida dars ishlanmasi va dars videosi",
            description="Boshlang‘ich sinf uchun 45 daqiqalik dars ishlanmasini tayyorlang va darsni videoga yozib oling. "
                        "Dars davomida barcha o‘quvchilarni savol-javobga jalb qiling.",
            instructions="1. Dars maqsadi va kutilgan natijalarni yozing.\n2. Kamida 3 darajadagi savollar tayyorlang.\n"
                         "3. Darsni videoga yozing (10–15 daqiqalik parcha).\n4. Refleksiya savollariga javob bering.",
            subject=subj, competency=q, start_date=BASE - timedelta(days=20), due_date=BASE + timedelta(days=10),
            created_by=mentor)
        a1.groups.add(g1)
        sync_targets(a1, [g1], [])
    with at(1):
        a2 = Assignment.objects.create(
            title="Interfaol metodlar asosida dars loyihasi",
            description="«Aqliy hujum», «Klaster» yoki juftlikda ishlash kabi interfaol metodlardan foydalangan holda "
                        "dars loyihasini tayyorlang.",
            instructions="1. Kamida ikkita interfaol metod tanlang.\n2. Har bir bosqichga vaqt belgilang.\n"
                         "3. Dars loyihasi va dars videosini yuklang.",
            subject=subj2, competency=Competency.objects.get(code="communication"),
            start_date=BASE - timedelta(days=1), due_date=BASE + timedelta(days=14), created_by=mentor)
        a2.groups.add(g1)
        sync_targets(a2, [g1], [])

    # --- Aziz: to'liq rivojlanish sikli (Gibbs -> qayta ishlash -> Kolb -> tasdiqlandi) ---
    with at(14):
        create_baseline(req(mentor), aziz, goal=None, overall_comment="Birinchi kuzatilgan dars asosida.",
                        details=details([(11, "", "Dars bosqichlariga vaqt belgilanmagan", "Har bosqichga vaqt ajrating"),
                                         (12, "", "", ""),
                                         (7, "", "Savollar asosan yopiq", "Ochiq va fikrlashga undaydigan savollar qo‘shing"),
                                         (10, "", "", ""),
                                         (8, "", "Refleksiya qisqa va yuzaki", "Fikrlaringizni dalil bilan asoslang")]))
    with at(13):
        goal = Goal.objects.create(
            student=aziz, title="Dars davomida barcha o‘quvchilarni savol-javobga jalb qilish", competency=q,
            start_date=(BASE - timedelta(days=13)).date(), target_date=(BASE + timedelta(days=40)).date(),
            status=Goal.Status.IN_PROGRESS,
            expected_outcome="Har bir darsda o‘quvchilarning kamida 80 foizi savol-javobda qatnashadi.")
        Goal.objects.create(
            student=aziz, title="Dars bosqichlarini vaqt bo‘yicha aniq rejalashtirish",
            competency=Competency.objects.get(code="planning"),
            start_date=(BASE - timedelta(days=13)).date(), target_date=(BASE + timedelta(days=60)).date(),
            expected_outcome="Har bir dars ishlanmasida bosqichlar va vaqt jadvali bo‘ladi.")
    p = work(aziz, a1, goal, "Savol-javob darsi: «Tabiat»", "3-sinf, tabiatshunoslik", "gibbs", GIBBS_AZIZ, 11)
    with at(9):
        assess_version(req(mentor), p.latest_version, decision=Assessment.Decision.REVISION,
                       overall_comment="Yaxshi boshlanish. Savollar turini ko‘paytiring.",
                       details=details([(14, "", "", "Vaqt rejasini jadval ko‘rinishida bering"), (14, "", "", ""),
                                        (10, "", "Kutish vaqti 2 soniyadan kam", "Savoldan keyin 5–7 soniya kuting"),
                                        (13, "", "", ""), (12, "", "", "Har bir fikrni dalil bilan asoslang")]))
    with at(5):
        up = UploadForm(data={"note": "Ochiq savollar va juftlikda muhokama qo‘shildi."},
                        files=MultiValueDict({"files": [pdf("dars_ishlanmasi_v2.pdf")]}))
        assert up.is_valid(), up.errors
        p.refresh_from_db()
        v2 = upload_files(req(aziz), p, up.cleaned_data["files"], up.cleaned_data["note"])
    with at(5, -2):
        kolb = list(rs.active_questions("kolb"))
        r = rs.save_draft(req(aziz), v2, kolb, {x.pk: a for x, a in zip(kolb, KOLB_AZIZ)}, framework="kolb")
        rs.submit(req(aziz), r, kolb)
    with at(3):
        v2.refresh_from_db()
        assess_version(req(mentor), v2, decision=Assessment.Decision.APPROVED,
                       overall_comment="Aniq o‘sish ko‘rinmoqda. Ish tasdiqlandi.",
                       details=details([(17, "", "", ""), (16, "", "", ""),
                                        (17, "", "", "Bu usulni boshqa fanlarda ham qo‘llang"),
                                        (16, "", "", ""), (16, "", "", "")]))
        MentorFeedback.objects.create(portfolio=p, version=v2, mentor=mentor,
                                      text="Ajoyib! Juftlikda muhokama usuli juda yaxshi natija berdi.")

    # --- Dilnoza: ish yuborilgan, tekshirish kutilmoqda ---
    with at(12):
        create_baseline(req(mentor), dilnoza, goal=None, overall_comment="Kuzatilgan dars asosida.",
                        details=details([(13, "", "", ""), (12, "", "", ""), (9, "", "", ""), (12, "", "", ""),
                                         (10, "", "", "")]))
    work(dilnoza, a1, None, "Savol-javob darsi: «Ona tili»", "4-sinf, ona tili", "gibbs", GIBBS_DILNOZA, 2)

    # --- Sardor: tasdiqlangan ish (Kolb) ---
    with at(12):
        create_baseline(req(mentor), sardor, goal=None, overall_comment="Kuzatilgan dars asosida.",
                        details=details([(12, "", "", ""), (13, "", "", ""), (11, "", "", ""), (13, "", "", ""),
                                         (11, "", "", "")]))
    ps = work(sardor, a1, None, "O‘yin va savol-javob: matematika", "2-sinf, matematika", "kolb", KOLB_SARDOR, 8)
    with at(6):
        assess_version(req(mentor), ps.latest_version, decision=Assessment.Decision.APPROVED,
                       overall_comment="Ijodiy yondashuv. Ish tasdiqlandi.",
                       details=details([(16, "", "", ""), (17, "", "", ""), (18, "", "", ""), (17, "", "", ""),
                                        (15, "", "", "")]))

    # --- Madina: qayta ishlashga qaytarilgan ---
    pm = work(madina, a1, None, "«Atrofimizdagi olam» darsi", "3-sinf", "gibbs", GIBBS_MADINA, 6)
    with at(4):
        assess_version(req(mentor), pm.latest_version, decision=Assessment.Decision.REVISION,
                       overall_comment="Savollar sonini ko‘paytiring va o‘quvchilarga ko‘proq so‘z bering.",
                       details=details([(13, "", "", ""), (12, "", "", ""), (8, "", "Savollar kam", "Har bosqichda savol bering"),
                                        (11, "", "", ""), (12, "", "", "")]))

    # --- Otabek: topshiriqni qabul qilgan ---
    AssignmentTarget.objects.filter(assignment=a1, student=otabek).update(status="accepted")
    print("tayyor:", User.objects.count(), "foydalanuvchi,", Assessment.objects.count(), "baho", file=sys.stderr)


if __name__ == "__main__":
    main()
