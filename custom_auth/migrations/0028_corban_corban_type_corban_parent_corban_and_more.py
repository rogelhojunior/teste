# Generated by Django 4.2.3 on 2023-12-20 18:52

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('custom_auth', '0027_merge_20231116_1933'),
    ]

    operations = [
        migrations.AddField(
            model_name='corban',
            name='corban_type',
            field=models.SmallIntegerField(blank=True, choices=[(1, 'Corban Master'), (2, 'Substabelecido'), (3, 'Loja'), (4, 'Filial')], null=True, verbose_name='Grau do Corban'),
        ),
        migrations.AddField(
            model_name='corban',
            name='parent_corban',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='sub_corbans', to='custom_auth.corban', verbose_name='Corban Superior'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='nivel_hierarquia',
            field=models.SmallIntegerField(blank=True, choices=[(5, 'Administrador'), (4, 'Dono da Loja'), (3, 'Gerente'), (2, 'Supervisor'), (1, 'Digitador')], null=True, verbose_name='Nível Hierárquico'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='supervisor',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='subordinados', to=settings.AUTH_USER_MODEL, verbose_name='Gestor'),
        ),
    ]
