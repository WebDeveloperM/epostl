"""Namunaviy (demo) ma’lumotlar: tashkiliy tuzilma, foydalanuvchilar va to‘liq rivojlanish sikli.

    python manage.py seed_demo            # faqat DEBUG=True bo‘lganda
    python manage.py seed_demo --force    # production'da ham (ehtiyot bo‘ling!)
"""
from datetime import timedelta
from types import SimpleNamespace

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.datastructures import MultiValueDict

from apps.accounts.models import MentorAssignment, Role, User
from apps.assessments.models import Assessment
from apps.assessments.services import assess_version, create_baseline
from apps.assignments.models import Assignment
from apps.assignments.services import sync_targets
from apps.competencies.models import AssessmentCriterion, Competency
from apps.goals.models import Goal
from apps.organization.models import Department, Direction, Faculty, StudyGroup
from apps.portfolios.forms import PortfolioCreateForm, UploadForm
from apps.portfolios.services import create_portfolio, upload_files
from apps.reflections import services as reflection_services
from apps.subjects.models import Subject

PASSWORDS = {"admin": "Admin12345!", "ustoz": "Ustoz12345!", "talaba": "Talaba12345!"}

PDF = (b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
       b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 144]>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n")


def fake_request(user):
    return SimpleNamespace(user=user, META={"REMOTE_ADDR": "127.0.0.1", "HTTP_USER_AGENT": "seed_demo"})


class Command(BaseCommand):
    help = "Makes demo data: school structure, users and one full growth example (in English)."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Run even if DEBUG=False")
        parser.add_argument("--no-history", action="store_true", help="Do not make the growth example")

    def handle(self, *args, **opts):
        if not settings.DEBUG and not opts["force"]:
            raise CommandError("Demo data is made only when DEBUG=True (or use --force).")
        with transaction.atomic():
            org = self._organization()
            users = self._users(org)
            assignment = self._assignment(org, users)
        if not opts["no_history"] and not Assessment.objects.filter(student=users["students"][0]).exists():
            with transaction.atomic():  # xato bo‘lsa yarim sikl qolmasin
                self._history(users, assignment)
        self.stdout.write(self.style.SUCCESS("Demo data is ready. Sign-in details:"))
        self.stdout.write(f"  Admin:    admin / {PASSWORDS['admin']}")
        self.stdout.write(f"  Teacher:  ustoz / {PASSWORDS['ustoz']}")
        self.stdout.write(f"  Students: talaba1, talaba2, talaba3 / {PASSWORDS['talaba']}")

    # --- Tashkiliy tuzilma ---
    def _organization(self):
        faculty, _ = Faculty.objects.get_or_create(name='Faculty of Education', defaults={"short_name": "FE"})
        dep, _ = Department.objects.get_or_create(faculty=faculty, name='Teaching and Psychology Department')
        direction, _ = Direction.objects.get_or_create(
            code="60110500", defaults={"faculty": faculty, "department": dep, "name": 'Primary Education'})
        g1, _ = StudyGroup.objects.get_or_create(name="BT-21", defaults={"direction": direction, "course": 3,
                                                                          "academic_year": "2026-2027"})
        g2, _ = StudyGroup.objects.get_or_create(name="BT-22", defaults={"direction": direction, "course": 3,
                                                                          "academic_year": "2026-2027"})
        subject, _ = Subject.objects.get_or_create(code="PA-301", defaults={"name": 'Teaching Practice',
                                                                            "department": dep})
        Subject.objects.get_or_create(code="TM-205", defaults={"name": 'Teaching Methods', "department": dep})
        return {"faculty": faculty, "department": dep, "groups": [g1, g2], "subject": subject}

    def _user(self, username, password, role_code, **fields):
        user, created = User.objects.get_or_create(username=username, defaults={
            **fields, "role": Role.objects.get(code=role_code)})
        if created:
            user.set_password(password)
            user.save()
        return user

    def _users(self, org):
        admin = self._user("admin", PASSWORDS["admin"], Role.Code.ADMIN, last_name="System", first_name="Admin",
                           is_staff=True, is_superuser=True, email="admin@example.uz")
        mentor = self._user("ustoz", PASSWORDS["ustoz"], Role.Code.MENTOR, last_name="Saidova", first_name="Malika",
                            middle_name="Akramovna", department=org["department"], email="ustoz@example.uz",
                            external_id="EMP-0001")
        names = [("Karimov", "Aziz", "Rustamovich"), ("Toshmatova", "Dilnoza", "Baxtiyorovna"),
                 ("Ergashev", "Sardor", "Alisherovich")]
        students = [
            self._user(f"talaba{i}", PASSWORDS["talaba"], Role.Code.STUDENT, last_name=ln, first_name=fn,
                       middle_name=mn, group=org["groups"][0], external_id=f"ST-00{i}")
            for i, (ln, fn, mn) in enumerate(names, start=1)
        ]
        MentorAssignment.objects.get_or_create(mentor=mentor, group=org["groups"][0], is_active=True,
                                               defaults={"assigned_by": admin})
        return {"admin": admin, "mentor": mentor, "students": students}

    def _assignment(self, org, users):
        now = timezone.now()
        assignment, created = Assignment.objects.get_or_create(
            title='Lesson plan and lesson video using questions and answers',
            defaults={
                "description": 'Make a 45-minute lesson plan for primary school and record the lesson on video. Get all pupils to join in questions and answers during the lesson.',
                "instructions": '1. Write the lesson goal and the results you want.\n2. Prepare questions of at least 3 levels.\n3. Record the lesson on video (a clip of 10–15 minutes).\n4. Answer the self-review questions.',
                "subject": org["subject"],
                "competency": Competency.objects.filter(code="questioning").first(),
                "start_date": now - timedelta(days=20),
                "due_date": now + timedelta(days=10),
                "created_by": users["mentor"],
            },
        )
        if created:
            assignment.groups.add(org["groups"][0])
            sync_targets(assignment, [org["groups"][0]], [])
        return assignment

    # --- To‘liq rivojlanish sikli namunasi ---
    def _details(self, scores):
        criteria = list(AssessmentCriterion.objects.filter(is_active=True).order_by("order"))
        return [{"criterion": c, "score": min(s, c.max_score), "comment": "", "weaknesses": w, "recommendations": r}
                for c, (s, w, r) in zip(criteria, scores)]

    def _history(self, users, assignment):
        student, mentor = users["students"][0], users["mentor"]
        s_req, m_req = fake_request(student), fake_request(mentor)

        # 1. Boshlang‘ich baholash
        create_baseline(m_req, student, goal=None, overall_comment='Based on the first lesson I watched.', details=self._details([
            (11, 'The lesson steps have no planned time', 'Give a time to each step'),
            (12, "", ""), (7, 'The questions are mostly closed questions', 'Add open questions and questions that make pupils think'),
            (10, "", ""), (8, 'The self-review is too short and shallow', 'Use proof to support your words'),
        ]))
        # 2. Maqsad
        goal = Goal.objects.create(
            student=student, title='Get all pupils to join in questions and answers during the lesson',
            competency=Competency.objects.get(code="questioning"), start_date=timezone.localdate() - timedelta(days=15),
            target_date=timezone.localdate() + timedelta(days=45),
            expected_outcome='In every lesson, at least 80 percent of the pupils join in the questions and answers.',
        )
        # 3–4. Rejalashtirish va amaliy ish (v1)
        form = PortfolioCreateForm(
            data={"title": 'Question-and-answer lesson: "Nature"', "assignment": assignment.pk, "goal": goal.pk,
                  "material_type": "lesson_plan", "description": 'Grade 3, natural science', "note": ""},
            files=MultiValueDict({"files": [SimpleUploadedFile("dars_ishlanmasi_v1.pdf", PDF, "application/pdf")]}),
            student=student,
        )
        if not form.is_valid():
            raise CommandError(f"Demo work form error: {form.errors}")
        portfolio = create_portfolio(s_req, form)
        v1 = portfolio.latest_version
        # 5. Refleksiya — Gibbs modeli (6 bosqich)
        gibbs = list(reflection_services.active_questions("gibbs"))
        answers_v1 = [
            'I taught a 45-minute lesson in grade 3. I wanted all the pupils to join in the questions and '
            'answers. Only 6–7 pupils answered, and the others just watched.',
            'At first I felt excited. Then I felt worried, because most pupils stayed quiet.',
            'Good: the problem question at the start of the lesson made pupils curious. See the raised hands at '
            'minute 3 of the video. Bad: my questions were mostly closed.',
            'I did not wait long enough for answers, so shy pupils had no time to think.',
            'I learned that open questions and a longer waiting time help more pupils to speak.',
            'I will use open questions and the "think, then talk in pairs" way.',
        ]
        r1 = reflection_services.save_draft(s_req, v1, gibbs, {q.pk: a for q, a in zip(gibbs, answers_v1)},
                                            framework="gibbs")
        reflection_services.submit(s_req, r1, gibbs)
        # 6. Ustoz fikri va baholash — qayta ishlashga
        v1.refresh_from_db()
        assess_version(m_req, v1, decision=Assessment.Decision.REVISION,
                       overall_comment='A good start. Use more kinds of questions.', details=self._details([
                           (14, "", 'Put the time plan in a table'), (14, "", ""),
                           (10, 'The waiting time is less than 2 seconds', 'Wait 5–7 seconds after a question'),
                           (13, "", ""), (12, "", 'Support each idea with proof'),
                       ]))
        # 7. Ishni takomillashtirish (v2)
        portfolio.refresh_from_db()
        upload = UploadForm(data={"note": 'Added open questions and talking in pairs.'},
                            files=MultiValueDict({"files": [SimpleUploadedFile("dars_ishlanmasi_v2.pdf", PDF,
                                                                               "application/pdf")]}))
        if not upload.is_valid():
            raise CommandError(f"Demo upload form error: {upload.errors}")
        v2 = upload_files(s_req, portfolio, upload.cleaned_data["files"], upload.cleaned_data["note"])
        # Refleksiya — Kolb modeli (4 bosqich): ikkinchi tajriba boshqa model bilan tahlil qilinadi
        kolb = list(reflection_services.active_questions("kolb"))
        answers_v2 = [
            'I taught the lesson again with open questions. Pupils talked in pairs first, and I waited 5–7 '
            'seconds after each question.',
            'After talking in pairs, 17 of 20 pupils answered, and the answers were fuller. I ran a little short '
            'of time, so the last step was short.',
            'Waiting time and talking in pairs give shy pupils time to think. This is the same as the "wait '
            'time" idea in teaching books.',
            'I will keep 5 minutes for the last step and try the same way in other subjects.',
        ]
        r2 = reflection_services.save_draft(s_req, v2, kolb, {q.pk: a for q, a in zip(kolb, answers_v2)},
                                            framework="kolb")
        reflection_services.submit(s_req, r2, kolb)
        v2.refresh_from_db()
        # 8. Natijalarni taqqoslash uchun takroriy baholash — tasdiqlash
        assess_version(m_req, v2, decision=Assessment.Decision.APPROVED,
                       overall_comment='Clear growth. The work is approved.', details=self._details([
                           (17, "", ""), (16, "", ""), (17, "", 'Use this way in other subjects too'),
                           (16, "", ""), (16, "", ""),
                       ]))
        self.stdout.write("  A full growth example was made (talaba1).")
