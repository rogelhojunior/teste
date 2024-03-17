from django.db import models


class LogAverbacaoINSS(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    response = models.TextField()

    def __str__(self):
        return f'{self.timestamp}' or ''

    class Meta:
        verbose_name = '4. Averbação INSS'
        verbose_name_plural = '4. Averbação INSS'
