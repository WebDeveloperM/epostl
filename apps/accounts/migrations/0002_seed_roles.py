from django.db import migrations

ROLES = [
    ("admin", "Administrator", "Foydalanuvchilar, tashkiliy tuzilma va tizim sozlamalarini boshqaradi"),
    ("mentor", "Ustoz", "Talabalarga topshiriq beradi, ishlarni baholaydi va tavsiya beradi"),
    ("student", "Talaba", "Maqsad qo‘yadi, topshiriqlarni bajaradi, refleksiya yozadi"),
]


def seed(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    for code, name, description in ROLES:
        Role.objects.update_or_create(code=code, defaults={"name": name, "description": description})


class Migration(migrations.Migration):
    dependencies = [("accounts", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
