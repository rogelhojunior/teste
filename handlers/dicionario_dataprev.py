success_mappings = {
    'successfully_included': ('BD', 'Inclusão efetuada com sucesso'),
    'successfully_removed': ('BF', 'Exclusão (ou baixa) efetuada com sucesso'),
    'successfully_reactivated': ('BR', 'Reativação efetuada com sucesso'),
    'successfully_suspended': ('BS', 'Suspensão efetuada com sucesso'),
    'succesfully_included': ('BD', 'Inclusão efetuada com sucesso'),
    'succesfully_removed': ('BF', 'Exclusão (ou baixa) efetuada com sucesso'),
    'succesfully_reactivated': ('BR', 'Reativação efetuada com sucesso'),
    'succesfully_suspended': ('BS', 'Suspensão efetuada com sucesso'),
}

error_mappings = {
    'consignable_margin_excceded': ('HW', 'Margem consignável excedida'),
    'benefit_blocked_by_tbm': (
        'IT',
        'Benefício bloqueado por transferência de benefício',
    ),
    'benefit_blocked_by_beneficiary': ('IE', 'Benefício bloqueado pelo beneficiário'),
    'invalid_disbursement_account': ('AN', 'Conta corrente/DV do favorecido inválidos'),
    'reservation_already_included': ('HX', 'Empréstimo já cadastrado'),
    'benefit_blocked_by_granting_process': (
        'IF',
        'Benefício bloqueado por TBM ou bloqueado na concessão',
    ),
    'processing_payroll': (
        'AV',
        'Não é possível realizar a operação até que seja concluído o processamento da folha de pagamento do INSS',
    ),
    'invalid_cbc': ('OF', 'O CBC da IF pagadora está inválido'),
    'first_name_mismatch': ('IA', 'Nome divergente'),
    'legal_representative_document_number_mismatch': (
        'OS',
        'O CPF não corresponde ao CPF do representante legal ativo',
    ),
    'invalid_state': ('AY', 'Sigla do Estado do favorecido inválida'),
    'operation_not_allowed_on_this_reservation_status': (
        'HZ',
        'Não é possível fazer a operação com o empréstimo nesta situação ',
    ),
    'invalid_contract_date': (
        'AP',
        'Competência de início de desconto ou data de início ou fim de contrato inválida',
    ),
    'required_fields_missing': (
        'GA',
        'O(s) campo(s) obrigatório(s) não informados: Proponente, um dos campos (Beneficio, Número Unico, CPF do Titular) e um dos campos (CBC Origem, período da operação)',
    ),
    'cbc_missing': ('BC', 'Requisição sem CBC'),
    'contract_number_missing': ('NC', 'A requisição está sem número de contrato'),
    'benefit_number_missing': ('NB', 'Requisição sem número do benefício'),
    'invalid_bank_code': ('CA', 'Código do banco inválido'),
    'exceeded_number_of_allowed_contracts': (
        'HR',
        'Quantidade de contratos permitida excedida',
    ),
    'invalid_image_format': ('PV', 'Imagem com formato errado'),
    'operation_not_allowed_IR': (
        'IR',
        'Prazo da operação é maior que a data de extinção de cota do benefício',
    ),
    'wrong_bank_code_destination': (
        'PK',
        'O número da portabilidade foi encontrado com o destino errado do código do banco',
    ),
    'wrong_benefit_number_on_portability': (
        'PH',
        'O número da portabilidade foi encontrado com o número do benefício errado',
    ),
}


def retorno_sucesso_dataprev(enumerator):
    if enumerator in success_mappings:
        codigo, descricao = success_mappings[enumerator]
        return codigo, descricao
    else:
        print(
            "O valor do 'enumerator' não corresponde a nenhuma chave em success_mappings."
        )


def retorno_erro_dataprev(enumerator):
    if enumerator in error_mappings:
        codigo, descricao = error_mappings[enumerator]
        return codigo, descricao
    else:
        print(
            "O valor do 'enumerator' não corresponde a nenhuma chave em success_mappings."
        )
