"""Profile photos: check an uploaded picture, shrink it, and save it.

Every upload is re-drawn as a small square JPEG. That keeps photos light, removes hidden
details phones add to pictures (such as where the photo was taken), and means nothing but
a plain image is ever stored or served.
"""
import io

from django.db import transaction
from django.utils import timezone
from PIL import Image, ImageOps, UnidentifiedImageError

from .models import ProfilePhoto

SIZE = 400                              # saved as 400 x 400 pixels
MAX_UPLOAD_BYTES = 10 * 1024 * 1024     # 10 MB
MAX_PIXELS = 50_000_000                 # refuse absurdly large pictures before decoding them
ALLOWED_FORMATS = {"JPEG", "MPO", "PNG", "WEBP"}   # MPO is what some phones call a JPEG
ACCEPT = "image/jpeg,image/png,image/webp"
BACKDROP = (10, 22, 40)                 # behind see-through pictures: the avatar's dark blue

WRONG_TYPE = "Please choose a JPG, PNG or WebP photo."
TOO_BIG = "That photo is too large. Please choose one under 10 MB."
UNREADABLE = "We couldn't read that photo. Please try a different one."


class PhotoError(ValueError):
    """The upload can't be used; the message is safe to show the member."""


def prepare(upload):
    """Return the upload as square JPEG bytes, or raise PhotoError."""
    if upload is None:
        raise PhotoError(WRONG_TYPE)
    if getattr(upload, "size", 0) > MAX_UPLOAD_BYTES:
        raise PhotoError(TOO_BIG)
    try:
        upload.seek(0)
        image = Image.open(upload)
        if image.format not in ALLOWED_FORMATS:
            raise PhotoError(WRONG_TYPE)
        if image.width * image.height > MAX_PIXELS:
            raise PhotoError(TOO_BIG)
        image = ImageOps.exif_transpose(image)          # turn it the right way up
        if image.mode in ("RGBA", "LA", "P"):
            image = image.convert("RGBA")
            flat = Image.new("RGB", image.size, BACKDROP)
            flat.paste(image, mask=image.getchannel("A"))
            image = flat
        else:
            image = image.convert("RGB")
        image = ImageOps.fit(image, (SIZE, SIZE), Image.LANCZOS, centering=(0.5, 0.5))
        out = io.BytesIO()
        image.save(out, "JPEG", quality=86, optimize=True, progressive=True)
        return out.getvalue()
    except PhotoError:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError, SyntaxError):
        raise PhotoError(UNREADABLE)


def save_bytes(profile, data):
    with transaction.atomic():
        ProfilePhoto.objects.update_or_create(profile=profile, defaults={"image": data})
        profile.photo_updated_at = timezone.now()
        profile.save(update_fields=["photo_updated_at", "updated_at"])


def set_photo(profile, upload):
    """Check, shrink and save an uploaded photo. Raises PhotoError if it can't be used."""
    save_bytes(profile, prepare(upload))


def remove_photo(profile):
    with transaction.atomic():
        ProfilePhoto.objects.filter(profile=profile).delete()
        profile.photo_updated_at = None
        profile.save(update_fields=["photo_updated_at", "updated_at"])
