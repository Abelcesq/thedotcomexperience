import base64
import hashlib
import hmac
from datetime import datetime, time
from io import StringIO
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import Profile
from accounts.tests import make
from dots.models import Dot, DotMembership
from dots.schedule import parse_time, parse_weekday, reminder_time
from . import reminders, service
from .models import SmsLog

PT = ZoneInfo("America/Los_Angeles")
TWILIO = dict(TWILIO_ACCOUNT_SID="ACtest", TWILIO_AUTH_TOKEN="secret-token",
              TWILIO_MESSAGING_SERVICE_SID="MGtest", SITE_URL="https://members.thedotx.com")
OK = service.Result(ok=True, provider_id="SM123")


def at(day, hour, minute=0):
    """A moment in November 2026, Pacific time. Nov 10 2026 is a Tuesday."""
    return datetime(2026, 11, day, hour, minute, tzinfo=PT)


class ScheduleTests(TestCase):
    def test_days_and_times_are_read_the_way_staff_type_them(self):
        for text, expected in [("Tuesday", 1), ("tuesdays", 1), ("Tues", 1), ("Thursday night", 3),
                               ("SUN", 6), ("wed", 2), ("", None), ("weekly", None)]:
            self.assertEqual(parse_weekday(text), expected, text)
        for text, expected in [("7:00 PM", time(19)), ("7pm", time(19)), ("7:30 p.m.", time(19, 30)),
                               ("19:00", time(19)), ("12 AM", time(0)), ("12:15 pm", time(12, 15)),
                               ("9 am", time(9)), ("evening", None), ("25:00", None), ("7:75 pm", None)]:
            self.assertEqual(parse_time(text), expected, text)

    def test_reminders_respect_quiet_hours(self):
        self.assertEqual(reminder_time(at(10, 19), 3), at(10, 16))        # 7pm meeting -> 4pm
        self.assertEqual(reminder_time(at(10, 9), 3), at(10, 8))          # 9am meeting -> 8am, not 6am
        self.assertEqual(reminder_time(at(10, 6, 30), 3), at(9, 18))      # 6:30am -> 6pm the evening before

    def test_a_dot_with_an_unreadable_schedule_is_rejected(self):
        dot = Dot(name="Test", city="Davis", meeting_night="Someday", meeting_time="late")
        with self.assertRaises(ValidationError) as ctx:
            dot.full_clean()
        self.assertEqual(set(ctx.exception.message_dict), {"meeting_night", "meeting_time"})
        Dot(name="Test", city="Davis", meeting_night="Tuesday", meeting_time="7:00 PM").full_clean()
        with self.assertRaises(ValidationError):
            Dot(name="Test", city="Davis", timezone="Mars/Olympus").full_clean()


@override_settings(**TWILIO)
class ReminderTests(TestCase):
    def setUp(self):
        self.amb = make("amb@x.com", Profile.Role.AMBASSADOR, name="Elena", phone="+19165550100", sms_opt_in=True)
        self.dot = Dot.objects.create(name="Midtown Dot", city="Sacramento", meeting_night="Tuesday",
                                      meeting_time="7:00 PM", location="1200 K St",
                                      ambassador=self.amb.user, status=Dot.Status.ACTIVE)
        self.ana = self.seat(make("ana@x.com", name="Ana", phone="+19165550101", sms_opt_in=True))
        self.no_consent = self.seat(make("nc@x.com", phone="+19165550102", sms_opt_in=False))
        self.no_phone = self.seat(make("np@x.com", phone="", sms_opt_in=True))
        self.lapsed = self.seat(make("old@x.com", phone="+19165550103", sms_opt_in=True,
                                     status=Profile.MembershipStatus.CANCELED))
        self.not_seated = make("ns@x.com", phone="+19165550104", sms_opt_in=True)

    def seat(self, profile):
        DotMembership.objects.create(dot=self.dot, user=profile.user)
        return profile

    def test_a_reminder_is_due_from_three_hours_before_until_the_meeting_starts(self):
        self.assertEqual(reminders.due(at(10, 15, 59)), [])
        self.assertEqual([d for d, _ in reminders.due(at(10, 16, 1))], [self.dot])
        self.assertEqual([d for d, _ in reminders.due(at(10, 18, 59))], [self.dot])
        self.assertEqual(reminders.due(at(10, 19, 1)), [])            # already started
        self.assertEqual(reminders.due(at(11, 16, 1)), [])            # Wednesday
        self.dot.status = Dot.Status.PAUSED; self.dot.save()
        self.assertEqual(reminders.due(at(10, 16, 1)), [])

    def test_only_opted_in_seated_members_in_good_standing_are_texted_once(self):
        with patch("sms.service._post_to_twilio", return_value=OK) as post:
            reminders.send_due(at(10, 16, 5))
            reminders.send_due(at(10, 16, 15))                         # the job runs again
            reminders.send_due(at(10, 18, 55))
        texted = sorted(call.args[0] for call in post.call_args_list)
        self.assertEqual(texted, ["+19165550100", "+19165550101"])     # the Ambassador and Ana, once each
        body = post.call_args_list[0].args[1]
        self.assertEqual(body, "The Dot Com Experience: Midtown Dot meets today at 7:00 PM at 1200 K St. "
                               "Reply STOP to opt out.")
        log = SmsLog.objects.get(user=self.ana.user)
        self.assertEqual((log.status, log.provider_id, str(log.meeting_date)), ("sent", "SM123", "2026-11-10"))

    def test_next_weeks_meeting_gets_its_own_reminder(self):
        with patch("sms.service._post_to_twilio", return_value=OK) as post:
            reminders.send_due(at(10, 16, 5))
            reminders.send_due(at(17, 16, 5))
        self.assertEqual(post.call_count, 4)

    def test_a_long_address_is_left_out_to_keep_it_one_text(self):
        self.dot.location = "The community room behind the old library annex, " * 3
        text = reminders.reminder_text(self.dot, at(10, 19), at(10, 16).date())
        self.assertLessEqual(len(text), 160)
        self.assertEqual(text, "The Dot Com Experience: Midtown Dot meets today at 7:00 PM. Reply STOP to opt out.")
        self.assertLessEqual(len(reminders.confirmation_text()), 160)

    def test_an_early_meeting_is_announced_the_evening_before_as_tomorrow(self):
        self.dot.meeting_time = "6:30 AM"; self.dot.save()
        with patch("sms.service._post_to_twilio", return_value=OK) as post:
            reminders.send_due(at(9, 18, 5))
        self.assertIn("meets tomorrow at 6:30 AM", post.call_args_list[0].args[1])

    def test_if_twilio_says_the_member_opted_out_we_stop_texting_them(self):
        gone = service.Result(ok=False, error="Attempt to send to unsubscribed recipient", code=21610)
        with patch("sms.service._post_to_twilio", return_value=gone):
            reminders.send_due(at(10, 16, 5))
        self.ana.refresh_from_db()
        self.assertFalse(self.ana.sms_opt_in)
        self.assertEqual(SmsLog.objects.get(user=self.ana.user).status, "failed")

    def test_if_twilio_is_unreachable_the_next_run_tries_again(self):
        down = service.Result(ok=False, error="Could not reach Twilio")
        with patch("sms.service._post_to_twilio", return_value=down):
            reminders.send_due(at(10, 16, 5))
        self.assertEqual(SmsLog.objects.count(), 0)
        with patch("sms.service._post_to_twilio", return_value=OK) as post:
            reminders.send_due(at(10, 16, 15))
        self.assertEqual(post.call_count, 2)

    def test_dry_run_sends_nothing(self):
        out = StringIO()
        with patch("sms.service._post_to_twilio") as post, patch("sms.reminders.timezone.now", return_value=at(10, 16, 5)):
            call_command("send_dot_reminders", "--dry-run", stdout=out)
        post.assert_not_called()
        self.assertIn("would send: Midtown Dot", out.getvalue())
        self.assertEqual(SmsLog.objects.count(), 0)


class NotConfiguredTests(TestCase):
    def test_without_twilio_settings_nothing_is_sent_or_logged(self):
        ana = make("ana@x.com", phone="+19165550101", sms_opt_in=True)
        with patch("sms.service._post_to_twilio") as post:
            self.assertIsNone(reminders.send_test(ana))
            out = StringIO()
            call_command("send_dot_reminders", stdout=out)
        post.assert_not_called()
        self.assertIn("not configured", out.getvalue())
        self.assertEqual(SmsLog.objects.count(), 0)


@override_settings(**TWILIO)
class InboundTests(TestCase):
    def setUp(self):
        self.ana = make("ana@x.com", phone="+19165550101", sms_opt_in=True)
        self.url = reverse("sms_inbound")

    def post(self, body, token="secret-token", sender="+19165550101"):
        params = {"From": sender, "Body": body, "To": "+18335550000"}
        payload = "https://members.thedotx.com/sms/inbound/" + "".join(k + params[k] for k in sorted(params))
        sig = base64.b64encode(hmac.new(token.encode(), payload.encode(), hashlib.sha1).digest()).decode()
        return self.client.post(self.url, params, headers={"X-Twilio-Signature": sig})

    def test_stop_switches_reminders_off_and_start_switches_them_back_on(self):
        self.assertEqual(self.post(" stop ").status_code, 200)
        self.ana.refresh_from_db()
        self.assertFalse(self.ana.sms_opt_in)
        self.post("START")
        self.ana.refresh_from_db()
        self.assertTrue(self.ana.sms_opt_in)
        self.assertIsNotNone(self.ana.sms_opt_in_at)

    def test_other_replies_change_nothing(self):
        self.post("thanks, see you there")
        self.ana.refresh_from_db()
        self.assertTrue(self.ana.sms_opt_in)

    def test_requests_not_signed_by_twilio_are_refused(self):
        self.assertEqual(self.post("STOP", token="wrong").status_code, 403)
        self.assertEqual(self.client.post(self.url, {"From": "+19165550101", "Body": "STOP"}).status_code, 403)
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.ana.refresh_from_db()
        self.assertTrue(self.ana.sms_opt_in)


@override_settings(**TWILIO)
class OptInTests(TestCase):
    def setUp(self):
        self.me = make("me@x.com")
        self.client.force_login(self.me.user)

    def save(self, **extra):
        data = {"display_name": "Mia", "city": "Davis", "bio": "", "directory_visible": "on",
                "phone_country": "US", "phone_number": "(916) 555-0123", **extra}
        with patch("sms.service._post_to_twilio", return_value=OK) as post:
            self.client.post(reverse("profile_edit"), data)
        self.me.refresh_from_db()
        return post

    def test_opting_in_records_when_and_sends_one_confirmation(self):
        post = self.save(sms_opt_in="on")
        self.assertIsNotNone(self.me.sms_opt_in_at)
        self.assertEqual(post.call_count, 1)
        self.assertIn("Reply HELP for help, STOP to opt out", post.call_args.args[1])
        self.assertEqual(self.save(sms_opt_in="on").call_count, 0)           # saving again: no repeat
        self.assertEqual(self.save(sms_opt_in="on", phone_number="(916) 555-0199").call_count, 1)  # new number

    def test_opting_out_clears_the_record_and_sends_nothing(self):
        self.save(sms_opt_in="on")
        post = self.save()
        self.assertFalse(self.me.sms_opt_in)
        self.assertIsNone(self.me.sms_opt_in_at)
        self.assertEqual(post.call_count, 0)


class AdminTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser("boss", "boss@x.com", "pw-Test-12345")
        self.client.force_login(self.admin)
        self.ana = make("ana@x.com", phone="+19165550101", sms_opt_in=True)
        self.quiet = make("q@x.com", phone="+19165550102", sms_opt_in=False)
        self.url = reverse("admin:accounts_profile_changelist")

    def test_dot_and_log_admin_pages_load_and_show_reminder_status(self):
        Dot.objects.create(name="Midtown Dot", city="Sacramento", meeting_night="Tuesday", meeting_time="7:00 PM")
        page = self.client.get(reverse("admin:dots_dot_changelist"))
        self.assertContains(page, "Next reminder text")
        self.assertContains(page, "No meeting day/time set")               # the seeded Sacramento Dot
        self.assertEqual(self.client.get(reverse("admin:dots_dot_add")).status_code, 200)
        self.assertEqual(self.client.get(reverse("admin:sms_smslog_changelist")).status_code, 200)

    def test_test_text_action_explains_when_texting_is_off(self):
        data = {"action": "send_test_text", "_selected_action": [self.ana.pk]}
        self.assertContains(self.client.post(self.url, data, follow=True), "switched on yet")

    @override_settings(**TWILIO)
    def test_test_text_action_texts_only_opted_in_members(self):
        data = {"action": "send_test_text", "_selected_action": [self.ana.pk, self.quiet.pk]}
        with patch("sms.service._post_to_twilio", return_value=OK) as post:
            page = self.client.post(self.url, data, follow=True)
        self.assertEqual([c.args[0] for c in post.call_args_list], ["+19165550101"])
        self.assertContains(page, "Test text sent to 1 member")
        self.assertContains(page, "1 skipped")
