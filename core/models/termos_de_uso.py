from ckeditor.fields import RichTextField
from django.db import models


class TermosDeUso(models.Model):
    termos_de_uso = RichTextField(blank=True)
    politica_privacidade = RichTextField(blank=True)

    class Meta:
        verbose_name = '5. Termo de Uso'
        verbose_name_plural = '5. Termos de Uso'
