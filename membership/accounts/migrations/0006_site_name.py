"""Name the site, so emails say "The Dot Com Experience" instead of Django's default "example.com"."""
from django.conf import settings
from django.db import migrations


def name_site(apps, schema_editor):
    Site = apps.get_model("sites", "Site")
    Site.objects.update_or_create(
        pk=settings.SITE_ID,
        defaults={"domain": "members.thedotx.com", "name": "The Dot Com Experience"})


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0005_profile_sms_opt_in_at"),
        ("sites", "0002_alter_domain_unique"),
    ]

    operations = [migrations.RunPython(name_site, migrations.RunPython.noop)]
