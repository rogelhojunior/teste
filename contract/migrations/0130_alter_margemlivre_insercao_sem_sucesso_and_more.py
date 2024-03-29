# Generated by Django 4.2.3 on 2023-11-27 21:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contract', '0129_refinanciamento_sucesso_finalizada_proposta'),
    ]

    operations = [
        migrations.AlterField(
            model_name='margemlivre',
            name='insercao_sem_sucesso',
            field=models.TextField(blank=True, help_text='Caso a insercao não foi bem sucedida aqui aparece o motivo do erro', null=True, verbose_name='Motivo de erro na insercao QITECH'),
        ),
        migrations.AlterField(
            model_name='portabilidade',
            name='insercao_sem_sucesso',
            field=models.TextField(blank=True, help_text='Caso a insercao não foi bem sucedida aqui aparece o motivo do erro', null=True, verbose_name='Motivo de erro na insercao QITECH'),
        ),
        migrations.AlterField(
            model_name='refinanciamento',
            name='insercao_sem_sucesso',
            field=models.TextField(blank=True, help_text='Caso a insercao não foi bem sucedida aqui aparece o motivo do erro', null=True, verbose_name='Motivo de erro na insercao QITECH'),
        ),
    ]
