from __future__ import annotations

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission


User = get_user_model()


class UserAdminCreateForm(forms.Form):
    username = forms.CharField(max_length=150, required=True)
    email = forms.EmailField(required=False)
    first_name = forms.CharField(required=False)
    last_name = forms.CharField(required=False)

    password1 = forms.CharField(widget=forms.PasswordInput, required=True, label="Password")
    password2 = forms.CharField(widget=forms.PasswordInput, required=True, label="Password confirmation")

    is_active = forms.BooleanField(required=False, initial=True)
    is_staff = forms.BooleanField(required=False, initial=False)
    is_superuser = forms.BooleanField(required=False, initial=False)

    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all().order_by("name"),
        required=False,
        widget=forms.SelectMultiple,
    )
    user_permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.all().select_related("content_type").order_by("content_type__app_label", "codename"),
        required=False,
        widget=forms.SelectMultiple,
        label="Permissions directes",
    )

    def clean_username(self):
        username = (self.cleaned_data.get("username") or "").strip()
        if not username:
            raise forms.ValidationError("Username obligatoire.")
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("Ce username existe déjà.")
        return username

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password1") or ""
        p2 = cleaned.get("password2") or ""
        if p1 != p2:
            raise forms.ValidationError("Les mots de passe ne correspondent pas.")
        if len(p1) < 6:
            raise forms.ValidationError("Mot de passe trop court (min 6).")
        return cleaned
