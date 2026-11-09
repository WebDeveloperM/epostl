from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.accounts.services import mentor_student_ids
from apps.audit.services import log_action
from apps.core.utils import tr

from .frameworks import CARRY_OVER, CHOOSABLE, DEFAULT_FRAMEWORK, FRAMEWORKS, get_framework
from .models import Reflection, ReflectionAnswer, ReflectionEvidence, ReflectionQuestion


def visible_reflections(user):
    if user.is_platform_admin:
        return Reflection.objects.all()
    if user.is_mentor:
        return Reflection.objects.filter(
            Q(student_id__in=mentor_student_ids(user))
            | Q(portfolio_version__portfolio__assignment__created_by=user)
        )
    if user.is_student:
        return Reflection.objects.filter(student=user)
    return Reflection.objects.none()


def active_questions(framework=DEFAULT_FRAMEWORK.value):
    """Tanlangan modelning faol savollari (noma’lum model bo‘lsa — standart model)."""
    return ReflectionQuestion.objects.filter(is_active=True, framework=get_framework(framework).code)


def available_frameworks():
    """Tanlash ekrani uchun: faol savoli bor modellar (savollar soni bilan)."""
    counts = dict(ReflectionQuestion.objects.filter(is_active=True).order_by()
                  .values_list("framework").annotate(n=Count("id")))
    return [{"info": FRAMEWORKS[code], "question_count": counts[code]}
            for code in ("gibbs", "kolb") if counts.get(code)]


def missing_required(questions, answers: dict) -> list:
    return [q for q in questions if q.is_required and not answers.get(q.pk)]


@transaction.atomic
def save_draft(request, version, questions, answers: dict, evidence_files=(), link="", link_description="",
               framework=DEFAULT_FRAMEWORK.value):
    """Qoralamani saqlaydi. Model refleksiya yaratilganda tanlanadi va keyin o‘zgarmaydi."""
    if version.portfolio.student_id != request.user.pk:
        raise PermissionDenied
    reflection, created = Reflection.objects.get_or_create(
        portfolio_version=version,
        defaults={"student": request.user, "framework": get_framework(framework).code})
    if not created and reflection.is_locked:
        raise ValidationError(_("Ish baholangan — refleksiyani endi o‘zgartirib bo‘lmaydi."))
    for q in questions:
        if q.framework != reflection.framework:  # boshqa modelning savoli aralashib ketmasin
            continue
        ReflectionAnswer.objects.update_or_create(
            reflection=reflection, question=q,
            defaults={"answer": answers.get(q.pk, ""), "question_text": q.text, "stage": q.stage},
        )
    for uploaded, info in evidence_files:
        ReflectionEvidence.objects.create(
            reflection=reflection, file=uploaded, original_name=info.original_name, file_size=info.size,
            mime_type=info.mime_type, category=info.category, description=link_description,
        )
    if link:
        ReflectionEvidence.objects.create(reflection=reflection, link=link, description=link_description)
    reflection.save(update_fields=["updated_at"])
    log_action(request, "create" if created else "update", reflection)
    return reflection


def can_change_framework(reflection: Reflection) -> bool:
    """Modelni faqat qoralama paytida almashtirish mumkin (yuborilgandan keyin javoblar to‘liq deb hisoblanadi)."""
    return (reflection.status == Reflection.Status.DRAFT and not reflection.is_locked
            and reflection.framework in CHOOSABLE)


@transaction.atomic
def change_framework(request, reflection: Reflection, new_code: str):
    """Qoralamani boshqa modelga o‘tkazadi: javoblar mos bosqichlarga ko‘chadi, dalillar o‘z joyida qoladi."""
    if reflection.student_id != request.user.pk:
        raise PermissionDenied
    reflection = Reflection.objects.select_for_update().get(pk=reflection.pk)
    if reflection.is_locked:
        raise ValidationError(_("Ish baholangan — refleksiyani endi o‘zgartirib bo‘lmaydi."))
    if reflection.status != Reflection.Status.DRAFT:
        raise ValidationError(_("Modelni faqat ustozga yuborishdan oldin almashtirish mumkin."))
    old_code = reflection.framework
    mapping = CARRY_OVER.get((old_code, new_code))
    if new_code not in CHOOSABLE or old_code == new_code or mapping is None:
        raise ValidationError(_("Bu modelga o‘tib bo‘lmaydi."))
    new_questions = list(active_questions(new_code))
    if not new_questions:
        raise ValidationError(_("Tanlangan modelda faol savollar yo‘q."))

    carried = {}  # yangi bosqich -> [matnlar]
    for answer in reflection.answers.select_related("question"):
        target = mapping.get(answer.stage)
        if target and answer.answer.strip():
            carried.setdefault(target, []).append(answer.answer.strip())
    reflection.answers.all().delete()
    reflection.framework = new_code
    reflection.save(update_fields=["framework", "updated_at"])
    for q in new_questions:
        ReflectionAnswer.objects.create(
            reflection=reflection, question=q, question_text=q.text, stage=q.stage,
            answer="\n\n".join(carried.get(q.stage, [])))
    log_action(request, "update", reflection, framework=f"{old_code} -> {new_code}")
    return reflection


def submit(request, reflection: Reflection, questions):
    """Refleksiyani yakunlab ustozga yuboradi; ish versiyasi ham tekshirishga yuboriladi."""
    from apps.portfolios.services import submit_version

    answers = {a.question_id: a.answer.strip() for a in reflection.answers.all()}
    missing = missing_required(questions, answers)
    if missing:
        raise ValidationError(_("Quyidagi savollarga javob bering: %(q)s")
                              % {"q": "; ".join(tr(q.text) for q in missing)})
    version = reflection.portfolio_version
    with transaction.atomic():
        if reflection.status != Reflection.Status.SUBMITTED:
            reflection.status = Reflection.Status.SUBMITTED
            reflection.submitted_at = timezone.now()
            reflection.save(update_fields=["status", "submitted_at", "updated_at"])
        if not version.is_submitted:
            submit_version(request, version)
    return reflection


def delete_evidence(request, evidence: ReflectionEvidence):
    if evidence.reflection.is_locked:
        raise ValidationError(_("Baholangan refleksiya dalilini o‘chirib bo‘lmaydi."))
    log_action(request, "delete", evidence)
    if evidence.file:
        evidence.file.delete(save=False)
    evidence.delete()
