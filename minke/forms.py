# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django import forms


class MinkeForm(forms.Form):
    action = forms.CharField(required=True, widget=forms.HiddenInput())

    class Media:
        css = {'all': ('minke/css/minke_form.css',)}


class InitialPasswordForm(forms.Form):
    initial_password = forms.CharField(
        label='Pass-Phrase',
        help_text='Pass phrase to decrypt the ssh-private-key.',
        max_length=100,
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Pass-Phrase',
            'autofocus': '',
            'required': ''})
        )
