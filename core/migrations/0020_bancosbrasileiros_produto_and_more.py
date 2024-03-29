# Generated by Django 4.1.3 on 2023-05-22 18:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('custom_auth', '0005_corban_mesa_corban'),
        ('core', '0019_remove_cliente_cd_cliente_parceiro_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='bancosbrasileiros',
            name='produto',
            field=models.ManyToManyField(blank=True, help_text='Selecione os produtos disponíveis para este banco', related_name='bank_products', to='custom_auth.produtos', verbose_name='Produtos'),
        ),
        migrations.AlterField(
            model_name='bancosbrasileiros',
            name='aceita_liberacao',
            field=models.BooleanField(default=False, verbose_name='Aceita liberação?'),
        ),
    ]
