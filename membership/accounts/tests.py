import re

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from .models import Profile, TierChange

User = get_user_model()
R = Profile.Role
ACTIVE = Profile.MembershipStatus.ACTIVE


def make(email, role=R.MEMBER, status=ACTIVE, name=None, upline=None, **extra):
    user = User.objects.create_user(username=email, email=email, password="pw-Test-12345")
    p = user.profile
    p.role, p.membership_status, p.reports_to = role, status, upline
    p.display_name = name or email.split("@")[0].title()
    for k, v in extra.items():
        setattr(p, k, v)
    p.save()
    return p


class MemberIdTests(TestCase):
    def test_every_new_account_is_a_member_with_a_unique_id(self):
        ids = set()
        for i in range(40):
            p = User.objects.create_user(username=f"u{i}", email=f"u{i}@x.com").profile
            self.assertEqual(p.role, R.MEMBER)
            self.assertRegex(p.member_id, r"^DX-\d{6}$")
            self.assertIsNotNone(p.role_since)
            ids.add(p.member_id)
        self.assertEqual(len(ids), 40)

    def test_member_id_never_changes_on_save(self):
        p = make("a@x.com")
        first = p.member_id
        p.city = "Sacramento"
        p.save()
        self.assertEqual(Profile.objects.get(pk=p.pk).member_id, first)

    def test_public_name_never_falls_back_to_email(self):
        user = User.objects.create_user(username="private@x.com", email="private@x.com")
        self.assertEqual(user.profile.name, "Member")
        self.assertNotIn("@", str(user.profile))


class LadderTests(TestCase):
    def setUp(self):
        self.regional = make("reg@x.com", R.REGIONAL)
        self.leader = make("ll@x.com", R.LOCAL_LEADER, upline=self.regional)
        self.amb = make("amb@x.com", R.AMBASSADOR, upline=self.leader)
        self.amb2 = make("amb2@x.com", R.AMBASSADOR, upline=self.leader)
        self.m1 = make("m1@x.com", upline=self.amb)
        self.m2 = make("m2@x.com", upline=self.amb)
        self.m3 = make("m3@x.com", upline=self.amb, status=Profile.MembershipStatus.CANCELED)
        self.m4 = make("m4@x.com", upline=self.amb2)

    def test_upline_must_be_the_tier_directly_above(self):
        self.m1.reports_to = self.leader           # a member cannot report to a local leader
        with self.assertRaises(ValidationError):
            self.m1.full_clean()
        self.m1.reports_to = self.amb
        self.m1.full_clean()
        self.regional.reports_to = self.leader     # the top of the ladder has no upline
        with self.assertRaises(ValidationError):
            self.regional.full_clean()
        self.amb.reports_to = self.amb             # never yourself
        with self.assertRaises(ValidationError):
            self.amb.full_clean()

    def test_counts_roll_up_and_active_means_paying_non_charter_members(self):
        a = self.amb.team_stats()
        self.assertEqual((a["members"], a["active_members"], a["cap"]), (3, 2, 30))
        l = self.leader.team_stats()
        self.assertEqual((l["ambassadors"], l["members"], l["active_members"], l["cap"]), (2, 4, 3, 10))
        r = self.regional.team_stats()
        self.assertEqual((r["local_leaders"], r["ambassadors"], r["members"], r["active_members"]),
                         (1, 2, 4, 3))
        self.assertFalse(a["over_cap"])

    def test_over_cap_is_flagged(self):
        with self.settings(TIER_CAPS={"members_per_ambassador": 2,
                                      "ambassadors_per_local_leader": 10,
                                      "local_leaders_per_regional": 10}):
            self.assertTrue(self.amb.team_stats()["over_cap"])

    def test_promotion_keeps_the_organization_consistent_and_is_logged(self):
        orphaned = self.amb.change_role(R.LOCAL_LEADER, note="promoted")
        self.amb.refresh_from_db()
        self.assertEqual(self.amb.role, R.LOCAL_LEADER)
        self.assertIsNone(self.amb.reports_to)          # a Local Leader can't report to a Local Leader
        self.assertEqual(orphaned, 3)                   # their members need a new Ambassador
        self.m1.refresh_from_db()
        self.assertIsNone(self.m1.reports_to)
        change = TierChange.objects.get(profile=self.amb)
        self.assertEqual((change.from_role, change.to_role), (R.AMBASSADOR, R.LOCAL_LEADER))

    def test_member_promoted_to_ambassador_leaves_their_old_group(self):
        self.m1.change_role(R.AMBASSADOR)
        self.m1.refresh_from_db()
        self.assertIsNone(self.m1.reports_to)
        self.assertEqual(self.amb.team_stats()["members"], 2)


class AdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("boss", "boss@x.com", "pw-Test-12345")
        self.client.force_login(self.admin)
        self.amb = make("amb@x.com", R.AMBASSADOR)
        self.m1 = make("m1@x.com")
        self.m2 = make("m2@x.com")
        self.url = reverse("admin:accounts_profile_changelist")

    def test_admin_pages_load(self):
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertEqual(self.client.get(reverse("admin:accounts_profile_organization")).status_code, 200)
        page = self.client.get(reverse("admin:accounts_profile_change", args=[self.m1.pk]))
        self.assertContains(page, self.m1.member_id)
        self.assertEqual(self.client.get(self.url, {"q": self.m1.member_id}).status_code, 200)

    def test_bulk_set_tier_action(self):
        self.client.post(self.url, {"action": "make_ambassador", "_selected_action": [self.m1.pk]})
        self.m1.refresh_from_db()
        self.assertEqual(self.m1.role, R.AMBASSADOR)
        self.assertEqual(TierChange.objects.filter(profile=self.m1, changed_by=self.admin).count(), 1)

    def test_assign_upline_by_member_id(self):
        data = {"action": "assign_upline", "_selected_action": [self.m1.pk, self.m2.pk, self.amb.pk]}
        self.assertContains(self.client.post(self.url, data), "Member ID")       # asks for the ID first
        data.update({"apply": "Assign", "upline_member_id": self.amb.member_id.lower()})
        self.client.post(self.url, data)
        self.m1.refresh_from_db(); self.m2.refresh_from_db(); self.amb.refresh_from_db()
        self.assertEqual(self.m1.reports_to, self.amb)
        self.assertEqual(self.m2.reports_to, self.amb)
        self.assertIsNone(self.amb.reports_to)              # wrong tier → skipped, not mis-filed
        self.assertEqual(self.amb.team_stats()["members"], 2)

    def test_assign_upline_rejects_unknown_id(self):
        data = {"action": "assign_upline", "_selected_action": [self.m1.pk],
                "apply": "Assign", "upline_member_id": "DX-000000"}
        self.assertContains(self.client.post(self.url, data), "No member has that Member ID")

    def test_changing_tier_on_the_edit_page_is_logged(self):
        url = reverse("admin:accounts_profile_change", args=[self.m1.pk])
        form = self.client.get(url).context["adminform"].form
        data = {k: ("" if v is None else v) for k, v in form.initial.items()}
        data.update({"role": R.AMBASSADOR, "reports_to": "", "user": self.m1.user_id,
                     "tier_changes-TOTAL_FORMS": 0, "tier_changes-INITIAL_FORMS": 0})
        data = {k: v for k, v in data.items() if not isinstance(v, bool) or v}
        resp = self.client.post(url, data)
        self.assertEqual(resp.status_code, 302, getattr(resp, "context", None) and resp.context["adminform"].form.errors)
        self.m1.refresh_from_db()
        self.assertEqual(self.m1.role, R.AMBASSADOR)
        self.assertTrue(TierChange.objects.filter(profile=self.m1, to_role=R.AMBASSADOR).exists())


class OwnProfilePageTests(TestCase):
    def test_profile_page_shows_member_id_and_tier(self):
        amb = make("amb@x.com", R.AMBASSADOR, name="Ana Ambassador")
        me = make("me@x.com", upline=amb, name="Mia Member")
        self.client.force_login(me.user)
        page = self.client.get(reverse("profile"))
        self.assertContains(page, me.member_id)
        self.assertContains(page, "Ana Ambassador")
        self.assertContains(page, "Your Ambassador")

    def test_member_can_edit_bio_and_hide_from_directory(self):
        me = make("me@x.com")
        self.client.force_login(me.user)
        self.client.post(reverse("profile_edit"), {"display_name": "Mia", "city": "Davis",
                                                    "bio": "Here to grow.", "phone": ""})
        me.refresh_from_db()
        self.assertEqual(me.bio, "Here to grow.")
        self.assertFalse(me.directory_visible)
