import io
import os

import boto3
import newrelic
import pandas as pd
import tablib
from axes.decorators import axes_dispatch
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.views import PasswordResetView
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.generics import GenericAPIView, get_object_or_404
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from contract.constants import EnumTipoAnexo
from core.constants import EnumNivelHierarquia
from custom_auth.anexo_usuario import AnexoUsuario

from .admin import UserResource
from .forms import CSVUploadForm, CustomPasswordResetForm, CustomPasswordResetFrontForm
from .models import Corban, FeatureToggle, UserAddress, UserProfile
from .serializers import (
    DocumentosUsuarioSerializer,
    RegistrationSerializer,
    UserAddressSerializer,
    UserProfileSerializer,
)
from .services import handle_new_access_token, handle_new_refresh_token


class UserAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, _):
        user = self.request.user
        serializer = UserProfileSerializer(user)

        data = dict(serializer.data)
        environment = settings.URL_FORMALIZACAO_CLIENTE
        data['check_url'] = f'{environment}/user/{user.unique_id}/'
        data['enable_face_match'] = FeatureToggle.is_feature_active(
            FeatureToggle.FACE_MATCHING
        )

        return Response(data)


@api_view(['POST'])
@permission_classes((AllowAny,))
def registration_view(request):
    data = {}
    if request.method == 'POST':
        print(request.POST)
        print(request.data)
        serializer = RegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            data['message'] = 'Cadastro realizado com sucesso! '
            data['identifier'] = user.identifier
            token_obj, _ = Token.objects.get_or_create(user=user)

            postal_code = request.data.get('postal_code')
            address = request.data.get('address')
            address_number = request.data.get('address_number')
            address_complement = request.data.get('address_complement')
            address_neighborhood = request.data.get('address_neighborhood')
            city = request.data.get('city')
            state = request.data.get('state')
            UserAddress.objects.create(
                user=user,
                postal_code=postal_code,
                address=address,
                is_principal=True,
                address_number=address_number,
                address_complement=address_complement,
                address_neighborhood=address_neighborhood,
                city=city,
                state=state,
            )

            token = token_obj.key
            data['token'] = token
        else:
            data = serializer.errors

    print(data)
    return Response(data)


@csrf_exempt
@api_view(['POST'])
@axes_dispatch
@permission_classes((AllowAny,))
def login_view(request):
    username = request.data.get('identifier')
    password = request.data.get('password')
    device_id = request.data.get('device_id')
    print(device_id)

    if username is None or password is None:
        return Response(
            {'error': 'Todos os campos são obrigatórios'}, status=HTTP_400_BAD_REQUEST
        )

    user = authenticate(request, username=username, password=password)

    if not user:
        return Response(
            {'error': 'E-mail ou senha não conferem. Tente novamente.'},
            status=HTTP_404_NOT_FOUND,
        )

    # environment = settings.URL_FORMALIZACAO_CLIENTE

    token, _ = Token.objects.get_or_create(user=user)
    current_user = token.user
    if user and device_id:
        user.device_id = device_id
        user.save()

    return Response(
        {'token': token.key, 'identifier': current_user.identifier}, status=HTTP_200_OK
    )


@api_view(['GET'])
@permission_classes((AllowAny,))
def check_user_view(request):
    if request.user.is_authenticated:
        user = request.user
        return Response({'is_checked': user.is_checked, 'unique_id': user.unique_id})
    return Response(status=status.HTTP_401_UNAUTHORIZED)


@api_view(['POST'])
@permission_classes((AllowAny,))
def change_user_password(request):
    old_password = request.data.get('old_password')
    new_password = request.data.get('new_password')
    confirm_new_password = request.data.get('confirm_new_password')
    user_token = request.data.get('token')

    if (
        not old_password
        or not new_password
        or not user_token
        or not confirm_new_password
    ):
        return Response(
            {'error': 'Todos os campos são obrigatórios'}, status=HTTP_400_BAD_REQUEST
        )

    if new_password != confirm_new_password:
        return Response(
            {'error': 'Confirmação de senha não confere'}, status=HTTP_400_BAD_REQUEST
        )

    token_obj = get_object_or_404(Token, key=user_token)
    current_user = token_obj.user

    if authenticate(request, username=current_user.identifier, password=old_password):
        current_user.set_password(new_password)
        current_user.save()
        return Response({}, status=HTTP_200_OK)
    else:
        return Response(
            {'error': 'Informações incorretas, confira os dados e tente novamente.'},
            status=HTTP_400_BAD_REQUEST,
        )


@api_view(['POST'])
@permission_classes((AllowAny,))
def save_address(request):
    user_token = request.data.get('token')

    token_obj = get_object_or_404(Token, key=user_token)
    user = token_obj.user

    name = request.data.get('name', '')
    postal_code = request.data.get('postal_code', '').replace('-', '').replace('.', '')
    address = request.data.get('address', '')
    address_neighborhood = request.data.get('address_neighborhood', '')
    address_number = request.data.get('address_number', '')
    address_complement = request.data.get('address_complement', '')
    city = request.data.get('city', '')
    state = request.data.get('state', '')

    _, created = UserAddress.objects.get_or_create(
        user=user,
        name=name,
        postal_code=postal_code,
        address=address,
        is_principal=True,
        address_neighborhood=address_neighborhood,
        address_number=address_number,
        address_complement=address_complement,
        city=city,
        state=state,
    )
    if created:
        return Response({}, status=HTTP_200_OK)
    else:
        return Response({'error': 'Registro duplicado.'}, status=HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def set_principal_address(request):
    user = request.user

    address_id = request.data.get('address_id', '')
    address = get_object_or_404(UserAddress, pk=address_id)

    if address.user == user:
        UserAddress.objects.filter(user=user).update(is_principal=False)

        address.is_principal = True
        address.save()

        return Response({}, status=HTTP_200_OK)

    else:
        return Response({'error': 'Operação inválida.'}, status=HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def get_principal_address(request):
    user = request.user

    address = UserAddress.objects.filter(is_principal=True, user=user).first()
    address_serializer = UserAddressSerializer(address)

    return Response(address_serializer.data, status=HTTP_200_OK)


class EnvioDocumentosUsuario(GenericAPIView):
    """
    Método utilizado para inserção de anexos (documentos) dos usuários.
    """

    permission_classes = [AllowAny]
    serializer_class = DocumentosUsuarioSerializer

    def post(self, request):
        try:
            print('1. Iniciando processamento do POST...')

            arquivo = request.data.get('arquivo')
            tipo_anexo = request.data.get('tipo_anexo')
            unique_id = request.data.get('unique_id')

            print(f"Nome do arquivo: {arquivo.name if arquivo else 'N/A'}")
            print(f'Tipo de anexo: {tipo_anexo}')
            print(f'ID único: {unique_id}')
            print(f"Tipo do objeto 'arquivo': {type(arquivo)}")

            usuario = UserProfile.objects.get(unique_id=unique_id)
            print(f'Usuário encontrado: {usuario}')

            if arquivo:
                extensao = os.path.splitext(arquivo.name)[1].lstrip('.').lower()
                object_key, tipo_anexo = self.gerar_nome_arquivo(
                    usuario, tipo_anexo, extensao
                )
                url = self.upload_arquivo_s3(
                    arquivo, object_key, settings.AWS_USER_DOCS_BUCKET_NAME
                )
                print(f'URL gerada: {url}')
                if data := self.gerar_data(url, tipo_anexo, usuario):
                    anexo_usuario, created = AnexoUsuario.objects.update_or_create(
                        usuario=usuario, defaults=data
                    )
                    print(f"Anexo de usuário criado: {'Sim' if created else 'Não'}")
                    if not anexo_usuario:
                        raise Exception('Erro ao salvar o documento no banco de dados.')

            return Response(
                {'message': 'Documentos Inseridos com sucesso'},
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            print(f'ERRO AO ENVIAR DOCUMENTOS: {str(e)}')
            return Response(
                {'message': f'Ocorreu um erro: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

    def upload_arquivo_s3(self, arquivo, object_key, bucket_name_s3):
        try:
            _, extensao = os.path.splitext(arquivo.name)
            extensao = extensao.lstrip('.').lower()
            file_stream = io.BytesIO(arquivo.read())

            s3_cliente = boto3.client(
                's3',
                region_name='us-east-1',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            )

            content_type = self.determinar_content_type(extensao)

            s3_cliente.upload_fileobj(
                file_stream,
                bucket_name_s3,
                object_key,
                ExtraArgs={'ContentType': content_type},
            )

            return s3_cliente.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket_name_s3, 'Key': object_key},
                ExpiresIn=31536000,
            )
        except Exception as e:
            print(f'Erro ao fazer upload no S3: {e}')
            return None

    """
        Migrar pra uma classe que gerencia o s3 no futuro
    """

    def gerar_nome_arquivo(self, usuario, tipo_anexo, extensao):
        nome_pasta = str(usuario.unique_id)
        tipo_anexo = int(tipo_anexo)

        if tipo_anexo == EnumTipoAnexo.DOCUMENTO_FRENTE:
            nome_final = f'{nome_pasta}_documento_frente.{extensao}'
        elif tipo_anexo == EnumTipoAnexo.DOCUMENTO_VERSO:
            nome_final = f'{nome_pasta}_documento_verso.{extensao}'
        elif tipo_anexo == EnumTipoAnexo.CNH:
            nome_final = f'{nome_pasta}_cnh.{extensao}'
        elif tipo_anexo == EnumTipoAnexo.SELFIE:
            nome_final = f'{nome_pasta}_selfie.{extensao}'
        else:
            raise ValueError(f'Tipo de anexo não suportado: {tipo_anexo}')

        return f'{nome_pasta}/{nome_final}', tipo_anexo

    def determinar_content_type(self, extensao):
        if extensao in ['jpg', 'jpeg']:
            return 'image/jpeg'
        elif extensao == 'png':
            return 'image/png'
        else:
            raise ValueError(f'Extensão de arquivo não suportada: {extensao}')

    def gerar_data(self, url, tipo_anexo, usuario):
        """Retorna o conjunto de dados correto baseado no tipo_anexo."""
        data = {'tipo_anexo': tipo_anexo, 'usuario': usuario}

        if tipo_anexo == EnumTipoAnexo.SELFIE:
            data['selfie_url'] = url
        elif tipo_anexo in [EnumTipoAnexo.DOCUMENTO_FRENTE, EnumTipoAnexo.CNH]:
            data['anexo_url'] = url
        elif tipo_anexo == EnumTipoAnexo.DOCUMENTO_VERSO:
            data['verso_url'] = None

        return data


class AtualizarSenhaAPIView(APIView):
    """
    API para alterar a senha de um usuário
    """

    def post(self, request):
        """
        Endpoint para alterar a senha de um usuário.

        Recebe a senha atual e a nova senha como dados da requisição POST.

        Args:
            request: Objeto da requisição HTTP.

        Returns:
            Response: Resposta da API indicando o sucesso ou falha da operação.
        """
        try:
            senha_atual = request.data.get('senhaAtual')
            senha_nova = request.data.get('senhaNova')

            if not (senha_atual and senha_nova):
                return Response(
                    {'error': 'Todos os campos são obrigatórios'},
                    status=HTTP_400_BAD_REQUEST,
                )

            user = get_object_or_404(UserProfile, identifier=request.user.identifier)
            self.atualizar_senha(user, senha_atual, senha_nova)

            return Response({}, status=HTTP_200_OK)
        except Exception as e:
            print(e)
            newrelic.agent.notice_error()
            return Response(
                {
                    'error': 'Houve um erro ao tentar alterar a senha do usuário. '
                    'Verifique os dados e tente novamente'
                },
                status=HTTP_400_BAD_REQUEST,
            )

    def atualizar_senha(self, user, senha_atual, senha_nova):
        """
        Atualiza a senha do usuário se a autenticação for bem-sucedida.

        Args:
            user (UserProfile): Instância do usuário cuja senha será alterada.
            senha_atual (str): Senha atual do usuário.
            senha_nova (str): Nova senha desejada para o usuário.

        Raises:
            ValueError: Se as informações fornecidas estiverem incorretas.
        """
        if authenticate(
            request=self.request, username=user.identifier, password=senha_atual
        ):
            user.set_password(senha_nova)
            user.save()
        else:
            raise ValueError(
                'Informações incorretas, confira os dados e tente novamente.'
            )


def get_corban(request, corban_id):
    corban = Corban.objects.get(id=corban_id)
    produtos = corban.produtos.all().values('id', 'nome')

    nivel_selecionado_str = request.GET.get('nivel')
    if nivel_selecionado_str and nivel_selecionado_str.isdigit():
        nivel_selecionado = int(nivel_selecionado_str)
    else:
        nivel_selecionado = EnumNivelHierarquia.DIGITADOR

    nivel_acima = nivel_selecionado + 1  # Nível imediatamente superior

    supervisores = list(
        UserProfile.objects.filter(
            corban_id=corban_id, nivel_hierarquia=nivel_acima
        ).values('id', 'name')
    )
    supervisores.insert(0, {'id': '', 'name': '---------'})  # Adiciona a opção padrão

    return JsonResponse({'produtos': list(produtos), 'supervisores': supervisores})


def upload_csv(request):
    if request.method == 'POST':
        form = CSVUploadForm(request.POST, request.FILES)
        if form.is_valid():
            excel_file = request.FILES['csv_file']
            df = pd.read_excel(excel_file)
            csv_data = df.to_csv(index=False)

            # Convertendo a string CSV para um Dataset
            dataset = tablib.Dataset()
            dataset.csv = csv_data

            user_resource = UserResource()
            # Agora você pode passar o Dataset corretamente
            user_resource.import_supervisors(dataset)
            # Redirecione ou mostre uma mensagem de sucesso
            messages.success(
                request,
                'Supervisores importados com sucesso. Acompanhe o resultado nos usuários desejados',
            )
            return redirect('/admin/custom_auth/userprofile/')
    else:
        form = CSVUploadForm()

    return render(
        request, 'admin/custom_auth/userprofile/csv_upload.html', {'form': form}
    )


class CustomTokenObtainPairView(TokenObtainPairView):
    def finalize_response(self, request, response, *args, **kwargs):
        if response.status_code == HTTP_200_OK:
            return handle_new_refresh_token(
                identifier=request.data.get('identifier'), request=request
            )

        return super(TokenObtainPairView, self).finalize_response(
            request, response, *args, **kwargs
        )


class CustomTokenRefreshView(TokenRefreshView):
    def finalize_response(self, request, response, *args, **kwargs):
        if response.status_code == HTTP_200_OK:
            return JsonResponse(
                handle_new_access_token(
                    refresh=request.data.get('refresh'),
                    access=response.data.get('access'),
                )
            )

        return super(TokenRefreshView, self).finalize_response(
            request, response, *args, **kwargs
        )


class CustomPasswordResetView(PasswordResetView):
    template_name = 'registration/password_reset_form.html'
    form_class = CustomPasswordResetForm
    success_url = reverse_lazy('password_reset_done')

    # Override the form_valid method if needed
    def form_valid(self, form):
        # You can add any custom logic here if needed
        # Call the parent form_valid method to handle form submission
        return super().form_valid(form)


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        form = CustomPasswordResetFrontForm(data=request.data)
        if form.is_valid():
            form.save()
            return JsonResponse({'status': 'success'})
        else:
            errors = {field: error_list[0] for field, error_list in form.errors.items()}
            return JsonResponse(
                {'status': 'error', 'errors': errors}, status=HTTP_400_BAD_REQUEST
            )


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, uidb64, token, *args, **kwargs):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = UserProfile.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, UserProfile.DoesNotExist):
            return Response({'status': 'invalid link'}, status=400)

        if user is not None and default_token_generator.check_token(user, token):
            new_password = request.data.get('password')
            try:
                # Validate the password using Django's validators and custom validator
                validate_password(new_password, user)

                # Set the new password
                user.set_password(new_password)
                user.is_initial_password = False
                user.save()

                return Response({'status': 'Senha alterada com sucesso!'}, status=200)
            except ValidationError as e:
                # Return the error messages if the password is invalid
                return Response({'status': 'error', 'errors': e.messages}, status=400)
        else:
            return Response({'status': 'Link inválido'}, status=400)
