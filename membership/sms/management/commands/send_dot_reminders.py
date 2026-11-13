from django.core.management.base import BaseCommand

from sms import reminders, service


class Command(BaseCommand):
    help = ("Text members a reminder before their Dot meets. Run it every 10 minutes "
            "(Heroku Scheduler); each member is texted once per meeting.")

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="Show who would be texted, without sending anything.")

    def handle(self, *args, dry_run=False, **options):
        if not service.is_configured() and not dry_run:
            self.stdout.write("Texting is not configured (no Twilio settings); nothing sent.")
            return
        report = reminders.send_due(dry_run=dry_run)
        for dot, profile, outcome, body in report:
            self.stdout.write(f"{outcome}: {dot.name} -> {profile.member_id} | {body}")
        self.stdout.write(f"{len(report)} reminder(s) {'checked' if dry_run else 'processed'}.")
