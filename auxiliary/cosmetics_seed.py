from collections import defaultdict

from django.db import transaction

from auxiliary.models import (
    BusinessArea,
    BusinessProcess,
    CatalogType,
    CatalogValue,
    CommercialTerm,
    Department,
    ImpactLevel,
    OrganizationalRole,
    SystemModel,
    SystemModule,
)
from base.ui.registry import get_modules


BUSINESS_AREAS = (
    ('BA-COS-DT', 'Direção Técnica', 'Governança técnica e responsabilidade sanitária.'),
    (
        'BA-COS-PD',
        'Pesquisa e Desenvolvimento',
        'Desenvolvimento e transferência de produtos cosméticos.',
    ),
    ('BA-COS-PROD', 'Produção', 'Pesagem, fabricação, envase e embalagem.'),
    (
        'BA-COS-CQ',
        'Controle da Qualidade',
        'Ensaios físico-químicos e microbiológicos.',
    ),
    (
        'BA-COS-GQ',
        'Garantia da Qualidade',
        'Sistema da qualidade, validação e liberação.',
    ),
    (
        'BA-COS-AR',
        'Assuntos Regulatórios',
        'Regularização e manutenção de produtos cosméticos.',
    ),
    ('BA-COS-SUP', 'Suprimentos', 'Compras e qualificação comercial de fornecedores.'),
    (
        'BA-COS-LOG',
        'Armazenagem e Logística',
        'Recebimento, armazenagem e expedição.',
    ),
    (
        'BA-COS-COM',
        'Comercial e Atendimento',
        'Vendas, SAC e cosmetovigilância.',
    ),
    ('BA-COS-FIN', 'Financeiro', 'Contas, tesouraria e controladoria.'),
    ('BA-COS-RH', 'Recursos Humanos', 'Pessoas, competências e treinamentos.'),
    (
        'BA-COS-ENG',
        'Engenharia e Manutenção',
        'Utilidades e infraestrutura industrial.',
    ),
    (
        'BA-COS-SSMA',
        'Saúde, Segurança e Meio Ambiente',
        'Segurança ocupacional e gestão ambiental.',
    ),
    (
        'BA-COS-TI',
        'Tecnologia da Informação',
        'Sistemas, infraestrutura e segurança da informação.',
    ),
)

BUSINESS_PROCESSES = (
    ('BPC-COS-DEV', 'Desenvolvimento de formulações', 'BA-COS-PD'),
    ('BPC-COS-TRANSF', 'Transferência de tecnologia', 'BA-COS-PD'),
    ('BPC-COS-QUAL-MP', 'Qualificação de matérias-primas', 'BA-COS-GQ'),
    ('BPC-COS-QUAL-ME', 'Qualificação de materiais de embalagem', 'BA-COS-GQ'),
    ('BPC-COS-PES', 'Pesagem e dispensação', 'BA-COS-PROD'),
    ('BPC-COS-FAB', 'Fabricação de cosméticos', 'BA-COS-PROD'),
    ('BPC-COS-ENV', 'Envase', 'BA-COS-PROD'),
    ('BPC-COS-EMB', 'Embalagem', 'BA-COS-PROD'),
    ('BPC-COS-FQ', 'Controle físico-químico', 'BA-COS-CQ'),
    ('BPC-COS-MICRO', 'Controle microbiológico', 'BA-COS-CQ'),
    ('BPC-COS-LIB', 'Liberação de lote', 'BA-COS-GQ'),
    ('BPC-COS-DESV', 'Gestão de desvios', 'BA-COS-GQ'),
    ('BPC-COS-CAPA', 'Gestão de CAPA', 'BA-COS-GQ'),
    ('BPC-COS-MUD', 'Controle de mudanças', 'BA-COS-GQ'),
    ('BPC-COS-REG', 'Regularização de cosméticos', 'BA-COS-AR'),
    ('BPC-COS-RECL', 'Tratamento de reclamações', 'BA-COS-COM'),
    ('BPC-COS-COSVIG', 'Cosmetovigilância', 'BA-COS-COM'),
    ('BPC-COS-REC', 'Recolhimento de produto', 'BA-COS-GQ'),
    ('BPC-COS-COMP', 'Compras', 'BA-COS-SUP'),
    ('BPC-COS-REC-MAT', 'Recebimento de materiais', 'BA-COS-LOG'),
    ('BPC-COS-ARM', 'Armazenagem', 'BA-COS-LOG'),
    ('BPC-COS-EXP', 'Expedição', 'BA-COS-LOG'),
    ('BPC-COS-MAN', 'Manutenção industrial', 'BA-COS-ENG'),
    ('BPC-COS-AUD', 'Auditoria interna da qualidade', 'BA-COS-GQ'),
)

DEPARTMENTS = (
    ('DEP-COS-FORM', 'Desenvolvimento de Formulações', 'BA-COS-PD'),
    ('DEP-COS-FAB', 'Fabricação', 'BA-COS-PROD'),
    ('DEP-COS-ENV', 'Envase', 'BA-COS-PROD'),
    ('DEP-COS-EMB', 'Embalagem', 'BA-COS-PROD'),
    ('DEP-COS-FQ', 'Laboratório Físico-Químico', 'BA-COS-CQ'),
    ('DEP-COS-MICRO', 'Laboratório de Microbiologia', 'BA-COS-CQ'),
    ('DEP-COS-VALID', 'Validação e Qualificação', 'BA-COS-GQ'),
    ('DEP-COS-LIB', 'Liberação e Documentação', 'BA-COS-GQ'),
    ('DEP-COS-FORN', 'Qualificação de Fornecedores', 'BA-COS-GQ'),
    ('DEP-COS-REG', 'Regularização de Produtos', 'BA-COS-AR'),
    ('DEP-COS-SAC', 'SAC e Cosmetovigilância', 'BA-COS-COM'),
    ('DEP-COS-COMP', 'Compras', 'BA-COS-SUP'),
    ('DEP-COS-ALMOX', 'Almoxarifado', 'BA-COS-LOG'),
    ('DEP-COS-EXP', 'Expedição', 'BA-COS-LOG'),
    ('DEP-COS-MAN', 'Manutenção', 'BA-COS-ENG'),
    ('DEP-COS-TI', 'Sistemas e Infraestrutura', 'BA-COS-TI'),
    ('DEP-COS-AUD', 'Auditoria Interna', 'BA-COS-GQ'),
)

ORGANIZATIONAL_ROLES = (
    ('ORG-COS-GGQ', 'Gerente de Garantia da Qualidade'),
    ('ORG-COS-AGQ', 'Analista de Garantia da Qualidade'),
    ('ORG-COS-GCQ', 'Gerente de Controle da Qualidade'),
    ('ORG-COS-ACQ', 'Analista de Controle da Qualidade'),
    ('ORG-COS-FORM', 'Formulador Cosmético'),
    ('ORG-COS-MICRO', 'Microbiologista'),
    ('ORG-COS-SPROD', 'Supervisor de Produção'),
    ('ORG-COS-OFAB', 'Operador de Fabricação'),
    ('ORG-COS-OENV', 'Operador de Envase'),
    ('ORG-COS-IEMB', 'Inspetor de Embalagem'),
    ('ORG-COS-REG', 'Analista de Assuntos Regulatórios'),
    ('ORG-COS-COMP', 'Comprador'),
    ('ORG-COS-ALMOX', 'Almoxarife'),
    ('ORG-COS-PCP', 'Planejador de Produção'),
    ('ORG-COS-MAN', 'Técnico de Manutenção'),
    ('ORG-COS-COSVIG', 'Analista de SAC e Cosmetovigilância'),
    ('ORG-COS-AUD', 'Auditor Interno'),
)

COMMERCIAL_TERMS = (
    ('CTM-COS-PG0', 'Pagamento à vista', CommercialTerm.TermType.PAYMENT, 0),
    ('CTM-COS-PG7', 'Pagamento em 7 dias', CommercialTerm.TermType.PAYMENT, 7),
    ('CTM-COS-PG14', 'Pagamento em 14 dias', CommercialTerm.TermType.PAYMENT, 14),
    ('CTM-COS-PG21', 'Pagamento em 21 dias', CommercialTerm.TermType.PAYMENT, 21),
    ('CTM-COS-PG28', 'Pagamento em 28 dias', CommercialTerm.TermType.PAYMENT, 28),
    ('CTM-COS-PG30', 'Pagamento em 30 dias', CommercialTerm.TermType.PAYMENT, 30),
    ('CTM-COS-PG45', 'Pagamento em 45 dias', CommercialTerm.TermType.PAYMENT, 45),
    ('CTM-COS-PG60', 'Pagamento em 60 dias', CommercialTerm.TermType.PAYMENT, 60),
    ('CTM-COS-PG90', 'Pagamento em 90 dias', CommercialTerm.TermType.PAYMENT, 90),
    ('CTM-COS-RET', 'Retirada pelo comprador', CommercialTerm.TermType.DELIVERY, 0),
    ('CTM-COS-CIF', 'Entrega CIF', CommercialTerm.TermType.DELIVERY, 7),
    ('CTM-COS-FOB', 'Entrega FOB', CommercialTerm.TermType.DELIVERY, 0),
)

IMPACT_NAMES = (
    (1, 'Baixo', 'success'),
    (2, 'Médio', 'warning'),
    (3, 'Alto', 'danger'),
    (4, 'Crítico', 'dark'),
)
IMPACT_TYPES = tuple(value for value, _label in ImpactLevel.LevelType.choices)
IMPACT_CODE_PARTS = {
    ImpactLevel.LevelType.SEVERITY: 'SEV',
    ImpactLevel.LevelType.CRITICALITY: 'CRIT',
    ImpactLevel.LevelType.PRIORITY: 'PRI',
    ImpactLevel.LevelType.RISK: 'RISK',
}

CATALOGS = (
    (
        'CTG-COS-MATERIAL',
        'Tipo de material cosmético',
        'material_type',
        (
            ('CV-COS-MAT-MP', 'Matéria-prima', 'raw_material'),
            ('CV-COS-MAT-ME', 'Material de embalagem', 'packaging_material'),
            ('CV-COS-MAT-SEMI', 'Produto semielaborado', 'semi_finished'),
            ('CV-COS-MAT-PA', 'Produto acabado', 'finished_product'),
        ),
    ),
    (
        'CTG-COS-APRESENT',
        'Apresentação cosmética',
        'presentation',
        (
            ('CV-COS-APR-CREME', 'Creme', 'cream'),
            ('CV-COS-APR-LOCAO', 'Loção', 'lotion'),
            ('CV-COS-APR-GEL', 'Gel', 'gel'),
            ('CV-COS-APR-SHAMPOO', 'Xampu', 'shampoo'),
            ('CV-COS-APR-COND', 'Condicionador', 'conditioner'),
            ('CV-COS-APR-SAB', 'Sabonete líquido', 'liquid_soap'),
            ('CV-COS-APR-SERUM', 'Sérum', 'serum'),
            ('CV-COS-APR-AERO', 'Aerossol', 'aerosol'),
        ),
    ),
    (
        'CTG-COS-RECL-ORIG',
        'Origem da reclamação',
        'complaint_origin',
        (
            ('CV-COS-REC-CONS', 'Consumidor', 'consumer'),
            ('CV-COS-REC-CLI', 'Cliente', 'customer'),
            ('CV-COS-REC-DIST', 'Distribuidor', 'distributor'),
            ('CV-COS-REC-VIG', 'Autoridade sanitária', 'health_authority'),
        ),
    ),
    (
        'CTG-COS-DESV',
        'Classificação de desvio',
        'deviation_class',
        (
            ('CV-COS-DESV-MEN', 'Menor', 'minor'),
            ('CV-COS-DESV-MAI', 'Maior', 'major'),
            ('CV-COS-DESV-CRI', 'Crítico', 'critical'),
        ),
    ),
    (
        'CTG-COS-EMB',
        'Tipo de embalagem',
        'packaging_type',
        (
            ('CV-COS-EMB-PRIM', 'Embalagem primária', 'primary'),
            ('CV-COS-EMB-SEC', 'Embalagem secundária', 'secondary'),
            ('CV-COS-EMB-TER', 'Embalagem de transporte', 'tertiary'),
        ),
    ),
    (
        'CTG-COS-ARM',
        'Condição de armazenamento',
        'storage_condition',
        (
            ('CV-COS-ARM-AMB', 'Temperatura ambiente', 'ambient'),
            ('CV-COS-ARM-15-30', 'Entre 15 °C e 30 °C', '15_30_c'),
            ('CV-COS-ARM-2-8', 'Refrigerado entre 2 °C e 8 °C', '2_8_c'),
            ('CV-COS-ARM-LUZ', 'Protegido da luz', 'protected_from_light'),
        ),
    ),
    (
        'CTG-COS-UNID',
        'Unidade organizacional',
        'organizational_unit',
        (
            ('CV-COS-UNID-PD', 'Pesquisa e Desenvolvimento', 'research_development'),
            ('CV-COS-UNID-PROD', 'Produção', 'production'),
            ('CV-COS-UNID-CQ', 'Controle da Qualidade', 'quality_control'),
            ('CV-COS-UNID-GQ', 'Garantia da Qualidade', 'quality_assurance'),
            ('CV-COS-UNID-AR', 'Assuntos Regulatórios', 'regulatory_affairs'),
            ('CV-COS-UNID-LOG', 'Armazenagem e Logística', 'logistics'),
        ),
    ),
)


def _upsert(model, code, **values):
    instance = model.objects.filter(code=code).first() or model(code=code)
    for field_name, value in values.items():
        setattr(instance, field_name, value)
    instance.is_active = True
    instance.full_clean()
    instance.save()
    return instance


@transaction.atomic
def seed_cosmetics_auxiliary_data():
    counts = defaultdict(int)
    areas = {}
    for code, name, description in BUSINESS_AREAS:
        areas[code] = _upsert(BusinessArea, code, name=name, description=description)
        counts['business_areas'] += 1

    for code, name, area_code in BUSINESS_PROCESSES:
        _upsert(
            BusinessProcess,
            code,
            name=name,
            description=f'Processo cosmético: {name}.',
            area=areas[area_code],
        )
        counts['business_processes'] += 1

    for code, name, area_code in DEPARTMENTS:
        _upsert(
            Department,
            code,
            name=name,
            description=f'Departamento da indústria cosmética: {name}.',
            area=areas[area_code],
        )
        counts['departments'] += 1

    for code, name in ORGANIZATIONAL_ROLES:
        _upsert(
            OrganizationalRole,
            code,
            name=name,
            description=f'Função organizacional cosmética: {name}.',
        )
        counts['organizational_roles'] += 1

    for code, name, term_type, days in COMMERCIAL_TERMS:
        _upsert(
            CommercialTerm,
            code,
            name=name,
            description=(
                f'Condição comercial de {name.lower()}; validar o instrumento contratual aplicável.'
            ),
            term_type=term_type,
            days=days,
        )
        counts['commercial_terms'] += 1

    for level_type in IMPACT_TYPES:
        for weight, name, color in IMPACT_NAMES:
            code = f'IL-COS-{IMPACT_CODE_PARTS[level_type]}-{weight}'
            _upsert(
                ImpactLevel,
                code,
                name=name,
                description=f'{name} para classificação de {level_type}.',
                level_type=level_type,
                weight=weight,
                color=color,
            )
            counts['impact_levels'] += 1

    for type_code, type_name, target_field, values in CATALOGS:
        catalog_type = _upsert(
            CatalogType,
            type_code,
            name=type_name,
            description=f'Catálogo cosmético: {type_name}.',
            target_field=target_field,
        )
        counts['catalog_types'] += 1
        for order, (value_code, value_name, technical_value) in enumerate(values, start=1):
            _upsert(
                CatalogValue,
                value_code,
                name=value_name,
                description=f'Valor de {type_name.lower()}: {value_name}.',
                catalog_type=catalog_type,
                value=technical_value,
                order=order * 10,
            )
            counts['catalog_values'] += 1

    module_refs = {}
    for module in get_modules():
        code = f'SM-{module.slug.upper().replace("-", "_")}'
        module_refs[module.slug] = _upsert(
            SystemModule,
            code,
            name=module.label,
            description=module.description,
            app_label=module.slug,
            menu_label=module.label,
        )
        counts['system_modules'] += 1

    seen_models = set()
    for module in get_modules():
        for resource in module.resources:
            model = resource.model
            key = (model._meta.app_label, model._meta.model_name)
            if key in seen_models:
                continue
            seen_models.add(key)
            app_label, model_name = key
            _upsert(
                SystemModel,
                f'SMD-{app_label}.{model_name}',
                name=str(model._meta.verbose_name).capitalize(),
                description=f'Model do recurso {resource.label}.',
                module=module_refs[module.slug],
                app_label=app_label,
                model_name=model_name,
            )
            counts['system_models'] += 1

    return dict(sorted(counts.items()))
