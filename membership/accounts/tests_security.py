"""Sign-up protection, email verification by code, the email sender, and two-step verification."""
import re
import time
from unittest.mock import patch

from allauth.account.models import EmailAddress
from allauth.mfa.models import Authenticator
from allauth.mfa.totp.internal import auth as totp
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from dots.models import DotApplication, Waitlist

User = get_user_model()
PASSWORD = "correct-horse-battery-9"
VERIFY = dict(ACCOUNT_EMAIL_VERIFICATION="mandatory", ACCOUNT_EMAIL_VERIFICATION_BY_CODE_ENABLED=True)
CAPTCHA = dict(RECAPTCHA_SITE_KEY="site", RECAPTCHA_SECRET_KEY="secret", RECAPTCHA_MIN_SCORE=0.5)
HUMAN = {"success": True, "score": 0.9}
ROBOT = {"success": True, "score": 0.1}


def signup_data(email="ana@example.com", **extra):
    return {"first_name": "Ana", "email": email, "password1": PASSWORD, "password2": PASSWORD,
            "coc_agreed": "on", **extra}


def code_in(message):
    return re.search(r"\b(\d{6})\b", message.body).group(1)


class Base(TestCase):
    def setUp(self):
        cache.clear()          # sign-in rate limits are kept in the cache


@override_settings(**VERIFY)
class EmailCodeSignupTests(Base):
    def test_a_new_member_must_enter_the_emailed_code_before_they_are_signed_in(self):
        resp = self.client.post(reverse("account_signup"), signup_data())
        self.assertRedirects(resp, reverse("account_email_verification_sent"), fetch_redirect_response=False)
        self.assertNotIn("_auth_user_id", self.client.session)             # not signed in yet
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["ana@example.com"])
        self.assertTrue(mail.outbox[0].subject.startswith("The Dot Com Experience"))
        page = self.client.get(reverse("account_email_verification_sent"))
        self.assertContains(page, "ana@example.com")
        self.assertContains(page, 'class="brand"', msg_prefix="uses the site's own look")
        self.assertContains(page, 'class="field formrow"', msg_prefix="code box uses the site's field styling")

        wrong = self.client.post(reverse("account_email_verification_sent"), {"code": "000000"})
        self.assertEqual(wrong.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

        self.client.post(reverse("account_email_verification_sent"), {"code": code_in(mail.outbox[0])})
        self.assertIn("_auth_user_id", self.client.session)
        self.assertTrue(EmailAddress.objects.get(email="ana@example.com").verified)
        self.assertTrue(User.objects.get(email="ana@example.com").profile.coc_agreed)

    def test_an_unverified_account_cannot_sign_in_without_the_code(self):
        self.client.post(reverse("account_signup"), signup_data())
        self.client.logout(); cache.clear(); mail.outbox.clear()
        resp = self.client.post(reverse("account_login"), {"login": "ana@example.com", "password": PASSWORD})
        self.assertRedirects(resp, reverse("account_email_verification_sent"), fetch_redirect_response=False)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(len(mail.outbox), 1)                              # a fresh code was sent

    def test_the_hidden_bot_trap_creates_nothing_but_looks_like_success(self):
        resp = self.client.post(reverse("account_signup"), signup_data("bot@spam.test", website="http://spam"))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(User.objects.filter(email="bot@spam.test").exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_signup_page_hides_the_trap_field_from_people(self):
        page = self.client.get(reverse("account_signup")).content.decode()
        self.assertIn('name="website"', page)
        self.assertIn("position: absolute", page)


@override_settings(**CAPTCHA)
class CaptchaTests(Base):
    def test_signup_needs_a_human_looking_recaptcha_answer(self):
        url = reverse("account_signup")
        self.assertContains(self.client.get(url), "recaptcha/api.js?render=site")
        with patch("thedotx.captcha._ask_google", return_value=HUMAN) as google:
            self.assertContains(self.client.post(url, signup_data()), "confirm you’re not a robot")   # no token sent
            google.assert_not_called()
        with patch("thedotx.captcha._ask_google", return_value=ROBOT):
            self.client.post(url, signup_data(**{"g-recaptcha-response": "tok"}))
        self.assertFalse(User.objects.filter(email="ana@example.com").exists())
        with patch("thedotx.captcha._ask_google", return_value={"success": True, "score": 0.9, "action": "waitlist"}):
            self.client.post(url, signup_data(**{"g-recaptcha-response": "tok"}))     # token from another form
        self.assertFalse(User.objects.filter(email="ana@example.com").exists())
        with patch("thedotx.captcha._ask_google", return_value={"success": True, "score": 0.9, "action": "signup"}):
            self.client.post(url, signup_data(**{"g-recaptcha-response": "tok"}))
        self.assertTrue(User.objects.filter(email="ana@example.com").exists())

    def test_if_google_is_unreachable_real_people_are_not_locked_out(self):
        with patch("thedotx.captcha._ask_google", side_effect=OSError("down")):
            self.client.post(reverse("account_signup"), signup_data(**{"g-recaptcha-response": "tok"}))
        self.assertTrue(User.objects.filter(email="ana@example.com").exists())

    def test_waitlist_and_dot_request_forms_are_protected_too(self):
        wait = {"first_name": "Ben", "email": "ben@example.com", "city": "Davis", "intent": "join"}
        with patch("thedotx.captcha._ask_google", return_value=ROBOT):
            self.client.post(reverse("waitlist_signup"), {**wait, "g-recaptcha-response": "tok"})
        self.assertEqual(Waitlist.objects.count(), 0)
        with patch("thedotx.captcha._ask_google", return_value=HUMAN):
            self.client.post(reverse("waitlist_signup"), {**wait, "g-recaptcha-response": "tok", "website": "spam"})
            self.assertEqual(Waitlist.objects.count(), 0, "bot trap: nothing saved")
            self.client.post(reverse("waitlist_signup"), {**wait, "g-recaptcha-response": "tok"})
            self.assertEqual(Waitlist.objects.count(), 1)
            apply = {"full_name": "Ben Ortiz", "email": "ben@example.com", "city": "Davis", "why": "x", "agree": "on"}
            self.client.post(reverse("request_dot"), {**apply, "g-recaptcha-response": "tok", "website": "spam"})
            self.assertEqual(DotApplication.objects.count(), 0, "bot trap: nothing saved")
            self.client.post(reverse("request_dot"), {**apply, "g-recaptcha-response": "tok"})
            self.assertEqual(DotApplication.objects.count(), 1)

    def test_forms_show_no_recaptcha_until_the_secret_key_is_set(self):
        with self.settings(RECAPTCHA_SECRET_KEY=""):
            self.assertNotContains(self.client.get(reverse("account_signup")), "recaptcha")
            self.client.post(reverse("account_signup"), signup_data())
        self.assertTrue(User.objects.filter(email="ana@example.com").exists())


@override_settings(EMAIL_BACKEND="thedotx.email.ResendEmailBackend", RESEND_API_KEY="re_test",
                   DEFAULT_FROM_EMAIL="The Dot Com Experience <info@thedotcomexperience.com>")
class ResendBackendTests(Base):
    def test_email_goes_out_through_resend(self):
        with patch("thedotx.email._post", return_value=200) as post:
            sent = mail.send_mail("Your code", "123456", None, ["ana@example.com"])
        self.assertEqual(sent, 1)
        payload = post.call_args.args[0]
        self.assertEqual(payload["to"], ["ana@example.com"])
        self.assertEqual((payload["subject"], payload["text"]), ("Your code", "123456"))
        self.assertIn("info@thedotcomexperience.com", payload["from"])

    def test_a_delivery_failure_is_raised_not_hidden(self):
        with patch("thedotx.email._post", side_effect=OSError("resend down")):
            with self.assertLogs("thedotx.email", level="ERROR"), self.assertRaises(OSError):
                mail.send_mail("Your code", "123456", None, ["ana@example.com"])


class TwoStepTests(Base):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(username="ana@example.com", email="ana@example.com", password=PASSWORD)
        profile = self.user.profile
        profile.membership_status = "active"; profile.save()

    def sign_in(self):
        return self.client.post(reverse("account_login"), {"login": "ana@example.com", "password": PASSWORD})

    def current_code(self, secret):
        return totp.format_hotp_value(totp.hotp_value(secret, int(time.time()) // 30))

    def test_profile_asks_members_to_turn_it_on_once_their_email_is_confirmed(self):
        self.sign_in()
        page = self.client.get(reverse("profile"))
        self.assertContains(page, "Protect your account with two-step verification")
        self.assertContains(page, "First, confirm your email")
        EmailAddress.objects.create(user=self.user, email=self.user.email, verified=True, primary=True)
        self.assertContains(self.client.get(reverse("profile")), reverse("mfa_activate_totp"))

    def test_setting_up_google_authenticator_then_signing_in_needs_a_code(self):
        EmailAddress.objects.create(user=self.user, email=self.user.email, verified=True, primary=True)
        self.sign_in()
        # Changing security settings first asks for the password again.
        ask = self.client.get(reverse("mfa_activate_totp"))
        self.assertRedirects(ask, reverse("account_reauthenticate") + "?next=/accounts/2fa/totp/activate/",
                             fetch_redirect_response=False)
        self.assertEqual(self.client.get(ask["Location"]).status_code, 200)
        self.client.post(ask["Location"], {"password": PASSWORD})
        setup = self.client.get(reverse("mfa_activate_totp"))
        self.assertEqual(setup.status_code, 200)
        self.assertContains(setup, "data:image/svg+xml", msg_prefix="shows a QR code to scan")
        secret = setup.context["form"].secret
        self.assertEqual(self.client.post(reverse("mfa_activate_totp"), {"code": "000000"}).status_code, 200)
        self.assertFalse(Authenticator.objects.filter(user=self.user).exists())
        self.client.post(reverse("mfa_activate_totp"), {"code": self.current_code(secret)})
        self.assertTrue(Authenticator.objects.filter(user=self.user, type=Authenticator.Type.TOTP).exists())
        profile = self.client.get(reverse("profile"))
        self.assertNotContains(profile, "Protect your account with two-step verification")
        self.assertContains(profile, 'class="pill on">On<')

        # Next sign-in: the password alone is not enough.
        self.client.logout(); cache.clear()
        resp = self.sign_in()
        self.assertRedirects(resp, reverse("mfa_authenticate"), fetch_redirect_response=False)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(self.client.get(reverse("profile")).status_code, 302)
        self.client.post(reverse("mfa_authenticate"), {"code": "000000"})
        self.assertNotIn("_auth_user_id", self.client.session)
        # A backup (recovery) code works when the phone isn't to hand.
        backup = Authenticator.objects.get(user=self.user, type=Authenticator.Type.RECOVERY_CODES)
        self.client.post(reverse("mfa_authenticate"), {"code": backup.wrap().get_unused_codes()[0]})
        self.assertIn("_auth_user_id", self.client.session)
