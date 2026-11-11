from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import Profile
from accounts.tests import make
from .models import Block, Connection, Message, Report

R = Profile.Role
INCOMPLETE = Profile.MembershipStatus.INCOMPLETE


class CommunityBase(TestCase):
    def setUp(self):
        self.ana = make("ana@x.com", name="Ana Rivera", city="Sacramento")
        self.ben = make("ben@x.com", name="Ben Ortiz", city="Davis")
        self.amb = make("amb@x.com", R.AMBASSADOR, name="Cora Chartered")
        self.client.force_login(self.ana.user)

    def url(self, name, p=None):
        return reverse(name, args=[p.member_id]) if p else reverse(name)

    def connect(self, a, b):
        return Connection.objects.create(requester=a.user, addressee=b.user,
                                         status=Connection.Status.ACCEPTED)


class AccessTests(CommunityBase):
    def test_signed_out_visitors_are_sent_to_login(self):
        self.client.logout()
        for name in ("member_directory", "connections", "member_inbox", "my_team"):
            self.assertRedirects(self.client.get(self.url(name)),
                                 "/accounts/login/?next=" + self.url(name), fetch_redirect_response=False)

    def test_unpaid_signups_cannot_browse_members(self):
        newbie = make("new@x.com", status=INCOMPLETE)
        self.client.force_login(newbie.user)
        self.assertRedirects(self.client.get(self.url("member_directory")), reverse("join"))
        self.assertRedirects(self.client.get(self.url("member_profile", self.ben)), reverse("join"))


class DirectoryTests(CommunityBase):
    def test_lists_active_members_with_tier_and_never_shows_email_or_phone(self):
        self.ben.phone = "+19165550123"; self.ben.save()
        page = self.client.get(self.url("member_directory"))
        self.assertContains(page, "Ben Ortiz")
        self.assertContains(page, "Cora Chartered")
        self.assertContains(page, "Ambassador")
        self.assertNotContains(page, "ben@x.com")
        self.assertNotContains(page, "9165550123")
        profile = self.client.get(self.url("member_profile", self.ben))
        self.assertContains(profile, self.ben.member_id)
        self.assertNotContains(profile, "ben@x.com")
        self.assertNotContains(profile, "9165550123")

    def test_search_by_name_city_member_id_and_tier(self):
        get = lambda **kw: self.client.get(self.url("member_directory"), kw).content.decode()
        self.assertIn("Ben Ortiz", get(q="ortiz"))
        self.assertNotIn("Ben Ortiz", get(q="sacramento"))
        self.assertIn("Ben Ortiz", get(q=self.ben.member_id.lower()))
        html = get(tier="ambassador")
        self.assertIn("Cora Chartered", html)
        self.assertNotIn("Ben Ortiz", html)

    def test_hidden_inactive_and_blocked_members_do_not_appear(self):
        hidden = make("hid@x.com", name="Hidden Hank", directory_visible=False)
        lapsed = make("old@x.com", name="Lapsed Lou", status=Profile.MembershipStatus.CANCELED)
        Block.objects.create(blocker=self.ben.user, blocked=self.ana.user)
        html = self.client.get(self.url("member_directory")).content.decode()
        for name in ("Hidden Hank", "Lapsed Lou", "Ben Ortiz"):
            self.assertNotIn(name, html)
        self.assertEqual(self.client.get(self.url("member_profile", hidden)).status_code, 404)
        self.assertEqual(self.client.get(self.url("member_profile", self.ben)).status_code, 404)

    def test_hidden_member_is_still_visible_to_their_own_ambassador(self):
        hidden = make("hid@x.com", name="Hidden Hank", directory_visible=False, upline=self.amb)
        self.client.force_login(self.amb.user)
        self.assertEqual(self.client.get(self.url("member_profile", hidden)).status_code, 200)


class ConnectionTests(CommunityBase):
    def test_request_accept_then_connected(self):
        self.client.post(self.url("member_connect", self.ben))
        conn = Connection.between(self.ana.user, self.ben.user)
        self.assertEqual(conn.status, Connection.Status.PENDING)
        self.assertContains(self.client.get(self.url("member_profile", self.ben)), "Request sent")
        self.client.force_login(self.ben.user)
        self.assertContains(self.client.get(self.url("connections")), "Ana Rivera")
        self.client.post(self.url("member_accept", self.ana))
        conn.refresh_from_db()
        self.assertEqual(conn.status, Connection.Status.ACCEPTED)
        self.assertContains(self.client.get(self.url("member_profile", self.ana)), "Connected")

    def test_decline_removes_the_request_and_duplicates_are_ignored(self):
        self.client.post(self.url("member_connect", self.ben))
        self.client.post(self.url("member_connect", self.ben))
        self.assertEqual(Connection.objects.count(), 1)
        self.client.force_login(self.ben.user)
        self.client.post(self.url("member_decline", self.ana))
        self.assertEqual(Connection.objects.count(), 0)

    def test_requesting_someone_who_already_asked_you_connects_you(self):
        Connection.objects.create(requester=self.ben.user, addressee=self.ana.user)
        self.client.post(self.url("member_connect", self.ben))
        self.assertEqual(Connection.between(self.ana.user, self.ben.user).status,
                         Connection.Status.ACCEPTED)

    def test_cannot_accept_a_request_meant_for_someone_else(self):
        Connection.objects.create(requester=self.ben.user, addressee=self.amb.user)
        self.assertEqual(self.client.post(self.url("member_accept", self.ben)).status_code, 404)

    @override_settings(COMMUNITY_MAX_REQUESTS_PER_DAY=2)
    def test_daily_request_limit(self):
        others = [make(f"o{i}@x.com") for i in range(3)]
        for o in others:
            self.client.post(self.url("member_connect", o))
        self.assertEqual(Connection.objects.filter(requester=self.ana.user).count(), 2)

    def test_actions_require_post_and_ignore_offsite_next(self):
        self.assertEqual(self.client.get(self.url("member_connect", self.ben)).status_code, 405)
        self.connect(self.ana, self.ben)
        resp = self.client.post(self.url("member_disconnect", self.ben), {"next": "https://evil.example/"})
        self.assertRedirects(resp, reverse("connections"), fetch_redirect_response=False)


class MessagingTests(CommunityBase):
    def send(self, to, body="Hello there"):
        return self.client.post(self.url("member_thread", to), {"body": body})

    def test_strangers_cannot_message(self):
        self.assertRedirects(self.client.get(self.url("member_thread", self.ben)),
                             self.url("member_profile", self.ben))
        self.send(self.ben)
        self.assertEqual(Message.objects.count(), 0)

    def test_connected_members_can_message_and_reading_marks_it_read(self):
        self.connect(self.ana, self.ben)
        self.send(self.ben, "Coffee after the Dot?")
        msg = Message.objects.get()
        self.assertEqual((msg.sender, msg.recipient, msg.read_at), (self.ana.user, self.ben.user, None))
        self.client.force_login(self.ben.user)
        self.assertContains(self.client.get(self.url("member_inbox")), "Coffee after the Dot?")
        self.assertContains(self.client.get(reverse("profile")), 'class="count">1<')
        self.assertContains(self.client.get(self.url("member_thread", self.ana)), "Coffee after the Dot?")
        msg.refresh_from_db()
        self.assertIsNotNone(msg.read_at)

    def test_a_member_and_their_ambassador_can_message_without_connecting(self):
        self.ana.reports_to = self.amb; self.ana.save()
        self.send(self.amb, "See you Tuesday")
        self.assertEqual(Message.objects.count(), 1)
        self.client.force_login(self.amb.user)
        self.assertContains(self.client.get(self.url("my_team")), "Ana Rivera")

    def test_blocking_stops_messages_both_ways_and_removes_the_connection(self):
        self.connect(self.ana, self.ben)
        self.client.force_login(self.ben.user)
        self.client.post(self.url("member_block", self.ana))
        self.assertIsNone(Connection.between(self.ana.user, self.ben.user))
        self.client.post(self.url("member_thread", self.ana), {"body": "hi"})
        self.client.force_login(self.ana.user)
        self.send(self.ben)
        self.assertEqual(Message.objects.count(), 0)

    def test_message_text_is_escaped_and_length_is_limited(self):
        self.connect(self.ana, self.ben)
        self.send(self.ben, "<script>alert(1)</script>")
        page = self.client.get(self.url("member_thread", self.ben))
        self.assertNotContains(page, "<script>alert(1)</script>")
        self.assertContains(page, "&lt;script&gt;")
        self.send(self.ben, "x" * 2001)
        self.assertEqual(Message.objects.count(), 1)

    @override_settings(COMMUNITY_MAX_MESSAGES_PER_5_MIN=3)
    def test_message_rate_limit(self):
        self.connect(self.ana, self.ben)
        for i in range(5):
            self.send(self.ben, f"msg {i}")
        self.assertEqual(Message.objects.count(), 3)

    def test_cannot_read_a_thread_you_are_not_part_of(self):
        self.connect(self.ben, self.amb)
        Message.objects.create(sender=self.ben.user, recipient=self.amb.user, body="private words")
        self.assertNotContains(self.client.get(self.url("member_inbox")), "private words")
        resp = self.client.get(self.url("member_thread", self.ben), follow=True)
        self.assertNotContains(resp, "private words")

    def test_report_captures_the_conversation_for_staff(self):
        self.connect(self.ana, self.ben)
        Message.objects.create(sender=self.ben.user, recipient=self.ana.user, body="buy my course")
        self.client.post(self.url("member_report", self.ben), {"reason": "Selling in messages"})
        report = Report.objects.get()
        self.assertEqual((report.reporter, report.reported), (self.ana.user, self.ben.user))
        self.assertIn("buy my course", report.conversation_snapshot)


class TeamTests(CommunityBase):
    def test_team_page_is_for_charter_holders(self):
        self.assertRedirects(self.client.get(self.url("my_team")), reverse("profile"))
        self.ana.reports_to = self.amb; self.ana.save()
        self.client.force_login(self.amb.user)
        page = self.client.get(self.url("my_team"))
        self.assertContains(page, "Ana Rivera")
        self.assertContains(page, self.ana.member_id)
