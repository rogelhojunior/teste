# Processo de inserção de proposta para contrato de Portabilidade

Ao final da jornada de portabilidade é necessário gerar um link para a formalização, então o front-end manda uma requisição para o back-end no endpoint:

```bash
POST /api/contratos/formalizacao/enviar-link/
```

contendo no corpo da requisição apenas os token do envelope de contratos que deverão ser formalizados, exemplo:

```json
{
    "token":"066d2f49-057f-4b0a-926d-fe95455f995f"
}
```

A função *link_formalizacao_envelope* será chamada recebendo como parâmetro o token do envelope. Para cada contrato dentro desse envelope de contratos, se o contrato for do tipo portabilidade então a função *insert_portability_proposal* será chamada assincronamente, isso é, para cada contrato de Portabilidade dentro do envelope existirá uma thread executando em paralelo.

Cada uma dessas threads será responsável por enviar um request para QITech. Para auxiliar nessa tarefa a classe *QiTechProposalInserter* foi criada, a função *send_proposal* desta classe é responsável por enviar o request. Antes de enviar a proposta à Qi Tech a flag *is_proposal_being_inserted* do objeto de Portabilidade é mudada para True.

Esse request possui um payload grande e complexo que esta sendo montado pela classe *PayloadBuilder* dentro do módulo *core/tasks/insert_portability_proposal/PayloadBuilder.py*

O request é feito e a resposta é guardada dentro do objeto *QiTechProposalInserter* e então uma das funções de tratamento de dados podem ser chamadas para salvar os dados que foram retornados da QiTech. Uma função para tratar sucesso (status = 200 ou 201 ou 202) e outra para tratar erro.

A função que trata uma resposta de sucesso precisa fazer uma série de verificações antes de aceitar ou recusar a proposta. Essas verificações são as condições dentro da função *validate_proposal* da classe *QiTechProposalInserter*. Se a proposta for válida os seguintes status serão salvos:

- status do objeto Contrato: *EnumContratoStatus.AGUARDANDO_FORMALIZACAO*
- status do objeto Portabilidade: *ContractStatus.FORMALIZACAO_CLIENTE*

se não for válida os status serão:

- status do objeto Contrato: *EnumContratoStatus.CANCELADO*
- status do objeto Portabilidade: *ContractStatus.REPROVADO*

Enquanto tudo isso é feito o cliente final poderá acessar a URL de formalização, carregando a página de formalização do envelope de contratos, a front-end (dessa vez o sistema Happy Formalização) enviará um request para o back-end no seguinte endpoint:

*GET /api/detalhe-formalizacao/**&lt;token-envelope&gt;**/*

Esse endpoint primeiro verifica se todos os contratos do envelope já foram processados, isso é, se nenhum contrato no envelope esta com a flag *is_proposal_being_inserted* igual a True:

```python
envelope = EnvelopeContratos(token_envelope=token)
if envelope.is_any_proposal_being_inserted():
    payload = {
        'not_ready': True,
        'reason': 'Ainda há contratos sendo processados',
    }
    return Response(payload, status=HTTP_200_OK)
```

como podemos ver o seguinte payload será enviado de volta ao front-end caso ainda hajam contratos processando:

```python
{
    'not_ready': True,
    'reason': 'Ainda há contratos sendo processados',
}
```

dessa forma o front-end pode exibir uma mensagem e uma tela de carregando e pode se conectar com o WSS (Web Socket Server) para aguardar uma mensagem de **"all done"**, isso é, todos os contratos foram finalizados. Para receber essa mensagem é necessário se conectar no WSS usando como id o token do envelope, ao receber a mensagem o front-end faz novamente a requisição e o back-end retornará os dados necessários para seguir com a formalização.

Para que retornar a mensagem "All done" pelo WSS o sistema back-end, a cada processamento de contrato, verifica se ainda existe algum contrato no mesmo envelope que ainda esta sendo processado, usando a função:

```python
envelope.is_any_proposal_being_inserted()
```

se essa função retornar *False* então o back-end manda uma mensagem para o WSS usando a chave do token como id com os seguintes dados:

```json
{
    "message": "all done",
    "type": "CONTRACTS_PROCESSED"
}
```

Uma vez todos os contratos do envelope processados e uma vez notificado o front-end (que nem sempre estará esperando a mensagem, mas esta tem que ser enviada de qualquer forma), o macro procedimento *inserir proposta de portabilidade* esta finalizado.
