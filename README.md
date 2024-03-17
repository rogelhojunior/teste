<p align="center">
  <img src="https://www.byxcapital.com.br/logo_byx.png" width=25% align="right"/>
</p>
<h1 align="center">Happy Originação 💼🎉</h1>

<p align="center">
  Bem-vindo ao Happy Originação, o seu lugar para tudo relacionado a cartões consignados e portabilidade. Estamos entusiasmados por tê-lo conosco na nossa jornada!
</p>

## Índice 📝

1. [Introdução](#introdução-)
2. [Requisitos Básicos](#requisitos-básicos-)
3. [Instalação dos Requisitos](#instalação-dos-requisitos-)
4. [Clonando o Repositório](#clonando-o-repositório-)
5. [Local Settings](#local-settings-)
6. [Diretórios do Projeto](#diretórios-do-projeto-)
7. [Requirements](#requirements-)
8. [APIs no Postman](#apis-no-postman-)
9. [Padrão de código](#padrão-de-código-)
10. [Contribuidores](#contribuidores-)

---
## Introdução 🚀

Bem-vindo ao Happy Originação, um sistema de gerenciamento focado em soluções para cartão consignado e portabilidade (por enquanto).

Aqui, no Happy Originação, trabalhamos para tornar a gestão dos nossos produtos a mais tranquila possível.
Nosso sistema visa facilitar o trabalho dos gestores,
fornecendo todas as ferramentas necessárias para uma administração eficiente.

Seja você um desenvolvedor veterano ou um recém-chegado à nossa equipe,
estamos felizes em tê-lo conosco.
Esta documentação visa guiá-lo em todas as etapas necessárias para configurar e entender nosso projeto.

Vamos começar!

## Requisitos Básicos 💻

Para rodar este projeto, você precisará ter instalado:

- Python
- IDE (preferencialmente PyCharm)
- Git Bash
- MySQL

## Instalação dos Requisitos 🔧

Este é um guia básico sobre como instalar os requisitos:

1. **Python**: Você pode baixar o Python do site oficial [aqui](https://www.python.org/downloads/).
2. **PyCharm**: Baixe e instale o PyCharm da JetBrains [aqui](https://www.jetbrains.com/pycharm/download/).
3. **Git Bash**: O Git Bash pode ser baixado e instalado a partir deste [link](https://gitforwindows.org/).
4. **MySQL**: Você pode baixar o MySQL [aqui](https://dev.mysql.com/downloads/installer/).

## Clonando o Repositório 📦

Para clonar o repositório, você pode seguir os passos abaixo:

Com o git Bash instalado e configurado clone o repositorio abra o Git Bash/terminal/cmd e execute o seguinte comando:
git clone [https://github.com/byxcapital/originacao-backend](https://github.com/byxcapital/originacao-backend)


## Variáveis de ambiente 🔑

O arquivo `.env.develop` permite personalizar as configurações do ambiente de desenvolvimento. Para rodar o projeto, criei uma cópia do arquivo `.env.develop` e renomeie para `.env`, assim o seu projeto terá as variáveis de ambiente necessárias para rodar na sua máquina. O arquivo `.env` não é versionado, assim você pode testar diferentes valores para as variáveis de ambiente.

Sempre que uma nova variável de ambiente for adicionada, além de incluir no seu arquivo `.env`, você deve incluir no arquivo `.env.develop`, assim qualquer desenvolvedor vai conseguir rodar o projeto com essa nova variável de ambiente. Além disso, você deve carregar essa variável no arquivo `settings.py`, para que o projeto tenha esse novo valor. Para adicionar uma nova variável de ambiente no projeto, seguir os passos abaixo:

- Adicione a variável no arquivo `.env`:
    ```
    CHAVE_STRING="STRING"
    CHAVE_INT=1234
    CHAVE_BOOL=True
    CHAVE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\nhdkaadjsl...\ndhasdhasH\n-----END PRIVATE KEY-----"
    ```

- Adicione a variável no arquivo `settings.py` para que o projeto enxergue a nova variável:
    ```
    from decouple import config (caso não tenha importado ainda)

    CHAVE_STRING = config('CHAVE_STRING')
    CHAVE_INT = config('CHAVE_INT', cast=int)
    CHAVE_BOOL = config('CHAVE_BOOL', default=False, cast=bool)
    CHAVE_PRIVATE_KEY = config('CHAVE_PRIVATE_KEY').replace('\\n', '\n')
    ```

- Use a variável em qualquer arquivo do projeto:
    ```
    from django.conf import settings (caso não tenha importado ainda)

    url = f'{settings.CHAVE_STRING}/rota-api'

    soma_limite = settings.CHAVE_INT + 1

    if settings.CHAVE_BOOL:
        func()

    chave_autenticaçao = pegar_chave_autenticacao(settings.CHAVE_PRIVATE_KEY)
    ```


| Variável | Valor Exemplo | Descrição                                                           |
|:---------|:--------------|:--------------------------------------------------------------------|
| `DEBUG` | `True` | Ativa ou desativa o modo de depuração.                              |
| `ALLOWED_HOSTS` | `['*']` | Lista de hosts/domínios permitidos.                                 |
| `CSRF_TRUSTED_ORIGINS` | `['https://exemplo.com']` | Lista de origens confiáveis para o CSRF.                            |
| `SITE_ID` | `1` | ID do site no banco de dados.                                       |
| `STATIC_URL` | `'/static/'` | URL para acessar os arquivos estáticos.                             |
| `DATABASES` | `{...}` | Configurações do banco de dados.                                    |
| `ADMIN_NAME` | `"D100"` | Nome do administrador.                                              |
| `ADMIN_EMAIL` | `"contato@laratech.com.br"` | Email do administrador.                                             |
| `IS_LOCAL` | `True` | Indica se o ambiente é local.                                       |
| `IS_STAGING` | `False` | Indica se o ambiente é de staging.                                  |
| `IS_PROD` | `False` | Indica se o ambiente é de produção.                                 |
| `PRIVATE_KEY` | `open("caminho_para_chave.pem", "r").read()` | Chave privada.                                                      |
| `LOGGING` | `{...}` | Configurações de log.                                               |
| `BUCKET_NAME_AMIGOZ` | `"documentos-clientes-amigoz"` | Nome do bucket para clientes Amigoz.                                |
| `BUCKET_NAME_PORTABILIDADE` | `"documentos-clientes-portabilidade"` | Nome do bucket para portabilidade de clientes.                      |
| `BUCKET_NAME_INSS` | `"documentos-cliente-inss"` | Nome do bucket para clientes INSS.                                  |
| `BUCKET_NAME_TERMOS` | `"termos-amigoz"` | Nome do bucket para termos Amigoz.                                  |
| `BUCKET_NAME_TERMOS_IN100` | `"termos-in100"` | Nome do bucket para termos IN100.                                   |
| `CELERY_BROKER_URL` | `'redis://localhost:6379/0'` | URL do broker do Celery.                                            |
| `CONST_HUB_URL` | `"https://byx-hub-homolog.azurewebsites.net"` | URL do hub.                                                         |
| `BANKSOFT_USER` | `"------"` | Usuário Banksoft.(peça a um administrador)                          |
| `BANKSOFT_PASS` | `"--------"` | Senha Banksoft.(peça a um administrador)                            |
| `URL_TEMSAUDE` | `"https://qa.api.tempravoce.com"` | URL da Tem Saúde.                                                   |
| `URL_TOKEN_ZEUS` | `"https://develop.dd.meutem.com.br/v1/api-auth/login"` | URL do token Zeus.                                                  |
| `TEMSAUDE_COMPANYID` | `"-----"` | ID da empresa Tem Saúde(peça a um administrador).                   |
| `TEMSAUDE_APIKEY` | `"------"` | Chave API da Tem Saúde(peça a um administrador).                    |
| `TEMSAUDE_CODONIX` | `"-----"` | Código Onix da Tem Saúde(peça a um administrador).                  |
| `URL_UNICO_SERVICES` | `"https://crediariohomolog.acesso.io/byxcapitalhml/services/v3/AcessoService.svc"` | URL de serviços da Unico.                  |
| `UNICO_API_KEY` | `"------"` | Chave API dos serviços da Unico(peça a um administrador).                  |
| `BASE_URL` | `"http://localhost:8000"` | URL onde está rodando o projeto.                                    |
| `QITECH_INTEGRATION_KEY` | `"------"` | Chave API QITECH (Deve ser solicitado a QITECH)                     |
| `QITECH_CLIENT_PRIVATE_KEY` | `"------"` | Chave PRIVADA BYX/QITECH (Deve ser solicitado a QITECH).            |
| `QITECH_DATE_FORMAT` | `"------"` | Formato de data utilizado na comunicação com os enpoints da QITECH. |
| `QITECH_BASE_ENDPOINT_URL` | `"------"` | URL base para os endpoints da QITECH.                               |
| `QITECH_ENDPOINT_DEBT_SIMULATION` | `"------"` | Enpoint da simulação de contrato da QITECH.                         |

**Configurações do Amazon S3**

O projeto utiliza o Amazon S3 para armazenamento de documentos. Os nomes dos buckets são:

- `BUCKET_NAME_AMIGOZ`: "documentos-clientes-amigoz"
- `BUCKET_NAME_PORTABILIDADE`: "documentos-clientes-portabilidade"
- `BUCKET_NAME_INSS`: "documentos-cliente-inss"
- `BUCKET_NAME_TERMOS`: "termos-amigoz"

**Configurando AWS CLI**

Para configurar o AWS CLI em seu computador, siga os passos abaixo:

1. Baixe e instale o AWS CLI de acordo com o seu sistema operacional: https://aws.amazon.com/cli/
2. Abra o terminal e execute o comando `aws configure`.
3. Insira as chaves de acesso (Access Key ID e Secret Access Key) fornecidas pelo time.
4. Defina a região padrão e o formato de saída, se necessário.

O projeto utiliza o banco de dados MySQL. As configurações são as seguintes:

- `ENGINE`: django.db.backends.mysql
- `NAME`: {nome_do_banco}
- `USER`: {seu_user}
- `PASSWORD`: {sua_senha}
- `HOST`: localhost
- `PORT`: (vazio)
- `OPTIONS`: {'charset': 'utf8', 'use_unicode': True}

**DATABASES** = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'originacao',
        'USER': 'nome_usuario_banco',
        'PASSWORD': 'senha_banco',
        'HOST': 'localhost',
        'PORT': '',
        'OPTIONS': {
            'charset': 'utf8',
            'use_unicode': True, },
    },
}

**LOGGING** = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'base': {
            'format': '{name} ({levelname}) :: {message}',
            'style': '{'
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'base'
        },
        'logtail': {
            'class': 'logtail.LogtailHandler',
            'formatter': 'base',
            'source_token': 'Nz2rhiECTufK5UaGH9NmQJfB'
        },
    },
    'loggers': {
        'digitacao': {
            'handlers': ['console', 'logtail'],
            'level': 'INFO'
        },
        'cliente': {
            'handlers': ['console', 'logtail'],
            'level': 'INFO'
        },
        'webhookqitech': {
            'handlers': ['console', 'logtail'],
            'level': 'INFO'
        },
        'celery': {
            'handlers': ['console', 'logtail'],
            'level': 'INFO',
            'propagate': False,
        },
    }
}

## Diretórios do Projeto 📂

- 📂 [`.github`](./.github) - Contém arquivos específicos do GitHub, como workflows do GitHub Actions.
- 📂 [`api_log`](./api_log) - Contém os logs gerados pela API do projeto.
- 📂 [`auditoria`](./auditoria) - Utilizado para recursos de auditoria, contendo logs de auditoria ou código relacionado à auditoria.
- 📂 [`contract`](./contract) - Contém informações ou código relacionado a contratos e aos nossos produtos.
- 📂 [`core`](./core) - Contem codigos do cliente e codigos que são comuns a todos os produtos.
- 📂 [`credentials`](./credentials) - Contém arquivos de credenciais usados pelo projeto, como chaves privadas.
- 📂 [`custom auth`](./custom%20auth) - Contém código personalizado para autenticação no aplicativo.
- 📂 [`handlers`](./handlers) - Contém manipuladores para diferentes eventos ou erros que o aplicativo pode encontrar.
- 📂 [`static`](./static) - Diretório para arquivos estáticos, como CSS, JavaScript ou imagens usadas pelo aplicativo.
- 📂 [`templates`](./templates) - Contém templates, para páginas HTML se o projeto for um aplicativo da web.


## Requirements 📋

Os requirements do projeto estão listados no arquivo `requirements.txt`. Você pode instalar todos os requirements com o comando `pip install -r requirements.txt`.

| Biblioteca                 | Descrição                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
|----------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| anyio                      | Biblioteca de E/S assíncrona com uma interface comum para várias bibliotecas de E/S assíncrona                                                                                                                                                                                                                                                                                                                                                                                 |
| asgiref                    | Base do Django Channels                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| attrs                      | Biblioteca para escrever classes sem boilerplate                                                                                                                                                                                                                                                                                                                                                                                                                               |
| boto3                      | SDK da Amazon Web Services (AWS) para Python                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| botocore                   | Base do Boto3                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| certifi                    | Coleção de certificados raiz                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| cffi                       | Biblioteca para chamar código C a partir de Python                                                                                                                                                                                                                                                                                                                                                                                                                             |
| charset-normalizer         | Biblioteca para normalizar a codificação de caracteres                                                                                                                                                                                                                                                                                                                                                                                                                         |
| click                      | Criação de interfaces de linha de comando                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| colorama                   | Impressão de texto colorido no console                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| cryptography               | Várias primitivas criptográficas e receitas                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| decorator                  | Simplifica o uso de decoradores                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| defusedxml                 | XML library with several security hardenings                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| Django                     | Framework para desenvolvimento web                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| django-admin-interface     | Tema moderno e personalizável para o admin do Django                                                                                                                                                                                                                                                                                                                                                                                                                           |
| django-admin-rangefilter   | Adiciona o filtro por intervalo de datas no admin do Django                                                                                                                                                                                                                                                                                                                                                                                                                    |
| django-auditlog            | Faz log de alterações nos modelos do Django                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| django-axes                | Bloqueia tentativas de login após determinado número de falhas                                                                                                                                                                                                                                                                                                                                                                                                                 |
| django-colorfield          | Campo colorido personalizado para o Django                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| django-cors-headers        | Lidar com o cabeçalho CORS em um aplicativo Django                                                                                                                                                                                                                                                                                                                                                                                                                             |
| django-flat-responsive     | Tema responsivo para o admin do Django                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| django-flat-theme          | Outro tema para o admin do Django                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| django-import-export       | Ferramenta para fazer importação/exportação de dados no Django                                                                                                                                                                                                                                                                                                                                                                                                                 |
| django-tinymce             | Integração do editor HTML TinyMCE com o Django                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| djangorestframework        | Framework para construção de APIs no Django                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| djangorestframework-simplejwt | Autenticação JWT para o Django Rest Framework                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| ecdsa                      | Implementação do algoritmo ECDSA                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| et-xmlfile                 | Biblioteca de baixo consumo de memória para criar arquivos XML                                                                                                                                                                                                                                                                                                                                                                                                                 |
| future                     | Camada de compatibilidade entre Python 2 e Python 3                                                                                                                                                                                                                                                                                                                                                                                                                            |
| geocoder                   | Geocodificação de endereços                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| geographiclib              | Ferramentas para resolver problemas geodésicos                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| geopy                      | Cliente para vários serviços de geocodificação populares                                                                                                                                                                                                                                                                                                                                                                                                                       |
| gunicorn                   | Servidor HTTP WSGI para UNIX                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| h11                        | Biblioteca para HTTP/1.1                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| httpcore                   | Biblioteca para HTTP/1.1 e HTTP/2                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| httpx                      | Cliente HTTP com interface similar à do requests, mas com suporte a HTTP/1.1 e HTTP/2                                                                                                                                                                                                                                                                                                                                                                                          |
| idna                       | Biblioteca para suportar o padrão IDNA                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| isodate                    | Implementação do padrão ISO 8601                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| jmespath                   | Linguagem de consulta para JSON                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| lxml                       | Processamento de XML e HTML                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| MarkupPy                   | Biblioteca para gerar marcações HTML e XML                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| mysqlclient                | Cliente MySQL para Python                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| numpy                      | Pacote para computação científica                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| odfpy                      | Leitura e escrita de arquivos ODF                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| onesignal-sdk              | Biblioteca para facilitar a interação com a API do OneSignal                                                                                                                                                                                                                                                                                                                                                                                                                   |
| openpyxl                   | Leitura/escrita de arquivos .xlsx                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| Pillow                     | Manipulação de imagens                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| platformdirs               | Biblioteca para localização de diretórios específicos da plataforma                                                                                                                                                                                                                                                                                                                                                                                                            |
| pyasn1                     | Implementação do protocolo ASN.1                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| pycep-correios             | Consulta de CEPs no serviço dos Correios                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| pycparser                  | Parser para a linguagem C                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| pycpfcnpj                  | Validação de CPFs e CNPJs                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| PyJWT                      | Codificação e decodificação de JWTs                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| PyPDF2                     | Leitura/escrita de arquivos PDF                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| pyshorteners               | Biblioteca para encurtar URLs                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| python-dateutil            | Extensões para o módulo datetime                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| python-jose                | Codificação e decodificação de JWTs                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| python-slugify             | Criação de slugs para URLs                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| pytz                       | Definições de fuso horário                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| PyYAML                     | Leitura/escrita de arquivos YAML                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| ratelim                    | Decorador para limitação de taxa                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| reportlab                  | Criação de documentos em PDF                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| requests                   | Enviar solicitações HTTP                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| requests-file              | Transporte FILE para a biblioteca requests                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| requests-toolbelt          | Coleção de utilitários para a biblioteca requests                                                                                                                                                                                                                                                                                                                                                                                                                              |
| rfc3986                    | Validação de URIs conforme a RFC 3986                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| rsa                        | Implementação do algoritmo RSA                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| s3transfer                 | Biblioteca da AWS para transferências de arquivos para o S3                                                                                                                                                                                                                                                                                                                                                                                                                    |
| secure-smtplib             | Cliente SMTP com suporte a TLS e SSL                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| sentry-sdk                 | SDK do Sentry para Python                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| six                        | Camada de compatibilidade entre Python 2 e Python 3                                                                                                                                                                                                                                                                                                                                                                                                                            |
| sniffio                    | Detecção de bibliotecas de E/S assíncrona                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| sqlparse                   | Analisador sintático para SQL                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| tablib                     | Biblioteca para formatar e manipular dados tabulares                                                                                                                                                                                                                                                                                                                                                                                                                           |
| text-unidecode             | Biblioteca para transliterar Unicode para ASCII                                                                                                                                                                                                                                                                                                                                                                                                                                |
| typing_extensions          | Backports de adições ao módulo typing                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| tzdata                     | Base de dados de fuso horário                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| urllib3                    | Biblioteca para enviar solicitações HTTP                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| xlrd                       | Leitura de arquivos .xls e .xlsx                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| xlwt                       | Escrita de arquivos .xls                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| xmltodict                  | Trabalhar com XML de uma maneira mais pythonica                                                                                                                                                                                                                                                                                                                                                                                                                                |
| zeep                       | Cliente SOAP moderno para Python                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| geocoder                   | Geocodificação de endereços                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| xmltodict                  | Trabalhar com XML de uma maneira mais pythonica                                                                                                                                                                                                                                                                                                                                                                                                                                |
| numpy                      | Pacote para computação científica                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| pycpfcnpj                  | Validação de CPFs e CNPJs                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| django-admin-rangefilter   | Adiciona o filtro por intervalo de datas no admin do Django                                                                                                                                                                                                                                                                                                                                                                                                                    |
| secure-smtplib             | Cliente SMTP com suporte a TLS e SSL                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| celery                     | Biblioteca para gerenciamento de tarefas assíncronas                                                                                                                                                                                                                                                                                                                                                                                                                           |
| logtail-python             | SDK do Logtail para Python                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| django-ckeditor            | Integração do CKEditor com o Django                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| gevent                     | Biblioteca para programação assíncrona baseada em greenlets e eventos                                                                                                                                                                                                                                                                                                                                                                                                          |
| django_extensions          | Essa biblioteca fornece várias ferramentas adicionais que podem ser úteis durante o desenvolvimento de aplicativos Django.                                                                                                                                                                                                                                                                                                                                                     |
| pyOpenSSL                  | É uma biblioteca Python que fornece uma interface para o OpenSSL, permitindo que você trabalhe com criptografia e comunicação segura em aplicativos Python. Ele oferece funcionalidades para criar e verificar certificados digitais, estabelecer conexões seguras por meio de SSL/TLS, criptografar e descriptografar dados e muito mais. É amplamente usado para adicionar segurança a aplicativos da web, transferência de dados criptografados e autenticação de usuários. |
| django-celery-beat         | É uma extensão do Celery para agendar tarefas periódicas (cronjobs) em aplicativos Django. Ele oferece uma interface fácil de usar para agendar tarefas de rotina, como execução de tarefas em horários específicos, agendamento de tarefas diárias, semanais ou mensais, e muito mais. É útil para automatizar tarefas recorrentes e pode ser configurado diretamente no painel de administração do Django.                                                                   |
| python-decouple| Biblioteca utilizada para recuperar as variáveis de ambiente que estão em um arquivo .env|

## APIs no Postman 🤖

Todas as APIs do projeto estão disponíveis no Postman. Para acessá-las, importe a coleção fornecida pelo time. Para fazer isso, siga os passos abaixo:

1. Abra o Postman.
2. Clique no ícone de "Import" no canto superior esquerdo da janela.
3. Selecione a opção "Import From Link" ou "Upload Files", dependendo de como a coleção foi compartilhada com você.
   - Se for um link, cole o link da coleção e clique em "Import".
   - Se for um arquivo, navegue até o local do arquivo e selecione-o para importar.
4. Após a importação, a coleção aparecerá no painel esquerdo do Postman, na seção "Collections".
5. Clique na coleção importada para expandi-la e ver todas as APIs disponíveis.
6. Selecione a API desejada e insira os parâmetros necessários, se aplicável, antes de enviar a solicitação.

Agora você está pronto para testar e explorar todas as APIs do projeto utilizando o Postman.

## Padrão de código ⌨️

Para padronizar o código do projeto, utilizamos a ferramenta "pre-commit" para organizar e formatar com um padrão pré estipulado. A instalação e utilização é sem simples, sendo quase tudo ajustado automaticamente pela ferramenta, podendo ficar apenas alguns pequenos ajustes.
Para instalar e utilizar o "pre-commit":

1. Abra o terminal e rode o comando para instalar as dependências de dev:
```
    pip install -r dev-requirements.txt
```
2. Rode o comando abaixo para instalar os hooks do "pre-commit" na sua pasta ".git":
```
    pre-commit install
```
3. Após isso, é só fazer um commit que a ferramenta vai analisar os arquivos dentro do commit e fazer os ajustes conforme o padrão do projeto, e apontar os problemas que a ferramenta não conseguir ajustar automaticamente.
4. Se não tiver nada fora do padrão, o seu commit será realizado.
5. (Opcional): Se você quiser acelerar o processo, instale no seu editor de código as extensões do Flake8 e do Black, que o editor de código vai apontar os ajustes que serão feitos automaticamente.

Obs: Usuários de Windows que se depararam com o erro `RuntimeError: no .dist-info at` podem resolver com uma das duas possibilidades abaixo:

1. Excluir a pasta `virtualenv` que o erro vai apontar. Normalmente será algo parecido com: `C:\Users\<Nome_Usuario>\AppData\Local\Packages\PythonSoftwareFoundation.Python.<versao_python>_qbz5n2kfra8p0\LocalCache\Local\pypa\virtualenv`.
2. Habilitar caminhos longos no Windows: https://superuser.com/questions/1119883/windows-10-enable-ntfs-long-paths-policy-option-missing


## Contribuidores 👥

Agradecemos a todos que contribuíram para este projeto.
