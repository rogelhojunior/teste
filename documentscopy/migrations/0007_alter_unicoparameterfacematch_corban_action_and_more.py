# Generated by Django 4.2.3 on 2024-01-19 11:01

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("custom_auth", "0039_alter_corban_parent_corban_and_more"),
        ("documentscopy", "0006_confiaparameter"),
    ]

    operations = [
        migrations.AlterField(
            model_name="unicoparameterfacematch",
            name="corban_action",
            field=models.IntegerField(
                choices=[(0, "Aprovar"), (1, "Pendenciar"), (2, "Análise Mesa")],
                default=0,
                verbose_name="Ação",
            ),
        ),
        migrations.CreateModel(
            name="ConfiaParameterFaceMatch",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "result",
                    models.IntegerField(
                        choices=[
                            (0, "Confirmado"),
                            (104, "Sem Retorno"),
                            (999, "Não Confirmado"),
                        ],
                        default=104,
                        verbose_name="Resultado",
                    ),
                ),
                (
                    "corban_action",
                    models.IntegerField(
                        choices=[
                            (0, "Aprovar"),
                            (1, "Pendenciar"),
                            (2, "Análise Mesa"),
                        ],
                        default=0,
                        verbose_name="Ação",
                    ),
                ),
                (
                    "parameter",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="documentscopy.confiaparameter",
                        verbose_name="Parametro",
                    ),
                ),
            ],
            options={
                "verbose_name": "Biometria Facial",
                "verbose_name_plural": "Biometria Facial",
            },
        ),
        migrations.CreateModel(
            name="BPOConfig",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("corbans", models.ManyToManyField(to="custom_auth.corban")),
                ("products", models.ManyToManyField(to="documentscopy.product")),
            ],
            options={
                "verbose_name": "Distribuidor de BPOs",
                "verbose_name_plural": "Distribuidor de BPOs",
            },
        ),
    ]
