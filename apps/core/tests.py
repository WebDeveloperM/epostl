"""Platformaning asosiy testlari: sahifalar, ruxsatlar (RBAC), fayl xavfsizligi, to‘liq rivojlanish sikli."""
import io
import os
import shutil
import tempfile
from datetime import timedelta

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import MentorAssignment, Role, User
from apps.analytics.services import competency_comparison
from apps.assessments.models import Assessment
from apps.assignments.models import Assignment, AssignmentTarget
from apps.competencies.models import AssessmentCriterion
from apps.core.files import validate_uploaded_file
from apps.goals.models import Goal
from apps.organization.models import Faculty
from apps.portfolios.models import Portfolio, PortfolioFile
from apps.reflections.models import Reflection, ReflectionQuestion

PDF = (b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n")
MEDIA = tempfile.mkdtemp(prefix="portfolio-test-media-")
FAST_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


def pdf(name="ish.pdf"):
    return SimpleUploadedFile(name, PDF, content_type="application/pdf")


@override_settings(MEDIA_ROOT=MEDIA, PASSWORD_HASHERS=FAST_HASHERS)
class PlatformTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", force=True, stdout=io.StringIO())
        cls.admin = User.objects.get(username="admin")
        cls.mentor = User.objects.get(username="ustoz")
        cls.s1 = User.objects.get(username="talaba1")
        cls.s2 = User.objects.get(username="talaba2")
        cls.portfolio = Portfolio.objects.get(student=cls.s1)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        cache.clear()


class PagesRenderTests(PlatformTestCase):
    """Har bir rol uchun asosiy sahifalar xatosiz ochilishi."""

    def assert_ok(self, user, urls):
        self.client.force_login(user)
        for url in urls:
            with self.subTest(user=user.username, url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200, f"{url} -> {response.status_code}")

    def test_student_pages(self):
        p = self.portfolio
        v = p.versions.order_by("version_number").first()
        goal = Goal.objects.filter(student=self.s1).first()
        assignment = Assignment.objects.first()
        reflection = Reflection.objects.filter(student=self.s1).first()
        assessment = Assessment.objects.filter(student=self.s1).first()
        self.assert_ok(self.s1, [
            reverse("dashboard"), reverse("goals:list"), reverse("goals:create"),
            reverse("goals:detail", args=[goal.pk]), reverse("goals:update", args=[goal.pk]),
            reverse("assignments:list"), reverse("assignments:list") + "?status=overdue",
            reverse("assignments:detail", args=[assignment.pk]),
            reverse("portfolios:list"), reverse("portfolios:create"),
            reverse("portfolios:detail", args=[p.pk]), reverse("portfolios:detail", args=[p.pk]) + "?v=1",
            reverse("portfolios:update", args=[p.pk]), reverse("portfolios:upload", args=[p.pk]),
            reverse("reflections:list"), reverse("reflections:detail", args=[reflection.pk]),
            reverse("assessments:list"), reverse("assessments:detail", args=[assessment.pk]),
            reverse("analytics:index"), reverse("notifications:list"),
            reverse("accounts:profile"), reverse("accounts:password_change"),
        ])
        # yangi talaba (ma’lumotsiz) dashboardi
        self.assert_ok(self.s2, [reverse("dashboard"), reverse("analytics:index"),
                                 reverse("portfolios:create") + f"?assignment={assignment.pk}"])
        # birinchi versiya fayli
        f = PortfolioFile.objects.filter(version=v).first()
        self.client.force_login(self.s1)
        self.assertEqual(self.client.get(reverse("portfolios:file", args=[f.pk])).status_code, 200)

    def test_mentor_pages(self):
        p = self.portfolio
        latest = p.latest_version
        assignment = Assignment.objects.first()
        self.assert_ok(self.mentor, [
            reverse("dashboard"), reverse("analytics:students"),
            reverse("analytics:student_detail", args=[self.s1.pk]),
            reverse("analytics:student_detail", args=[self.s2.pk]),
            reverse("assignments:list"), reverse("assignments:create"),
            reverse("assignments:create") + f"?student={self.s2.pk}",
            reverse("assignments:detail", args=[assignment.pk]),
            reverse("assignments:update", args=[assignment.pk]),
            reverse("assessments:queue"), reverse("assessments:list"),
            reverse("assessments:assess", args=[latest.pk]),
            reverse("assessments:baseline", args=[self.s2.pk]),
            reverse("portfolios:list"), reverse("portfolios:detail", args=[p.pk]),
            reverse("reflections:list"), reverse("reflections:list") + "?filter=new",
            reverse("goals:list"), reverse("notifications:list"), reverse("accounts:profile"),
        ])

    def test_admin_pages(self):
        crud = ["organization:faculty", "organization:department", "organization:direction",
                "organization:group", "subjects:subject", "competencies:competency",
                "competencies:criterion", "reflections:question"]
        urls = [reverse("dashboard"), reverse("analytics:index"), reverse("analytics:students"),
                reverse("accounts:user_list"), reverse("accounts:user_list") + "?role=3&status=active&q=a",
                reverse("accounts:user_create"), reverse("accounts:user_update", args=[self.s1.pk]),
                reverse("accounts:user_update", args=[self.mentor.pk]),
                reverse("accounts:user_import"), reverse("accounts:mentor_assignment_list"),
                reverse("accounts:mentor_assignment_create"), reverse("audit:list"),
                reverse("audit:list") + "?action=login&from=2020-01-01&to=2030-01-01",
                reverse("core:settings"), reverse("portfolios:list"), reverse("assignments:list"),
                reverse("portfolios:detail", args=[self.portfolio.pk])]
        for name in crud:
            urls += [reverse(f"{name}_list"), reverse(f"{name}_create")]
        faculty_pk = Faculty.objects.values_list("pk", flat=True).first()
        urls.append(reverse("organization:faculty_update", args=[faculty_pk]))
        urls.append(reverse("organization:faculty_delete", args=[faculty_pk]))
        self.assert_ok(self.admin, urls)
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("accounts:user_import_template"))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.content.startswith(b"PK"))

    def test_anonymous_redirects_to_login(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])
        self.assertEqual(self.client.get(reverse("accounts:login")).status_code, 200)


class AccessControlTests(PlatformTestCase):
    def test_student_cannot_see_other_students_data(self):
        self.client.force_login(self.s2)
        p = self.portfolio
        f = PortfolioFile.objects.filter(version__portfolio=p).first()
        a = Assessment.objects.filter(student=self.s1).first()
        r = Reflection.objects.filter(student=self.s1).first()
        g = Goal.objects.filter(student=self.s1).first()
        for url in [reverse("portfolios:detail", args=[p.pk]), reverse("portfolios:file", args=[f.pk]),
                    reverse("assessments:detail", args=[a.pk]), reverse("reflections:detail", args=[r.pk]),
                    reverse("goals:detail", args=[g.pk]), reverse("portfolios:upload", args=[p.pk]),
                    reverse("reflections:edit", args=[p.latest_version.pk])]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)
        # ro‘yxatlarda ham ko‘rinmaydi
        self.assertNotContains(self.client.get(reverse("portfolios:list")), p.title)

    def test_role_restrictions(self):
        self.client.force_login(self.s1)
        for url in [reverse("accounts:user_list"), reverse("assignments:create"), reverse("assessments:queue"),
                    reverse("audit:list"), reverse("core:settings"), reverse("organization:faculty_list"),
                    reverse("analytics:students")]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.mentor)
        for url in [reverse("accounts:user_list"), reverse("audit:list"), reverse("goals:create")]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_unassigned_mentor_cannot_assess_or_view(self):
        other = User.objects.create_user("ustoz2", password="x", role=Role.objects.get(code="mentor"))
        self.client.force_login(other)
        latest = self.portfolio.latest_version
        self.assertEqual(self.client.get(reverse("assessments:assess", args=[latest.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse("portfolios:detail", args=[self.portfolio.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("analytics:student_detail", args=[self.s1.pk])).status_code, 404)

    def test_blocked_user_cannot_login(self):
        self.s2.is_active = False
        self.s2.save()
        ok = self.client.login(username="talaba2", password="Talaba12345!")
        self.assertFalse(ok)

    def test_login_throttling(self):
        url = reverse("accounts:login")
        for _i in range(5):
            self.client.post(url, {"username": "talaba3", "password": "wrong"})
        response = self.client.post(url, {"username": "talaba3", "password": "Talaba12345!"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Too many wrong tries")

    def test_force_password_change(self):
        self.s2.must_change_password = True
        self.s2.save()
        self.client.force_login(self.s2)
        response = self.client.get(reverse("dashboard"))
        self.assertRedirects(response, reverse("accounts:password_change"))


class FileSecurityTests(PlatformTestCase):
    def test_valid_pdf_accepted(self):
        info = validate_uploaded_file(pdf())
        self.assertEqual(info.category, "document")
        self.assertEqual(info.mime_type, "application/pdf")

    def test_disguised_executable_rejected(self):
        fake = SimpleUploadedFile("dars.pdf", b"MZ\x90\x00" + b"\x00" * 200, content_type="application/pdf")
        with self.assertRaises(ValidationError):
            validate_uploaded_file(fake)

    def test_forbidden_extension_rejected(self):
        with self.assertRaises(ValidationError):
            validate_uploaded_file(SimpleUploadedFile("skript.html", b"<script>alert(1)</script>"))

    @override_settings(PROTECTED_MEDIA_USE_X_ACCEL=False)
    def test_range_request_for_media(self):
        self.client.force_login(self.s1)
        f = PortfolioFile.objects.filter(version__portfolio=self.portfolio).first()
        content = f.file.open("rb").read()
        f.file.close()
        response = self.client.get(reverse("portfolios:file", args=[f.pk]), HTTP_RANGE="bytes=0-9")
        self.assertEqual(response.status_code, 206)
        self.assertEqual(b"".join(response.streaming_content), content[:10])
        self.assertEqual(response["Content-Range"], f"bytes 0-9/{len(content)}")
        self.assertEqual(response["Accept-Ranges"], "bytes")

    def test_media_url_not_public(self):
        f = PortfolioFile.objects.filter(version__portfolio=self.portfolio).first()
        self.assertEqual(self.client.get("/media/" + f.file.name).status_code, 404)


class DevelopmentCycleTests(PlatformTestCase):
    def test_versions_are_preserved(self):
        versions = list(self.portfolio.versions.order_by("version_number"))
        self.assertEqual([v.version_number for v in versions], [1, 2])
        self.assertTrue(all(v.files.exists() for v in versions))
        self.assertTrue(all(hasattr(v, "assessment") for v in versions))
        self.assertEqual(self.portfolio.status, Portfolio.Status.APPROVED)

    def test_initial_vs_latest_comparison(self):
        cmp = competency_comparison(self.s1)
        row = next(r for r in cmp["rows"] if r["competency"].code == "questioning")
        self.assertEqual(row["initial"], 35.0)  # boshlang‘ich: 7/20
        self.assertEqual(row["latest"], 85.0)   # oxirgi: 17/20
        self.assertGreater(row["delta"], 0)

    def test_full_cycle_over_http(self):
        """Ustoz topshiriq beradi → talaba yuklaydi → refleksiya → qayta ishlash → v2 → tasdiqlash."""
        s2 = self.s2
        group = s2.group
        # 1. Ustoz topshiriq beradi (guruhga)
        self.client.force_login(self.mentor)
        now = timezone.localtime()
        response = self.client.post(reverse("assignments:create"), {
            "title": "Muloqot ko‘nikmasi bo‘yicha dars", "description": "Tavsif",
            "start_date": now.strftime("%Y-%m-%dT%H:%M"),
            "due_date": (now + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M"),
            "groups": [group.pk], "is_active": "on",
            "attachments": [pdf("yoriqnoma.pdf")],
        })
        self.assertEqual(response.status_code, 302, getattr(response, "context", None) and response.context["form"].errors)
        assignment = Assignment.objects.get(title="Muloqot ko‘nikmasi bo‘yicha dars")
        target = AssignmentTarget.objects.get(assignment=assignment, student=s2)
        self.assertEqual(target.status, AssignmentTarget.Status.NEW)
        self.assertTrue(s2.notifications.filter(type="assignment_new").exists())

        # 2. Talaba qabul qiladi va dars rejasini yuklaydi
        self.client.force_login(s2)
        self.client.post(reverse("assignments:accept", args=[assignment.pk]))
        target.refresh_from_db()
        self.assertEqual(target.status, AssignmentTarget.Status.ACCEPTED)
        response = self.client.post(reverse("portfolios:create"), {
            "title": "Dars rejasi", "assignment": assignment.pk, "material_type": "lesson_plan",
            "files": [pdf("reja.pdf")],
        })
        self.assertEqual(response.status_code, 302)
        work = Portfolio.objects.get(student=s2, assignment=assignment)
        v1 = work.latest_version

        # 3. Refleksiya: qoralama → yuborish
        q = {f"q_{x.pk}": f"Javob {x.pk}" for x in ReflectionQuestion.objects.filter(is_active=True)}
        self.client.post(reverse("reflections:edit", args=[v1.pk]), {**q, "framework": "gibbs", "action": "draft"})
        self.assertEqual(Reflection.objects.get(portfolio_version=v1).status, Reflection.Status.DRAFT)
        self.assertEqual(Reflection.objects.get(portfolio_version=v1).framework, "gibbs")
        self.client.post(reverse("reflections:edit", args=[v1.pk]), {**q, "action": "submit"})
        work.refresh_from_db()
        self.assertEqual(work.status, Portfolio.Status.SUBMITTED)
        self.assertTrue(self.mentor.notifications.filter(type="work_submitted").exists())

        # 4. Ustoz baholaydi va qayta ishlashga qaytaradi
        self.client.force_login(self.mentor)
        criteria = AssessmentCriterion.objects.filter(is_active=True)
        scores = {f"score_{c.pk}": 10 for c in criteria}
        response = self.client.post(reverse("assessments:assess", args=[v1.pk]),
                                    {**scores, "decision": "revision", "overall_comment": "Qayta ishlang"})
        self.assertEqual(response.status_code, 302)
        work.refresh_from_db()
        self.assertEqual(work.status, Portfolio.Status.REVISION)
        target.refresh_from_db()
        self.assertEqual(target.status, AssignmentTarget.Status.REVISION)
        # ball maksimaldan oshsa — rad etiladi
        bad = self.client.post(reverse("assessments:assess", args=[v1.pk]),
                               {**scores, f"score_{criteria[0].pk}": 99, "decision": "approved"})
        self.assertEqual(bad.status_code, 200)

        # 5. Talaba yangi versiya yuklaydi — v1 o‘chmaydi
        self.client.force_login(s2)
        self.client.post(reverse("portfolios:upload", args=[work.pk]), {"files": [pdf("reja_v2.pdf")], "note": "Tuzatildi"})
        work.refresh_from_db()
        self.assertEqual(work.current_version, 2)
        self.assertTrue(PortfolioFile.objects.filter(version=v1).exists())
        v2 = work.latest_version
        # ikkinchi ish boshqa model (Kolb) bilan tahlil qilinadi
        response = self.client.post(reverse("reflections:edit", args=[v2.pk]),
                                    {**q, "framework": "kolb", "action": "submit"}, follow=True)
        self.assertEqual(Reflection.objects.get(portfolio_version=v2).framework, "kolb")
        work.refresh_from_db()
        self.assertEqual(work.status, Portfolio.Status.SUBMITTED, [str(m) for m in response.context["messages"]])

        # 6. Ustoz tasdiqlaydi; natijalar taqqoslanadi
        self.client.force_login(self.mentor)
        self.client.post(reverse("assessments:assess", args=[v2.pk]),
                         {**{f"score_{c.pk}": 16 for c in criteria}, "decision": "approved"})
        work.refresh_from_db()
        target.refresh_from_db()
        self.assertEqual(work.status, Portfolio.Status.APPROVED)
        self.assertEqual(target.status, AssignmentTarget.Status.APPROVED)
        cmp = competency_comparison(s2)
        self.assertTrue(all(r["latest"] > r["initial"] for r in cmp["rows"] if r["initial"] is not None))

    def test_new_group_member_receives_group_assignment(self):
        assignment = Assignment.objects.first()
        newcomer = User.objects.create_user("talaba9", password="x", role=Role.objects.get(code="student"))
        newcomer.group = assignment.groups.first()
        newcomer.save()
        self.assertTrue(AssignmentTarget.objects.filter(assignment=assignment, student=newcomer).exists())


class ImportTests(PlatformTestCase):
    def test_excel_import_all_or_nothing(self):
        from openpyxl import Workbook

        def workbook(rows):
            wb = Workbook()
            ws = wb.active
            ws.append(["Familiya", "Ism", "Otasining ismi", "Login", "Parol", "Email", "Telefon", "Rol",
                       "Guruh", "Kafedra", "ID raqam"])
            for r in rows:
                ws.append(r)
            buf = io.BytesIO()
            wb.save(buf)
            return SimpleUploadedFile("users.xlsx", buf.getvalue())

        self.client.force_login(self.admin)
        url = reverse("accounts:user_import")
        good = ["Aliyev", "Vali", "", "vali.aliyev", "", "", "", "talaba", "BT-21", "", "ST-900"]
        bad = ["Xato", "Qator", "", "talaba1", "", "", "", "talaba", "YOQ-99", "", ""]
        self.client.post(url, {"file": workbook([good, bad])})
        self.assertFalse(User.objects.filter(username="vali.aliyev").exists())  # hammasi yoki hech biri

        response = self.client.post(url, {"file": workbook([good, ["Saidov", "Anvar", "", "a.saidov", "", "", "",
                                                                    "ustoz", "", "Teaching and Psychology Department",
                                                                    "EMP-77"]])})
        self.assertEqual(response.status_code, 200)
        vali = User.objects.get(username="vali.aliyev")
        self.assertTrue(vali.is_student and vali.must_change_password)
        self.assertEqual(vali.group.name, "BT-21")
        self.assertTrue(User.objects.get(username="a.saidov").is_mentor)
        # guruh topshirig‘i ham avtomatik biriktirildi
        self.assertTrue(AssignmentTarget.objects.filter(student=vali).exists())

    def test_mentor_assignment_constraint(self):
        from django.db import IntegrityError, transaction

        with self.assertRaises(IntegrityError), transaction.atomic():
            MentorAssignment.objects.create(mentor=self.mentor, student=self.s1, group=self.s1.group)


class ReflectionDraftCase(PlatformTestCase):
    """Talaba2 ishi (refleksiyasiz) — refleksiya testlari uchun umumiy tayyorlov."""


    def setUp(self):
        super().setUp()
        self.assignment = Assignment.objects.first()
        self.client.force_login(self.s2)
        self.client.post(reverse("assignments:accept", args=[self.assignment.pk]))
        self.client.post(reverse("portfolios:create"), {
            "title": "Model sinovi", "assignment": self.assignment.pk, "material_type": "lesson_plan",
            "files": [pdf("model.pdf")]})
        self.version = Portfolio.objects.get(student=self.s2, title="Model sinovi").latest_version
        self.url = reverse("reflections:edit", args=[self.version.pk])

    def answers(self, framework, **extra):
        data = {f"q_{q.pk}": f"Javob {q.stage or q.order}" for q in
                ReflectionQuestion.objects.filter(is_active=True, framework=framework)}
        return {**data, "framework": framework, **extra}


class ReflectionModelTests(ReflectionDraftCase):
    """Refleksiya modellari: Gibbs (6 bosqich), Kolb (4 bosqich) va qisqa refleksiya."""

    def test_questions_are_seeded_for_each_model(self):
        from apps.reflections.frameworks import FRAMEWORKS

        for code, count in (("gibbs", 6), ("kolb", 4), ("simple", 5)):
            qs = ReflectionQuestion.objects.filter(framework=code, is_active=True)
            info = FRAMEWORKS[code]
            self.assertEqual(qs.count(), count, code)
            self.assertEqual(len(info.stages), {"gibbs": 6, "kolb": 4, "simple": 0}[code])
            # har bir bosqichga aynan bitta savol; kodlar modelga mos
            self.assertEqual([q.stage for q in qs], info.stage_codes if info.stages else [""] * count)

    def test_student_must_choose_a_model_first(self):
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, "student/reflections/choose.html")
        self.assertContains(response, "Gibbs Reflective Cycle")
        self.assertContains(response, "Kolb")
        # noma’lum yoki yashirin model tanlovi e’tiborga olinmaydi
        self.assertTemplateUsed(self.client.get(self.url + "?model=bogus"), "student/reflections/choose.html")
        self.assertTemplateUsed(self.client.get(self.url + "?model=simple"), "student/reflections/choose.html")

    def test_form_groups_questions_by_stage(self):
        response = self.client.get(self.url + "?model=gibbs")
        self.assertTemplateUsed(response, "student/reflections/form.html")
        sections = response.context["form"].sections()
        self.assertEqual([s["stage"].code for s in sections],
                         ["description", "feelings", "evaluation", "analysis", "conclusion", "action_plan"])
        self.assertEqual(len(response.context["form"].questions), 6)
        self.assertContains(response, 'name="framework" value="gibbs"')
        kolb = self.client.get(self.url + "?model=kolb")
        self.assertEqual(len(kolb.context["form"].questions), 4)
        self.assertEqual(kolb.context["progress"], {"done": 0, "total": 4, "percent": 0})

    def test_edit_form_cannot_switch_the_model(self):
        self.client.post(self.url, self.answers("kolb", action="draft"))
        reflection = Reflection.objects.get(portfolio_version=self.version)
        self.assertEqual(reflection.framework, "kolb")
        self.assertEqual(reflection.answers.count(), 4)
        self.assertTrue(all(a.stage for a in reflection.answers.all()))
        # keyinchalik so‘rovda boshqa model yuborilsa ham o‘zgarmaydi
        self.client.post(self.url, {**self.answers("kolb"), "framework": "gibbs", "action": "draft"})
        reflection.refresh_from_db()
        self.assertEqual(reflection.framework, "kolb")
        self.assertEqual(reflection.answers.count(), 4)
        response = self.client.get(self.url + "?model=gibbs")
        self.assertEqual(response.context["framework"].code, "kolb")
        self.assertEqual(response.context["progress"]["done"], 4)

    def test_required_questions_of_the_chosen_model_are_needed_to_submit(self):
        data = self.answers("gibbs")
        data[next(k for k in data if k.startswith("q_"))] = ""  # bitta majburiy savol bo‘sh
        self.client.post(self.url, {**data, "action": "submit"})
        self.assertEqual(Reflection.objects.get(portfolio_version=self.version).status, Reflection.Status.DRAFT)
        self.client.post(self.url, {**self.answers("gibbs"), "action": "submit"})
        self.assertEqual(Reflection.objects.get(portfolio_version=self.version).status,
                         Reflection.Status.SUBMITTED)

    def test_answers_are_shown_in_stage_order(self):
        self.client.post(self.url, self.answers("gibbs", action="submit"))
        reflection = Reflection.objects.get(portfolio_version=self.version)
        groups = reflection.grouped_answers()
        self.assertEqual([g[0].code for g in groups],
                         ["description", "feelings", "evaluation", "analysis", "conclusion", "action_plan"])
        self.assertEqual([a.number for _s, _i, items in groups for a in items], [1, 2, 3, 4, 5, 6])
        for user in (self.s2, self.mentor):
            self.client.force_login(user)
            response = self.client.get(reverse("reflections:detail", args=[reflection.pk]))
            self.assertContains(response, "What happened")
            self.assertContains(response, "My next steps")
            self.assertContains(response, "Gibbs Reflective Cycle")

    def test_answers_without_stages_still_show(self):
        simple = Reflection.objects.create(student=self.s2, portfolio_version=self.version, framework="simple")
        q = ReflectionQuestion.objects.filter(framework="simple").first()
        simple.answers.create(question=q, question_text=q.text, answer="Eski javob")
        ((stage, index, items),) = simple.grouped_answers()
        self.assertIsNone(stage)
        self.assertEqual((index, len(items)), (0, 1))
        self.client.force_login(self.mentor)
        self.assertContains(self.client.get(reverse("reflections:detail", args=[simple.pk])), "Eski javob")

    def test_demo_shows_two_models_in_the_growth_example(self):
        refs = Reflection.objects.filter(student=self.s1).order_by("portfolio_version__version_number")
        self.assertEqual([r.framework for r in refs], ["gibbs", "kolb"])
        self.assertEqual([len(r.grouped_answers()) for r in refs], [6, 4])

    def test_admin_question_form_checks_the_stage(self):
        from apps.reflections.forms import ReflectionQuestionForm

        def form(**fields):
            data = {"framework": "gibbs", "stage": "analysis", "text": "Savol?", "order": 1,
                    "is_required": "on", "is_active": "on", **fields}
            return ReflectionQuestionForm(data)

        self.assertTrue(form().is_valid())
        self.assertFalse(form(stage="").is_valid())  # Gibbs uchun bosqich kerak
        self.assertFalse(form(stage="active_experimentation").is_valid())  # Kolb bosqichi Gibbs'ga mos emas
        self.assertTrue(form(framework="simple", stage="").is_valid())  # qisqa refleksiyada bosqich yo‘q
        self.assertFalse(form(framework="simple", stage="analysis").is_valid())

    def test_admin_can_open_question_pages(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("reflections:question_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Gibbs Reflective Cycle")
        self.assertEqual(self.client.get(reverse("reflections:question_create")).status_code, 200)

    def test_model_pages_are_translated(self):
        self.assertContains(self.client.get(self.url), "Choose a self-review model")
        self.client.post(reverse("set_language"), {"language": "uz", "next": "/"})
        response = self.client.get(self.url)
        self.assertContains(response, "Refleksiya modelini tanlang")
        self.assertContains(response, "Gibbs refleksiya sikli")
        form = self.client.get(self.url + "?model=kolb")
        self.assertContains(form, "Aniq tajriba")
        self.assertNotContains(form, "What I did")


class ReflectionModelChangeTests(ReflectionDraftCase):
    """Modelni qoralama paytida almashtirish: javoblar mos bosqichlarga ko‘chadi."""

    def change_url(self):
        return reverse("reflections:change_model", args=[self.version.pk])

    def stage_answers(self):
        reflection = Reflection.objects.get(portfolio_version=self.version)
        return reflection, {a.stage: a.answer for a in reflection.answers.all()}

    def test_gibbs_answers_move_to_the_matching_kolb_stages(self):
        gibbs = ReflectionQuestion.objects.filter(framework="gibbs", is_active=True)
        data = {f"q_{q.pk}": f"[{q.stage}]" for q in gibbs}
        self.client.post(self.url, {**data, "framework": "gibbs", "action": "draft"})
        response = self.client.post(self.change_url(), {**data, "target_framework": "kolb"}, follow=True)
        reflection, answers = self.stage_answers()
        self.assertEqual(reflection.framework, "kolb")
        self.assertEqual(set(answers), {"concrete_experience", "reflective_observation",
                                        "abstract_conceptualization", "active_experimentation"})
        self.assertEqual(answers["concrete_experience"], "[description]")
        # ikki bosqich bitta bosqichga tushsa, matnlar ketma-ket birlashadi — hech narsa yo‘qolmaydi
        self.assertEqual(answers["reflective_observation"], "[feelings]\n\n[evaluation]")
        self.assertEqual(answers["abstract_conceptualization"], "[analysis]\n\n[conclusion]")
        self.assertEqual(answers["active_experimentation"], "[action_plan]")
        self.assertEqual(reflection.answers.count(), 4)
        self.assertContains(response, "Change model")
        self.assertEqual(response.context["framework"].code, "kolb")

    def test_kolb_answers_move_back_to_gibbs(self):
        self.client.post(self.url, self.answers("kolb", action="draft"))
        self.client.post(self.change_url(), {**self.answers("kolb"), "target_framework": "gibbs"})
        reflection, answers = self.stage_answers()
        self.assertEqual(reflection.framework, "gibbs")
        self.assertEqual(reflection.answers.count(), 6)
        self.assertTrue(answers["description"] and answers["analysis"] and answers["action_plan"])
        self.assertEqual(answers["feelings"], "")  # Kolb'da mos bosqich yo‘q

    def test_unsaved_edits_are_saved_before_the_change(self):
        self.client.post(self.url, self.answers("gibbs", action="draft"))
        question = ReflectionQuestion.objects.get(framework="gibbs", stage="description")
        edited = {**self.answers("gibbs"), f"q_{question.pk}": "YANGI MATN"}
        self.client.post(self.change_url(), {**edited, "target_framework": "kolb"})
        _reflection, answers = self.stage_answers()
        self.assertEqual(answers["concrete_experience"], "YANGI MATN")

    def test_model_cannot_be_changed_after_sending_or_scoring(self):
        self.client.post(self.url, self.answers("gibbs", action="submit"))
        self.client.post(self.change_url(), {**self.answers("gibbs"), "target_framework": "kolb"})
        self.assertEqual(Reflection.objects.get(portfolio_version=self.version).framework, "gibbs")
        # ustoz baholagan demo refleksiya (talaba1) ham o‘zgarmaydi
        self.client.force_login(self.s1)
        locked = Reflection.objects.get(student=self.s1, framework="gibbs")
        self.client.post(reverse("reflections:change_model", args=[locked.portfolio_version_id]),
                         {"target_framework": "kolb"})
        locked.refresh_from_db()
        self.assertEqual((locked.framework, locked.answers.count()), ("gibbs", 6))

    def test_invalid_or_same_model_is_rejected(self):
        self.client.post(self.url, self.answers("gibbs", action="draft"))
        for target in ("gibbs", "simple", "bogus", ""):
            with self.subTest(target=target):
                self.client.post(self.change_url(), {**self.answers("gibbs"), "target_framework": target})
                self.assertEqual(Reflection.objects.get(portfolio_version=self.version).framework, "gibbs")
                self.assertEqual(Reflection.objects.get(portfolio_version=self.version).answers.count(), 6)

    def test_only_the_owner_can_change_the_model(self):
        self.client.post(self.url, self.answers("gibbs", action="draft"))
        self.client.force_login(self.mentor)
        self.assertEqual(self.client.post(self.change_url(), {"target_framework": "kolb"}).status_code, 403)
        self.client.force_login(self.s1)
        self.assertEqual(self.client.post(self.change_url(), {"target_framework": "kolb"}).status_code, 404)
        self.assertEqual(Reflection.objects.get(portfolio_version=self.version).framework, "gibbs")

    def test_before_the_first_save_the_other_model_just_opens(self):
        response = self.client.post(self.change_url(), {"target_framework": "kolb"})
        self.assertRedirects(response, self.url + "?model=kolb", fetch_redirect_response=False)
        self.assertFalse(Reflection.objects.filter(portfolio_version=self.version).exists())

    def test_form_offers_the_change_only_for_drafts(self):
        self.assertContains(self.client.get(self.url + "?model=gibbs"), "Choose another model")
        self.client.post(self.url, self.answers("gibbs", action="draft"))
        response = self.client.get(self.url)
        self.assertContains(response, "Change model")
        self.assertContains(response, 'name="target_framework" value="kolb"')
        self.assertNotContains(response, 'name="target_framework" value="gibbs"')
        self.client.post(self.url, self.answers("gibbs", action="submit"))
        self.assertNotContains(self.client.get(self.url), "Change model")

    def test_change_logs_an_audit_entry(self):
        from apps.audit.models import AuditLog

        self.client.post(self.url, self.answers("gibbs", action="draft"))
        before = AuditLog.objects.count()
        self.client.post(self.change_url(), {**self.answers("gibbs"), "target_framework": "kolb"})
        self.assertGreater(AuditLog.objects.count(), before)


class KeyInsightsTests(PlatformTestCase):
    """Portfolio sahifasidagi «Asosiy xulosalar» bloki."""

    def test_insights_come_from_the_last_stages_of_each_model(self):
        reflections = Reflection.objects.filter(student=self.s1).order_by("portfolio_version__version_number")
        gibbs, kolb = reflections
        self.assertEqual([i["label"] for i in gibbs.insights()], ["What I learned", "My next steps"])
        self.assertEqual([i["label"] for i in kolb.insights()], ["What it means", "What I will try"])
        self.assertIn("open questions", gibbs.insights()[0]["text"])

    def test_portfolio_page_shows_insights_for_student_and_mentor(self):
        url = reverse("portfolios:detail", args=[self.portfolio.pk])
        for user in (self.s1, self.mentor, self.admin):
            self.client.force_login(user)
            response = self.client.get(url)
            self.assertContains(response, "Main lessons")
            self.assertEqual([i["version"].version_number for i in response.context["insights"]], [1, 2])
            self.assertContains(response, "Gibbs Reflective Cycle")
            self.assertContains(response, "Kolb")
            self.assertContains(response, "wait time")

    def test_no_block_without_a_sent_reflection(self):
        Reflection.objects.filter(student=self.s1).update(status=Reflection.Status.DRAFT)
        self.client.force_login(self.s1)
        response = self.client.get(reverse("portfolios:detail", args=[self.portfolio.pk]))
        self.assertNotContains(response, "Main lessons")
        self.assertEqual(response.context["insights"], [])

    def test_quick_self_review_uses_the_last_answer(self):
        q = list(ReflectionQuestion.objects.filter(framework="simple").order_by("order"))
        r = Reflection.objects.filter(student=self.s1).first()
        r.framework = "simple"
        r.save()
        r.answers.all().delete()
        for i, question in enumerate(q):
            r.answers.create(question=question, question_text=question.text, answer=f"A{i}")
        r = Reflection.objects.get(pk=r.pk)
        self.assertEqual([i["text"] for i in r.insights()], ["A4"])
        self.assertEqual(len(r.grouped_answers()), 1)


class ModelStatsTests(PlatformTestCase):
    """Refleksiya modellari bo‘yicha analitika."""

    def stats(self, **kw):
        from apps.analytics.services import reflection_model_stats

        return reflection_model_stats(**kw)

    def test_demo_has_one_reflection_per_model(self):
        stats = self.stats()
        self.assertEqual([m["info"].code for m in stats], ["gibbs", "kolb"])
        gibbs, kolb = stats
        self.assertEqual((gibbs["reflections"], gibbs["students"], kolb["reflections"]), (1, 1, 1))
        self.assertEqual([len(gibbs["stages"]), len(kolb["stages"])], [6, 4])
        self.assertTrue(gibbs["avg_words"] > 5 and kolb["avg_words"] > 5)
        self.assertEqual((gibbs["scored"], kolb["scored"]), (1, 1))  # ikkalasi ham baholangan
        self.assertTrue(0 < gibbs["avg_score"] < kolb["avg_score"] <= 100)
        self.assertIsNotNone(gibbs["shortest"])
        self.assertEqual(max(r["bar"] for r in gibbs["stages"]), 100)

    def test_drafts_are_not_counted(self):
        Reflection.objects.filter(student=self.s1, framework="kolb").update(status=Reflection.Status.DRAFT)
        self.assertEqual([m["info"].code for m in self.stats()], ["gibbs"])

    def test_scope_limits_the_numbers(self):
        self.assertEqual(self.stats(reflections=Reflection.objects.filter(student=self.s2)), [])
        mine = self.stats(reflections=Reflection.objects.filter(student=self.s1))
        self.assertEqual(len(mine), 2)

    def test_pages_show_the_block(self):
        pages = [(self.admin, reverse("analytics:index")), (self.s1, reverse("analytics:index")),
                 (self.mentor, reverse("analytics:students")),
                 (self.mentor, reverse("analytics:student_detail", args=[self.s1.pk]))]
        for user, url in pages:
            with self.subTest(user=user.username, url=url):
                self.client.force_login(user)
                response = self.client.get(url)
                self.assertContains(response, "Results by self-review model")
                self.assertContains(response, "Gibbs Reflective Cycle")
                self.assertContains(response, "What happened")
        # ma’lumotsiz talabada blok chiqmaydi
        self.client.force_login(self.s2)
        self.assertNotContains(self.client.get(reverse("analytics:index")), "Results by self-review model")

    def test_block_is_translated(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("set_language"), {"language": "uz", "next": "/"})
        response = self.client.get(reverse("analytics:index"))
        self.assertContains(response, "Refleksiya modellari bo‘yicha tahlil")
        self.assertContains(response, "Gibbs refleksiya sikli")
        self.assertNotContains(response, "Results by self-review model")


class MobileLayoutTests(PlatformTestCase):
    """Mobil moslashuv: viewport, jadvallarni kartaga aylantirish, 2 ustunli statistika."""

    def html(self, user, url):
        if user:
            self.client.force_login(user)
        else:
            self.client.logout()
        return self.client.get(url).content.decode()

    def test_every_layout_declares_a_mobile_viewport(self):
        pages = [(None, "/"), (None, reverse("accounts:login")), (self.s1, reverse("dashboard"))]
        for user, url in pages:
            with self.subTest(url=url):
                html = self.html(user, url)
                self.assertIn('name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"', html)
                self.assertIn('name="theme-color"', html)

    def test_list_pages_turn_into_cards_on_phones_but_small_summaries_do_not(self):
        stacked = [
            (self.admin, reverse("accounts:user_list")), (self.admin, reverse("competencies:competency_list")),
            (self.admin, reverse("audit:list")), (self.mentor, reverse("analytics:students")),
            (self.mentor, reverse("assignments:list")), (self.s1, reverse("portfolios:list")),
            (self.s1, reverse("reflections:list")), (self.s1, reverse("assessments:list")),
            (self.s1, reverse("goals:list")), (self.s1, reverse("assignments:list")),
        ]
        for user, url in stacked:
            with self.subTest(url=url):
                self.assertIn("table-stack", self.html(user, url))
        # kichik raqamli jadvallar (taqqoslash) odatdagidek qoladi
        self.assertNotIn("table-stack", self.html(self.s1, reverse("analytics:index")))

    def test_stat_cards_are_two_per_row_on_phones(self):
        for user in (self.s1, self.mentor, self.admin):
            with self.subTest(user=user.username):
                html = self.html(user, reverse("dashboard"))
                self.assertIn('class="col-6 col-xl-3"', html)
                self.assertNotIn('class="col-sm-6 col-xl-3"', html)

    def test_mobile_assets_are_in_place(self):
        from pathlib import Path

        from django.conf import settings

        static = Path(settings.BASE_DIR) / "static"
        css = (static / "css" / "app.css").read_text(encoding="utf-8")
        for needle in ("@media (max-width: 575.98px)", ".table.table-stack", "attr(data-label)", "env(safe-area-inset"):
            self.assertIn(needle, css)
        js = (static / "js" / "app.js").read_text(encoding="utf-8")
        self.assertIn('setAttribute("data-label"', js)
        self.assertIn("Escape", js)  # yon menyu Esc bilan yopiladi
        self.assertIn("labelWidth", (static / "js" / "charts.js").read_text(encoding="utf-8"))

    def test_landing_language_menu_opens_inside_the_screen_on_phones(self):
        """Landing'da til tugmasi chapda turadi; o'ngga tekislangan menyu ekrandan chiqib ketardi."""
        from pathlib import Path

        from django.conf import settings

        css = (Path(settings.BASE_DIR) / "static" / "css" / "landing.css").read_text(encoding="utf-8")
        self.assertIn(".lp-navbar .dropdown-menu.lang-menu { left: 0; right: auto; }", css)
        html = self.html(None, "/")
        self.assertIn("lang-menu", html)
        self.assertIn('lang="uz"', html)
        self.assertIn('lang="en"', html)


class AdminTelegramLinkTests(PlatformTestCase):
    """«Administratorga» — .env dagi ADMIN_TELEGRAM_URL orqali Telegramga olib boradigan havola."""

    LINK = "https://t.me/bnpz_admin"

    def test_value_is_checked_and_normalised(self):
        from apps.core.utils import telegram_url

        for given, expected in [
            ("https://t.me/bnpz_admin", "https://t.me/bnpz_admin"),
            ("  https://t.me/+AbCdEf123  ", "https://t.me/+AbCdEf123"),
            ("@bnpz_admin", "https://t.me/bnpz_admin"),
            ("bnpz_admin", "https://t.me/bnpz_admin"),
            ("t.me/bnpz_admin", "https://t.me/bnpz_admin"),
            ("http://telegram.me/bnpz_admin", "http://telegram.me/bnpz_admin"),
            ("", ""), (None, ""),
            ("javascript:alert(1)", ""),                      # xavfli sxema
            ("https://evil.example/t.me/x", ""),              # Telegram emas
            ("https://t.me.evil.example/x", ""),              # domen o‘xshash, lekin boshqa
            ("ftp://t.me/bnpz_admin", ""),
            ("not a link", ""),
        ]:
            with self.subTest(given=given):
                self.assertEqual(telegram_url(given), expected)

    def test_link_appears_where_users_are_told_to_talk_to_the_admin(self):
        self.client.logout()
        with override_settings(ADMIN_TELEGRAM_URL=self.LINK):
            landing = self.client.get("/").content.decode()
            login = self.client.get(reverse("accounts:login")).content.decode()
        anchor = f'<a class="admin-link" href="{self.LINK}" target="_blank" rel="noopener noreferrer">'
        self.assertEqual(landing.count(anchor), 3)  # savol-javob chetida, parol javobida va footerda
        self.assertEqual(login.count(anchor), 1)
        self.assertIn("Did not find your answer? Please talk to", landing)
        self.assertIn("the admin</a>", landing)
        self.assertIn("If you forgot your password, please talk to", login)

    def test_without_a_setting_or_with_a_bad_one_there_is_no_link(self):
        self.client.logout()
        for value in ("", "javascript:alert(1)", "https://evil.example/"):
            with self.subTest(value=value), override_settings(ADMIN_TELEGRAM_URL=value):
                landing = self.client.get("/").content.decode()
                self.assertNotIn("admin-link", landing)
                self.assertNotIn("javascript:", landing)
                self.assertIn("Please talk to the admin.", landing)  # matn o‘z joyida, havolasiz

    def test_link_text_follows_the_language(self):
        with override_settings(ADMIN_TELEGRAM_URL=self.LINK):
            self.client.post(reverse("set_language"), {"language": "uz", "next": "/"})
            html = self.client.get("/").content.decode()
        self.assertIn("Administratorga</a> murojaat qiling.", html)
        self.assertNotIn("the admin", html)

    def test_env_files_document_the_setting(self):
        from pathlib import Path

        from django.conf import settings

        # .dockerignore ba’zi .env* fayllarni tasvirga kiritmaydi — mavjudlarini tekshiramiz
        found = [Path(settings.BASE_DIR) / name for name in (".env.example", ".env.docker.example")
                 if (Path(settings.BASE_DIR) / name).exists()]
        self.assertTrue(found)
        for path in found:
            self.assertIn("ADMIN_TELEGRAM_URL=", path.read_text(encoding="utf-8"), path.name)


class StaticVersionTests(PlatformTestCase):
    """Statik havolalarga hash qo‘shiladi: nginx 30 kun keshlasa ham yangi CSS/JS darhol ko‘rinadi."""

    def test_static_urls_carry_a_content_hash(self):
        import re

        from django.contrib.staticfiles.storage import staticfiles_storage

        url = staticfiles_storage.url("css/app.css")
        self.assertRegex(url, r"^/static/css/app\.css\?v=[0-9a-f]{10}$")
        self.assertEqual(url, staticfiles_storage.url("css/app.css"))  # barqaror
        self.assertNotEqual(url, staticfiles_storage.url("css/landing.css"))
        self.assertEqual(staticfiles_storage.url("images/yoq-fayl.svg"), "/static/images/yoq-fayl.svg")
        self.assertNotIn("?v=", staticfiles_storage.url("../settings.py"))  # papkadan tashqariga chiqmaydi
        html = self.client.get("/").content.decode()
        for name in ("css/app.css", "css/landing.css", "js/landing.js"):
            self.assertRegex(html, rf"/static/{re.escape(name)}\?v=[0-9a-f]{{10}}")

    def test_hash_changes_when_the_file_changes(self):
        from pathlib import Path

        from django.contrib.staticfiles.storage import staticfiles_storage

        with tempfile.TemporaryDirectory() as root, override_settings(STATIC_ROOT=root):
            probe = Path(root) / "probe.css"
            probe.write_text("a{color:red}", encoding="utf-8")
            first = staticfiles_storage.url("probe.css")
            self.assertRegex(first, r"^/static/probe\.css\?v=[0-9a-f]{10}$")
            probe.write_text("a{color:blue}", encoding="utf-8")  # hajmi bir xil, mazmuni boshqa
            os.utime(probe, (1_000_000_000, 1_000_000_000))  # vaqt belgisi aniq o‘zgargan bo‘lsin (taymer aniqligi)
            self.assertNotEqual(first, staticfiles_storage.url("probe.css"))


class LandingTests(PlatformTestCase):
    """Bosh sahifa (/) — hamma uchun ochiq landing; boshqaruv paneli /dashboard/ da."""

    SECTIONS = ("about", "slides", "cycle", "models", "features", "roles", "faq")

    def text_of(self, response):
        import re

        html = response.content.decode()
        return html, re.sub(r"<[^>]+>", " ", re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S))

    def test_root_is_a_public_landing_page(self):
        self.client.logout()
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "landing.html")
        self.assertEqual(reverse("landing"), "/")
        self.assertEqual(reverse("dashboard"), "/dashboard/")

    def test_page_has_navbar_banner_slider_sections_and_footer(self):
        html, text = self.text_of(self.client.get("/"))
        self.assertIn("<header", html)
        self.assertIn("lp-navbar", html)
        self.assertIn("lp-hero", html)
        self.assertIn('id="lp-carousel"', html)
        self.assertEqual(html.count('class="carousel-item'), 4)
        for anchor in self.SECTIONS:
            with self.subTest(section=anchor):
                self.assertIn(f'id="{anchor}"', html)
                if anchor != "slides":  # slayder menyuda emas — u «Haqida» dan keyin o‘zi ko‘rinadi
                    self.assertIn(f'href="#{anchor}"', html)
        self.assertIn("<footer", html)
        self.assertEqual(html.count('class="accordion-item"'), 6)
        self.assertEqual(html.count("lp-step-num"), 8)
        # kirish tugmalari: navbar, banner, chaqiruv va footer
        self.assertGreaterEqual(html.count(reverse("accounts:login")), 4)
        for words in ("One online place to grow your teaching skills", "How it works", "Two popular self-review models",
                      "Gibbs Reflective Cycle", "Kolb's Experiential Learning Cycle", "Who can sign in?"):
            self.assertIn(words, text.replace("&#x27;", "'"))

    def test_slider_texts_are_not_mixed_up_with_other_pages(self):
        """Katalogda bitta matnga bitta tarjima bor: umumiy so‘zlar (Tahlil, Keyingi) boshqa ma’no bilan to‘qnashmasin."""
        import re

        html = self.client.get("/").content.decode()
        kickers = re.findall(r'<span class="lp-kicker">([^<]+)</span>\s*<h3 class="lp-slide-title">', html)
        self.assertEqual(kickers, ["Goals and plans", "Work items", "Self-review", "Reports and results"])
        self.assertIn('<span class="visually-hidden">Next slide</span>', html)
        self.assertIn('<span class="visually-hidden">Previous slide</span>', html)

    def test_every_slide_has_its_own_illustration(self):
        import re
        import xml.etree.ElementTree as ET
        from pathlib import Path

        from django.conf import settings

        html = self.client.get("/").content.decode()
        images = re.findall(r'<img class="lp-art" src="(/static/images/landing/[a-z-]+\.svg)\?v=[0-9a-f]{10}"', html)
        self.assertEqual(len(images), 4)
        self.assertEqual(len(set(images)), 4)  # har bir slaydning rasmi alohida
        self.assertEqual(sorted(i.rsplit("/", 1)[1] for i in images),
                         ["slide-analysis.svg", "slide-goals.svg", "slide-models.svg", "slide-versions.svg"])
        for url in images:
            with self.subTest(image=url):
                svg = Path(settings.BASE_DIR) / "static" / url.removeprefix("/static/")
                root = ET.parse(svg).getroot()  # yaroqli XML
                self.assertTrue(root.tag.endswith("svg"))
                self.assertTrue(root.get("viewBox"))
                self.assertNotIn("<script", svg.read_text(encoding="utf-8"))  # faqat chizma, kod yo‘q

    def test_language_is_english_by_default_and_the_switch_works(self):
        response = self.client.get("/", HTTP_ACCEPT_LANGUAGE="uz")
        self.assertContains(response, "Sign in")
        self.assertContains(response, 'lang="en"')
        self.assertContains(response, 'data-bs-toggle="dropdown"')
        self.assertContains(response, "bootstrap.bundle.min.js")
        self.client.post(reverse("set_language"), {"language": "uz", "next": "/"})
        response = self.client.get("/")
        html, text = self.text_of(response)
        self.assertIn('lang="uz"', html)
        self.assertIn("Qanday ishlaydi", text)
        self.assertIn("Gibbs refleksiya sikli", text)
        self.assertNotIn("How it works", text)
        self.assertNotIn("Sign in", text)

    def test_english_page_has_no_uzbek_leftovers(self):
        import re

        html = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", self.client.get("/").content.decode(), flags=re.S)
        leftovers = [w for w in re.findall(r"[A-Za-z]*[‘’ʻ][A-Za-z]*", html) if w != "O‘zbekcha"]
        self.assertEqual(leftovers, [])

    def test_signed_in_users_get_a_dashboard_button_instead_of_sign_in(self):
        for user in (self.s1, self.mentor, self.admin):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response = self.client.get("/")
                self.assertEqual(response.status_code, 200)  # yo‘naltirilmaydi
                self.assertContains(response, 'href="/dashboard/"')
                self.assertContains(response, "Open my dashboard")
                self.assertNotContains(response, 'href="/accounts/login/"')

    def test_dashboard_needs_login_and_login_leads_there(self):
        self.client.logout()
        response = self.client.get(reverse("dashboard"))
        self.assertRedirects(response, reverse("accounts:login") + "?next=/dashboard/", fetch_redirect_response=False)
        response = self.client.post(reverse("accounts:login"), {"username": "talaba2", "password": "Talaba12345!"})
        self.assertRedirects(response, reverse("dashboard"), fetch_redirect_response=False)

    def test_file_limits_in_the_faq_come_from_system_settings(self):
        from apps.core.models import SystemSettings

        settings_row = SystemSettings.get_solo()
        settings_row.max_upload_size_mb, settings_row.max_video_size_mb = 33, 777
        settings_row.save()
        html = self.client.get("/").content.decode()
        self.assertIn("33 MB", html)
        self.assertIn("777 MB", html)

    def test_login_page_logos_lead_to_the_landing_page(self):
        self.client.logout()
        html = self.client.get(reverse("accounts:login")).content.decode()
        self.assertIn('<a href="/" class="auth-brand', html)  # chap paneldagi logotip
        self.assertIn('<a href="/" class="auth-brand-mobile', html)  # mobil logotip

    def test_sidebar_home_link_is_active_on_the_dashboard(self):
        self.client.force_login(self.s1)
        self.assertIn('class="nav-link active" href="/dashboard/"',
                      self.client.get(reverse("dashboard")).content.decode())
        self.assertNotIn('class="nav-link active" href="/dashboard/"',
                         self.client.get(reverse("goals:list")).content.decode())

    def test_error_page_links_back_to_the_landing_page(self):
        self.client.logout()
        response = self.client.get("/there-is-no-such-page/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, 'href="/"', status_code=404)


class LanguageTests(PlatformTestCase):
    """Asosiy til — ingliz tili; o‘zbek tiliga o‘tish mumkin; tanlov saqlanadi."""

    def test_default_language_is_english_and_browser_header_is_ignored(self):
        response = self.client.get(reverse("accounts:login"), headers={"accept-language": "uz,ru;q=0.8"})
        self.assertContains(response, "Sign in")
        self.assertContains(response, '<html lang="en">')
        self.assertNotContains(response, "Tizimga kirish")

    def test_switching_to_uzbek_keeps_original_texts(self):
        response = self.client.post(reverse("set_language"), {"language": "uz", "next": reverse("accounts:login")})
        self.assertRedirects(response, reverse("accounts:login"), fetch_redirect_response=False)
        self.assertEqual(response.cookies["portfolio_language"].value, "uz")
        page = self.client.get(reverse("accounts:login"))
        self.assertContains(page, "Tizimga kirish")  # katalogda topilmagan matn inglizchaga tushib qolmaydi
        self.assertContains(page, '<html lang="uz">')
        self.assertNotContains(page, "Sign in")

    def test_logged_in_choice_is_saved_to_profile(self):
        self.client.force_login(self.s1)
        self.assertContains(self.client.get(reverse("dashboard")), "Welcome")
        self.client.post(reverse("set_language"), {"language": "uz", "next": "/"})
        self.s1.refresh_from_db()
        self.assertEqual(self.s1.language, "uz")
        self.assertContains(self.client.get(reverse("dashboard")), "Xush kelibsiz")

    def test_saved_language_is_used_on_a_new_browser(self):
        User.objects.filter(pk=self.s1.pk).update(language="uz")
        self.client.force_login(self.s1)  # cookie yo‘q
        self.assertContains(self.client.get(reverse("dashboard")), "Xush kelibsiz")

    def test_language_chosen_on_login_page_is_remembered_for_the_user(self):
        self.client.post(reverse("set_language"), {"language": "uz", "next": "/"})
        self.client.post(reverse("accounts:login"), {"username": "talaba2", "password": "Talaba12345!"})
        self.s2.refresh_from_db()
        self.assertEqual(self.s2.language, "uz")

    def test_invalid_language_and_unsafe_next_are_ignored(self):
        response = self.client.post(reverse("set_language"), {"language": "xx", "next": "https://evil.example/"})
        self.assertRedirects(response, "/", fetch_redirect_response=False)
        self.assertNotIn("portfolio_language", response.cookies)
        self.assertEqual(self.client.get(reverse("set_language")).status_code, 405)

    def test_login_page_loads_the_script_the_switch_needs(self):
        """Dropdown Bootstrap JS siz ochilmaydi (login sahifasi ilgari uni yuklamagan edi)."""
        self.client.logout()
        response = self.client.get(reverse("accounts:login"))
        self.assertContains(response, 'data-bs-toggle="dropdown"')
        self.assertContains(response, "bootstrap.bundle.min.js")

    def test_switch_button_is_in_the_top_bar(self):
        self.client.force_login(self.mentor)
        page = self.client.get(reverse("dashboard"))
        self.assertContains(page, 'name="language" value="uz"')
        self.assertContains(page, 'aria-label="Change language"')
        self.assertContains(page, "Teacher home")

    def test_every_page_is_free_of_uzbek_in_english(self):
        """Ingliz tilida hech bir asosiy sahifada o‘zbekcha qoldiq (‘ ’ belgilari) bo‘lmasligi kerak."""
        import re

        goal = Goal.objects.filter(student=self.s1).first()
        for user, urls in [
            (self.s1, [reverse("dashboard"), reverse("goals:list"), reverse("goals:detail", args=[goal.pk]),
                       reverse("assignments:list"), reverse("portfolios:list"), reverse("reflections:list"),
                       reverse("assessments:list"), reverse("analytics:index"),
                       reverse("portfolios:detail", args=[self.portfolio.pk])]),
            (self.mentor, [reverse("dashboard"), reverse("assignments:list"), reverse("assessments:queue")]),
            (self.admin, [reverse("dashboard"), reverse("accounts:user_list"), reverse("accounts:user_import"),
                          reverse("core:settings"), reverse("audit:list")]),
        ]:
            self.client.force_login(user)
            for url in urls:
                with self.subTest(user=user.username, url=url):
                    html = self.client.get(url).content.decode()
                    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S)
                    text = re.sub(r"<[^>]+>", " ", text)
                    leftovers = re.findall(r"[A-Za-z]*[‘’ʻ][A-Za-z]*", text)
                    leftovers = [w for w in leftovers if w != "O‘zbekcha"]  # til nomi o‘z tilida
                    self.assertEqual(leftovers, [], f"{url}: o‘zbekcha qoldiq {leftovers[:5]}")


class NotificationLanguageTests(PlatformTestCase):
    def test_each_recipient_reads_the_notification_in_their_own_language(self):
        from django.utils.translation import gettext as _

        from apps.notifications.models import Notification
        from apps.notifications.services import notify

        User.objects.filter(pk=self.s2.pk).update(language="uz")
        self.s2.refresh_from_db()
        notify([self.s1, self.s2], type=Notification.Type.ASSIGNMENT_NEW,
               title=lambda: _("Yangi topshiriq: %(t)s") % {"t": "X"})
        self.assertEqual(Notification.objects.get(recipient=self.s1, title__endswith="X").title, "New task: X")
        self.assertEqual(Notification.objects.get(recipient=self.s2, title__endswith="X").title, "Yangi topshiriq: X")


class CatalogTests(TestCase):
    """Tarjima kataloglari to‘liq va o‘rinbosarlari to‘g‘ri bo‘lishi kerak."""

    @staticmethod
    def entries(lang):
        import re
        from pathlib import Path

        from django.conf import settings

        text = (Path(settings.BASE_DIR) / "locale" / lang / "LC_MESSAGES" / "django.po").read_text(encoding="utf-8")
        pairs = re.findall(r'^msgid "(.*)"\nmsgstr "(.*)"$', text, flags=re.M)
        return [(i, s) for i, s in pairs if i]

    def test_english_catalog_is_complete_and_placeholders_match(self):
        import re

        ph = re.compile(r"%\([a-z_]+\)[sd]|%[sd]")
        entries = self.entries("en")
        self.assertGreater(len(entries), 800)
        for msgid, msgstr in entries:
            with self.subTest(msgid=msgid[:50]):
                self.assertTrue(msgstr.strip(), "bo‘sh tarjima")
                self.assertEqual(sorted(ph.findall(msgid)), sorted(ph.findall(msgstr)))

    def test_english_and_uzbek_catalogs_have_the_same_texts(self):
        """Yangi matn faqat en katalogga qo‘shilsa, o‘zbek tilida u inglizchaga tushib qolardi."""
        self.assertEqual({i for i, _s in self.entries("en")}, {i for i, _s in self.entries("uz")})

    def test_uzbek_catalog_keeps_original_texts(self):
        for msgid, msgstr in self.entries("uz"):
            self.assertEqual(msgid, msgstr)

    def test_compiled_catalog_matches_po(self):
        from django.utils import translation
        from django.utils.translation import gettext

        for msgid, msgstr in self.entries("en")[:60]:
            with translation.override("en"):
                self.assertEqual(gettext(msgid.replace(chr(92) + chr(34), chr(34))),
                                 msgstr.replace(chr(92) + chr(34), chr(34)).replace(chr(92) + "n", chr(10)))

    def test_every_text_used_in_code_is_in_the_catalog(self):
        """tools/catalog.py check: yangi matn katalogga qo‘shilmasa, test yiqiladi."""
        import importlib.util
        from pathlib import Path

        from django.conf import settings

        spec = importlib.util.spec_from_file_location("catalog_tool", Path(settings.BASE_DIR) / "tools" / "catalog.py")
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)
        known = {tool.unquote('"' + i + '"') for i, _s in self.entries("en")}
        missing = sorted(m for m in tool.used_msgids() if m.strip() and m not in known)
        self.assertEqual(missing, [], "Katalogga qo‘shing: python tools/catalog.py add yangi.json")
