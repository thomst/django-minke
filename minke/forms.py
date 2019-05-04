# -*- coding: utf-8 -*-

from django import forms


class MinkeForm(forms.Form):
    action = forms.CharField(required=True, widget=forms.HiddenInput())
    wait = forms.BooleanField(
        label='Wait till all sessions are processed.',
        required=False)

    class Media:
        css = {'all': ('minke/css/minke_form.css',)}


class PassphraseForm(forms.Form):
    connect_kwargs_passphrase = forms.CharField(
        label='Passphrase',
        help_text='Passphrase to decrypt an ssh-private-key.',
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
        return value.replace('\r\n', '\n').replace('\r', '\n')


class CommandForm(forms.Form):
    cmd = CommandField(
        label='Command',
        help_text='Command to execute. Use with care!',
    )
