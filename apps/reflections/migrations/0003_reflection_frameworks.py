from django.db import migrations, models

# (model, bosqich, tartib, savol, izoh)
QUESTIONS = [
    ("gibbs", "description", 1, "Nima sodir bo‘ldi?",
     "Voqeani ketma-ket, faqat faktlarga tayanib hikoya qiling."),
    ("gibbs", "feelings", 2, "Qanday his-tuyg‘ularni his qildingiz?",
     "Voqea paytida va undan keyin o‘zingizni qanday his qilganingizni yozing."),
    ("gibbs", "evaluation", 3, "Nima yaxshi, nima yomon chiqdi?",
     "Yaxshi va yomon tomonlarni dalillar bilan ko‘rsating."),
    ("gibbs", "analysis", 4, "Nima uchun bunday bo‘ldi?",
     "Sabablarni toping: nima yordam berdi, nima xalaqit qildi?"),
    ("gibbs", "conclusion", 5, "Bundan nimani o‘rgandingiz?",
     "Boshqacha nima qilish mumkin edi?"),
    ("gibbs", "action_plan", 6, "Keyingi safar nima qilasiz?",
     "Haqiqatan bajara oladigan aniq qadamlarni yozing."),
    ("kolb", "concrete_experience", 1, "Nima qildingiz?",
     "Tajribani tasvirlang: qayerda, kim bilan va nima bo‘ldi?"),
    ("kolb", "reflective_observation", 2, "Nimani payqadingiz?",
     "Voqeaga yon tomondan qarang. Nimani ko‘rdingiz va nimani o‘yladingiz?"),
    ("kolb", "abstract_conceptualization", 3, "Bu tajriba sizga nimani o‘rgatdi?",
     "Tajribani biror nazariya yoki qoida bilan bog‘lang."),
    ("kolb", "active_experimentation", 4, "Keyingi safar nimani sinab ko‘rasiz?",
     "Yangi g‘oyani ishda qo‘llash uchun aniq reja yozing."),
]


def seed(apps, schema_editor):
    Question = apps.get_model("reflections", "ReflectionQuestion")
    for framework, stage, order, text, help_text in QUESTIONS:
        Question.objects.get_or_create(
            framework=framework, text=text,
            defaults={"stage": stage, "order": order, "help_text": help_text})


def unseed(apps, schema_editor):
    Question = apps.get_model("reflections", "ReflectionQuestion")
    # javob berilgan savollarga tegmaymiz (PROTECT)
    Question.objects.filter(framework__in=["gibbs", "kolb"], answers__isnull=True).delete()


FRAMEWORK_CHOICES = [("gibbs", "Gibbs refleksiya sikli"), ("kolb", "Kolb tajriba orqali o‘rganish sikli"),
                     ("simple", "Qisqa refleksiya")]


class Migration(migrations.Migration):
    dependencies = [("reflections", "0002_seed_questions")]

    operations = [
        # Mavjud savollar va refleksiyalar — "Qisqa refleksiya" (5 savol) bo‘lib qoladi
        migrations.AddField(
            model_name="reflectionquestion", name="framework",
            field=models.CharField(max_length=20, choices=FRAMEWORK_CHOICES, default="simple",
                                   verbose_name="Model")),
        migrations.AddField(
            model_name="reflectionquestion", name="stage",
            field=models.CharField(max_length=40, blank=True, verbose_name="Bosqich")),
        migrations.AddField(
            model_name="reflection", name="framework",
            field=models.CharField(max_length=20, choices=FRAMEWORK_CHOICES, default="simple", db_index=True,
                                   verbose_name="Model")),
        # Yangi yozuvlar uchun standart — Gibbs
        migrations.AlterField(
            model_name="reflectionquestion", name="framework",
            field=models.CharField(max_length=20, choices=FRAMEWORK_CHOICES, default="gibbs",
                                   verbose_name="Model")),
        migrations.AlterField(
            model_name="reflection", name="framework",
            field=models.CharField(max_length=20, choices=FRAMEWORK_CHOICES, default="gibbs", db_index=True,
                                   verbose_name="Model")),
        migrations.AddField(
            model_name="reflectionanswer", name="stage",
            field=models.CharField(max_length=40, blank=True, verbose_name="Bosqich (nusxa)")),
        migrations.AlterModelOptions(
            name="reflectionquestion",
            options={"ordering": ["framework", "order", "id"], "verbose_name": "Refleksiya savoli",
                     "verbose_name_plural": "Refleksiya savollari"}),
        migrations.AddIndex(
            model_name="reflectionquestion",
            index=models.Index(fields=["framework", "is_active"], name="refl_q_framework_active")),
        migrations.RunPython(seed, unseed),
    ]
