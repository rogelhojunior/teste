from django import forms
from django.contrib import admin
from contract.products.cartao_beneficio.models.convenio import Convenios

from custom_auth.models import Corban
from documentscopy.services import get_entities_by_products, get_stores_by_corbans
from .models import BPOConfig, BPORow, UnicoParameter, UnicoParameterFaceMatch
from django.core.exceptions import NON_FIELD_ERRORS
from itertools import combinations


class BPOConfigForm(forms.ModelForm):
    class Meta:
        model = BPOConfig
        fields = '__all__'

    def clean(self):
        if self.cleaned_data.get('products'):
            if not self.cleaned_data.get('stores') and not self.cleaned_data.get(
                'corbans'
            ):
                for product in self.cleaned_data.get('products'):
                    qs = BPOConfig.objects.filter(
                        products__id=product.id,
                        corbans=None,
                        stores=None,
                    )

                    if self.instance.id:
                        qs = qs.exclude(id=self.instance.id)

                    if qs.exists():
                        raise forms.ValidationError({
                            NON_FIELD_ERRORS: [
                                f'Essa configuração conflita com a configuração {qs.first().id} para o produto {product}',
                            ],
                        })

            if not self.cleaned_data.get('stores') and self.cleaned_data.get('corbans'):
                for product in self.cleaned_data.get('products'):
                    for corban in self.cleaned_data.get('corbans'):
                        qs = BPOConfig.objects.filter(
                            products__id=product.id,
                            corbans__id=corban.id,
                            stores=None,
                        )

                        if self.instance.id:
                            qs = qs.exclude(id=self.instance.id)

                        if qs.exists():
                            raise forms.ValidationError({
                                NON_FIELD_ERRORS: [
                                    f'Essa configuração conflita com a configuração {qs.first().id} para o produto {product} e corban {corban}',
                                ],
                            })

            if self.cleaned_data.get('stores'):
                for product in self.cleaned_data.get('products'):
                    for store in self.cleaned_data.get('stores'):
                        qs = BPOConfig.objects.filter(
                            products__id=product.id,
                            stores__id=store.id,
                        )

                        if self.instance.id:
                            qs = qs.exclude(id=self.instance.id)

                        if qs.exists():
                            raise forms.ValidationError({
                                NON_FIELD_ERRORS: [
                                    f'Essa configuração conflita com a configuração {qs.first().id} para o produto {product} e loja {store}',
                                ],
                            })
        return self.cleaned_data


class UnicoParameterForm(forms.ModelForm):
    class Meta:
        model = UnicoParameter
        fields = '__all__'

    def clean(self):
        if self.cleaned_data.get('products'):
            if not self.cleaned_data.get('stores') and not self.cleaned_data.get(
                'corbans'
            ):
                for product in self.cleaned_data.get('products'):
                    qs = UnicoParameter.objects.filter(
                        products__id=product.id,
                        corbans=None,
                        stores=None,
                    )

                    if self.instance.id:
                        qs = qs.exclude(id=self.instance.id)

                    if qs.exists():
                        raise forms.ValidationError({
                            NON_FIELD_ERRORS: [
                                f'Essa configuração conflita com a configuração {qs.first().id} para o produto {product}',
                            ],
                        })

            if not self.cleaned_data.get('stores') and self.cleaned_data.get('corbans'):
                for product in self.cleaned_data.get('products'):
                    for corban in self.cleaned_data.get('corbans'):
                        qs = UnicoParameter.objects.filter(
                            products__id=product.id,
                            corbans__id=corban.id,
                            stores=None,
                        )

                        if self.instance.id:
                            qs = qs.exclude(id=self.instance.id)

                        if qs.exists():
                            raise forms.ValidationError({
                                NON_FIELD_ERRORS: [
                                    f'Essa configuração conflita com a configuração {qs.first().id} para o produto {product} e corban {corban}',
                                ],
                            })

            if self.cleaned_data.get('stores'):
                for product in self.cleaned_data.get('products'):
                    for store in self.cleaned_data.get('stores'):
                        qs = UnicoParameter.objects.filter(
                            products__id=product.id,
                            stores__id=store.id,
                        )

                        if self.instance.id:
                            qs = qs.exclude(id=self.instance.id)

                        if qs.exists():
                            raise forms.ValidationError({
                                NON_FIELD_ERRORS: [
                                    f'Essa configuração conflita com a configuração {qs.first().id} para o produto {product} e loja {store}',
                                ],
                            })
        return self.cleaned_data


class UnicoParameterFaceMatchFormset(forms.models.BaseInlineFormSet):
    def clean(self):
        if not self.forms:
            raise forms.ValidationError('É obrigatório cadastrar ao menos um parametro')

        for form in self.forms:
            if not form.is_valid():
                return
        forms_range = range(len(self.forms))
        forms_iter = combinations(forms_range, 2)
        for form_a, form_b in forms_iter:
            facematch_a = self.forms[form_a]
            facematch_b = self.forms[form_b]
            from_a = float(facematch_a.cleaned_data.get('score_from'))
            from_b = float(facematch_b.cleaned_data.get('score_from'))
            to_a = float(facematch_a.cleaned_data.get('score_to'))
            to_b = float(facematch_b.cleaned_data.get('score_to'))

            if (
                (from_a <= from_b <= to_a)
                or (from_a <= to_b <= to_a)
                or (from_b <= from_a <= to_b)
                or (from_b <= to_a <= to_b)
            ):
                raise forms.ValidationError(
                    'Seus parametros de biometria facial são conflitantes'
                )


class UnicoParameterFaceMatchForm(forms.ModelForm):
    class Meta:
        model = UnicoParameterFaceMatch
        fields = '__all__'

    def clean(self):
        if self.cleaned_data.get('score_from') >= self.cleaned_data.get('score_to'):
            raise forms.ValidationError(
                'O valor final deve ser maior que o valor inicial'
            )

        return self.cleaned_data


class ParameterAdmin(admin.ModelAdmin):
    filter_horizontal = ('products', 'entities', 'corbans', 'stores')

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        instance_id = None
        instance = None

        if not request.POST:
            if 'change' in request.path:
                instance_id = int(request.path.split('/')[-3])

            if instance_id:
                instance = self.model.objects.filter(id=instance_id)

            if db_field.name == 'stores':
                if instance and instance[0].corbans.exists():
                    corbans = list(instance.values_list('corbans__id', flat=True))

                    kwargs['queryset'] = get_stores_by_corbans(corbans)
                else:
                    kwargs['queryset'] = Corban.objects.none()

            if db_field.name == 'entities':
                if instance:
                    products = list(instance.values_list('products__id', flat=True))

                    kwargs['queryset'] = get_entities_by_products(products)
                else:
                    kwargs['queryset'] = Convenios.objects.none()

        return super().formfield_for_manytomany(db_field, request, **kwargs)


class UnicoParameterFaceMatchInline(admin.TabularInline):
    formset = UnicoParameterFaceMatchFormset
    form = UnicoParameterFaceMatchForm
    model = UnicoParameterFaceMatch
    extra = 0
    list_display = (
        'score_from',
        'score_to',
        'corban_action',
    )


class BPORowFormset(forms.models.BaseInlineFormSet):
    def clean(self):
        if not self.forms:
            raise forms.ValidationError('É obrigatório cadastrar ao menos um parametro')

        for form in self.forms:
            if not form.is_valid():
                return
        forms_range = range(len(self.forms))
        forms_iter = combinations(forms_range, 2)
        for form_a, form_b in forms_iter:
            facematch_a = self.forms[form_a]
            facematch_b = self.forms[form_b]
            from_a = float(facematch_a.cleaned_data.get('amount_from'))
            from_b = float(facematch_b.cleaned_data.get('amount_from'))
            to_a = float(facematch_a.cleaned_data.get('amount_to'))
            to_b = float(facematch_b.cleaned_data.get('amount_to'))

            if (
                (from_a <= from_b <= to_a)
                or (from_a <= to_b <= to_a)
                or (from_b <= from_a <= to_b)
                or (from_b <= to_a <= to_b)
            ):
                raise forms.ValidationError('Seus parametros são conflitantes')


class BPORowForm(forms.ModelForm):
    class Meta:
        model = UnicoParameterFaceMatch
        fields = '__all__'

    def clean(self):
        if self.cleaned_data.get('amount_from') >= self.cleaned_data.get('amount_to'):
            raise forms.ValidationError(
                'O valor final deve ser maior que o valor inicial'
            )

        return self.cleaned_data


class BPORowInline(admin.TabularInline):
    formset = BPORowFormset
    form = BPORowForm
    model = BPORow
    extra = 0
    list_display = (
        'bpo',
        'amount_from',
        'amount_to',
    )


class UnicoParameterAdmin(ParameterAdmin):
    form = UnicoParameterForm
    list_display = ('id',)
    inlines = [UnicoParameterFaceMatchInline]


class BPOConfigAdmin(ParameterAdmin):
    form = BPOConfigForm
    list_display = ('id',)
    filter_horizontal = ('products', 'entities', 'corbans', 'stores', 'ufs')
    inlines = [BPORowInline]


admin.site.register(BPOConfig, BPOConfigAdmin)
admin.site.register(UnicoParameter, UnicoParameterAdmin)
