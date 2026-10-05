from pathlib import Path

from django.conf import settings
from django.core.cache import cache

from . import profile as portal_profile
from . import session as portal_session
from .cache_helpers import cache_get_or_set_locked
from .models import SchoolProfile, Student

# Portal chrome uses a fixed professional blue (school DB may still store another accent).
PORTAL_BRAND_COLOR = "#1f5cf0"

DEFAULT_BRAND = {
    "school_name": "Educentric Portal",
    "school_display": "School Portal",
    "primary_color": PORTAL_BRAND_COLOR,
    "motto": "",
    "logo": "",
    "logo_url": "",
    "brand_initials": "EC",
    "has_logo": False,
}


def _brand_initials(name):
    source = (name or "").strip()
    parts = [part for part in source.replace("-", " ").split() if part]
    if len(parts) >= 2:
        return "".join(part[0] for part in parts[:2]).upper()
    return source[:2].upper() if source else "EC"


def _logo_url(logo_name):
    name = (logo_name or "").strip().lstrip("/")
    if not name:
        return ""
    path = Path(settings.MEDIA_ROOT) / name
    if not path.is_file():
        return ""
    return f"{settings.MEDIA_URL.rstrip('/')}/{name}"


def _load_school_branding():
    profile = SchoolProfile.objects.only(
        "official_name",
        "display_name",
        "motto",
        "school_logo",
    ).first()
    if profile:
        display = profile.display_name or profile.official_name or DEFAULT_BRAND["school_display"]
        logo_url = _logo_url(profile.school_logo)
        return {
            "school_name": profile.official_name or DEFAULT_BRAND["school_name"],
            "school_display": display,
            "primary_color": PORTAL_BRAND_COLOR,
            "motto": profile.motto or "",
            "logo": profile.school_logo or "",
            "logo_url": logo_url,
            "brand_initials": _brand_initials(display),
            "has_logo": bool(logo_url),
        }
    return DEFAULT_BRAND.copy()


def portal_branding(request):
    brand_ttl = getattr(settings, "PORTAL_BRANDING_CACHE_SECONDS", 3600)
    brand = cache_get_or_set_locked(
        "portal_school_branding_v3",
        _load_school_branding,
        brand_ttl,
    )

    siblings = []
    role = getattr(request, "portal_role", None)
    parent = getattr(request, "portal_parent", None)
    if role == portal_session.ROLE_PARENT and parent is not None:
        siblings_key = f"portal:siblings:{parent.pk}"
        siblings = cache.get(siblings_key)
        if siblings is None:
            siblings = [
                {"id": row.pk, "display_name": row.display_name}
                for row in Student.objects.filter(
                    parent_guardian_id=parent.pk,
                    is_suspended=False,
                )
                .only("pk", "first_name", "last_name", "assessment_number")
                .order_by("first_name", "last_name")
            ]
            siblings_ttl = getattr(settings, "PORTAL_SIBLINGS_CACHE_SECONDS", 300)
            cache.set(siblings_key, siblings, siblings_ttl)

    student = getattr(request, "portal_student", None)
    return {
        "brand": brand,
        "portal_role": role,
        "portal_student": student,
        "portal_parent": parent,
        "portal_siblings": siblings,
        "portal_can_edit_profile": role == portal_session.ROLE_PARENT and parent is not None,
        "portal_avatar_url": portal_profile.account_avatar_url(
            role=role, parent=parent, student=student
        ),
        "portal_avatar_initial": portal_profile.account_initial(
            role=role, parent=parent, student=student
        ),
    }
