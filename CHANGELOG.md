# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Endpoint `/historico-teimosinha-inss` que retorna as tentativas da Teimosinha INSS de forma paginada. [AM-707]
- Retorno de flag indicando se o contrato possui histórico de tentativa da Teimosinha INSS em `/detalhe-contratos`. [AM-707]
- O controle de exibição dos botões de ação dos contratos de cartão foi centralizado no `changeform_view`. [AM-727]
- Adicionada paradinha Corban para o Cartão. [AM-680]
- Adicionado retorno da pendência de averbação no endpoint `/detalhe-contratos`. [AM-687]
- Criado endpoint para regularização de uma pendência para averbação. [AM-687]
- Criado endpoint para consultar ofertas de cross-sell. [AM-629]
- Envio número matrícula para reserva margem Zetra
- Sabemi Termo de adesão Seguro Vida [WHIT-30]
- Integração Zetra reservando margem unificada [WHIT-29]
- Campos de dt_primeiro_pagamento e dt_ultimo_pagamento em Portabilidade
- Campos de dt_primeiro_pagamento e dt_ultimo_pagamento em Refinanciamento
- Verificação do tempo de expiração do benefício com a dt_ultimo_pagamento retornada na inserção das propostas.
- Adicionado no processamento da falha de pagamento a verificação do enumerator retornado, deixando passar apenas os mapeados
- Salvando data da primeira e última parcela de margem livre durante a inserção da proposta.
- Adição esteira `Derivacao - Checagem averbacao` [AM-539]
- Termo de adesão Seguro Prestamista (Plano Ouro) [WHIT-106]
- Termo de adesão Seguro Prestamista (Plano Diamante) [WHIT-236]
- Cancelamento dos Planos - Generali [AM-586]
- Adicionando a biblioteca holidays para saber se determinado dia é feriado ou não. Baseado na data atual, sempre retorna a próxima data que não seja sábado, domingo e não seja feriado.
- Criando utils para get_brazilian_bank e get_client_bank_data _[HO-750]_
- Renomeando método de **refin_payment_resubmission -> payment_resubmission**. [HO-750]
- Adicionando rota de resubmissão de pagamento para margem livre e método estático para selecionar o resource adequado dependendo do produto. [HO-750]
- Criando classe base de **PaymentResubmission**. Modificando classe o suficiente para o envio ser genérico tanto para MargemLivre quando para refinanciamento. [HO-750]
- Criando middleware de **DynamicSessionTimeoutMiddleware** e modelo de **BackofficeConfigs** [HO-721]
Passando o produto para realizar a resubmissão.
- Reserva de margem unificada pela averbadora Neoconsig [AM-570]
- Recálculo do Refinanciamento em Port+Refin utilizando a parcela original retornada E testando apenas as taxas cadastradas no backoffice.
- Novo parâmetro de percentual_variacao_troco_recalculo para verificar se o troco é válido dentro do intervalo definido.Caso não seja, avalia a próxima menor taxa e por fim, tenta enquadrar na menor delas [HO-824]
- **[Geral]** HIERARQUIA - Representante comercial (Byx)
- **[Geral]** HIERARQUIA - CRUD de usuários
- **[Geral]** Expiração de Senha e criação de senha Forte
- **[Geral]** Adição de filas novas para o celery. Fila nova de reports, recalculation e genéricas para processamentos leves e pesados.
- Adiciona action "Resimular Port + Refin" no admin de contratos.
- **[Port+Refin]** Agora a inserção da proposta de Port+Refin utiliza a parcela digitada ao invés da taxa.
- **[Port+Refin]** Agora no recálculo de Port+Refin, quando a Port é maior que o teto do inss cadastrado, reprova as duas propostas
### HO-733 e HO-732:
- Modificada a confirmação do refinanciamento para enviar uma nova payload
- Refatorando celery e removendo c -> 1 para quantidade de núcleos da aplicação
#### HO-733 e HO-732:
- `.env.develop`: Chave API `AWS3_LINK_SHORTENER_API_KEY` para serviço AWS3.
- `core/services/shorten_url/aws3_link_shortener.py`: Classes `BaseShortenURL`, `AWS3LinkShortURLService`,
  `ShortURLManager` para serviço AWS3.
- `core/dto/services/shorten_url/*`: DTOs para gerenciamento de encurtamento, remoção e rastreamento
  de URLs.
#### HO-673
- Implementação do validador PortabilityProposalValidator a gestão de propostas de portabilidade no retorno do WebHook.
- Atualizações e melhorias na integração com a API QiTech, incluindo uma nova classe QiTechAPIHandlerAdapter para a criação de novos adapters e DTOs, e implementação do serviço QiTechApiService.
- Melhorias na classe QiTechAPIHandlerAdapter para construção e execução de requests API, geração de headers encriptados, decodificação e validação de respostas API.
- Implementação do Sentry para tracking de erros.
#### HO-678
- Implementação do validador `ProposalInformationPendingApprovalValidator` para gestão de propostas pendentes.
- Junto ao `ProposalInformationPendin'gApprovalValidator` foi criado classes de strategies `PortabilityInformationPendingStrategy` e `RefinancingInformationPendingStrategy` para cuidar dos processamentos de propostas pendentes de **portabilidade** e **Port + Refin** oriundos do webhook da **QiTech**.
- Criação do botão `ATUALIZAR DADOS PENDENTES` e modal `Atualizar dados pendentes`.
- Criação da view `update_issue_button` e endpoint do django admin `/atualiza-pendencia`.
- Adição da variável global `HOMOLOG_ENVIRONMENT_FLAGS` para auxiliar no desenvolvimento de novas flags.
- Adição do enum `BrazilianStatesEnum` em `core/common/enums.py`.
- Adição do campo `original_proposals_status` em `StatusContrato`, para ter o histórico de status das propostas.
#### HO-857
Com base na configuração encontrada:
- Se a configuração indicar aprovação, o contrato será automaticamente aprovado.
- Se indicar reprovação, o contrato será automaticamente reprovado.
- Se a configuração for para "Análise Mesa", o contrato será direcionado para checagem manual.
#### Refactorings
- Remoção da view descontinuada `ReceberWebhookQitech` substituindo pela atual utilizada `ReceberWebhookQitech2`, renomeando a `ReceberWebhookQitech2` para `ReceberWebhookQitech` e removendo a `ReceberWebhookQitech`.
- Troca de path do package `validators` de `handlers/qitech_api/validators` para `handlers/webhook_qitech/validators`, para melhor contexto, afetando somete o import do `PortabilityProposalValidator` em `handlers/webhook_qitech/__init__.py`.
- Seleção de múltiplos produtos para exportar o relatório de contratos.
- Arquivo enviado por email ao extrair o relatório agora contém o nome dos produtos selecionados.

### Fixed
- `contract/products/portabilidade/api/views.py` e `contract/views.py`: Integração de `AWS3LinkShortURLService`
  substituindo pyshorteners em desenvolvimento.
- Substituição do pyshorteners pelo `ShortURLManager` para padronizar encurtamento de URLs.
- Função auxiliar `flag_short_url` em várias views para transição para AWS3.
- Verificações de ambiente para testes QA e PO, a serem removidas antes da produção.

###  WHITE-219
 - Adicionado pagamento via microserviço externo - repositório white_seguros. Esse repositório lida com a logica dos pagamentos da DIGIMAIS

### Changed
- **[Geral]** Relatórios de empréstimo - Filtragem dos status

### Removed


## [3.0.0] - 20-12-2023

### Added

- Todo o sistema antes da criação do CHANGELOG.md nesse repositório.

### Fixed

- Todo o sistema antes da criação do CHANGELOG.md nesse repositório.

### Changed

- Todo o sistema antes da criação do CHANGELOG.md nesse repositório.

### Removed

- Todo o sistema antes da criação do CHANGELOG.md nesse repositório.


## [Example]

### Added
- Funcionalidade adicionada [AM-000]


### Fixed
- Funcionalidade ajustada [FE-000]


### Changed
- Funcionalidade alterada [HO-000]


### Removed
- Funcionalidade removida [WHIT-000]
