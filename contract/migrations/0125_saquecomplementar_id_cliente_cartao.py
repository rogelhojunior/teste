# Generated by Django 4.2.3 on 2023-11-14 19:23

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0072_alter_clientecartaobeneficio_tipo_margem'),
        ('contract', '0124_merge_20231108_1641'),
    ]

    operations = [
        migrations.AddField(
            model_name='saquecomplementar',
            name='id_cliente_cartao',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='cliente_cartao_contrato_saque_complementar', to='core.clientecartaobeneficio', verbose_name='ID Cliente Cartão'),
        ),
    ]
