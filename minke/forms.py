# -*- coding: utf-8 -*-

from django import forms
from django.forms.widgets import Select
from django.utils.translation import gettext_lazy as _
from .utils import prepare_shell_command


class MinkeForm(forms.Form):
    session = forms.CharField(required=True, widget=forms.HiddenInput())
    select_across = forms.BooleanField(
        widget=forms.HiddenInput(),
        required=False,
        initial=False)
    minke_form = forms.BooleanField(
        widget=forms.HiddenInput(),
        required=False,
        initial=True)

    class Media:
        css = {'all': ('minke/css/minke_form.css',)}


class PassphraseForm(forms.Form):
    connect_kwargs_passphrase = forms.CharField(
        label=_('Passphrase'),
        help_text=_('Passphrase to decrypt an ssh-private-key.'),
        max_length=100,
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Passphrase',
            'autofocus': '',
            'required': ''})
        )


class CommandField(forms.CharField):
    widget = forms.Textarea
    def clean(self, value):
        value = super().clean(value)
        return prepare_shell_command(value)


class CommandForm(forms.Form):
    cmd = CommandField(
        label=_('Command'),
        help_text=_('Command to execute. Use with care!'),
    )


class ExtendedSelect(Select):
    """
    Select that allows to pass option-specific extra-attributes.
    """
    def __init__(self, attrs=None, extra_attrs=None, choices=()):
        super().__init__(attrs, choices)
        self.extra_attrs = extra_attrs or dict()

    def create_option(self, *args, **kwargs):
        option = super().create_option(*args, **kwargs)
        option['attrs'].update(self.extra_attrs.get(option['label'], dict()))
        return option


class SessionSelectForm(forms.Form):
    session = forms.ChoiceField(label=_('Session:'), widget=ExtendedSelect)
