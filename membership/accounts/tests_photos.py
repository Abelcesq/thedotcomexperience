"""Profile photos: upload, shrink, show, remove, and who may see them."""
import io

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from community.models import Block
from . import photos
from .models import Profile, ProfilePhoto

User = get_user_model()
ACTIVE = Profile.MembershipStatus.ACTIVE


def make(email, status=ACTIVE, **extra):
    user = User.objects.create_user(username=email, email=email, password="pw-Test-12345")
    p = user.profile
    p.membership_status = status
    p.display_name = email.split("@")[0].title()
    for k, v in extra.items():
        setattr(p, k, v)
    p.save()
    return p


def picture(fmt="JPEG", size=(900, 600), mode="RGB", name=None, exif=None):
    buf = io.BytesIO()
    image = Image.new(mode, size, (200, 40, 40, 128) if mode == "RGBA" else (200, 40, 40))
    kwargs = {"exif": exif} if exif else {}
    image.save(buf, fmt, **kwargs)
    types = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp", "GIF": "image/gif"}
    return SimpleUploadedFile(name or f"me.{fmt.lower()}", buf.getvalue(), content_type=types[fmt])


class PrepareTests(TestCase):
    def test_any_allowed_picture_becomes_a_small_square_jpeg(self):
        for fmt, mode in (("JPEG", "RGB"), ("PNG", "RGBA"), ("WEBP", "RGB")):
            data = photos.prepare(picture(fmt, mode=mode))
            out = Image.open(io.BytesIO(data))
            self.assertEqual((out.format, out.size, out.mode), ("JPEG", (400, 400), "RGB"), fmt)
            self.assertLess(len(data), 60_000)

    def test_hidden_details_such_as_location_are_stripped(self):
        exif = Image.Exif()
        exif[0x010F] = "PhoneMaker"          # camera make
        exif[0x8825] = {1: "N", 2: (38.0, 34.0, 54.0)}   # GPS position
        data = photos.prepare(picture("JPEG", exif=exif.tobytes()))
        self.assertEqual(len(Image.open(io.BytesIO(data)).getexif()), 0)
        self.assertNotIn(b"PhoneMaker", data)

    def test_sideways_phone_photos_are_turned_upright(self):
        # left half red, right half blue, tagged "rotate 90° to view"
        im = Image.new("RGB", (800, 400), (255, 0, 0)); im.paste((0, 0, 255), (400, 0, 800, 400))
        exif = Image.Exif(); exif[0x0112] = 6
        buf = io.BytesIO(); im.save(buf, "JPEG", exif=exif.tobytes(), quality=95)
        out = Image.open(io.BytesIO(photos.prepare(SimpleUploadedFile("p.jpg", buf.getvalue(), "image/jpeg"))))
        top, bottom = out.getpixel((200, 40)), out.getpixel((200, 360))
        self.assertGreater(top[0], 200); self.assertGreater(bottom[2], 200)   # now red above blue

    def test_things_that_are_not_photos_are_refused(self):
        bad = [
            SimpleUploadedFile("notes.jpg", b"<script>alert(1)</script>", "image/jpeg"),
            SimpleUploadedFile("page.png", b"\x89PNG\r\n\x1a\n" + b"junk" * 50, "image/png"),
            picture("GIF"),
            SimpleUploadedFile("empty.jpg", b"", "image/jpeg"),
        ]
        for upload in bad:
            with self.assertRaises(photos.PhotoError, msg=upload.name):
                photos.prepare(upload)
        with self.assertRaises(photos.PhotoError):
            photos.prepare(None)

    def test_oversized_uploads_are_refused(self):
        big = SimpleUploadedFile("big.jpg", b"0" * (photos.MAX_UPLOAD_BYTES + 1), "image/jpeg")
        with self.assertRaisesMessage(photos.PhotoError, "too large"):
            photos.prepare(big)
        old = photos.MAX_PIXELS
        photos.MAX_PIXELS = 1000
        try:
            with self.assertRaisesMessage(photos.PhotoError, "too large"):
                photos.prepare(picture("PNG", size=(200, 200)))
        finally:
            photos.MAX_PIXELS = old


class MemberPagePhotoTests(TestCase):
    def setUp(self):
        self.me = make("me@x.com")
        self.client.force_login(self.me.user)
        self.my_page = reverse("member_profile", args=[self.me.member_id])

    def test_my_page_offers_the_photo_picker_only_to_me(self):
        page = self.client.get(self.my_page)
        self.assertContains(page, f'action="{reverse("profile_photo")}"')
        self.assertContains(page, "Add a photo")
        other = make("other@x.com")
        theirs = self.client.get(reverse("member_profile", args=[other.member_id]))
        self.assertNotContains(theirs, reverse("profile_photo"))

    def test_uploading_replaces_the_initials_with_my_photo(self):
        go = self.client.post(reverse("profile_photo"), {"photo": picture(), "next": self.my_page})
        self.assertRedirects(go, self.my_page)
        self.me.refresh_from_db()
        self.assertTrue(self.me.has_photo)
        self.assertEqual(Image.open(io.BytesIO(bytes(self.me.photo.image))).size, (400, 400))
        page = self.client.get(self.my_page)
        self.assertContains(page, f'<img src="{self.me.photo_url}"')
        self.assertContains(page, "Change photo")
        self.assertContains(page, ">Remove</button>")
        # it also shows on the account page, in the directory and on the edit form
        for url in (reverse("profile"), reverse("member_directory"), reverse("profile_edit")):
            self.assertContains(self.client.get(url), self.me.photo_url.replace("&", "&amp;"), msg_prefix=url)

    def test_a_second_upload_replaces_the_first(self):
        self.client.post(reverse("profile_photo"), {"photo": picture()})
        first = Profile.objects.get(pk=self.me.pk).photo_updated_at
        self.client.post(reverse("profile_photo"), {"photo": picture("PNG")})
        self.assertEqual(ProfilePhoto.objects.filter(profile=self.me).count(), 1)
        self.assertGreaterEqual(Profile.objects.get(pk=self.me.pk).photo_updated_at, first)

    def test_removing_brings_the_initials_back(self):
        self.client.post(reverse("profile_photo"), {"photo": picture()})
        self.client.post(reverse("profile_photo"), {"remove": "1", "next": self.my_page})
        self.me.refresh_from_db()
        self.assertFalse(self.me.has_photo)
        self.assertFalse(ProfilePhoto.objects.filter(profile=self.me).exists())
        page = self.client.get(self.my_page)
        self.assertNotContains(page, "<img src=")
        self.assertContains(page, "Add a photo")

    def test_a_bad_file_changes_nothing_and_explains(self):
        go = self.client.post(reverse("profile_photo"),
                              {"photo": SimpleUploadedFile("x.jpg", b"not a picture", "image/jpeg"),
                               "next": self.my_page}, follow=True)
        self.assertContains(go, "couldn&#x27;t read that photo")
        self.assertFalse(Profile.objects.get(pk=self.me.pk).has_photo)
        nothing = self.client.post(reverse("profile_photo"), {"next": self.my_page}, follow=True)
        self.assertContains(nothing, "JPG, PNG or WebP")

    def test_upload_must_be_a_signed_in_post_and_stays_on_this_site(self):
        self.assertEqual(self.client.get(reverse("profile_photo")).status_code, 405)
        away = self.client.post(reverse("profile_photo"), {"photo": picture(), "next": "https://evil.example/"})
        self.assertRedirects(away, reverse("profile"))
        self.client.logout()
        anon = self.client.post(reverse("profile_photo"), {"photo": picture()})
        self.assertEqual(anon.status_code, 302)
        self.assertIn(reverse("account_login"), anon["Location"])

    def test_unpaid_accounts_can_set_a_photo_too(self):
        new = make("new@x.com", status="incomplete")
        self.client.force_login(new.user)
        self.client.post(reverse("profile_photo"), {"photo": picture()})
        new.refresh_from_db()
        self.assertTrue(new.has_photo)
        self.assertEqual(self.client.get(new.photo_url).status_code, 200)   # their own photo


class EditProfilePhotoTests(TestCase):
    def setUp(self):
        self.me = make("me@x.com")
        self.client.force_login(self.me.user)
        self.fields = {"display_name": "Me", "city": "Sacramento", "bio": "", "phone_country": "US",
                       "phone_number": "", "directory_visible": "on"}

    def test_the_edit_form_can_upload_and_remove_a_photo(self):
        page = self.client.get(reverse("profile_edit"))
        self.assertContains(page, 'enctype="multipart/form-data"')
        self.assertContains(page, 'name="photo"')
        self.assertNotContains(page, 'name="remove_photo"')            # nothing to remove yet
        self.assertRedirects(self.client.post(reverse("profile_edit"), {**self.fields, "photo": picture("PNG", mode="RGBA")}),
                             reverse("profile"))
        self.me.refresh_from_db()
        self.assertTrue(self.me.has_photo)
        self.assertContains(self.client.get(reverse("profile_edit")), 'name="remove_photo"')
        self.client.post(reverse("profile_edit"), {**self.fields, "remove_photo": "on"})
        self.me.refresh_from_db()
        self.assertFalse(self.me.has_photo)

    def test_saving_other_details_leaves_the_photo_alone(self):
        self.client.post(reverse("profile_photo"), {"photo": picture()})
        stamp = Profile.objects.get(pk=self.me.pk).photo_updated_at
        self.client.post(reverse("profile_edit"), {**self.fields, "city": "Davis"})
        me = Profile.objects.get(pk=self.me.pk)
        self.assertEqual((me.city, me.photo_updated_at), ("Davis", stamp))

    def test_a_bad_photo_is_reported_on_the_form_and_nothing_is_saved(self):
        page = self.client.post(reverse("profile_edit"),
                                {**self.fields, "city": "Davis", "photo": picture("GIF")})
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "JPG, PNG or WebP")
        me = Profile.objects.get(pk=self.me.pk)
        self.assertFalse(me.has_photo)
        self.assertNotEqual(me.city, "Davis")


class WhoCanSeePhotosTests(TestCase):
    def setUp(self):
        self.owner = make("owner@x.com")
        photos.save_bytes(self.owner, photos.prepare(picture()))
        self.owner.refresh_from_db()
        self.url = self.owner.photo_url

    def get_as(self, profile):
        self.client.force_login(profile.user)
        return self.client.get(self.url)

    def test_owner_and_other_active_members_can_see_it(self):
        mine = self.get_as(self.owner)
        self.assertEqual((mine.status_code, mine["Content-Type"]), (200, "image/jpeg"))
        self.assertIn("immutable", mine["Cache-Control"]); self.assertIn("private", mine["Cache-Control"])
        self.assertEqual(mine["X-Content-Type-Options"], "nosniff")
        self.assertEqual(Image.open(io.BytesIO(mine.content)).format, "JPEG")
        self.assertEqual(self.get_as(make("member@x.com")).status_code, 200)

    def test_people_outside_the_membership_cannot(self):
        self.assertEqual(self.get_as(make("unpaid@x.com", status="incomplete")).status_code, 404)
        self.client.logout()
        anon = self.client.get(self.url)
        self.assertEqual(anon.status_code, 302)
        self.assertIn(reverse("account_login"), anon["Location"])

    def test_blocked_and_hidden_members_follow_the_page_rules(self):
        blocked = make("blocked@x.com")
        Block.objects.create(blocker=self.owner.user, blocked=blocked.user)
        self.assertEqual(self.get_as(blocked).status_code, 404)
        stranger = make("stranger@x.com")
        self.owner.directory_visible = False
        self.owner.save()
        self.assertEqual(self.get_as(stranger).status_code, 404)        # hidden from the directory
        staff = make("staff@x.com"); staff.user.is_staff = True; staff.user.save()
        self.assertEqual(self.get_as(staff).status_code, 200)

    def test_members_without_a_photo_have_no_photo_address(self):
        plain = make("plain@x.com")
        self.assertEqual(plain.photo_url, "")
        self.client.force_login(plain.user)
        self.assertEqual(self.client.get(reverse("member_photo", args=[plain.member_id])).status_code, 404)
        self.assertEqual(self.client.get(reverse("member_photo", args=["DX-000000"])).status_code, 404)

    def test_deleting_the_account_deletes_the_photo(self):
        self.owner.user.delete()
        self.assertEqual(ProfilePhoto.objects.count(), 0)
