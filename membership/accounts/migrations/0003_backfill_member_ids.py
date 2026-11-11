"""Step 2 of 3: give every existing account a unique Member ID.

Kept in its own migration (its own transaction) so the data update never shares a
transaction with schema changes on PostgreSQL.
"""
import secrets

from django.db import migrations


def backfill(apps, schema_editor):
    Profile = apps.get_model("accounts", "Profile")
    used = set(Profile.objects.exclude(member_id__isnull=True).exclude(member_id="")
               .values_list("member_id", flat=True))
    for profile in Profile.objects.all().order_by("pk"):
        changed = []
        if not profile.member_id:
            candidate = None
            while candidate is None or candidate in used:
                candidate = "DX-" + "".join(secrets.choice("0123456789") for _ in range(6))
            used.add(candidate)
            profile.member_id = candidate
            changed.append("member_id")
        if profile.role_since is None:
            profile.role_since = profile.created_at
            changed.append("role_since")
        if changed:
            profile.save(update_fields=changed)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_tiers_and_community_fields"),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
