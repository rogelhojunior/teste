import json

import requests
from django.contrib.auth.decorators import permission_required
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.shortcuts import render

from core import settings
from .forms import APICallForm
from .models import APICallLog
import shlex  # Usado para escapar corretamente strings que serão usadas em shell commands
import logging


logger = logging.getLogger('digitacao')


@permission_required('api_caller.can_access_apicaller', login_url='/admin/')
def api_caller_view(request):
    response_data = None

    if request.method == 'POST':
        form = APICallForm(request.POST)
        if form.is_valid():
            method = form.cleaned_data['method']
            url = form.cleaned_data['url']
            # Converta strings JSON para dicionários
            headers = json.loads(form.cleaned_data['headers'])
            body = form.cleaned_data['body']

            curl_command = build_curl_command(method, url, headers, body)
            logger.info(f'cURL command: {url}: {curl_command}')
            if settings.ENVIRONMENT == 'PROD':
                response = requests.request(method, url, headers=headers, data=body)
            response = requests.request(
                method, url, headers=headers, data=body, verify=False
            )

            log = form.save(commit=False)
            log.response_status_code = response.status_code

            # Checa se a resposta é um JSON válido
            try:
                formatted_content = json.loads(response.text)
                log.response_content = json.dumps(formatted_content, indent=4)
            except json.JSONDecodeError:
                log.response_content = (
                    response.text
                )  # Se não for JSON, apenas use o texto bruto

            log.save()
            response_data = {
                'status_code': response.status_code,
                'content': log.response_content,
            }

    else:
        form = APICallForm()

    logs_list = APICallLog.objects.all().order_by('-timestamp')

    # Paginator
    paginator = Paginator(logs_list, 10)  # 10 logs por página

    page = request.GET.get('page')
    try:
        logs = paginator.page(page)
    except PageNotAnInteger:
        # Se a página não for um inteiro, exiba a primeira página.
        logs = paginator.page(1)
    except EmptyPage:
        # Se a página estiver fora do intervalo (por exemplo, 9999), exiba a última página de resultados.
        logs = paginator.page(paginator.num_pages)

    if (
        request.headers.get('x-requested-with') == 'XMLHttpRequest'
    ):  # Checando se é uma solicitação AJAX
        return render(request, 'api_caller/logs_section.html', {'logs': logs})
    else:
        return render(
            request,
            'api_caller/api_caller.html',
            {'form': form, 'logs': logs, 'response_data': response_data},
        )


def build_curl_command(url, method, headers, data):
    # Inicia o comando cURL
    curl_cmd = f'curl --location {shlex.quote(url)}'

    # Método HTTP
    if method.upper() in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']:
        curl_cmd += f' --request {method.upper()}'

    # Adiciona cabeçalhos
    for header, value in headers.items():
        curl_cmd += f" --header {shlex.quote(header + ': ' + value)}"

    # Adiciona corpo da solicitação se for um método que permite corpo
    if data and method.upper() in ['POST', 'PUT', 'PATCH']:
        # Converte o dicionário para uma string JSON e garante que está adequadamente escapada
        data_string = json.dumps(data)
        curl_cmd += f' --data-raw {shlex.quote(data_string)}'

    return curl_cmd
