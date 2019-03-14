# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django import forms


class MinkeForm(forms.Form):
    action = forms.CharField(required=True, widget=forms.HiddenInput())
    join = forms.BooleanField(
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
