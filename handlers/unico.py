import json
from datetime import datetime, timedelta

import boto3
import jwt
import requests
from django.conf import settings

s3_cliente = boto3.client(
    's3',
    region_name='us-east-1',
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
)


def gerar_assinatura_unico(private_key):
    # Transforma o tempo atual em epoch
    iat_epoch = int(datetime.now().timestamp())
    # Cria um tempo nova a partir da atual + 3 (Validade do token)
    exp_time = datetime.now() + timedelta(hours=3)
    exp_epoch = int(exp_time.timestamp())

    payload = {
        'iss': settings.ISS_UNICO,
        'aud': settings.URL_UNICO,
        'scope': '*',
        'exp': exp_epoch,
        'iat': iat_epoch,
    }

    encoded_jwt = jwt.encode(payload, private_key, algorithm='RS256')

    url = f'{settings.URL_UNICO}/oauth2/token'

    payload = f'grant_type=urn%3Aietf%3Aparams%3Aoauth%3Agrant-type%3Ajwt-bearer&assertion={encoded_jwt}'

    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Access-Control-Allow-Origin': '*',
    }

    response = requests.request('POST', url, headers=headers, data=payload)

    return json.loads(response.text)


def converter_sexo_unico(sexo: str) -> str:
    if sexo in {'1', 'F', 'Feminino'}:
        return 'F'
    elif sexo in {'2', 'M', 'Masculino'}:
        return 'M'
    else:
        return ''


def criar_biometria_unico(user: dict, imagebase64: str, access_token: str):
    payload = json.dumps({
        'subject': {
            'Code': user['nu_cpf'],
            'Name': user['nome_cliente'],
            'Gender': converter_sexo_unico(user['sexo']) if 'sexo' in user else None,
            'BirthDate': user.get('dt_nascimento'),
            'Email': user.get('email'),
            'Phone': user.get('telefone_celular'),
        },
        'onlySelfie': True,
        'imagebase64': imagebase64,
    })

    url = f'{settings.URL_UNICO_SERVICES}/processes'
    headers = {
        'Content-Type': 'application/json',
        'APIKEY': settings.UNICO_API_KEY,
        'Authorization': access_token,
    }

    return requests.request('POST', url, headers=headers, data=payload)
