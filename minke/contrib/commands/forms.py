# -*- coding: utf-8 -*-

from django import forms


class CommandForm(forms.Form):
    cmd = forms.ChoiceField(label='Command:')
