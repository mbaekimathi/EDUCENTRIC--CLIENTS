"""Profile settings helpers for parent/student portal accounts."""

from __future__ import annotations

import uuid
from pathlib import Path

from django.conf import settings
from django.core.files.storage import default_storage

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_PROFILE_IMAGE_BYTES = 2 * 1024 * 1024  # 2 MB


def media_url(name: str | None) -> str:
    cleaned = (name or "").strip().lstrip("/")
    if not cleaned:
        return ""
    from django.core.cache import cache

    cache_key = f"portal:media_exists:{cleaned}"
    exists = cache.get(cache_key)
    if exists is None:
        path = Path(settings.MEDIA_ROOT) / cleaned
        exists = path.is_file()
        cache.set(cache_key, exists, 120)
    if not exists:
        return ""
    return f"{settings.MEDIA_URL.rstrip('/')}/{cleaned}"


def account_avatar_url(*, role: str | None, parent=None, student=None) -> str:
    """Avatar for the signed-in account (parent photo when guardian, else student)."""
    from . import session as portal_session

    if role == portal_session.ROLE_PARENT and parent is not None:
        return media_url(getattr(parent, "profile_image", None))
    if student is not None:
        return media_url(getattr(student, "profile_image", None))
    return ""


def account_initial(*, role: str | None, parent=None, student=None) -> str:
    from . import session as portal_session

    if role == portal_session.ROLE_PARENT and parent is not None:
        name = (parent.full_name or "").strip()
    elif student is not None:
        name = (student.display_name or "").strip()
    else:
        name = ""
    return (name[:1] or "U").upper()


def validate_profile_image(uploaded) -> str | None:
    """Return an error message, or None when the upload is acceptable."""
    if uploaded is None:
        return None
    content_type = (getattr(uploaded, "content_type", "") or "").lower()
    if content_type and not content_type.startswith("image/"):
        return "Please upload an image file (JPG, PNG, WEBP, or GIF)."
    ext = Path(getattr(uploaded, "name", "") or "").suffix.lower()
    if ext and ext not in ALLOWED_IMAGE_EXTENSIONS:
        return "Please upload an image file (JPG, PNG, WEBP, or GIF)."
    size = getattr(uploaded, "size", 0) or 0
    if size > MAX_PROFILE_IMAGE_BYTES:
        return "Profile photo must be 2 MB or smaller."
    return None


def store_profile_image(uploaded, folder: str = "parents/profiles") -> str:
    ext = Path(getattr(uploaded, "name", "") or "").suffix.lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        ext = ".jpg"
    name = f"{folder}/{uuid.uuid4().hex}{ext}"
    saved = default_storage.save(name, uploaded)
    from django.core.cache import cache

    cache.set(f"portal:media_exists:{saved}", True, 120)
    return saved


def delete_stored_image(name: str | None) -> None:
    cleaned = (name or "").strip().lstrip("/")
    if not cleaned:
        return
    if default_storage.exists(cleaned):
        default_storage.delete(cleaned)
    from django.core.cache import cache

    cache.delete(f"portal:media_exists:{cleaned}")

