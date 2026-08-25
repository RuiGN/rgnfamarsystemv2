from datetime import date

from django import forms
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase

from base.ui.actions.forms import build_action_form
from base.ui.actions.modules.production import PRODUCTION_ACTIONS
from base.ui.actions.types import (
    ActionConfig,
    ActionConfirmation,
    ActionField,
    FieldKind,
    SubmissionFormat,
)
from production.models import ProductionOrder


User = get_user_model()


def action_with_fields(*fields, confirmation=None, submission_format=SubmissionFormat.JSON):
    return ActionConfig(
        module_slug='production',
        resource_slug='orders',
        app_label='production',
        model=ProductionOrder,
        action_name='complete',
        route_name='v1_production:order-complete',
        detail=True,
        label='Concluir',
        description='Concluir a ordem de produção.',
        success_message='Ordem concluída.',
        permissions=('production.change_productionorder',),
        fields=fields,
        confirmation=confirmation,
        submission_format=submission_format,
    )


class ActionFormTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('relation-user', 'relation@example.com')

    def setUp(self):
        self.request = RequestFactory().get('/')

    def test_form_builds_decimal_confirmation_and_ignores_extra_fields(self):
        config = PRODUCTION_ACTIONS[5]
        form_class = build_action_form(config, self.request)
        form = form_class(
            {
                'actual_yield_quantity': '98.750',
                'confirmation_phrase': 'CONFIRMAR',
                'unexpected': 'ignored',
            }
        )

        assert form.is_valid(), form.errors
        assert form.cleaned_payload() == {'actual_yield_quantity': '98.750'}

    def test_form_maps_all_field_kinds_and_serializes_python_values(self):
        fields = (
            ActionField('text', 'Texto', max_length=20, placeholder='Informe'),
            ActionField('textarea', 'Descrição', FieldKind.TEXTAREA),
            ActionField('integer', 'Inteiro', FieldKind.INTEGER, min_value=1, max_value=9),
            ActionField('decimal', 'Decimal', FieldKind.DECIMAL),
            ActionField('boolean', 'Ativo', FieldKind.BOOLEAN),
            ActionField('date', 'Data', FieldKind.DATE),
            ActionField('datetime', 'Data e hora', FieldKind.DATETIME),
            ActionField(
                'choice',
                'Escolha',
                FieldKind.CHOICE,
                choices=(('one', 'Um'), ('two', 'Dois')),
            ),
            ActionField(
                'relation',
                'Usuário',
                FieldKind.RELATION,
                queryset_factory=lambda request: User.objects.filter(pk=self.user.pk),
            ),
            ActionField('hidden', 'Oculto', FieldKind.HIDDEN, initial_factory=lambda r, o: 'ctx'),
            ActionField('json', 'Parâmetros', FieldKind.JSON),
        )
        form_class = build_action_form(action_with_fields(*fields), self.request)

        assert isinstance(form_class.base_fields['text'], forms.CharField)
        assert isinstance(form_class.base_fields['textarea'].widget, forms.Textarea)
        assert isinstance(form_class.base_fields['integer'], forms.IntegerField)
        assert isinstance(form_class.base_fields['decimal'], forms.DecimalField)
        assert isinstance(form_class.base_fields['boolean'], forms.BooleanField)
        assert isinstance(form_class.base_fields['date'], forms.DateField)
        assert isinstance(form_class.base_fields['datetime'], forms.DateTimeField)
        assert isinstance(form_class.base_fields['choice'], forms.ChoiceField)
        assert isinstance(form_class.base_fields['relation'], forms.ModelChoiceField)
        assert isinstance(form_class.base_fields['hidden'].widget, forms.HiddenInput)
        assert isinstance(form_class.base_fields['json'], forms.JSONField)

        form = form_class(
            {
                'text': 'valor',
                'textarea': 'detalhes',
                'integer': '3',
                'decimal': '10.25',
                'boolean': 'on',
                'date': '2026-07-20',
                'datetime': '2026-07-20 12:30:00',
                'choice': 'one',
                'relation': str(self.user.pk),
                'hidden': 'ctx',
                'json': '{"valid": true}',
            }
        )

        assert form.is_valid(), form.errors
        payload = form.cleaned_payload()
        assert payload['integer'] == 3
        assert payload['decimal'] == '10.25'
        assert payload['boolean'] is True
        assert payload['date'] == date(2026, 7, 20).isoformat()
        assert payload['datetime'] == form.cleaned_data['datetime'].isoformat()
        assert payload['relation'] == self.user.pk
        assert payload['json'] == {'valid': True}

    def test_action_fields_receive_project_widget_metadata(self):
        fields = (
            ActionField('document', 'CPF/CNPJ'),
            ActionField('email', 'Email'),
            ActionField('phone', 'Telefone'),
            ActionField('zipcode', 'CEP'),
            ActionField('total_amount', 'Valor total', FieldKind.DECIMAL),
            ActionField('evidence_file', 'Evidência', FieldKind.FILE),
        )
        form_class = build_action_form(action_with_fields(*fields), self.request)

        assert form_class.base_fields['document'].widget.attrs['data-mask'] == 'cpf-cnpj'
        assert form_class.base_fields['document'].widget.attrs['data-icon'] == 'feather-file-text'
        assert form_class.base_fields['email'].widget.attrs['placeholder'] == 'nome@empresa.com'
        assert form_class.base_fields['email'].widget.attrs['data-icon'] == 'feather-mail'
        assert form_class.base_fields['phone'].widget.attrs['type'] == 'tel'
        assert form_class.base_fields['phone'].widget.attrs['placeholder'] == '(00) 00000-0000'
        assert form_class.base_fields['phone'].widget.attrs['data-icon'] == 'feather-phone'
        assert form_class.base_fields['zipcode'].widget.attrs['data-mask'] == 'cep'
        assert form_class.base_fields['zipcode'].widget.attrs['placeholder'] == '00000-000'
        assert form_class.base_fields['zipcode'].widget.attrs['data-icon'] == 'feather-map-pin'
        assert form_class.base_fields['total_amount'].widget.attrs['placeholder'] == '0,00'
        assert (
            form_class.base_fields['total_amount'].widget.attrs['data-icon']
            == 'feather-dollar-sign'
        )
        assert form_class.base_fields['evidence_file'].widget.attrs['data-icon'] == 'feather-upload'

    def test_form_validates_json_confirmation_limits_and_custom_widget(self):
        config = action_with_fields(
            ActionField(
                'payload',
                'Parâmetros',
                FieldKind.JSON,
                required=True,
                widget_factory=lambda: forms.PasswordInput(),
            ),
            confirmation=ActionConfirmation(
                'Confirmar execução',
                'Revise os parâmetros.',
                typed_phrase='EXECUTAR',
            ),
        )
        form_class = build_action_form(config, self.request)

        assert isinstance(form_class.base_fields['payload'].widget, forms.PasswordInput)
        invalid = form_class({'payload': '{invalid', 'confirmation_phrase': 'errado'})
        assert not invalid.is_valid()
        assert 'payload' in invalid.errors
        assert 'confirmation_phrase' in invalid.errors

    def test_multipart_form_preserves_declared_upload(self):
        config = action_with_fields(
            ActionField('evidence', 'Evidência', FieldKind.FILE, required=True),
            submission_format=SubmissionFormat.MULTIPART,
        )
        form_class = build_action_form(config, self.request)
        upload = SimpleUploadedFile('evidence.txt', b'evidence')
        form = form_class({}, {'evidence': upload})

        assert form.is_valid(), form.errors
        assert form.cleaned_payload() == {'evidence': upload}
