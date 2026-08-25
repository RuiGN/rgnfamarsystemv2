from base.ui.actions.types import (
    ActionConfig,
    ActionConfirmation,
    ActionField,
    FieldKind,
)
from production.models import ProductionOrder


PERMISSIONS = ('production.change_productionorder',)
OPERATIONAL_PERMISSIONS = {
    'reserve_materials': (
        'production.change_productionorder',
        'production.change_materialconsumption',
        'inventory.add_stockmovement',
    ),
    'issue_materials': (
        'production.change_productionorder',
        'production.change_materialconsumption',
        'inventory.add_stockmovement',
    ),
    'receive_outputs': (
        'production.receive_productionoutput',
        'inventory.add_stockmovement',
    ),
    'calculate_cost': (
        'production.change_productionorder',
        'costing.add_productioncostcapture',
    ),
}


def _action(
    action_name,
    label,
    description,
    success_message,
    allowed_states,
    *,
    icon='feather-play',
    tone='primary',
    fields=(),
    confirmation=None,
    permissions=PERMISSIONS,
):
    return ActionConfig(
        module_slug='production',
        resource_slug='orders',
        app_label='production',
        model=ProductionOrder,
        action_name=action_name,
        route_name=f'v1_production:order-{action_name.replace("_", "-")}',
        detail=True,
        label=label,
        description=description,
        success_message=success_message,
        permissions=permissions,
        icon=icon,
        tone=tone,
        fields=fields,
        allowed_states=allowed_states,
        confirmation=confirmation,
    )


PRODUCTION_ACTIONS = (
    _action(
        'approve',
        'Aprovar',
        'Aprovar a ordem de produção para a etapa de liberação.',
        'Ordem de produção aprovada.',
        (ProductionOrder.Status.DRAFT,),
        icon='feather-check',
        confirmation=ActionConfirmation(
            'Aprovar ordem de produção',
            'Confirme que os dados da ordem foram revisados antes da aprovação.',
            acknowledge_label='Confirmo que revisei os dados da ordem.',
        ),
    ),
    _action(
        'release',
        'Liberar',
        'Liberar a ordem aprovada para execução na produção.',
        'Ordem de produção liberada.',
        (ProductionOrder.Status.APPROVED,),
        icon='feather-unlock',
        confirmation=ActionConfirmation(
            'Liberar ordem de produção',
            'Confirme que fórmula e roteiro estão aprovados e vigentes.',
            acknowledge_label='Confirmo a revisão das condições de liberação.',
        ),
    ),
    _action(
        'start',
        'Iniciar',
        'Iniciar a execução da ordem de produção liberada.',
        'Execução da ordem de produção iniciada.',
        (ProductionOrder.Status.RELEASED,),
        icon='feather-play-circle',
    ),
    _action(
        'pause',
        'Pausar',
        'Pausar temporariamente a execução da ordem de produção.',
        'Execução da ordem de produção pausada.',
        (ProductionOrder.Status.IN_PROGRESS,),
        icon='feather-pause-circle',
    ),
    _action(
        'resume',
        'Retomar',
        'Retomar a execução da ordem de produção pausada.',
        'Execução da ordem de produção retomada.',
        (ProductionOrder.Status.PAUSED,),
        icon='feather-play-circle',
    ),
    _action(
        'complete',
        'Concluir',
        'Concluir a execução e registrar o rendimento real da ordem.',
        'Ordem de produção concluída.',
        (ProductionOrder.Status.IN_PROGRESS,),
        icon='feather-check-circle',
        fields=(
            ActionField(
                'actual_yield_quantity',
                'Rendimento real',
                FieldKind.DECIMAL,
                required=True,
                min_value=0,
            ),
        ),
        confirmation=ActionConfirmation(
            'Concluir ordem de produção',
            'Esta ação encerra a execução da ordem e registra o rendimento informado.',
            typed_phrase='CONFIRMAR',
        ),
    ),
    _action(
        'cancel',
        'Cancelar',
        'Cancelar a ordem de produção com justificativa obrigatória.',
        'Ordem de produção cancelada.',
        ProductionOrder.CANCELLABLE_STATUSES,
        icon='feather-x-circle',
        tone='danger',
        fields=(
            ActionField(
                'cancel_reason',
                'Justificativa do cancelamento',
                FieldKind.TEXTAREA,
                required=True,
                max_length=2000,
            ),
        ),
        confirmation=ActionConfirmation(
            'Cancelar ordem de produção',
            'O cancelamento interrompe definitivamente o fluxo desta ordem.',
            typed_phrase='CANCELAR',
        ),
    ),
    _action(
        'reserve_materials',
        'Separar matérias-primas',
        'Reservar lotes aprovados para a ordem.',
        'Matérias-primas separadas.',
        (ProductionOrder.Status.APPROVED, ProductionOrder.Status.RELEASED),
        icon='feather-package',
        permissions=OPERATIONAL_PERMISSIONS['reserve_materials'],
        confirmation=ActionConfirmation(
            'Separar matérias-primas',
            'A reserva será feita para todas as linhas alocadas.',
            acknowledge_label='Confirmo os lotes e endereços informados.',
        ),
    ),
    _action(
        'issue_materials',
        'Baixar matérias-primas',
        'Baixa os materiais reservados para consumo na ordem.',
        'Matérias-primas baixadas.',
        (ProductionOrder.Status.IN_PROGRESS,),
        icon='feather-log-out',
        permissions=OPERATIONAL_PERMISSIONS['issue_materials'],
        confirmation=ActionConfirmation(
            'Baixar matérias-primas',
            'Consumo, perda e devolução devem reconciliar cada reserva.',
            typed_phrase='CONFIRMAR',
        ),
    ),
    _action(
        'receive_outputs',
        'Receber produtos acabados',
        'Recebe os produtos acabados em quarentena com rastreabilidade.',
        'Produtos acabados recebidos.',
        (ProductionOrder.Status.COMPLETED,),
        icon='feather-download',
        permissions=OPERATIONAL_PERMISSIONS['receive_outputs'],
        confirmation=ActionConfirmation(
            'Receber produto acabado',
            'Os lotes entrarão em quarentena e dependerão do fluxo de QA.',
            acknowledge_label='Confirmo as quantidades e os destinos.',
        ),
    ),
    _action(
        'calculate_cost',
        'Calcular custo',
        'Captura o custo da ordem concluída para o período informado.',
        'Custo da ordem calculado.',
        (ProductionOrder.Status.COMPLETED, ProductionOrder.Status.CLOSED),
        icon='feather-dollar-sign',
        permissions=OPERATIONAL_PERMISSIONS['calculate_cost'],
        fields=(
            ActionField('period_start', 'Início do período', FieldKind.DATE, required=True),
            ActionField('period_end', 'Fim do período', FieldKind.DATE, required=True),
        ),
    ),
)
