"""Modellardan ERD hujjatini (Mermaid + jadvallar) avtomatik generatsiya qiladi: docs/ERD.md

    python manage.py generate_erd
"""
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import models
from django.utils import translation

APP_ORDER = ["accounts", "organization", "subjects", "competencies", "goals", "assignments", "portfolios",
             "reflections", "assessments", "notifications", "audit", "core"]

TYPE_NAMES = {
    "AutoField": "serial", "BigAutoField": "bigserial", "CharField": "varchar", "TextField": "text",
    "SlugField": "varchar", "EmailField": "varchar", "URLField": "varchar", "BooleanField": "boolean",
    "DateField": "date", "DateTimeField": "timestamptz", "PositiveSmallIntegerField": "smallint",
    "PositiveIntegerField": "integer", "PositiveBigIntegerField": "bigint", "IntegerField": "integer",
    "JSONField": "jsonb", "GenericIPAddressField": "inet", "FileField": "varchar (fayl yo‘li)",
    "ImageField": "varchar (fayl yo‘li)", "ForeignKey": "bigint FK", "OneToOneField": "bigint FK UNIQUE",
}


def _type(field):
    name = field.get_internal_type()
    t = TYPE_NAMES.get(name, name)
    if getattr(field, "max_length", None) and name in ("CharField", "SlugField", "EmailField", "URLField"):
        t = f"varchar({field.max_length})"
    return t


def _constraints(model):
    lines = []
    for c in model._meta.constraints:
        if isinstance(c, models.UniqueConstraint):
            cond = f" WHERE {c.condition}" if c.condition is not None else ""
            lines.append(f"UNIQUE({', '.join(c.fields)}){cond} — `{c.name}`")
        elif isinstance(c, models.CheckConstraint):
            lines.append(f"CHECK {c.condition} — `{c.name}`")
    return lines


class Command(BaseCommand):
    help = "docs/ERD.md faylini modellardan generatsiya qiladi"

    def handle(self, *args, **options):
        # Hujjat o‘zbek tilida yoziladi (model maydon nomlari ham shu tilda chiqsin)
        with translation.override("uz"):
            self._write(options)

    def _write(self, options):
        model_list = []
        for label in APP_ORDER:
            model_list += list(apps.get_app_config(label).get_models())
        auth_m2m = []
        out = ["# Ma’lumotlar bazasi tuzilmasi (PostgreSQL ERD)", "",
               "> Bu fayl `python manage.py generate_erd` buyrug‘i bilan modellardan avtomatik yaratiladi — "
               "qo‘lda tahrirlamang.", "",
               "## Rivojlanish siklining ma’lumotlar bazasidagi bog‘liqligi", "",
               "```mermaid", "flowchart LR",
               "  B[\"1. Boshlang‘ich baholash<br/>assessments kind=baseline\"] --> G[\"2. Maqsad<br/>goals\"]",
               "  G --> A[\"3. Rejalashtirish<br/>assignments + assignment_targets\"]",
               "  A --> P[\"4. Amaliy ish<br/>portfolios → portfolio_versions → portfolio_files\"]",
               "  P --> R[\"5. Refleksiya<br/>reflections + reflection_answers (1:1 versiya)\"]",
               "  R --> M[\"6. Ustoz bahosi<br/>assessments kind=work + assessment_details, mentor_feedback\"]",
               "  M -->|qayta ishlash| P2[\"7. Takomillashtirish<br/>yangi portfolio_version (v+1)\"]",
               "  P2 --> C[\"8. Taqqoslash<br/>dastlabki vs keyingi assessment_details\"]",
               "  C -->|yangi sikl| G", "```", "",
               "* `portfolios.goal_id` va `portfolios.assignment_id` ishni maqsad va topshiriqqa bog‘laydi;",
               "* `portfolio_versions` hech qachon o‘chirilmaydi — har bir qayta yuklash yangi versiya;",
               "* `reflections.portfolio_version_id` va `assessments.portfolio_version_id` — UNIQUE (har versiyaga bitta);",
               "* `assessment_details.max_score` — mezon maksimal balining nusxasi (mezon keyin o‘zgarsa ham tarix buzilmaydi);",
               "* `reflection_answers.question_text` — savol matnining nusxasi (savol o‘zgarsa ham javob konteksti saqlanadi).",
               "", "## ER diagramma", "", "```mermaid", "erDiagram"]
        for model in model_list:
            table = model._meta.db_table
            for field in model._meta.get_fields():
                if isinstance(field, (models.ForeignKey, models.OneToOneField)) and field.concrete:
                    target = field.related_model._meta.db_table
                    if isinstance(field, models.OneToOneField):
                        card = "|o--o|" if field.null else "||--||"
                    else:
                        card = "|o--o{" if field.null else "||--o{"
                    out.append(f"  {target} {card} {table} : \"{field.name}\"")
                elif isinstance(field, models.ManyToManyField) and field.concrete:
                    target = field.related_model._meta.db_table
                    out.append(f"  {table} }}o--o{{ {target} : \"{field.name} (M2M)\"")
            if model is apps.get_model(settings.AUTH_USER_MODEL):
                auth_m2m.append(table)
        out += ["```", "", "## Jadvallar", ""]
        for model in model_list:
            meta = model._meta
            out.append(f"### `{meta.db_table}` — {meta.verbose_name_plural} (`{meta.label}`)")
            out.append("")
            out.append("| Maydon | Turi | Majburiy | Bog‘lanish / izoh |")
            out.append("|---|---|---|---|")
            for field in meta.concrete_fields:
                col = field.column
                note = []
                if field.primary_key:
                    note.append("PK")
                if isinstance(field, (models.ForeignKey, models.OneToOneField)):
                    on_delete = field.remote_field.on_delete.__name__
                    note.append(f"→ `{field.related_model._meta.db_table}.id` ({on_delete})")
                if field.unique and not field.primary_key:
                    note.append("UNIQUE")
                if field.choices:
                    note.append("qiymatlar: " + ", ".join(f"`{v}`" for v, _l in field.choices))
                if field.has_default() and not callable(field.default) and field.default not in ("", None):
                    note.append(f"standart: `{field.default}`")
                if field.db_index and not field.unique and not isinstance(field, models.ForeignKey):
                    note.append("INDEX")
                if field.primary_key or getattr(field, "auto_now", False) or getattr(field, "auto_now_add", False):
                    required = "avto"
                else:
                    required = "yo‘q" if (field.null or field.blank) else "ha"
                out.append(f"| `{col}` | {_type(field)} | {required} | {field.verbose_name}"
                           f"{'; ' + '; '.join(note) if note else ''} |")
            for field in meta.local_many_to_many:
                through = field.remote_field.through._meta.db_table
                out.append(f"| *{field.name}* | M2M | — | `{through}` orqali → "
                           f"`{field.related_model._meta.db_table}` |")
            constraints = _constraints(model)
            if constraints:
                out.append("")
                out.append("Cheklovlar: " + "; ".join(constraints))
            out.append("")
        path = Path(settings.BASE_DIR) / "docs" / "ERD.md"
        path.parent.mkdir(exist_ok=True)
        path.write_text("\n".join(out), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"ERD yaratildi: {path}"))
