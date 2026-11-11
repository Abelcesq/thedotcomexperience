"""Step 3 of 3: make the Member ID required + unique, and add the tier-change history."""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

ROLE_CHOICES = [
    ("member", "Member"), ("ambassador", "Ambassador"), ("local_leader", "Local Leader"),
    ("regional", "Regional"), ("admin", "Admin"),
]


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_backfill_member_ids"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="profile", name="member_id",
            field=models.CharField(db_index=True, editable=False, max_length=12, unique=True),
        ),
        migrations.CreateModel(
            name="TierChange",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False,
                                           verbose_name="ID")),
                ("from_role", models.CharField(choices=ROLE_CHOICES, max_length=20)),
                ("to_role", models.CharField(choices=ROLE_CHOICES, max_length=20)),
                ("note", models.CharField(blank=True, max_length=255)),
                ("changed_at", models.DateTimeField(auto_now_add=True)),
                ("changed_by", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="tier_changes_made", to=settings.AUTH_USER_MODEL)),
                ("profile", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="tier_changes",
                    to="accounts.profile")),
            ],
            options={"ordering": ["-changed_at"]},
        ),
    ]
