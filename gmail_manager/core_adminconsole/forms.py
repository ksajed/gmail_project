

from __future__ import annotations

from django import forms

from core_people.models import Person


class NurseAdminForm(forms.ModelForm):
    """Admin Console: édition des infirmiers mandatés (Person role='nurse')."""

    class Meta:
        model = Person
        fields = ["first_name", "last_name", "email", "phone"]


# --- ADMINCONSOLE_FORMS_IAM_V2:BEGIN ---
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Group, Permission, User

class UserAdminCreateForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username","email","first_name","last_name","is_active","is_staff","is_superuser","groups","user_permissions")

    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all().order_by("name"),
        required=False,
        widget=forms.SelectMultiple(attrs={"size":"8"}),
    )
    user_permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.select_related("content_type").all().order_by("content_type__app_label","codename"),
        required=False,
        widget=forms.SelectMultiple(attrs={"size":"10"}),
    )

class UserAdminUpdateForm(forms.ModelForm):
    new_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(render_value=False),
        help_text="Optionnel : si rempli, change le mot de passe.",
    )

    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all().order_by("name"),
        required=False,
        widget=forms.SelectMultiple(attrs={"size":"8"}),
    )
    user_permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.select_related("content_type").all().order_by("content_type__app_label","codename"),
        required=False,
        widget=forms.SelectMultiple(attrs={"size":"10"}),
    )

    class Meta:
        model = User
        fields = ("username","email","first_name","last_name","is_active","is_staff","is_superuser","groups","user_permissions")

    def save(self, commit=True):
        u = super().save(commit=False)
        pw = (self.cleaned_data.get("new_password") or "").strip()
        if pw:
            u.set_password(pw)
        if commit:
            u.save()
            self.save_m2m()
        return u

class GroupAdminForm(forms.ModelForm):
    permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.select_related("content_type").all().order_by("content_type__app_label","codename"),
        required=False,
        widget=forms.SelectMultiple(attrs={"size":"14"}),
    )

    class Meta:
        model = Group
        fields = ("name","permissions")
# --- ADMINCONSOLE_FORMS_IAM_V2:END ---
