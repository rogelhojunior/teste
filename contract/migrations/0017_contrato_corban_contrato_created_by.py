# Generated by Django 4.1.3 on 2023-04-25 21:43

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('custom_auth', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('contract', '0016_remove_cartaobeneficio_id_envelope_unico_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='contrato',
            name='corban',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='custom_auth.corban', verbose_name='Corban'),
        ),
        migrations.AddField(
            model_name='contrato',
            name='created_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.DO_NOTHING, to=settings.AUTH_USER_MODEL, verbose_name='Criado por'),
        ),
    ]
