# -*- coding: utf-8 -*-

from django import forms


class TestForm(forms.Form):
    one = forms.IntegerField(
        label='One',
        help_text='A number!',
        required=True,
    )
    two = forms.IntegerField(
        label='Two',
        help_text='Another number!',
        required=True,
    )
