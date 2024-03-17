"""
This module implements DataFrameGenerator class.
"""

# third
from django.db.models.query import QuerySet
import pandas as pd
from contract.models.contratos import Contrato
from rest_framework.exceptions import ValidationError
from contract.products.consignado_inss.models.dados_in100 import DadosIn100

# local
from contract.utils import get_contrato_status_name, get_tipo_conta_name
from scripts.generate_port_refin_dataframe.thread_pool import ThreadPool
from scripts.generate_port_refin_dataframe.utils import (
    calculate_endorsed_dataprev,
    calculate_last_tentative_port,
    calculate_last_tentative_refin,
    calculate_qi_tech_status,
)
from utils.bank import get_client_bank_data


class DataFrameGenerator:
    """
    This class is responsible to generate the report to the script
    generate_port_refin_dataframe
    """

    def __init__(self, queryset: QuerySet):
        columns = [
            'id',
            'contrato_portabilidade__chave_proposta',
            'contrato_refinanciamento__chave_operacao',
            'numero_beneficio',
            'status',
            'contrato_portabilidade__status',
            'contrato_refinanciamento__status',
        ]
        self.pool_executor = ThreadPool()
        self.pool_columns = []

        self.df = pd.DataFrame(list(queryset.values(*columns)))

    def rename_columns(self):
        # Define a dictionary mapping old column names to new column names
        new_names = {
            'contrato_portabilidade__chave_proposta': 'proposta',
            'contrato_refinanciamento__chave_operacao': 'operacao',
            'contrato_portabilidade__status': 'port_status_code',
            'contrato_refinanciamento__status': 'refin_status_code',
        }

        # Rename columns using the rename() method
        self.df.rename(columns=new_names, inplace=True)

    def humanize_status(self):
        # humanize status
        self.df['status'] = self.df['status'].apply(
            lambda x: get_contrato_status_name(x)
        )

        # humanize port status
        self.df['status_port'] = self.df['port_status_code'].apply(
            lambda x: get_contrato_status_name(x)
        )

        # humanize refin status
        self.df['status_refin'] = self.df['refin_status_code'].apply(
            lambda x: get_contrato_status_name(x)
        )

        # humanize tipo conta
        self.df['conta_tipo'] = self.df['conta_tipo'].apply(
            lambda x: get_tipo_conta_name(x)
        )

    def clean_columns(self):
        self.df.drop(
            [
                'port_status_code',
                'refin_status_code',
            ],
            axis=1,
            inplace=True,
        )

    def display_preview(self):
        print('Data Frame Preview ---------------------------------------')
        print(self.df)

        print('\n\nData Frame Info ---------------------------------------')
        print(self.df.info())

        print('\n\nData Frame Describe ---------------------------------------')
        print(self.df.describe())

    def add_pool_column(self, column_names: list, base_column_name: str, function):
        # str to list
        if isinstance(column_names, str):
            column_names = [column_names]

        # create columns
        for column_id, column_name in enumerate(column_names):
            self.df[column_name] = None
            self.pool_columns.append([column_name, column_id])

        # adding thread
        number_of_rows = self.df.shape[0]
        for i in range(number_of_rows):
            base_value = self.df.loc[i, base_column_name]
            thread_id = self.pool_executor.add_thread(function, base_value)

            # filling the ids on the destination columns
            # to replace them later
            for column_id, column_name in enumerate(column_names):
                # fill column
                response_pair_id = '%d,%d' % (thread_id, column_id)
                self.df.loc[i, column_name] = response_pair_id

    def add_endorsement_on_dataprev_column(self):
        self.add_pool_column(
            'endorsed_on_dataprev', 'operacao', calculate_endorsed_dataprev
        )

    def add_qi_tech_status_column(self):
        self.add_pool_column('qi_tech_status', 'proposta', calculate_qi_tech_status)

    def add_last_tentative_columns(self):
        self.add_pool_column(
            ['port_last_tentative_status', 'port_last_tentative_date'],
            'proposta',
            calculate_last_tentative_port,
        )
        self.add_pool_column(
            ['refin_last_tentative_status', 'refin_last_tentative_date'],
            'proposta',
            calculate_last_tentative_refin,
        )

    def fill_pool_columns(self):
        # execute all the threads
        self.pool_executor.submit_all()

        # fill the data frame with the results
        for column in self.pool_columns:
            column_name, _ = column
            self.df[column_name] = self.df[column_name].apply(self.extract_response)

    def extract_response(self, ids: str):
        thread_id, column_id = ids.split(',')
        return self.pool_executor.get(int(thread_id))[int(column_id)]

    def add_bank_data_columns(self):
        bank_data_series = self.df['id'].apply(self.get_bank_data)
        self.df = pd.concat([self.df, bank_data_series], axis=1)

    def get_bank_data(self, id: int):
        # get client
        contract = Contrato.objects.get(id=id)
        client = contract.cliente

        # get bank data
        try:
            bank_data = get_client_bank_data(client, [4])
            conta_tipo = bank_data.conta_tipo
            conta_banco = bank_data.conta_banco
            conta_agencia = bank_data.conta_agencia
            conta_numero = bank_data.conta_numero
            conta_digito = bank_data.conta_digito
        except ValidationError:
            msg = 'No bank data'
            conta_tipo = conta_banco = conta_agencia = conta_numero = conta_digito = msg

        # insert them on apply
        values_to_insert = [
            conta_tipo,
            conta_banco,
            conta_agencia,
            conta_numero,
            conta_digito,
        ]
        names = [
            'conta_tipo',
            'conta_banco',
            'conta_agencia',
            'conta_numero',
            'conta_digito',
        ]

        return pd.Series(values_to_insert, index=names)

    def add_in100_tipo_beneficio(self):
        def get_in100_tipo_beneficio(id: int) -> int:
            contrato = Contrato.objects.get(id=id)
            cliente = contrato.cliente
            in100s = DadosIn100.objects.filter(cliente=cliente)
            benefits = [str(in100.numero_beneficio) for in100 in in100s]
            return ', '.join(benefits)

        self.df['in100_tipo_beneficio'] = self.df['id'].apply(get_in100_tipo_beneficio)
