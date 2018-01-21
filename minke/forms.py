from django import forms


class SSHKeyPassPhrase(forms.Form):
    pass_phrase = forms.CharField(
        label='Pass-Phrase',
        help_text='Pass phrase to decrypt the ssh-private-key.',
        max_length=100,
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Pass-Phrase',
            'autofocus': '',
            'required': ''})
        )
