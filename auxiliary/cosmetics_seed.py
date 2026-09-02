from collections import defaultdict

from django.core.exceptions import ValidationError
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
from reference_data.manifest import CatalogManifest


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


def build_auxiliary_catalog_payload() -> dict[str, tuple]:
    """Materializa todo o seed auxiliar, inclusive o registry, em ordem estável."""

    impact_levels = tuple(
        (
            f'IL-COS-{IMPACT_CODE_PARTS[level_type]}-{weight}',
            name,
            f'{name} para classificação de {level_type}.',
            level_type,
            weight,
            color,
        )
        for level_type in IMPACT_TYPES
        for weight, name, color in IMPACT_NAMES
    )
    catalog_types = tuple(
        (
            type_code,
            type_name,
            f'Catálogo cosmético: {type_name}.',
            target_field,
        )
        for type_code, type_name, target_field, _values in CATALOGS
    )
    catalog_values = tuple(
        (
            value_code,
            value_name,
            f'Valor de {type_name.lower()}: {value_name}.',
            type_code,
            technical_value,
            order * 10,
        )
        for type_code, type_name, _target_field, values in CATALOGS
        for order, (value_code, value_name, technical_value) in enumerate(values, start=1)
    )

    modules = tuple(get_modules())
    system_modules = tuple(
        sorted(
            (
                f'SM-{module.slug.upper().replace("-", "_")}',
                module.label,
                module.description,
                module.slug,
                module.label,
            )
            for module in modules
        )
    )
    seen_models = set()
    system_models = []
    for module in modules:
        module_code = f'SM-{module.slug.upper().replace("-", "_")}'
        for resource in module.resources:
            model = resource.model
            key = (model._meta.app_label, model._meta.model_name)
            if key in seen_models:
                continue
            seen_models.add(key)
            app_label, model_name = key
            system_models.append(
                (
                    f'SMD-{app_label}.{model_name}',
                    str(model._meta.verbose_name).capitalize(),
                    f'Model do recurso {resource.label}.',
                    module_code,
                    app_label,
                    model_name,
                )
            )

    return {
        'auxiliary.BusinessArea': tuple(BUSINESS_AREAS),
        'auxiliary.BusinessProcess': tuple(
            (code, name, f'Processo cosmético: {name}.', area_code)
            for code, name, area_code in BUSINESS_PROCESSES
        ),
        'auxiliary.Department': tuple(
            (
                code,
                name,
                f'Departamento da indústria cosmética: {name}.',
                area_code,
            )
            for code, name, area_code in DEPARTMENTS
        ),
        'auxiliary.OrganizationalRole': tuple(
            (code, name, f'Função organizacional cosmética: {name}.')
            for code, name in ORGANIZATIONAL_ROLES
        ),
        'auxiliary.CommercialTerm': tuple(
            (
                code,
                name,
                f'Condição comercial de {name.lower()}; validar o instrumento contratual aplicável.',
                term_type,
                days,
            )
            for code, name, term_type, days in COMMERCIAL_TERMS
        ),
        'auxiliary.ImpactLevel': impact_levels,
        'auxiliary.CatalogType': catalog_types,
        'auxiliary.CatalogValue': catalog_values,
        'auxiliary.SystemModule': system_modules,
        'auxiliary.SystemModel': tuple(
            sorted(system_models, key=lambda record: (record[4], record[5]))
        ),
    }


AUXILIARY_CATALOG_PAYLOAD = build_auxiliary_catalog_payload()

AUXILIARY_CATALOG_MANIFEST = CatalogManifest(
    identifier='rgn-cosmetics-auxiliary-catalogs',
    version='2026.1',
    source_date='2026-09-02',
    source_urls=('https://github.com/RuiGN/rgnfamarsystemv2',),
    namespaces=(
        'BA-COS-',
        'BPC-COS-',
        'DEP-COS-',
        'ORG-COS-',
        'CTM-COS-',
        'IL-COS-',
        'CTG-COS-',
        'CV-COS-',
        'SM-',
        'SMD-',
    ),
    expected_counts={
        'auxiliary.BusinessArea': 14,
        'auxiliary.BusinessProcess': 24,
        'auxiliary.Department': 17,
        'auxiliary.OrganizationalRole': 17,
        'auxiliary.CommercialTerm': 12,
        'auxiliary.ImpactLevel': 16,
        'auxiliary.CatalogType': 7,
        'auxiliary.CatalogValue': 32,
        'auxiliary.SystemModule': 29,
        'auxiliary.SystemModel': 200,
    },
    sha256='02aa1bc8e5fa77022a611079ea49d129eb12836c6490c3fb32c2e6412b5638c3',
    provenance=(
        'Conteúdo curado em pt-BR no repositório RGN Farma System.',
        'SystemModule e SystemModel materializados do registry de interface versionado no release.',
    ),
    license_name='Conteúdo proprietário; uso interno autorizado no RGN Farma System',
    license_url='https://github.com/RuiGN/rgnfamarsystemv2',
)


def _validate_auxiliary_catalog_payload(payload: dict[str, tuple]) -> None:
    if set(payload) != set(AUXILIARY_CATALOG_MANIFEST.expected_counts):
        raise ValidationError('As seções auxiliares divergem do manifesto.')
    counts = {section: len(records) for section, records in payload.items()}
    if counts != AUXILIARY_CATALOG_MANIFEST.expected_counts:
        raise ValidationError('As contagens auxiliares divergem do manifesto.')
    for section, records in payload.items():
        codes = [record[0] for record in records]
        if len(codes) != len(set(codes)):
            raise ValidationError(f'{section}: código duplicado.')
    try:
        AUXILIARY_CATALOG_MANIFEST.validate_payload(payload)
    except ValueError as exc:
        raise ValidationError(
            'O conteúdo auxiliar diverge do SHA-256 literal do manifesto.'
        ) from exc

    area_codes = {record[0] for record in payload['auxiliary.BusinessArea']}
    for section in ('auxiliary.BusinessProcess', 'auxiliary.Department'):
        missing = sorted(record[3] for record in payload[section] if record[3] not in area_codes)
        if missing:
            raise ValidationError(f'{section}: área inexistente: {", ".join(missing)}.')
    catalog_type_codes = {record[0] for record in payload['auxiliary.CatalogType']}
    missing_types = sorted(
        record[3]
        for record in payload['auxiliary.CatalogValue']
        if record[3] not in catalog_type_codes
    )
    if missing_types:
        raise ValidationError(f'Tipo de catálogo inexistente: {", ".join(missing_types)}.')
    module_codes = {record[0] for record in payload['auxiliary.SystemModule']}
    missing_modules = sorted(
        record[3] for record in payload['auxiliary.SystemModel'] if record[3] not in module_codes
    )
    if missing_modules:
        raise ValidationError(f'Módulo do sistema inexistente: {", ".join(missing_modules)}.')


def _prepare_instance(model, code, **values):
    instance = model.objects.filter(code=code).first() or model(code=code)
    for field_name, value in values.items():
        setattr(instance, field_name, value)
    instance.is_active = True
    excluded_relations = {
        field_name
        for field_name, value in values.items()
        if hasattr(value, '_meta') and value.pk is None
    }
    instance.full_clean(exclude=excluded_relations or None)
    return instance


def _prepare_auxiliary_catalog_payload(payload: dict[str, tuple]) -> None:
    areas = {
        code: _prepare_instance(BusinessArea, code, name=name, description=description)
        for code, name, description in payload['auxiliary.BusinessArea']
    }
    for code, name, description, area_code in payload['auxiliary.BusinessProcess']:
        _prepare_instance(
            BusinessProcess,
            code,
            name=name,
            description=description,
            area=areas[area_code],
        )
    for code, name, description, area_code in payload['auxiliary.Department']:
        _prepare_instance(
            Department,
            code,
            name=name,
            description=description,
            area=areas[area_code],
        )
    for code, name, description in payload['auxiliary.OrganizationalRole']:
        _prepare_instance(
            OrganizationalRole,
            code,
            name=name,
            description=description,
        )
    for code, name, description, term_type, days in payload['auxiliary.CommercialTerm']:
        _prepare_instance(
            CommercialTerm,
            code,
            name=name,
            description=description,
            term_type=term_type,
            days=days,
        )
    for code, name, description, level_type, weight, color in payload['auxiliary.ImpactLevel']:
        _prepare_instance(
            ImpactLevel,
            code,
            name=name,
            description=description,
            level_type=level_type,
            weight=weight,
            color=color,
        )
    catalog_types = {}
    for code, name, description, target_field in payload['auxiliary.CatalogType']:
        catalog_types[code] = _prepare_instance(
            CatalogType,
            code,
            name=name,
            description=description,
            target_field=target_field,
        )
    for code, name, description, type_code, value, order in payload['auxiliary.CatalogValue']:
        _prepare_instance(
            CatalogValue,
            code,
            name=name,
            description=description,
            catalog_type=catalog_types[type_code],
            value=value,
            order=order,
        )
    modules = {}
    for code, name, description, app_label, menu_label in payload['auxiliary.SystemModule']:
        modules[code] = _prepare_instance(
            SystemModule,
            code,
            name=name,
            description=description,
            app_label=app_label,
            menu_label=menu_label,
        )
    for code, name, description, module_code, app_label, model_name in payload[
        'auxiliary.SystemModel'
    ]:
        _prepare_instance(
            SystemModel,
            code,
            name=name,
            description=description,
            module=modules[module_code],
            app_label=app_label,
            model_name=model_name,
        )


def validate_cosmetics_auxiliary_data() -> dict[str, tuple]:
    """Valida manifesto, relações e models antes de qualquer escrita."""

    payload = build_auxiliary_catalog_payload()
    _validate_auxiliary_catalog_payload(payload)
    _prepare_auxiliary_catalog_payload(payload)
    return payload


def _upsert(model, code, **values):
    instance = model.objects.filter(code=code).first()
    if instance is None:
        instance = model(code=code)
        changed = True
    else:
        changed = False
    for field_name, value in values.items():
        field = model._meta.get_field(field_name)
        if field.is_relation and field.many_to_one:
            current = getattr(instance, field.attname)
            expected = value.pk if value is not None else None
        else:
            current = getattr(instance, field_name)
            expected = value
        if current != expected:
            setattr(instance, field_name, value)
            changed = True
    if not instance.is_active:
        instance.is_active = True
        changed = True
    if changed:
        instance.full_clean()
        instance.save()
    return instance


def _seed_cosmetics_auxiliary_data() -> dict[str, int]:
    payload = validate_cosmetics_auxiliary_data()

    counts = defaultdict(int)
    areas = {}
    for code, name, description in payload['auxiliary.BusinessArea']:
        areas[code] = _upsert(BusinessArea, code, name=name, description=description)
        counts['business_areas'] += 1

    for code, name, description, area_code in payload['auxiliary.BusinessProcess']:
        _upsert(
            BusinessProcess,
            code,
            name=name,
            description=description,
            area=areas[area_code],
        )
        counts['business_processes'] += 1

    for code, name, description, area_code in payload['auxiliary.Department']:
        _upsert(
            Department,
            code,
            name=name,
            description=description,
            area=areas[area_code],
        )
        counts['departments'] += 1

    for code, name, description in payload['auxiliary.OrganizationalRole']:
        _upsert(
            OrganizationalRole,
            code,
            name=name,
            description=description,
        )
        counts['organizational_roles'] += 1

    for code, name, description, term_type, days in payload['auxiliary.CommercialTerm']:
        _upsert(
            CommercialTerm,
            code,
            name=name,
            description=description,
            term_type=term_type,
            days=days,
        )
        counts['commercial_terms'] += 1

    for code, name, description, level_type, weight, color in payload['auxiliary.ImpactLevel']:
        _upsert(
            ImpactLevel,
            code,
            name=name,
            description=description,
            level_type=level_type,
            weight=weight,
            color=color,
        )
        counts['impact_levels'] += 1

    catalog_types = {}
    for code, name, description, target_field in payload['auxiliary.CatalogType']:
        catalog_types[code] = _upsert(
            CatalogType,
            code,
            name=name,
            description=description,
            target_field=target_field,
        )
        counts['catalog_types'] += 1
    for code, name, description, type_code, value, order in payload['auxiliary.CatalogValue']:
        _upsert(
            CatalogValue,
            code,
            name=name,
            description=description,
            catalog_type=catalog_types[type_code],
            value=value,
            order=order,
        )
        counts['catalog_values'] += 1

    module_refs = {}
    for code, name, description, app_label, menu_label in payload['auxiliary.SystemModule']:
        module_refs[code] = _upsert(
            SystemModule,
            code,
            name=name,
            description=description,
            app_label=app_label,
            menu_label=menu_label,
        )
        counts['system_modules'] += 1

    for code, name, description, module_code, app_label, model_name in payload[
        'auxiliary.SystemModel'
    ]:
        _upsert(
            SystemModel,
            code,
            name=name,
            description=description,
            module=module_refs[module_code],
            app_label=app_label,
            model_name=model_name,
        )
        counts['system_models'] += 1

    return dict(sorted(counts.items()))


def seed_cosmetics_auxiliary_data(*, use_current_transaction: bool = False) -> dict[str, int]:
    """Carrega auxiliares, reutilizando opcionalmente a transação coordenadora."""

    if use_current_transaction:
        return _seed_cosmetics_auxiliary_data()
    with transaction.atomic():
        return _seed_cosmetics_auxiliary_data()
