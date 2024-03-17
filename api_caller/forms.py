from django import forms

from .models import APICallLog


class APICallForm(forms.ModelForm):
    class Meta:
        model = APICallLog
        fields = ['method', 'url', 'headers', 'body']
