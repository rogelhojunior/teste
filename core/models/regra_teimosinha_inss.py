from django.db import models


class RegraTeimosinhaINSS(models.Model):
    codigo = models.CharField(
        max_length=10,
        help_text='Informe o código de letras que terá o reprocessamento da reserva de margem.',
    )
    descricao = models.TextField(
        verbose_name='Descrição',
        help_text='Informe a descrição do código de letras que terá o reprocessamento da reserva de margem.',
        blank=True,
    )
    produto = models.ForeignKey(
        'custom_auth.Produtos',
        on_delete=models.CASCADE,
        help_text='Selecione o produto que será atendido por essa regra.',
    )
    intervalo_reprocessamento = models.IntegerField(
        verbose_name='Intervalo de reprocessamento',
        help_text='Informe o tempo de intervalo em minutos para reprocessar o contrato que tiver de receber o código de retorno da Dataprev dessa regra na Reserva de margem. Caso a Dataprev retorne BD, não haverá nova tentativa.',
    )
    quantidade_tentativas = models.PositiveIntegerField(
        verbose_name='Quantidade de tentativas',
        help_text='Informe quantas tentativas o sistema deverá realizar, respeitando o intervalo escolhido. Caso a Dataprev retorne BD antes do prazo escolhido, não haverá nova tentativa.',
    )
    ativo = models.BooleanField(
        verbose_name='Ativo',
        default=True,
    )

    criado_em = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Criado em',
    )
    modificado_em = models.DateTimeField(
        auto_now=True,
        verbose_name='Modificado em',
    )

    def __str__(self):
        return f'Regra {self.codigo} - {str(self.produto)}'

    class Meta:
        verbose_name = 'Teimosinha INSS'
        verbose_name_plural = '9. Teimosinha INSS'
