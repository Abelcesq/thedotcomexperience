"""Step 1 of 3: add the Member ID (nullable for now), tier ladder, upline link, profile fields."""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

ROLE_CHOICES = [
    ("member", "Member"), ("ambassador", "Ambassador"), ("local_leader", "Local Leader"),
    ("regional", "Regional"), ("admin", "Admin"),
]


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile", name="member_id",
            field=models.CharField(max_length=12, null=True, editable=False),
        ),
        migrations.AddField(
            model_name="profile", name="bio",
            field=models.CharField(blank=True, max_length=300),
        ),
        migrations.AddField(
            model_name="profile", name="directory_visible",
            field=models.BooleanField(
                default=True,
                help_text="Show this member in the member directory and let other members view their profile."),
        ),
        migrations.AddField(
            model_name="profile", name="role_since",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="profile", name="reports_to",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name="downline", to="accounts.profile",
                verbose_name="reports to (upline)",
                help_text="A Member reports to an Ambassador, an Ambassador to a Local Leader, "
                          "a Local Leader to a Regional."),
        ),
        migrations.AlterField(
            model_name="profile", name="role",
            field=models.CharField(choices=ROLE_CHOICES, default="member", max_length=20,
                                   verbose_name="tier"),
        ),
    ]
