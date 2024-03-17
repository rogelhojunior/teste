from django.db import models


class APICallLog(models.Model):
    METHOD_CHOICES = (
        ('POST', 'POST'),
        ('GET', 'GET'),
        ('PATCH', 'PATCH'),
    )
    method = models.CharField(max_length=10, choices=METHOD_CHOICES)
    url = models.URLField(max_length=500)
    headers = models.TextField(null=True, blank=True)
    body = models.TextField(null=True, blank=True)
    response_status_code = models.PositiveIntegerField(null=True, blank=True)
    response_content = models.TextField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.method} {self.url} ({self.timestamp})'

    class Meta:
        permissions = [
            ('can_access_apicaller', 'Can Access API Caller'),
        ]
