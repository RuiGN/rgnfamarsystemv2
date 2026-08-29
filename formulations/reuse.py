from django import forms
from django.db import IntegrityError
from django.db.models import Max

from base.ui.forms import build_resource_form
from formulations.models import MasterFormula


VERSION_CONFLICT_MESSAGE = (
    'Esta versão já foi utilizada para o produto selecionado. '
    'Atualize a versão e tente novamente.'
)

COMPONENT_REUSE_FIELDS = (
    'line_number',
    'role',
    'quantity',
    'expected_loss_percent',
    'conversion_factor',
    'is_active',
)


def next_formula_version(product_id: int) -> int:
    maximum = MasterFormula.objects.filter(product_id=product_id).aggregate(
        maximum=Max('version')
    )['maximum']
    return (maximum or 0) + 1


def master_formula_reuse_initial(source: MasterFormula) -> dict[str, object]:
    return {
        'product': source.product_id,
        'version': next_formula_version(source.product_id),
        'status': MasterFormula.Status.DRAFT,
        'batch_size': source.batch_size,
        'batch_unit': source.batch_unit_id,
        'expected_yield_percent': source.expected_yield_percent,
        'effective_from': source.effective_from,
        'effective_to': source.effective_to,
        'notes': source.notes,
    }


def component_reuse_initial(source: MasterFormula) -> list[dict[str, object]]:
    initial = []
    for component in source.components.order_by('line_number', 'pk'):
        row = {field: getattr(component, field) for field in COMPONENT_REUSE_FIELDS}
        row['material'] = component.material_id
        row['unit'] = component.unit_id
        initial.append(row)
    return initial


def build_master_formula_reuse_form(resource) -> type[forms.ModelForm]:
    parent_form = build_resource_form(resource)

    class MasterFormulaReuseForm(parent_form):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.fields.pop('copied_from', None)
            self.fields['status'].disabled = True
            self.fields['status'].initial = MasterFormula.Status.DRAFT

    return MasterFormulaReuseForm


def is_formula_version_conflict(error: IntegrityError) -> bool:
    cause = error.__cause__
    constraint_name = getattr(getattr(cause, 'diag', None), 'constraint_name', '')
    if constraint_name == 'unique_formula_product_version':
        return True
    message = str(error)
    return (
        'formulations_masterformula.product_id' in message
        and 'formulations_masterformula.version' in message
    )
