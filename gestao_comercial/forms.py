from django import forms
from django.core.exceptions import ValidationError

from gestao_comercial.models.representante_comercial import (
    Agente,
    Gerente,
    Superintendente,
)


class AgenteInlineForm(forms.ModelForm):
    class Meta:
        model = Agente
        fields = ['supervisor_direto', 'representante_comercial']

    def clean(self):
        cleaned_data = super().clean()
        supervisor_direto = cleaned_data.get('supervisor_direto')
        representante_comercial = cleaned_data.get('representante_comercial')

        if supervisor_direto:
            if (
                supervisor_direto.representante_comercial.nu_cpf_cnpj
                == representante_comercial.nu_cpf_cnpj
            ):
                raise ValidationError(
                    'O número de CPF do representante comercial não pode ser igual ao número de CPF do supervisor direto.'
                )

        if not supervisor_direto:
            raise ValidationError('O campo supervisor direto deve ser preenchido.')

        return cleaned_data


class GerenteInlineForm(forms.ModelForm):
    class Meta:
        model = Gerente
        fields = ['supervisor_direto', 'representante_comercial']

    def clean(self):
        cleaned_data = super().clean()
        supervisor_direto = cleaned_data.get('supervisor_direto')
        representante_comercial = cleaned_data.get('representante_comercial')

        if supervisor_direto:
            if (
                supervisor_direto.representante_comercial.nu_cpf_cnpj
                == representante_comercial.nu_cpf_cnpj
            ):
                raise ValidationError(
                    'O número de CPF do representante comercial não pode ser igual ao número de CPF do supervisor direto.'
                )

        if not supervisor_direto:
            raise ValidationError('O campo supervisor direto deve ser preenchido.')

        return cleaned_data


class SuperintendenteInlineForm(forms.ModelForm):
    class Meta:
        model = Superintendente
        fields = ['supervisor_direto', 'representante_comercial']

    def clean(self):
        cleaned_data = super().clean()
        supervisor_direto = cleaned_data.get('supervisor_direto')

        if not supervisor_direto:
            self.supervisor_direto = 'Não Possui'
            raise ValidationError(
                'O campo supervisor direto deve ser preenchido. No caso de não possuir Responsável Direto, apenas escreva "Não Possui"'
            )

        return cleaned_data
