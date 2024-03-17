from import_export import fields, resources

from core.models import DossieINSS


class DossieINSSResource(resources.ModelResource):
    cpf = fields.Field(attribute='cpf', column_name='CPF')
    matricula = fields.Field(attribute='matricula', column_name='Matrícula')
    data_envio = fields.Field(attribute='data_envio', column_name='Data do Envio')
    contrato_id = fields.Field(
        attribute='contrato_id', column_name='Número do Contrato'
    )
    codigo_retorno = fields.Field(
        attribute='codigo_retorno', column_name='Código de Retorno'
    )
    hash_operacao = fields.Field(
        attribute='hash_operacao', column_name='Hash da Operação'
    )
    detalhe_erro = fields.Field(
        attribute='detalhe_erro',
        column_name='Detalhe do Erro',
        default=None,
    )

    class Meta:
        model = DossieINSS
        fields = (
            'cpf',
            'matricula',
            'data_envio',
            'contrato',
            'codigo_retorno',
            'hash_operacao',
            'detalhe_erro',
        )
        export_order = fields
