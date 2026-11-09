from django.db import migrations


def seed(apps, schema_editor):
    SystemSettings = apps.get_model("core", "SystemSettings")
    SystemSettings.objects.get_or_create(pk=1)


class Migration(migrations.Migration):
    dependencies = [("core", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
