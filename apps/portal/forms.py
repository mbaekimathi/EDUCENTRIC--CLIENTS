from django import forms
from django.core.validators import RegexValidator

from .models import ParentGuardian


class ParentProfileForm(forms.Form):
    full_name = forms.CharField(
        max_length=200,
        label="Full name",
        widget=forms.TextInput(
            attrs={
                "class": "profile-field",
                "autocomplete": "name",
            }
        ),
    )
    relationship_to_student = forms.CharField(
        max_length=80,
        label="Relationship to student",
        widget=forms.TextInput(
            attrs={
                "class": "profile-field",
                "placeholder": "e.g. Mother, Father, Guardian",
            }
        ),
    )
    phone_number = forms.CharField(
        max_length=24,
        label="Phone number",
        validators=[
            RegexValidator(r"^\+?[0-9\s-]{7,24}$", "Enter a valid phone number."),
        ],
        widget=forms.TextInput(
            attrs={
                "class": "profile-field",
                "autocomplete": "tel",
                "inputmode": "tel",
            }
        ),
    )
    email = forms.EmailField(
        required=False,
        label="Email",
        widget=forms.EmailInput(
            attrs={
                "class": "profile-field",
                "autocomplete": "email",
            }
        ),
    )
    profile_image = forms.ImageField(
        required=False,
        label="Profile photo",
        widget=forms.FileInput(
            attrs={
                "accept": "image/jpeg,image/png,image/webp,image/gif",
                "class": "profile-file",
            }
        ),
    )
    clear_profile_image = forms.BooleanField(
        required=False,
        label="Remove current photo",
    )

    def __init__(self, *args, parent: ParentGuardian | None = None, **kwargs):
        self.parent = parent
        super().__init__(*args, **kwargs)
        if parent is not None and not self.is_bound:
            self.fields["full_name"].initial = parent.full_name
            self.fields["relationship_to_student"].initial = parent.relationship_to_student
            self.fields["phone_number"].initial = parent.phone_number
            self.fields["email"].initial = parent.email or ""

    def clean_phone_number(self):
        phone = (self.cleaned_data.get("phone_number") or "").strip()
        qs = ParentGuardian.objects.filter(phone_number=phone)
        if self.parent is not None:
            qs = qs.exclude(pk=self.parent.pk)
        if qs.exists():
            raise forms.ValidationError("That phone number is already used by another guardian.")
        return phone

    def clean_email(self):
        return (self.cleaned_data.get("email") or "").strip()

    def clean_full_name(self):
        return (self.cleaned_data.get("full_name") or "").strip()

    def clean_relationship_to_student(self):
        return (self.cleaned_data.get("relationship_to_student") or "").strip()
