"""Foydalanuvchilar, rollar va ustoz-talaba bog‘lanishlari bo‘yicha biznes-logika."""
from __future__ import annotations

import io
import secrets
import string
from dataclasses import dataclass, field

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Q
from django.conf import settings
from django.utils import translation
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy

from apps.audit.services import log_action
from apps.organization.models import Department, StudyGroup

from .models import MentorAssignment, Role, User, phone_validator


# --- Ustoz <-> talaba -----------------------------------------------------
def mentor_students(mentor: User):
    """Ustozga to‘g‘ridan-to‘g‘ri yoki guruh orqali biriktirilgan faol talabalar."""
    direct = MentorAssignment.objects.filter(mentor=mentor, is_active=True, student__isnull=False)
    groups = MentorAssignment.objects.filter(mentor=mentor, is_active=True, group__isnull=False)
    return (
        User.objects.students()
        .filter(is_active=True)
        .filter(Q(pk__in=direct.values("student_id")) | Q(group_id__in=groups.values("group_id")))
        .select_related("group", "group__direction")
    )


def mentor_student_ids(mentor: User):
    """Subquery uchun: ustoz talabalarining ID lari."""
    return mentor_students(mentor).values("pk")


def mentor_groups(mentor: User):
    return StudyGroup.objects.filter(
        mentor_links__mentor=mentor, mentor_links__is_active=True
    ).distinct()


def student_mentors(student: User):
    links = MentorAssignment.objects.filter(is_active=True).filter(
        Q(student=student) | Q(group_id=student.group_id, group__isnull=False)
    )
    return User.objects.mentors().filter(is_active=True, pk__in=links.values("mentor_id"))


def is_mentor_of(mentor: User, student: User) -> bool:
    if not mentor.is_mentor or not student.is_student:
        return False
    links = MentorAssignment.objects.filter(mentor=mentor, is_active=True)
    return links.filter(Q(student=student) | Q(group_id=student.group_id, group__isnull=False)).exists()


def can_view_profile(viewer: User, target: User) -> bool:
    if viewer.pk == target.pk or viewer.is_platform_admin:
        return True
    if viewer.is_mentor:
        return target.is_mentor or is_mentor_of(viewer, target)
    if viewer.is_student:
        return target.is_mentor and is_mentor_of(target, viewer)
    return False


# --- Foydalanuvchi yaratish ----------------------------------------------
PASSWORD_ALPHABET = string.ascii_letters + string.digits


def generate_password(length: int = 10) -> str:
    while True:
        pwd = "".join(secrets.choice(PASSWORD_ALPHABET) for _i in range(length))
        if any(c.isdigit() for c in pwd) and any(c.isupper() for c in pwd) and any(c.islower() for c in pwd):
            return pwd


def set_active(request, user: User, active: bool):
    user.is_active = active
    user.save(update_fields=["is_active"])
    log_action(request, "unblock" if active else "block", user)


# --- Excel import ---------------------------------------------------------
IMPORT_COLUMNS = [
    ("last_name", _lazy("Familiya"), True),
    ("first_name", _lazy("Ism"), True),
    ("middle_name", _lazy("Otasining ismi"), False),
    ("username", _lazy("Login"), True),
    ("password", _lazy("Parol"), False),
    ("email", _lazy("Email"), False),
    ("phone", _lazy("Telefon"), False),
    ("role", _lazy("Rol"), True),
    ("group", _lazy("Guruh"), False),
    ("department", _lazy("Kafedra"), False),
    ("external_id", _lazy("ID raqam"), False),
]
ROLE_ALIASES = {
    "talaba": Role.Code.STUDENT, "student": Role.Code.STUDENT, "студент": Role.Code.STUDENT,
    "ustoz": Role.Code.MENTOR, "mentor": Role.Code.MENTOR, "teacher": Role.Code.MENTOR, "o‘qituvchi": Role.Code.MENTOR,
    "oqituvchi": Role.Code.MENTOR, "преподаватель": Role.Code.MENTOR,
    "admin": Role.Code.ADMIN, "administrator": Role.Code.ADMIN, "администратор": Role.Code.ADMIN,
}


def _norm(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value).strip()


def _header_key(value: str) -> str:
    return _norm(value).lower().replace("’", "'").replace("‘", "'").replace("ʻ", "'")


def header_map() -> dict:
    """Ustun sarlavhalari -> maydon. Excel fayl istalgan tilda (ingliz yoki o‘zbek) bo‘lishi mumkin."""
    mapping = {key: key for key, _l, _r in IMPORT_COLUMNS}
    for code, _name in settings.LANGUAGES:
        with translation.override(code):
            for key, label, _req in IMPORT_COLUMNS:
                mapping[_header_key(str(label))] = key
    return mapping


@dataclass
class ImportRow:
    row_number: int
    data: dict
    errors: list = field(default_factory=list)
    generated_password: str = ""
    user: User | None = None


@dataclass
class ImportResult:
    rows: list
    created: list
    errors: list
    applied: bool

    @property
    def has_errors(self):
        return bool(self.errors)


def build_import_template() -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation

    wb = Workbook()
    ws = wb.active
    ws.title = _("Foydalanuvchilar")
    ws.append([str(label) for _k, label, _r in IMPORT_COLUMNS])
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="4F46E5")
    ws.append(["Karimov", "Aziz", "Rustamovich", "aziz.karimov", "", "aziz@example.uz",
               "+998901234567", _("talaba"), "PED-21", "", "ST-000123"])
    ws.append(["Saidova", "Malika", "Akramovna", "m.saidova", "", "m.saidova@example.uz",
               "+998907654321", _("ustoz"), "", _("Pedagogika kafedrasi"), "EMP-0042"])
    for col, width in zip("ABCDEFGHIJK", (16, 14, 18, 18, 14, 26, 16, 12, 12, 26, 14)):
        ws.column_dimensions[col].width = width
    dv = DataValidation(type="list", formula1='"%s"' % ",".join([_("talaba"), _("ustoz"), "admin"]), allow_blank=False)
    ws.add_data_validation(dv)
    dv.add("H2:H2000")

    info = wb.create_sheet(_("Yo‘riqnoma"))
    info.append([_("Ustun"), _("Majburiy"), _("Izoh")])
    notes = {
        "password": _("Bo‘sh qoldirilsa, tizim parol yaratadi va natija sahifasida ko‘rsatadi."),
        "role": " / ".join([_("talaba"), _("ustoz"), "admin"]),
        "group": _("Talabalar uchun: tizimdagi guruh nomi (masalan, PED-21)."),
        "department": _("Ustozlar uchun: tizimdagi kafedra nomi."),
        "external_id": _("Talaba yoki xodim identifikatori (takrorlanmas)."),
    }
    for key, label, required in IMPORT_COLUMNS:
        info.append([str(label), _("ha") if required else _("yo‘q"), notes.get(key, "")])
    info.column_dimensions["A"].width = 18
    info.column_dimensions["C"].width = 70
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def _read_rows(file) -> list[ImportRow]:
    from openpyxl import load_workbook

    try:
        wb = load_workbook(file, read_only=True, data_only=True)
    except Exception as exc:
        raise ValidationError(_("Excel faylni o‘qib bo‘lmadi: %(e)s") % {"e": exc})
    ws = wb.worksheets[0]
    rows_iter = ws.iter_rows(values_only=True)
    try:
        header = next(rows_iter)
    except StopIteration:
        raise ValidationError(_("Fayl bo‘sh."))
    mapping = header_map()
    keys = [mapping.get(_header_key(h)) for h in header]
    missing = [str(label) for key, label, req in IMPORT_COLUMNS if req and key not in keys]
    if missing:
        raise ValidationError(_("Majburiy ustunlar topilmadi: %(c)s") % {"c": ", ".join(missing)})
    result = []
    for index, values in enumerate(rows_iter, start=2):
        if not values or all(_norm(v) == "" for v in values):
            continue
        data = {key: _norm(values[i]) if i < len(values) else "" for i, key in enumerate(keys) if key}
        result.append(ImportRow(row_number=index, data=data))
        if len(result) > 1000:
            raise ValidationError(_("Bir martada 1000 tadan ortiq qator import qilib bo‘lmaydi."))
    wb.close()
    return result


def _validate_row(row: ImportRow, roles: dict, groups: dict, departments: dict,
                  seen_usernames: set, seen_emails: set, seen_ids: set):
    d = row.data
    for key, label, required in IMPORT_COLUMNS:
        if required and not d.get(key):
            row.errors.append(_("«%(c)s» to‘ldirilmagan") % {"c": str(label)})
    username = d.get("username", "")
    if username:
        if len(username) > 150 or not all(c.isalnum() or c in "@.+-_" for c in username):
            row.errors.append(_("Login faqat harf, raqam va @ . + - _ belgilaridan iborat bo‘lishi kerak"))
        elif username.lower() in seen_usernames or User.objects.filter(username__iexact=username).exists():
            row.errors.append(_("«%(u)s» logini band") % {"u": username})
        seen_usernames.add(username.lower())

    role_code = ROLE_ALIASES.get(d.get("role", "").lower())
    if d.get("role") and not role_code:
        row.errors.append(_("Rol noma’lum: %(r)s") % {"r": d.get("role")})
    d["role_obj"] = roles.get(role_code)

    if email := d.get("email"):
        try:
            validate_email(email)
        except ValidationError:
            row.errors.append(_("Email noto‘g‘ri"))
        if email.lower() in seen_emails or User.objects.filter(email__iexact=email).exists():
            row.errors.append(_("«%(e)s» emaili band") % {"e": email})
        seen_emails.add(email.lower())
    if phone := d.get("phone"):
        try:
            phone_validator(phone)
        except ValidationError:
            row.errors.append(_("Telefon raqami noto‘g‘ri"))
    if ext := d.get("external_id"):
        if ext.lower() in seen_ids or User.objects.filter(external_id__iexact=ext).exists():
            row.errors.append(_("«%(i)s» ID raqami band") % {"i": ext})
        seen_ids.add(ext.lower())

    d["group_obj"] = None
    if group_name := d.get("group"):
        d["group_obj"] = groups.get(group_name.lower())
        if not d["group_obj"]:
            row.errors.append(_("Guruh topilmadi: %(g)s") % {"g": group_name})
    elif role_code == Role.Code.STUDENT:
        row.errors.append(_("Talaba uchun guruh ko‘rsatilishi shart"))

    d["department_obj"] = None
    if dep_name := d.get("department"):
        matches = departments.get(dep_name.lower(), [])
        if len(matches) == 1:
            d["department_obj"] = matches[0]
        elif not matches:
            row.errors.append(_("Kafedra topilmadi: %(k)s") % {"k": dep_name})
        else:
            row.errors.append(_("Kafedra nomi bir nechta fakultetda bor: %(k)s") % {"k": dep_name})

    if password := d.get("password"):
        probe = User(username=username, first_name=d.get("first_name", ""), last_name=d.get("last_name", ""),
                     email=d.get("email", ""))
        try:
            validate_password(password, probe)
        except ValidationError as exc:
            row.errors.append(_("Parol: %(e)s") % {"e": " ".join(exc.messages)})


def import_users_from_excel(request, file, *, skip_invalid: bool = False) -> ImportResult:
    rows = _read_rows(file)
    roles = {r.code: r for r in Role.objects.all()}
    groups = {g.name.lower(): g for g in StudyGroup.objects.all()}
    departments: dict[str, list] = {}
    for dep in Department.objects.all():
        departments.setdefault(dep.name.lower(), []).append(dep)

    seen_u, seen_e, seen_i = set(), set(), set()
    for row in rows:
        _validate_row(row, roles, groups, departments, seen_u, seen_e, seen_i)

    invalid = [r for r in rows if r.errors]
    if invalid and not skip_invalid:
        return ImportResult(rows=rows, created=[], errors=invalid, applied=False)

    created = []
    with transaction.atomic():
        for row in rows:
            if row.errors:
                continue
            d = row.data
            password = d.get("password") or generate_password()
            if not d.get("password"):
                row.generated_password = password
            user = User(
                username=d["username"],
                last_name=d.get("last_name", ""),
                first_name=d.get("first_name", ""),
                middle_name=d.get("middle_name", ""),
                email=d.get("email", ""),
                phone=d.get("phone", ""),
                role=d["role_obj"],
                group=d["group_obj"] if d["role_obj"] and d["role_obj"].code == Role.Code.STUDENT else None,
                department=d["department_obj"],
                external_id=d.get("external_id", ""),
                must_change_password=True,
            )
            user.set_password(password)
            user.save()
            row.user = user
            created.append(row)
        log_action(request, "import", None, message=_("Excel orqali %(n)s ta foydalanuvchi import qilindi")
                   % {"n": len(created)}, created=len(created), skipped=len(invalid))
    return ImportResult(rows=rows, created=created, errors=invalid, applied=True)
