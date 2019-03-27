# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django import forms


class CommandForm(forms.Form):
    cmd = forms.CharField(
        label='Command',
        help_text='Command to execute. Use with care!',
        widget=forms.Textarea,
    )
