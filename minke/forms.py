from django import forms


class InitialPasswordForm(forms.Form):
    minke_initial_password = forms.CharField(
        label='Pass-Phrase',
        help_text='Pass phrase to decrypt the ssh-private-key.',
        max_length=100,
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Pass-Phrase',
            'autofocus': '',
            'required': ''})
        )
