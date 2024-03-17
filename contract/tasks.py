import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMessage
from django.db.models import Q
from import_export.formats import base_formats

from contract.admin import contrato_resource_export
from contract.constants import EnumTipoProduto, ExportType
from contract.models.report_settings import ReportSettings
from contract.models.status_contrato import StatusContrato
from contract.products.cartao_beneficio.constants import ContractStatus


@shared_task(queue='reports')
def export_contracts(
    file_format_position, queryset_pks, user_pk, file_name: str, subject: str, body: str
):
    """
    Send report by email as a Celery shared task.
    """
    try:
        export_class = ImportExportContract(
            file_format_position, queryset_pks, user_pk, file_name, subject, body
        )
        export_class.get_export_data()
    except Exception as e:
        logging.error(f'Houve um erro ao exportar os contratos {e}')
        raise e


class ImportExportContract:
    def __init__(
        self, file_format_position, queryset_pks, user_email, file_name, subject, body
    ):
        self.formats = base_formats.DEFAULT_FORMATS
        self.escape_exported_data = False
        self.escape_html = False
        self.escape_formulae = False
        self.user_email = user_email
        self.file_name = file_name
        self.subject = subject
        self.body = body

        self.queryset_pks = queryset_pks
        self.file_format = self.get_export_formats()[file_format_position]()

    def get_export_formats(self):
        """
        Returns available export formats.
        """
        return [f for f in self.formats if f().can_export()]

    def get_data_for_export(self, *args, **kwargs):
        contrato_instance = contrato_resource_export(isFront=False)()
        contrato_instance.set_queryset_pks(self.queryset_pks)
        return contrato_instance.export(*args, **kwargs)

    def get_export_data(self, *args, **kwargs):
        """
        Returns file_format representation for given queryset.
        """
        content_type = self.file_format.get_content_type()
        data = self.get_data_for_export(*args, **kwargs)
        export_data = self.file_format.export_data(
            data,
            escape_output=self.escape_exported_data,
            escape_html=self.escape_html,
            escape_formulae=self.escape_formulae,
        )
        """
        encoding = kwargs.get("encoding")
        if not file_format.is_binary() and encoding:
            export_data = export_data.encode(encoding)
        """
        self.send_email_with_attachment(export_data, content_type)
        return export_data

    def send_email_with_attachment(self, export_data, content_type):
        """Trigger email with report attached."""
        # get email data from database
        report_settings = ReportSettings.objects.first()
        subject = report_settings.subject
        body = report_settings.msg_email

        # define sender address
        sender = settings.EMAIL_USUARIO

        # define recipient addresses
        recipient = [f'{self.user_email}']

        # create message object to be triggered
        subject = self.subject
        body = self.body
        email = EmailMessage(subject, body, sender, recipient)

        # add attachment to the email
        email.attach(self.get_export_file_name(), export_data, content_type)

        # send the email
        email.send()

    def get_export_file_name(self):
        return f'{self.file_name}.{self.file_format.get_extension()}'


class ExportContractsReport:
    def __init__(
        self, queryset, export_type, product_type, init_date, end_date, status
    ):
        self.queryset = queryset
        self.export_type = export_type
        self.product_type = product_type
        self.init_date = init_date
        self.end_date = end_date
        self.status = status

    def get_general_contracts(self):
        if self.status == 0:
            return self.queryset.filter(
                tipo_produto=self.product_type,
                criado_em__range=(self.init_date, self.end_date),
            ).order_by('criado_em')
        if self.product_type in (
            EnumTipoProduto.CARTAO_BENEFICIO,
            EnumTipoProduto.CARTAO_BENEFICIO_REPRESENTANTE,
            EnumTipoProduto.CARTAO_CONSIGNADO,
        ):
            return self.queryset.filter(
                tipo_produto=self.product_type,
                contrato_cartao_beneficio__status=self.status,
                criado_em__range=(self.init_date, self.end_date),
            ).order_by('criado_em')
        elif self.product_type in (EnumTipoProduto.SAQUE_COMPLEMENTAR,):
            return self.queryset.filter(
                tipo_produto=self.product_type,
                contrato_saque_complementar__status=self.status,
                criado_em__range=(self.init_date, self.end_date),
            ).order_by('criado_em')
        elif self.product_type == EnumTipoProduto.PORTABILIDADE:
            return self.queryset.filter(
                tipo_produto=self.product_type,
                contrato_portabilidade__status=self.status,
                criado_em__range=(self.init_date, self.end_date),
            ).order_by('criado_em')
        elif self.product_type == EnumTipoProduto.PORTABILIDADE_REFINANCIAMENTO:
            status_filter = Q(
                (
                    ~Q(
                        contrato_portabilidade__status=ContractStatus.INT_FINALIZADO.value
                    )
                    & Q(contrato_portabilidade__status=self.status)
                )
                | (
                    Q(
                        contrato_portabilidade__status=ContractStatus.INT_FINALIZADO.value
                    )
                    & Q(contrato_refinanciamento__status=self.status)
                )
            )

            return self.queryset.filter(
                Q(
                    tipo_produto=self.product_type,
                    criado_em__range=(self.init_date, self.end_date),
                )
                & status_filter
            ).order_by('criado_em')
        elif self.product_type == EnumTipoProduto.MARGEM_LIVRE:
            return self.queryset.filter(
                tipo_produto=self.product_type,
                contrato_margem_livre__status=self.status,
                criado_em__range=(self.init_date, self.end_date),
            ).order_by('criado_em')

    def get_queryset(self):
        if self.export_type == ExportType.GENERAL:
            self.queryset = self.get_general_contracts()
        elif self.export_type == ExportType.FINALIZATION:
            self.queryset = self.get_finalization_contracts()
        elif self.export_type == ExportType.BALANCE_RETURN:
            self.queryset = self.get_balance_return_contracts()

        return self.queryset

    def get_finalization_contracts(self):
        raise NotImplementedError

    def get_balance_return_contracts(self):
        raise NotImplementedError


class ExportBenefitCardReport(ExportContractsReport):
    def get_finalization_contracts(self):
        if self.product_type == EnumTipoProduto.CARTAO_BENEFICIO:
            return self.queryset.filter(
                Q(
                    tipo_produto__in=[
                        EnumTipoProduto.CARTAO_BENEFICIO,
                    ],
                    ultima_atualizacao__range=(self.init_date, self.end_date),
                )
                & (
                    Q(
                        contrato_cartao_beneficio__status=ContractStatus.FINALIZADA_EMISSAO_CARTAO.value,
                        contrato_cartao_beneficio__possui_saque=False,
                    )
                    | Q(
                        contrato_cartao_beneficio__status=ContractStatus.FINALIZADA_LIBERACAO_SAQUE.value,
                        contrato_cartao_beneficio__possui_saque=True,
                    )
                    | Q(
                        contrato_cartao_beneficio__status=ContractStatus.FINALIZADA_LIBERACAO_SAQUE.value,
                        contrato_cartao_beneficio__saque_parcelado=True,
                    )
                )
            ).order_by('ultima_atualizacao')

        elif self.product_type == EnumTipoProduto.CARTAO_BENEFICIO_REPRESENTANTE:
            return self.queryset.filter(
                Q(
                    tipo_produto__in=[
                        EnumTipoProduto.CARTAO_BENEFICIO_REPRESENTANTE,
                    ],
                    ultima_atualizacao__range=(self.init_date, self.end_date),
                )
                & (
                    Q(
                        contrato_cartao_beneficio__status=ContractStatus.FINALIZADA_EMISSAO_CARTAO.value,
                        contrato_cartao_beneficio__possui_saque=False,
                    )
                    | Q(
                        contrato_cartao_beneficio__status=ContractStatus.FINALIZADA_LIBERACAO_SAQUE.value,
                        contrato_cartao_beneficio__possui_saque=True,
                    )
                    | Q(
                        contrato_cartao_beneficio__status=ContractStatus.FINALIZADA_LIBERACAO_SAQUE.value,
                        contrato_cartao_beneficio__saque_parcelado=True,
                    )
                )
            ).order_by('ultima_atualizacao')

        elif self.product_type == EnumTipoProduto.CARTAO_CONSIGNADO:
            return self.queryset.filter(
                Q(
                    tipo_produto__in=[
                        EnumTipoProduto.CARTAO_CONSIGNADO,
                    ],
                    ultima_atualizacao__range=(self.init_date, self.end_date),
                )
                & (
                    Q(
                        contrato_cartao_beneficio__status=ContractStatus.FINALIZADA_EMISSAO_CARTAO.value,
                        contrato_cartao_beneficio__possui_saque=False,
                    )
                    | Q(
                        contrato_cartao_beneficio__status=ContractStatus.FINALIZADA_LIBERACAO_SAQUE.value,
                        contrato_cartao_beneficio__possui_saque=True,
                    )
                    | Q(
                        contrato_cartao_beneficio__status=ContractStatus.FINALIZADA_LIBERACAO_SAQUE.value,
                        contrato_cartao_beneficio__saque_parcelado=True,
                    )
                )
            ).order_by('ultima_atualizacao')

        elif self.product_type == EnumTipoProduto.SAQUE_COMPLEMENTAR:
            return self.queryset.filter(
                Q(
                    tipo_produto__in=[
                        EnumTipoProduto.SAQUE_COMPLEMENTAR,
                    ],
                    ultima_atualizacao__range=(self.init_date, self.end_date),
                )
                & (
                    Q(
                        contrato_saque_complementar__status=ContractStatus.FINALIZADA_LIBERACAO_SAQUE.value,
                        contrato_saque_complementar__possui_saque=True,
                    )
                    | Q(
                        contrato_saque_complementar__status=ContractStatus.FINALIZADA_LIBERACAO_SAQUE.value,
                        contrato_saque_complementar__saque_parcelado=True,
                    )
                )
            ).order_by('ultima_atualizacao')


class ExportPortabilityReport(ExportContractsReport):
    def get_finalization_contracts(self):
        return self.queryset.filter(
            tipo_produto=self.product_type,
            contrato_portabilidade__status=ContractStatus.INT_FINALIZADO.value,
            dt_pagamento_contrato__range=(self.init_date, self.end_date),
        ).order_by('ultima_atualizacao')

    def get_balance_return_contracts(self):
        balance_ids = (
            StatusContrato.objects.filter(
                nome=ContractStatus.SALDO_RETORNADO.value,
            )
            .values_list('contrato_id', flat=True)
            .distinct()
        )
        return self.queryset.filter(
            Q(
                tipo_produto=self.product_type,
                contrato_portabilidade__dt_recebimento_saldo_devedor__range=(
                    self.init_date,
                    self.end_date,
                ),
                id__in=balance_ids,
            )
        ).order_by('ultima_atualizacao')


class ExportFreeMarginReport(ExportContractsReport):
    def get_finalization_contracts(self):
        return self.queryset.filter(
            tipo_produto=self.product_type,
            contrato_margem_livre__status=ContractStatus.INT_FINALIZADO.value,
            contrato_margem_livre__dt_desembolso__range=(self.init_date, self.end_date),
        ).order_by('ultima_atualizacao')


class ExporPortabilityRefinancingReport(ExportContractsReport):
    def get_finalization_contracts(self):
        return self.queryset.filter(
            tipo_produto=self.product_type,
            contrato_refinanciamento__status=ContractStatus.INT_FINALIZADO_DO_REFIN.value,
            dt_pagamento_contrato__range=(self.init_date, self.end_date),
        ).order_by('ultima_atualizacao')

    def get_balance_return_contracts(self):
        balance_ids = (
            StatusContrato.objects.filter(
                nome=ContractStatus.SALDO_RETORNADO.value,
            )
            .values_list('contrato_id', flat=True)
            .distinct()
        )
        return self.queryset.filter(
            Q(
                tipo_produto=self.product_type,
                contrato_portabilidade__dt_recebimento_saldo_devedor__range=(
                    self.init_date,
                    self.end_date,
                ),
                id__in=balance_ids,
            )
        ).order_by('ultima_atualizacao')
