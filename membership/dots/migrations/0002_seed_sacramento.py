from django.db import migrations


def seed_sacramento(apps, schema_editor):
    Dot = apps.get_model("dots", "Dot")
    Dot.objects.get_or_create(
        name="Sacramento Dot",
        city="Sacramento",
        defaults=dict(
            region="CA",
            lat=38.5816,
            lng=-121.4944,
            status="forming",
            description="The first Dot — forming now in Sacramento, California.",
        ),
    )


def unseed_sacramento(apps, schema_editor):
    Dot = apps.get_model("dots", "Dot")
    Dot.objects.filter(name="Sacramento Dot", city="Sacramento").delete()


class Migration(migrations.Migration):
    dependencies = [("dots", "0001_initial")]
    operations = [migrations.RunPython(seed_sacramento, unseed_sacramento)]
