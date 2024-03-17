"""This file implements forms to custom_auth app."""

from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm
from django.contrib.auth.forms import UserCreationForm as DefaultCreationForm
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils.translation import gettext_lazy as _
from django_recaptcha.fields import ReCaptchaField

from core import settings
from custom_auth.custom_token_generator import custom_token_generator
from custom_auth.models import Corban, Produtos, UserProfile
from gestao_comercial.models.representante_comercial import RepresentanteComercial
from handlers.email import send_email


class UserForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        corban = cleaned_data.get('corban')
        produtos = cleaned_data.get('produtos')

        if corban and produtos:
            parent_produtos_ids = set(corban.produtos.values_list('id', flat=True))
            produtos_ids = {produto.id for produto in produtos}

            if invalid_produtos_ids := produtos_ids - parent_produtos_ids:
                invalid_produtos = Produtos.objects.filter(id__in=invalid_produtos_ids)
                invalid_produtos_names = [produto.nome for produto in invalid_produtos]
                invalid_produtos_str = ', '.join(invalid_produtos_names)

                raise ValidationError({
                    'produtos': f'Os seguintes produtos não estão presentes no Corban e não podem ser selecionados: {invalid_produtos_str}.'
                })

        return cleaned_data


class UserCreationForm(DefaultCreationForm):
    """
    A UserCreationForm with optional password inputs.
    """

    def __init__(self, *args, **kwargs):
        super(UserCreationForm, self).__init__(*args, **kwargs)
        self.fields['password1'].required = False
        self.fields['password2'].required = False
        # If one field gets autocompleted but not the other, our 'neither
        # password or both password' validation will be triggered.
        self.fields['password1'].widget.attrs['autocomplete'] = 'off'
        self.fields['password2'].widget.attrs['autocomplete'] = 'off'


class UserLoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super(UserLoginForm, self).__init__(*args, **kwargs)

    username = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': ''}),
        label='CPF do usuário',
    )

    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': ''}),
        label='Senha',
    )

    captcha = ReCaptchaField()


class CSVUploadForm(forms.Form):
    csv_file = forms.FileField()


class CorbanForm(forms.ModelForm):
    class Meta:
        model = Corban
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super(CorbanForm, self).__init__(*args, **kwargs)

        # Obter os identificadores dos usuários que são representantes comerciais e estão ativos
        user_ids = UserProfile.objects.filter(representante_comercial=True).values_list(
            'cpf', flat=True
        )

        # Obter os CPFs/CNPJs dos Representantes Comerciais que já estão associados a um Corban
        representantes_associados = Corban.objects.exclude(
            representante_comercial__isnull=True
        ).values_list('representante_comercial__nu_cpf_cnpj', flat=True)

        # Se estamos editando um Corban, inclua o representante comercial atual na lista
        if self.instance.pk and self.instance.representante_comercial:
            # Obter o CPF/CNPJ do representante comercial atual
            representante_atual_cpf_cnpj = (
                self.instance.representante_comercial.nu_cpf_cnpj
            )
            # Excluir o representante atual da lista de representantes já associados
            representantes_associados = [
                cpf_cnpj
                for cpf_cnpj in representantes_associados
                if cpf_cnpj != representante_atual_cpf_cnpj
            ]

        # Filtrar os RepresentanteComercial que são usuários ativos e não estão associados a um Corban
        self.fields[
            'representante_comercial'
        ].queryset = RepresentanteComercial.objects.filter(
            nu_cpf_cnpj__in=user_ids
        ).exclude(nu_cpf_cnpj__in=representantes_associados)

    def clean(self):
        cleaned_data = super().clean()
        parent_corban = cleaned_data.get('parent_corban')
        produtos = cleaned_data.get('produtos')

        if parent_corban and produtos:
            parent_produtos_ids = set(
                parent_corban.produtos.values_list('id', flat=True)
            )
            produtos_ids = {produto.id for produto in produtos}

            if invalid_produtos_ids := produtos_ids - parent_produtos_ids:
                invalid_produtos = Produtos.objects.filter(id__in=invalid_produtos_ids)
                invalid_produtos_names = [produto.nome for produto in invalid_produtos]
                invalid_produtos_str = ', '.join(invalid_produtos_names)

                raise ValidationError({
                    'produtos': f'Os seguintes produtos não estão presentes no Corban Superior e não podem ser adicionados: {invalid_produtos_str}.'
                })

        return cleaned_data


class CustomPasswordResetForm(PasswordResetForm):
    def clean_email(self):
        """
        Valida se o e-mail fornecido está associado a um usuário existente.
        """
        email = self.cleaned_data['email']
        if not UserProfile.objects.filter(email=email).exists():
            raise ValidationError(
                _('Não há usuário cadastrado com este endereço de e-mail.')
            )
        return email

    def save(self, request=None, *args, **kwargs):
        email = self.cleaned_data['email']
        user = UserProfile.objects.filter(email=email).first()

        if user and request:
            reset_link = self.get_reset_link(user, request)
            context = {
                'reset_link': reset_link,
                'user': user,
                'email_logo': f'{settings.EMAIL_LOGO}',
            }

            send_email(
                'registration/password_reset_email.html',
                'emails/account/password_reset_subject.txt',
                'Troca de Senha',
                email,
                context,
            )

    def get_reset_link(self, user, request):
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = custom_token_generator.make_token(user)
        reset_link = reverse(
            'password_reset_confirm', kwargs={'uidb64': uid, 'token': token}
        )
        return request.build_absolute_uri(reset_link)


class CustomPasswordResetFrontForm(PasswordResetForm):
    def clean_email(self):
        """
        Valida se o e-mail fornecido está associado a um usuário existente.
        """
        email = self.cleaned_data['email']
        if not UserProfile.objects.filter(email=email).exists():
            raise ValidationError(
                _('Não há usuário cadastrado com este endereço de e-mail.')
            )
        return email

    def save(self, request=None, *args, **kwargs):
        email = self.cleaned_data['email']
        if user := UserProfile.objects.filter(email=email).first():
            reset_link = self.get_reset_link(user)
            context = {
                'reset_link': reset_link,
                'user': user,
                'email_logo': f'{settings.EMAIL_LOGO}',
            }

            send_email(
                'registration/password_reset_email.html',
                'emails/account/password_reset_subject.txt',
                'Troca de Senha',
                email,
                context,
            )

    def get_reset_link(self, user):
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = custom_token_generator.make_token(user)
        # Remove '/login' from the URL if it exists
        base_url = settings.FRONT_LOGIN
        if base_url.endswith('/login'):
            base_url = base_url.rsplit('/login', 1)[0]

        return f'{base_url}/reset-password/{uid}/{token}/'
