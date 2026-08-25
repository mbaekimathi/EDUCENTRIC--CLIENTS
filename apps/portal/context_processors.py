from django.core.cache import cache

from . import session as portal_session
from .models import SchoolProfile, Student

DEFAULT_BRAND = {
    "school_name": "Educentric Portal",
    "school_display": "School Portal",
    "primary_color": "#c41230",
    "motto": "",
    "logo": "",
}


def portal_branding(request):
    brand = cache.get("portal_school_branding")
    if brand is None:
        profile = SchoolProfile.objects.only(
            "official_name",
            "display_name",
            "primary_color",
            "motto",
            "school_logo",
        ).first()
        if profile:
            brand = {
                "school_name": profile.official_name or DEFAULT_BRAND["school_name"],
                "school_display": profile.display_name or profile.official_name,
                "primary_color": profile.primary_color or DEFAULT_BRAND["primary_color"],
                "motto": profile.motto or "",
                "logo": profile.school_logo or "",
            }
        else:
            brand = DEFAULT_BRAND.copy()
        cache.set("portal_school_branding", brand, 300)

    siblings = []
    role = getattr(request, "portal_role", None)
    parent = getattr(request, "portal_parent", None)
    if role == portal_session.ROLE_PARENT and parent is not None:
        siblings = list(
            Student.objects.filter(
                parent_guardian_id=parent.pk,
                is_suspended=False,
            ).order_by("first_name", "last_name")
        )

    return {
        "brand": brand,
        "portal_role": role,
        "portal_student": getattr(request, "portal_student", None),
        "portal_parent": parent,
        "portal_siblings": siblings,
    }
