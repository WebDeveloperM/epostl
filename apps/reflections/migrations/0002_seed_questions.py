from django.db import migrations

QUESTIONS = [
    ("Men nimaga erishmoqchi edim?", "Dars yoki faoliyat oldidan qo‘ygan maqsadingizni yozing."),
    ("Amalda nima sodir bo‘ldi?", "Jarayonni ketma-ket, faktlarga tayanib tasvirlang."),
    ("Nima yaxshi chiqdi? Buni qaysi dalil ko‘rsatadi?",
     "Video lavha, o‘quvchilar javoblari, kuzatuv natijalari kabi dalillarni keltiring."),
    ("Qayerda qiyinchilik bo‘ldi va nima sababdan?", "Qiyinchilik sabablarini tahlil qiling."),
    ("Keyingi safar nimani o‘zgartiraman?", "Aniq va amalga oshirsa bo‘ladigan qadamlarni yozing."),
]


def seed(apps, schema_editor):
    Question = apps.get_model("reflections", "ReflectionQuestion")
    for order, (text, help_text) in enumerate(QUESTIONS, start=1):
        Question.objects.get_or_create(text=text, defaults={"help_text": help_text, "order": order})


class Migration(migrations.Migration):
    dependencies = [("reflections", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
