from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from contract.choices import (
    AVERBADORAS,
    TIPO_VINCULO_SIAPE,
    TIPOS_MARGEM,
    TIPOS_PRODUTO,
    TIPOS_PRODUTO_REGRA_IDADE,
)
from contract.products.cartao_beneficio.validators.validate_characters import (
    validate_max_length,
    validate_tipo_produto,
)


class Convenios(models.Model):
    # DADOS DO CONVENIO
    nome = models.CharField(verbose_name='Nome do convênio', max_length=300, null=True)
    averbadora = models.SmallIntegerField(
        verbose_name='Averbadora', choices=AVERBADORAS, null=True, blank=True
    )
    digitacao_manual = models.BooleanField(
        verbose_name='Permite digitação manual de contrato ?', default=False
    )
    senha_servidor = models.BooleanField(
        verbose_name='Solicita Senha Servidor ?', default=False
    )
    necessita_assinatura_fisica = models.BooleanField(
        verbose_name='Necessita assinatura física dos termos de contratação?',
        default=False,
    )
    permite_unificar_margem = models.BooleanField(
        verbose_name='Permite unificação de margem ?', default=False
    )
    fixar_valor_maximo = models.BooleanField(
        verbose_name='Fixar valor máximo de saque ?', default=False
    )
    permite_saque_complementar = models.BooleanField(
        verbose_name='Permite Saque Complementar ?', default=False
    )
    derivacao_mesa_averbacao = models.BooleanField(
        verbose_name='Derivação Mesa de Averbação', default=False
    )
    idade_minima_assinatura = models.IntegerField(
        verbose_name='Idade mínima para a obrigatoriedade da assinatura',
        null=True,
        blank=True,
    )
    ativo = models.BooleanField(verbose_name='Ativo?', default=False)

    # DADOS INSS
    convenio_inss = models.BooleanField(verbose_name='Convênio INSS?', default=False)
    horario_func_ativo = models.BooleanField(
        verbose_name='Horário de funcionamento ativo?', default=False
    )
    aviso_reducao_margem = models.BooleanField(
        verbose_name='Aviso de redução de margem ativo?', default=False
    )
    horario_func_inicio = models.TimeField(
        verbose_name='Horário de início de funcionamento', null=True, blank=True
    )
    horario_func_fim = models.TimeField(
        verbose_name='Horário de fim de funcionamento', null=True, blank=True
    )
    porcentagem_reducao_margem = models.DecimalField(
        verbose_name='Porcentagem aceita para redução da margem',
        decimal_places=2,
        max_digits=5,  # Porcentagens até 999.99%
        null=True,
        blank=True,
        default=0,
    )

    # NEOCONSIG
    cod_convenio = models.IntegerField(
        verbose_name='Código Convênio (Neoconsig)',
        null=True,
        blank=True,
    )

    # ZETRASOFT
    cod_convenio_zetra = models.CharField(
        verbose_name='Convenio (Apenas Zetra)',
        max_length=100,
        null=True,
        blank=True,
    )
    cliente_zetra = models.CharField(
        verbose_name='Convenio (Apenas Zetra)',
        max_length=100,
        null=True,
        blank=True,
    )

    # DADOS DE ACESSO AVERBADORA
    usuario_convenio = models.CharField(
        verbose_name='Usuário do Convênio', max_length=300, null=True, blank=True
    )
    senha_convenio = models.CharField(
        verbose_name='Senha do Convênio', max_length=16, null=True, blank=True
    )
    url = models.CharField(verbose_name='URL', max_length=300, null=True, blank=True)

    def clean(self):
        if self.necessita_assinatura_fisica and self.idade_minima_assinatura is None:
            raise ValidationError(
                'Necessário informar idade mínima para obrigatoriedade da assinatura física.'
            )

    def __str__(self):
        return f'{str(self.pk)}-{str(self.nome)}' or ''

    class Meta:
        verbose_name = 'Parâmetro - Convênio'
        verbose_name_plural = '1. Parâmetros - Convênios'


class ProdutoConvenio(models.Model):
    convenio = models.ForeignKey(
        Convenios,
        verbose_name='Convênio',
        on_delete=models.CASCADE,
        null=True,
        related_name='produto_convenio',
    )
    produto = models.SmallIntegerField(
        verbose_name='Produtos para a oferta',
        choices=TIPOS_PRODUTO,
        null=True,
        blank=True,
    )

    cod_servico_zetra = models.CharField(
        verbose_name='Serviço (Apenas Zetra)',
        max_length=100,
        null=True,
        blank=True,
    )

    # TIPO DE MARGEM
    tipo_margem = models.SmallIntegerField(
        verbose_name='Tipo Margem',
        choices=TIPOS_MARGEM,
        null=True,
        blank=True,
    )

    # REGRA DE IDADE
    idade_minima = models.IntegerField(
        verbose_name='Idade mínima', blank=False, default=0
    )
    idade_maxima = models.IntegerField(
        verbose_name='Idade máxima', blank=False, default=100
    )

    # LIMITES
    margem_minima = models.DecimalField(
        verbose_name='Margem mínima',
        decimal_places=2,
        max_digits=12,
        blank=False,
        default=0,
    )
    margem_maxima = models.DecimalField(
        verbose_name='Margem máxima',
        decimal_places=2,
        max_digits=12,
        blank=False,
        default=0,
    )
    limite_minimo_credito = models.DecimalField(
        verbose_name='Limite mínimo de crédito',
        decimal_places=2,
        max_digits=12,
        blank=False,
        default=0,
    )
    limite_maximo_credito = models.DecimalField(
        verbose_name='Limite máximo de crédito',
        decimal_places=2,
        max_digits=12,
        blank=False,
        default=0,
    )
    fator = models.DecimalField(
        verbose_name='Fator de multiplicação',
        decimal_places=7,
        max_digits=12,
        blank=False,
        default=0,
    )

    # TAXAS
    taxa_produto = models.DecimalField(
        verbose_name='Valor da Taxa do produto',
        decimal_places=2,
        max_digits=12,
        null=True,
        blank=True,
    )
    cet_am = models.DecimalField(
        verbose_name='Taxa CET a.m',
        decimal_places=2,
        max_digits=12,
        null=True,
        blank=True,
    )
    cet_aa = models.DecimalField(
        verbose_name='Taxa CET a.a',
        decimal_places=2,
        max_digits=12,
        null=True,
        blank=True,
    )

    # PARAMETROS DOCK
    data_vencimento_fatura = models.IntegerField(
        verbose_name='Dia de vencimento da fatura', null=True, blank=True
    )
    corte = models.IntegerField(
        verbose_name='Dia de corte da fatura', null=True, blank=True
    )
    id_produto_logo_dock = models.IntegerField(
        verbose_name='id_produto/Logo Dock', null=True, blank=True
    )

    id_plastico_dock = models.IntegerField(
        verbose_name='Id Plastico', null=True, blank=True
    )
    id_imagem_dock = models.IntegerField(
        verbose_name='Id Imagem', null=True, blank=True
    )
    saque_parc_cod_dock = models.IntegerField(
        verbose_name='Código Dock de Lançamento do Saque Parcelado',
        blank=True,
        null=True,
    )
    cartao_virtual = models.BooleanField(
        verbose_name='Substituir a criação do cartão físico para o cartão virtual?',
        default=False,
    )

    # PARAMETROS SAQUE
    percentual_saque = models.DecimalField(
        verbose_name='Percentual do limite para o Saque Rotativo e/ou Parcelado',
        decimal_places=2,
        max_digits=5,
        null=True,
        blank=True,
        default=0,
    )

    # SAQUE ROTATIVO
    permite_saque = models.BooleanField(
        verbose_name='Permite contratação de Saque Rotativo',
        null=True,
        blank=False,
        default=True,
    )
    vr_minimo_saque = models.DecimalField(
        verbose_name='Valor mínimo para solicitação do Saque Rotativo',
        decimal_places=7,
        max_digits=12,
        blank=True,
        null=True,
        default=0,
    )

    # SAQUE PARCELADO
    permite_saque_parcelado = models.BooleanField(
        verbose_name='Permite contratação de Saque Parcelado',
        null=True,
        blank=False,
        default=True,
    )
    saque_parc_val_min = models.DecimalField(
        verbose_name='Valor mínimo em reais da parcela',
        decimal_places=2,
        max_digits=12,
        blank=False,
        default=0,
    )
    saque_parc_qnt_min_parcelas = models.IntegerField(
        verbose_name='Quantidade mínima de parcelas', null=True, blank=True
    )
    saque_parc_val_total = models.IntegerField(
        verbose_name='Valor total da contratação mínimo em reais (Sem o cálculo CET)',
        null=True,
        blank=True,
        help_text='Este campo será preenchido ao final do cadastro.',
    )

    @property
    def valor_taxa_produto(self):
        return float(self.taxa_produto / 100)

    def clean(self):
        if self.permite_saque and (
            self.percentual_saque <= 0 or self.vr_minimo_saque <= 0
        ):
            raise ValidationError(
                'Os campos Percentual Saque e Valor Mínimo Saque são obrigatórios quando Permite Saque está ativado.'
            )

        if self.permite_saque_parcelado and (
            self.saque_parc_cod_dock is None
            or self.saque_parc_val_min is None
            or self.saque_parc_qnt_min_parcelas is None
        ):
            raise ValidationError(
                'Os campos Código Dock de Lançamento do Saque Parcelado, Valor mínimo em reais da parcela e '
                'Quantidade mínima de parcelas são obrigatórios quando Permite Saque Parcelado está ativado.'
            )

    def save(self, *args, **kwargs):
        if (
            self.saque_parc_val_min is not None
            and self.saque_parc_qnt_min_parcelas is not None
        ):
            self.saque_parc_val_total = (
                self.saque_parc_val_min * self.saque_parc_qnt_min_parcelas
            )
        super().save(*args, **kwargs)

    def get_tipo_produto_display(self):
        return dict(TIPOS_PRODUTO).get(self.produto)

    def __str__(self):
        return self.get_tipo_produto_display() or ''

    class Meta:
        verbose_name = 'Produto'
        verbose_name_plural = 'Produtos'


class OpcoesParcelamento(models.Model):
    convenio = models.ForeignKey(
        Convenios, verbose_name='Convênio', on_delete=models.CASCADE, null=True
    )
    qnt_parcelamento = models.IntegerField(
        verbose_name='Grupo de Parcelas', blank=True, null=True
    )

    class Meta:
        verbose_name = 'Opção Parcelamento'
        verbose_name_plural = 'Opções Parcelamento Saque'


class SubOrgao(models.Model):
    convenio = models.ForeignKey(
        Convenios,
        verbose_name='Convênio',
        on_delete=models.CASCADE,
        null=True,
        related_name='suborgao_convenio',
    )

    nome_orgao = models.CharField(
        verbose_name='Nome do Órgão', max_length=255, blank=False
    )

    codigo_folha = models.CharField(
        verbose_name='Código Folha', max_length=255, blank=True, null=True
    )

    ativo = models.BooleanField(verbose_name='Ativo', default=True)

    def __str__(self):
        return self.nome_orgao

    class Meta:
        verbose_name = 'Sub-Orgão'
        verbose_name_plural = 'Sub-Orgãos'


class RegrasIdade(models.Model):
    convenio = models.ForeignKey(
        Convenios, verbose_name='Convênio', on_delete=models.CASCADE, null=True
    )

    idade_minima = models.IntegerField(
        verbose_name='Idade mínima',
        blank=False,
        default=0,
        validators=[validate_max_length],
    )
    idade_maxima = models.IntegerField(
        verbose_name='Idade máxima',
        blank=False,
        default=100,
        validators=[validate_max_length],
    )

    produto = models.SmallIntegerField(
        verbose_name='Tipo de Produto',
        choices=TIPOS_PRODUTO_REGRA_IDADE,
        blank=True,
        null=True,
        validators=[validate_tipo_produto],
    )

    fator = models.DecimalField(
        verbose_name='Fator de multiplicação',
        decimal_places=2,
        max_digits=5,
        blank=False,
        default=0,
    )

    limite_minimo_credito = models.DecimalField(
        verbose_name='Limite mínimo de crédito',
        decimal_places=2,
        max_digits=8,
        blank=False,
        default=0,
    )

    limite_maximo_credito = models.DecimalField(
        verbose_name='Limite máximo de crédito',
        decimal_places=2,
        max_digits=8,
        blank=False,
        default=0,
    )

    tipo_vinculo_siape = models.SmallIntegerField(
        verbose_name='Tipo de Vinculo - SIAPE',
        choices=TIPO_VINCULO_SIAPE,
        null=True,
        blank=True,
    )

    ativo = models.BooleanField(verbose_name='Ativo?', default=True)

    grupo_parcelas = models.IntegerField(
        verbose_name='Grupo de Parcelas',
        blank=False,
        default=0,
        validators=[MaxValueValidator(999), MinValueValidator(0)],
    )

    grupo_parcelas_2 = models.IntegerField(
        verbose_name='Grupo de Parcelas',
        blank=False,
        default=0,
        validators=[MaxValueValidator(999), MinValueValidator(0)],
    )

    grupo_parcelas_3 = models.IntegerField(
        verbose_name='Grupo de Parcelas',
        blank=False,
        default=0,
        validators=[MaxValueValidator(999), MinValueValidator(0)],
    )

    grupo_parcelas_4 = models.IntegerField(
        verbose_name='Grupo de Parcelas',
        blank=False,
        default=0,
        validators=[MaxValueValidator(999), MinValueValidator(0)],
    )

    fator_compra = models.DecimalField(
        verbose_name='Fator de multiplicação de compra',
        decimal_places=2,
        max_digits=5,
        blank=False,
        default=0,
    )

    fator_saque = models.DecimalField(
        verbose_name='Fator de multiplicação de saque',
        decimal_places=2,
        max_digits=5,
        blank=False,
        default=0,
    )

    def __str__(self):
        return f'{self.convenio}'

    class Meta:
        verbose_name = 'Regra de Idade'
        verbose_name_plural = 'Regras de Idade'


class FontePagadora(models.Model):
    convenios = models.ForeignKey(
        Convenios,
        verbose_name='Convenios',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    razao_social = models.CharField(verbose_name='Razão Social', max_length=300)
    CNPJ = models.CharField(verbose_name='CNPJ', max_length=20)
    endereco = models.CharField(verbose_name='Endereço', max_length=255)
    email = models.CharField(verbose_name='E-mail', max_length=50)

    def __str__(self):
        return self.razao_social

    class Meta:
        verbose_name = 'Fonte Pagadora'
        verbose_name_plural = 'Fontes Pagadoras'


class SituacaoBeneficioINSS(models.Model):
    convenio = models.ForeignKey(
        Convenios, verbose_name='Convênio', on_delete=models.CASCADE, null=True
    )

    codigo = models.IntegerField(verbose_name='Código', blank=False, default=0)

    descricao = models.CharField(verbose_name='Descrição', max_length=255)

    permite_contratacao = models.BooleanField(
        verbose_name='Permite contratação?', default=False
    )

    class Meta:
        verbose_name = 'Situação Benefício/INSS'
        verbose_name_plural = 'Situação Benefício/INSS'


class EspecieBeneficioINSS(models.Model):
    convenio = models.ForeignKey(
        Convenios,
        verbose_name='Convênio',
        on_delete=models.CASCADE,
        null=True,
        related_name='convenio_especie',
    )

    codigo = models.IntegerField(verbose_name='Código', blank=False, default=0)

    descricao = models.CharField(verbose_name='Descrição', max_length=255)

    idade_minima = models.IntegerField(
        verbose_name='Idade mínima', blank=False, default=0
    )
    idade_maxima = models.IntegerField(
        verbose_name='Idade máxima', blank=False, default=100
    )

    permite_contratacao = models.BooleanField(
        verbose_name='Permite contratação?', default=False
    )

    class Meta:
        verbose_name = 'Espécie de Benefício INSS'
        verbose_name_plural = 'Espécie de Benefício INSS'


class PensaoAlimenticiaINSS(models.Model):
    convenio = models.ForeignKey(
        Convenios, verbose_name='Convênio', on_delete=models.CASCADE, null=True
    )

    codigo = models.IntegerField(verbose_name='Código', blank=False, default=0)

    descricao = models.CharField(verbose_name='Descrição', max_length=255)

    permite_contratacao = models.BooleanField(
        verbose_name='Permite contratação?', default=False
    )

    class Meta:
        verbose_name = 'Pensão Alimentícia INSS'
        verbose_name_plural = 'Pensão Alimentícia INSS'


class Seguros(models.Model):
    convenio = models.ForeignKey(
        Convenios,
        on_delete=models.CASCADE,
        verbose_name='Convênio',
        related_name='convenio_seguro',
        null=True,
    )
    plano = models.ForeignKey(
        'cartao_beneficio.Planos',
        on_delete=models.CASCADE,
        verbose_name='Plano',
        related_name='plano_seguro',
    )
    produto = models.SmallIntegerField(
        verbose_name='Produtos para a oferta',
        choices=TIPOS_PRODUTO,
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = 'Parâmetro – Plano'
        verbose_name_plural = 'Parâmetros – Planos'


class TipoVinculoSiape(models.Model):
    convenio = models.ForeignKey(
        Convenios, verbose_name='Convênio', on_delete=models.CASCADE, null=True
    )

    codigo = models.CharField(verbose_name='Código', max_length=255)

    descricao = models.CharField(verbose_name='Descrição', max_length=255)

    permite_contratacao = models.BooleanField(
        verbose_name='Permite contratação?', default=False
    )

    class Meta:
        verbose_name = 'Tipo de Vínculo – SIAPE'
        verbose_name_plural = 'Tipo de Vínculo – SIAPE'


class ClassificacaoSiape(models.Model):
    convenio = models.ForeignKey(
        Convenios,
        verbose_name='Convênio',
        on_delete=models.CASCADE,
        null=True,
        related_name='convenio_classificacao_siape',
    )

    codigo = models.IntegerField(verbose_name='Código', blank=False, default=0)

    descricao = models.CharField(verbose_name='Descrição', max_length=255)

    permite_contratacao = models.BooleanField(
        verbose_name='Permite contratação?', default=False
    )

    class Meta:
        verbose_name = 'Classificação – SIAPE'
        verbose_name_plural = 'Classificação – SIAPE'


class ConvenioSiape(models.Model):
    convenio = models.ForeignKey(
        Convenios,
        verbose_name='Convênio',
        on_delete=models.CASCADE,
        null=True,
        related_name='convenio_convenio_siape',
    )

    codigo = models.IntegerField(verbose_name='Código', blank=False, default=0)

    descricao = models.CharField(verbose_name='Descrição', max_length=255)

    permite_contratacao = models.BooleanField(
        verbose_name='Permite contratação?', default=False
    )

    class Meta:
        verbose_name = 'Convênio – SIAPE'
        verbose_name_plural = 'Convênio – SIAPE'
