from django.db import migrations

DATA = [
    ("planning", "Darsni rejalashtirish", "Dars maqsadi, tuzilmasi, vaqt va resurslarni rejalashtirish",
     "Darsni rejalashtirish"),
    ("explanation", "Mavzuni tushuntirish", "Mavzuni aniq, izchil va tushunarli bayon qilish",
     "Mavzuni tushuntirish aniqligi"),
    ("questioning", "Savol berish", "Turli darajadagi savollar bilan o‘quvchilarni fikrlashga undash",
     "Savol berish ko‘nikmasi"),
    ("communication", "O‘quvchilar bilan muloqot", "Hamkorlik, qayta aloqa va ijobiy muhit yaratish",
     "O‘quvchilar bilan muloqot"),
    ("reflection", "Refleksiya", "O‘z faoliyatini tahlil qilish va takomillashtirish",
     "Refleksiya va o‘zini tahlil qilish"),
]


def seed(apps, schema_editor):
    Competency = apps.get_model("competencies", "Competency")
    Criterion = apps.get_model("competencies", "AssessmentCriterion")
    for order, (code, name, description, criterion_name) in enumerate(DATA, start=1):
        comp, _ = Competency.objects.update_or_create(
            code=code, defaults={"name": name, "description": description, "order": order})
        Criterion.objects.get_or_create(
            name=criterion_name, defaults={"competency": comp, "max_score": 20, "order": order})


class Migration(migrations.Migration):
    dependencies = [("competencies", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
