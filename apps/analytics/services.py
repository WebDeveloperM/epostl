"""Rivojlanish va analitika: dastlabki va keyingi natijalarni taqqoslash, dinamika, statistika."""
from collections import OrderedDict, defaultdict
from datetime import datetime, timedelta

from django.db.models import Count, Prefetch, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.accounts.models import Role, User
from apps.assessments.models import Assessment, AssessmentDetail, MentorFeedback
from apps.assignments.models import Assignment, AssignmentTarget
from apps.audit.models import AuditLog
from apps.competencies.models import AssessmentCriterion, Competency
from apps.core import charts
from apps.core.utils import percent, tr
from apps.goals.models import Goal
from apps.organization.models import Faculty, StudyGroup
from apps.portfolios.models import Portfolio, PortfolioVersion
from apps.reflections.frameworks import FRAMEWORKS
from apps.reflections.models import Reflection, ReflectionAnswer


def _ordered_assessments(qs):
    return list(
        qs.order_by("created_at", "pk").prefetch_related(
            Prefetch("details", queryset=AssessmentDetail.objects.select_related("criterion"))
        )
    )


def _pick_initial_latest(series):
    """Boshlang‘ich baholash bo‘lsa — u dastlabki natija, aks holda eng birinchi baho."""
    if not series:
        return None, None
    baseline = next((s for s in series if s[0].kind == Assessment.Kind.BASELINE), None)
    initial = baseline or series[0]
    later = [s for s in series if s is not initial and s[0].created_at >= initial[0].created_at]
    latest = later[-1] if later else None
    return initial, latest


def competency_comparison(student, assessments=None) -> dict:
    """Kompetensiyalar bo‘yicha dastlabki va keyingi natija (foizda)."""
    qs = assessments if assessments is not None else Assessment.objects.filter(student=student)
    items = _ordered_assessments(qs)
    competencies = list(Competency.objects.filter(is_active=True))
    per_assessment = []
    for a in items:
        scores = defaultdict(lambda: [0, 0])
        for d in a.details.all():
            if d.criterion.competency_id:
                scores[d.criterion.competency_id][0] += d.score
                scores[d.criterion.competency_id][1] += d.max_score
        per_assessment.append((a, scores))

    rows = []
    for comp in competencies:
        series = [(a, s[comp.pk]) for a, s in per_assessment if comp.pk in s]
        initial, latest = _pick_initial_latest(series)
        ini = percent(*initial[1]) if initial else None
        lat = percent(*latest[1]) if latest else None
        rows.append({
            "competency": comp,
            "initial": ini,
            "latest": lat,
            "delta": round(lat - ini, 1) if ini is not None and lat is not None else None,
            "count": len(series),
        })
    rows = [r for r in rows if r["count"]] or rows
    return {
        "rows": rows,
        "labels": [tr(r["competency"].name) for r in rows],
        "initial": [r["initial"] for r in rows],
        "latest": [r["latest"] for r in rows],
        "has_data": any(r["initial"] is not None for r in rows),
        "has_latest": any(r["latest"] is not None for r in rows),
        "assessments_count": len(items),
    }


def criteria_comparison(student, assessments=None) -> list[dict]:
    """Har bir mezon bo‘yicha dastlabki va keyingi ball (asl shkalada, masalan 20 ballik)."""
    qs = assessments if assessments is not None else Assessment.objects.filter(student=student)
    items = _ordered_assessments(qs)
    criteria = OrderedDict((c.pk, c) for c in AssessmentCriterion.objects.all().order_by("order"))
    rows = []
    for cid, criterion in criteria.items():
        series = []
        for a in items:
            for d in a.details.all():
                if d.criterion_id == cid:
                    series.append((a, d))
        if not series:
            continue
        initial, latest = _pick_initial_latest(series)
        rows.append({
            "criterion": criterion,
            "max": initial[1].max_score,
            "initial": initial[1].score,
            "latest": latest[1].score if latest else None,
            "delta": latest[1].score - initial[1].score if latest else None,
            "history": [d.score for _a, d in series],
        })
    return rows


def score_timeline(student) -> dict:
    items = list(Assessment.objects.filter(student=student).order_by("created_at")
                 .select_related("portfolio_version__portfolio"))
    labels, values, notes = [], [], []
    for a in items:
        labels.append(timezone.localtime(a.created_at).strftime("%d.%m.%y"))
        values.append(a.percent)
        if a.portfolio_version_id:
            notes.append(f"{a.portfolio_version.portfolio.title} (v{a.portfolio_version.version_number})")
        else:
            notes.append(str(a.get_kind_display()))
    return {"labels": labels, "values": values, "notes": notes}


def _month_keys(months: int):
    today = timezone.localdate().replace(day=1)
    keys = []
    year, month = today.year, today.month
    for _i in range(months):
        keys.append((year, month))
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    return list(reversed(keys))


def monthly_dynamics(student, months: int = 6) -> dict:
    """Oylar bo‘yicha: bajarilgan (tasdiqlangan) topshiriqlar, yuklangan versiyalar, refleksiyalar."""
    keys = _month_keys(months)
    start = timezone.make_aware(datetime(keys[0][0], keys[0][1], 1))

    def bucket(dates):
        counter = defaultdict(int)
        for dt in dates:
            if dt:
                local = timezone.localtime(dt)
                counter[(local.year, local.month)] += 1
        return [counter.get(k, 0) for k in keys]

    approved = AssignmentTarget.objects.filter(student=student, status=AssignmentTarget.Status.APPROVED,
                                               completed_at__gte=start).values_list("completed_at", flat=True)
    versions = PortfolioVersion.objects.filter(portfolio__student=student, created_at__gte=start
                                               ).values_list("created_at", flat=True)
    reflections = Reflection.objects.filter(student=student, status=Reflection.Status.SUBMITTED,
                                            submitted_at__gte=start).values_list("submitted_at", flat=True)
    month_names = ["Yan", "Fev", "Mar", "Apr", "May", "Iyun", "Iyul", "Avg", "Sen", "Okt", "Noy", "Dek"]
    return {
        "labels": [f"{month_names[m - 1]} {str(y)[2:]}" for y, m in keys],
        "approved": bucket(approved),
        "versions": bucket(versions),
        "reflections": bucket(reflections),
    }


def repeat_work_results(student) -> list[dict]:
    """Takroriy ishlar: bir nechta versiyasi baholangan ishlar bo‘yicha birinchi va oxirgi natija."""
    rows = []
    portfolios = Portfolio.objects.filter(student=student).prefetch_related(
        Prefetch("versions", queryset=PortfolioVersion.objects.select_related("assessment").order_by("version_number")))
    for p in portfolios:
        assessed = [v.assessment for v in p.versions.all() if getattr(v, "assessment", None)]
        if len(assessed) >= 2:
            first, last = assessed[0], assessed[-1]
            rows.append({"portfolio": p, "first": first.percent, "last": last.percent,
                         "delta": round((last.percent or 0) - (first.percent or 0), 1),
                         "versions": len(assessed)})
    return rows


def student_summary(student) -> dict:
    goals = Goal.objects.filter(student=student)
    goal_counts = {r["status"]: r["n"] for r in goals.values("status").annotate(n=Count("id"))}
    works = Portfolio.objects.filter(student=student)
    work_counts = {r["status"]: r["n"] for r in works.values("status").annotate(n=Count("id"))}
    targets = AssignmentTarget.objects.filter(student=student, assignment__is_active=True)
    active_targets = targets.exclude(status=AssignmentTarget.Status.APPROVED)
    total_works = sum(work_counts.values())
    return {
        "goals_total": sum(goal_counts.values()),
        "goals_active": goal_counts.get(Goal.Status.NEW, 0) + goal_counts.get(Goal.Status.IN_PROGRESS, 0),
        "goals_completed": goal_counts.get(Goal.Status.COMPLETED, 0),
        "works_total": total_works,
        "works_counts": work_counts,
        "works_approved_percent": percent(work_counts.get(Portfolio.Status.APPROVED, 0), total_works, 0) or 0,
        "targets_total": targets.count(),
        "targets_active": active_targets.count(),
        "targets_completed": targets.filter(status=AssignmentTarget.Status.APPROVED).count(),
        "targets_revision": targets.filter(status=AssignmentTarget.Status.REVISION).count(),
        "reflections_total": Reflection.objects.filter(student=student, status=Reflection.Status.SUBMITTED).count(),
        "assessments_total": Assessment.objects.filter(student=student).count(),
    }


def student_dashboard(student) -> dict:
    summary = student_summary(student)
    active_targets = (AssignmentTarget.objects.filter(student=student, assignment__is_active=True)
                      .exclude(status=AssignmentTarget.Status.APPROVED)
                      .select_related("assignment", "assignment__subject").order_by("assignment__due_date")[:6])
    feedback = list(MentorFeedback.objects.filter(portfolio__student=student)
                    .select_related("mentor", "portfolio")[:5])
    assessments = list(Assessment.objects.filter(student=student).exclude(overall_comment="")
                       .select_related("mentor", "portfolio_version__portfolio")[:5])
    comments = sorted(
        [{"kind": "feedback", "author": f.mentor, "text": f.text, "at": f.created_at, "portfolio": f.portfolio}
         for f in feedback]
        + [{"kind": "assessment", "author": a.mentor, "text": a.overall_comment, "at": a.created_at,
            "portfolio": a.portfolio_version.portfolio if a.portfolio_version_id else None, "assessment": a}
           for a in assessments],
        key=lambda x: x["at"], reverse=True)[:5]
    recent_versions = (PortfolioVersion.objects.filter(portfolio__student=student)
                       .select_related("portfolio").prefetch_related("files").order_by("-created_at")[:5])
    return {
        "summary": summary,
        "active_targets": active_targets,
        "comments": comments,
        "recent_versions": recent_versions,
        "comparison": (cmp := competency_comparison(student)),
        "comparison_chart": comparison_chart(cmp),
    }


def reflection_model_stats(reflections=None) -> list[dict]:
    """Refleksiya modellari bo‘yicha: nechta, kimlar, javob uzunligi (so‘z), o‘rtacha ball va bosqichlar chuqurligi.

    `reflections` — Reflection queryset (None — hammasi); faqat ustozga yuborilganlar hisobga olinadi.
    Javob uzunligi taxminiy ko‘rsatkich; ball esa ishning o‘ziga ham bog‘liq (modelning isboti emas).
    """
    submitted = (Reflection.objects.all() if reflections is None else reflections).filter(
        status=Reflection.Status.SUBMITTED)
    counts = {r["framework"]: r for r in submitted.order_by().values("framework").annotate(
        n=Count("id"), students=Count("student", distinct=True))}
    if not counts:
        return []
    words, stage_words = defaultdict(list), defaultdict(list)
    answers = ReflectionAnswer.objects.filter(reflection__in=submitted.values("pk")).values_list(
        "reflection__framework", "stage", "answer")
    for framework, stage, text in answers.iterator():
        n = len(text.split())
        words[framework].append(n)
        stage_words[(framework, stage)].append(n)
    scores = defaultdict(list)
    assessed = Assessment.objects.filter(
        kind=Assessment.Kind.WORK, portfolio_version__reflection__in=submitted.values("pk")).values_list(
        "portfolio_version__reflection__framework", "total_score", "max_score")
    for framework, total, maximum in assessed:
        if maximum:
            scores[framework].append(total * 100 / maximum)

    def mean(values):
        return sum(values) / len(values) if values else 0

    result = []
    for code in ("gibbs", "kolb", "simple"):
        if code not in counts:
            continue
        info = FRAMEWORKS[code]
        rows = [{"stage": st, "index": i, "avg_words": round(mean(stage_words[(code, st.code)]))}
                for i, st in enumerate(info.stages, start=1)]
        top = max((r["avg_words"] for r in rows), default=0)
        for r in rows:
            r["bar"] = round(100 * r["avg_words"] / top) if top else 0
        result.append({
            "info": info, "reflections": counts[code]["n"], "students": counts[code]["students"],
            "avg_words": round(mean(words[code])), "stages": rows,
            "avg_score": round(mean(scores[code]), 1) if scores[code] else None, "scored": len(scores[code]),
            # eng qisqa bosqich (ikkitadan ko‘p bosqich bo‘lsa va farq bo‘lsa)
            "shortest": min(rows, key=lambda r: r["avg_words"])["stage"] if top and len(rows) > 1 else None,
        })
    return result


def comparison_chart(cmp: dict) -> dict:
    return charts.comparison_bar(cmp["labels"], cmp["initial"], cmp["latest"])


def mentor_overview(mentor, students) -> list[dict]:
    """Ustoz talabalari bo‘yicha rivojlanish ko‘rsatkichlari."""
    students = list(students)
    ids = [s.pk for s in students]
    by_student = defaultdict(list)
    for a in Assessment.objects.filter(student_id__in=ids).order_by("created_at", "pk"):
        by_student[a.student_id].append(a)
    works = {r["student_id"]: r for r in Portfolio.objects.filter(student_id__in=ids).values("student_id").annotate(
        total=Count("id"), pending=Count("id", filter=Q(status=Portfolio.Status.SUBMITTED)),
        approved=Count("id", filter=Q(status=Portfolio.Status.APPROVED)))}
    refl = {r["student_id"]: r["n"] for r in Reflection.objects.filter(
        student_id__in=ids, status=Reflection.Status.SUBMITTED).values("student_id").annotate(n=Count("id"))}
    goals = {r["student_id"]: r["n"] for r in Goal.objects.filter(
        student_id__in=ids, status__in=[Goal.Status.NEW, Goal.Status.IN_PROGRESS]
    ).values("student_id").annotate(n=Count("id"))}
    rows = []
    for s in students:
        series = [(a, None) for a in by_student.get(s.pk, [])]
        initial, latest = _pick_initial_latest(series)
        ini = initial[0].percent if initial else None
        lat = latest[0].percent if latest else None
        w = works.get(s.pk, {})
        rows.append({
            "student": s,
            "initial": ini,
            "latest": lat,
            "delta": round(lat - ini, 1) if ini is not None and lat is not None else None,
            "assessments": len(series),
            "works": w.get("total", 0),
            "pending": w.get("pending", 0),
            "approved": w.get("approved", 0),
            "reflections": refl.get(s.pk, 0),
            "active_goals": goals.get(s.pk, 0),
        })
    return rows


def mentor_dashboard(mentor) -> dict:
    from apps.accounts.services import mentor_student_ids, mentor_students
    from apps.assessments.services import pending_reviews

    students = mentor_students(mentor)
    student_ids = mentor_student_ids(mentor)
    week_ago = timezone.now() - timedelta(days=7)
    pending = pending_reviews(mentor)
    new_reflections = (Reflection.objects.filter(student_id__in=student_ids, status=Reflection.Status.SUBMITTED,
                                                 portfolio_version__assessment__isnull=True)
                       .select_related("student", "portfolio_version__portfolio").order_by("-submitted_at"))
    overview = mentor_overview(mentor, students)
    with_delta = [r for r in overview if r["delta"] is not None]
    return {
        "students_count": len(overview),
        "pending_count": pending.count(),
        "pending": pending[:6],
        "assessed_count": Assessment.objects.filter(mentor=mentor, kind=Assessment.Kind.WORK).count(),
        "assessed_week": Assessment.objects.filter(mentor=mentor, created_at__gte=week_ago).count(),
        "new_reflections_count": new_reflections.count(),
        "new_reflections": new_reflections[:5],
        "assignments_active": Assignment.objects.filter(created_by=mentor, is_active=True).count(),
        "overview": sorted(overview, key=lambda r: (r["pending"] == 0, r["student"].last_name))[:10],
        "avg_delta": round(sum(r["delta"] for r in with_delta) / len(with_delta), 1) if with_delta else None,
        "progress_chart": charts.comparison_bar(
            [r["student"].short_name for r in with_delta][:15],
            [r["initial"] for r in with_delta][:15],
            [r["latest"] for r in with_delta][:15],
            horizontal=True,
        ),
    }


def admin_dashboard() -> dict:
    users = User.objects.all()
    role_counts = {r["role__code"]: r["n"] for r in users.values("role__code").annotate(n=Count("id"))}
    faculties = Faculty.objects.annotate(
        students=Count("directions__groups__students", filter=Q(
            directions__groups__students__role__code=Role.Code.STUDENT), distinct=True),
        groups=Count("directions__groups", distinct=True),
        staff=Count("departments__staff", distinct=True),
    ).order_by("name")
    since = timezone.now() - timedelta(days=13)
    activity = {r["day"]: r["n"] for r in AuditLog.objects.filter(created_at__gte=since)
                .annotate(day=TruncDate("created_at")).values("day").annotate(n=Count("id"))}
    uploads = {r["day"]: r["n"] for r in PortfolioVersion.objects.filter(created_at__gte=since)
               .annotate(day=TruncDate("created_at")).values("day").annotate(n=Count("id"))}
    days = [timezone.localdate() - timedelta(days=i) for i in range(13, -1, -1)]
    portfolio_counts = {r["status"]: r["n"] for r in Portfolio.objects.values("status").annotate(n=Count("id"))}
    return {
        "users_total": users.count(),
        "users_active": users.filter(is_active=True).count(),
        "users_blocked": users.filter(is_active=False).count(),
        "students": role_counts.get(Role.Code.STUDENT, 0),
        "mentors": role_counts.get(Role.Code.MENTOR, 0),
        "admins": role_counts.get(Role.Code.ADMIN, 0),
        "faculties": faculties,
        "faculties_count": faculties.count(),
        "groups_count": StudyGroup.objects.count(),
        "assignments_total": Assignment.objects.count(),
        "assignments_active": Assignment.objects.filter(is_active=True, due_date__gte=timezone.now()).count(),
        "portfolios_total": sum(portfolio_counts.values()),
        "portfolio_counts": portfolio_counts,
        "reflections_total": Reflection.objects.filter(status=Reflection.Status.SUBMITTED).count(),
        "assessments_total": Assessment.objects.count(),
        "logins_today": AuditLog.objects.filter(action=AuditLog.Action.LOGIN,
                                                created_at__date=timezone.localdate()).count(),
        "recent_logs": AuditLog.objects.select_related("user")[:8],
        "activity_chart": charts.line_chart(
            [d.strftime("%d.%m") for d in days],
            [(_("Tizimdagi amallar"), [activity.get(d, 0) for d in days]),
             (_("Yuklangan ish versiyalari"), [uploads.get(d, 0) for d in days])],
        ),
        "roles_chart": charts.doughnut(
            [_("Talabalar"), _("Ustozlar"), _("Administratorlar")],
            [role_counts.get(Role.Code.STUDENT, 0), role_counts.get(Role.Code.MENTOR, 0),
             role_counts.get(Role.Code.ADMIN, 0)],
        ),
        "faculty_chart": charts.bar_chart(
            [str(f) for f in faculties], [(_("Talabalar soni"), [f.students for f in faculties])],
            horizontal=True,
        ),
    }


def platform_competency_averages() -> dict:
    """Barcha talabalar bo‘yicha kompetensiyalar: o‘rtacha dastlabki va keyingi natija."""
    students = User.objects.students().filter(assessments__isnull=False).distinct()
    sums = defaultdict(lambda: {"initial": [], "latest": []})
    for s in students:
        for row in competency_comparison(s)["rows"]:
            if row["initial"] is not None:
                sums[row["competency"].pk]["initial"].append(row["initial"])
            if row["latest"] is not None:
                sums[row["competency"].pk]["latest"].append(row["latest"])
    comps = list(Competency.objects.filter(is_active=True))

    def avg(values):
        return round(sum(values) / len(values), 1) if values else None

    labels = [tr(c.name) for c in comps]
    initial = [avg(sums[c.pk]["initial"]) for c in comps]
    latest = [avg(sums[c.pk]["latest"]) for c in comps]
    return {
        "labels": labels,
        "initial": initial,
        "latest": latest,
        "rows": list(zip(labels, initial, latest)),
        "chart": charts.comparison_bar(labels, initial, latest),
        "students": students.count(),
    }
