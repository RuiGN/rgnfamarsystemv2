"""Catálogos mestres curados para a operação cosmética single-instance."""

from auxiliary.cosmetics_seed import ORGANIZATIONAL_ROLES
from reference_data.manifest import CatalogManifest


UNITS = (
    ('UOM-KG', 'Kilograma', 'kg'),
    ('UOM-G', 'Grama', 'g'),
    ('UOM-MG', 'Miligrama', 'mg'),
    ('UOM-UG', 'Micrograma', 'µg'),
    ('UOM-L', 'Litro', 'L'),
    ('UOM-ML', 'Mililitro', 'mL'),
    ('UOM-UL', 'Microlitro', 'µL'),
    ('UOM-UN', 'Unidade', 'un'),
    ('UOM-PCT', 'Percentual', '%'),
    ('UOM-C', 'Grau Celsius', '°C'),
    ('UOM-K', 'Kelvin', 'K'),
    ('UOM-PA', 'Pascal', 'Pa'),
    ('UOM-KPA', 'Kilopascal', 'kPa'),
    ('UOM-BAR', 'Bar', 'bar'),
    ('UOM-S', 'Segundo', 's'),
    ('UOM-MIN', 'Minuto', 'min'),
    ('UOM-H', 'Hora', 'h'),
    ('UOM-M', 'Metro', 'm'),
    ('UOM-CM', 'Centímetro', 'cm'),
    ('UOM-MM', 'Milímetro', 'mm'),
    ('UOM-M2', 'Metro quadrado', 'm²'),
)

MASTER_CATEGORIES = (
    ('CAT-COS-FAM-HIG', 'Higiene pessoal', 'family', None),
    ('CAT-COS-FAM-CAP', 'Cuidados capilares', 'family', None),
    ('CAT-COS-FAM-FAC', 'Cuidados faciais', 'family', None),
    ('CAT-COS-FAM-COR', 'Cuidados corporais', 'family', None),
    ('CAT-COS-FAM-PERF', 'Perfumaria', 'family', None),
    ('CAT-COS-FAM-MAQ', 'Maquiagem', 'family', None),
    ('CAT-COS-FAM-SOLAR', 'Proteção solar', 'family', None),
    ('CAT-COS-GRP-MP', 'Matérias-primas', 'group', None),
    ('CAT-COS-GRP-ME', 'Materiais de embalagem', 'group', None),
    ('CAT-COS-GRP-SEMI', 'Produtos semielaborados', 'group', None),
    ('CAT-COS-GRP-PA', 'Produtos acabados', 'group', None),
    ('CAT-COS-FORM-SOL', 'Solução', 'cosmetic_form', None),
    ('CAT-COS-FORM-EMULSAO', 'Emulsão', 'cosmetic_form', None),
    ('CAT-COS-FORM-GEL', 'Gel', 'cosmetic_form', None),
    ('CAT-COS-FORM-SUSP', 'Suspensão', 'cosmetic_form', None),
    ('CAT-COS-FORM-AERO', 'Aerossol', 'cosmetic_form', None),
    ('CAT-COS-FORM-ANIDRA', 'Forma anidra', 'cosmetic_form', None),
    ('CAT-COS-FORM-PO', 'Pó', 'cosmetic_form', None),
    ('CAT-COS-FORM-BARRA', 'Barra', 'cosmetic_form', None),
    ('CAT-COS-FORM-BALS', 'Bálsamo', 'cosmetic_form', None),
    ('CAT-COS-FORM-SERUM', 'Sérum', 'cosmetic_form', None),
    ('CAT-COS-APR-FRASCO', 'Frasco', 'presentation', None),
    ('CAT-COS-APR-BISNAGA', 'Bisnaga', 'presentation', None),
    ('CAT-COS-APR-POTE', 'Pote', 'presentation', None),
    ('CAT-COS-APR-SACHE', 'Sachê', 'presentation', None),
    ('CAT-COS-APR-PUMP', 'Frasco com válvula', 'presentation', None),
    ('CAT-COS-APR-CONTA', 'Frasco conta-gotas', 'presentation', None),
    ('CAT-COS-APR-AERO', 'Lata aerossol', 'presentation', None),
    ('CAT-COS-APR-REFIL', 'Refil', 'presentation', None),
    ('CAT-COS-CONC-PP', 'Percentual massa/massa', 'concentration', None),
    ('CAT-COS-CONC-PV', 'Percentual massa/volume', 'concentration', None),
    ('CAT-COS-CONC-VV', 'Percentual volume/volume', 'concentration', None),
    ('CAT-COS-APL-CABELO', 'Cabelos', 'application_area', None),
    ('CAT-COS-APL-COURO', 'Couro cabeludo', 'application_area', None),
    ('CAT-COS-APL-FACE', 'Face', 'application_area', None),
    ('CAT-COS-APL-OLHOS', 'Área dos olhos', 'application_area', None),
    ('CAT-COS-APL-LABIOS', 'Lábios', 'application_area', None),
    ('CAT-COS-APL-CORPO', 'Corpo', 'application_area', None),
    ('CAT-COS-APL-MAOS', 'Mãos', 'application_area', None),
    ('CAT-COS-APL-PES', 'Pés', 'application_area', None),
    ('CAT-COS-APL-UNHAS', 'Unhas', 'application_area', None),
    ('CAT-COS-APL-AXILAS', 'Axilas', 'application_area', None),
)

COST_ELEMENTS = (
    ('CE-COS-MAT', 'Materiais diretos', 'material'),
    ('CE-COS-PERDA', 'Perdas de processo', 'loss'),
    ('CE-COS-MOD', 'Mão de obra direta', 'labor'),
    ('CE-COS-MAQ', 'Hora máquina', 'machine'),
    ('CE-COS-TERC', 'Serviços de terceiros', 'third_party'),
    ('CE-COS-ANAL', 'Análises laboratoriais', 'analysis'),
    ('CE-COS-CIF', 'Custos indiretos de fabricação', 'overhead'),
    ('CE-COS-IND', 'Custos indiretos administrativos', 'indirect'),
    ('CE-COS-TRIB', 'Tributos', 'tax'),
    ('CE-COS-NQ', 'Custo da não qualidade', 'non_quality'),
)

CUSTOMER_GROUPS = (
    ('CG-COS-VAREJO', 'Varejo especializado', 'Clientes do varejo especializado em cosméticos.'),
    ('CG-COS-DISTRIB', 'Distribuidores', 'Distribuidores de produtos cosméticos.'),
    ('CG-COS-FARMA', 'Farmácias e drogarias', 'Redes e lojas do canal farma.'),
    ('CG-COS-MASSA', 'Varejo alimentar', 'Supermercados e atacarejos.'),
    ('CG-COS-PROF', 'Canal profissional', 'Salões, clínicas e profissionais habilitados.'),
)

SALES_CHANNELS = (
    ('SC-COS-DIRETA', 'Venda direta', 'direct'),
    ('SC-COS-DISTRIB', 'Distribuidor', 'distributor'),
    ('SC-COS-ECOM', 'E-commerce', 'ecommerce'),
    ('SC-COS-REP', 'Representante comercial', 'representative'),
    ('SC-COS-PARC', 'Parceiro comercial', 'partner'),
)

CHART_ACCOUNTS = (
    ('COA-COS-1', 'Ativo', 'asset', None),
    ('COA-COS-1.1', 'Estoques', 'asset', 'COA-COS-1'),
    ('COA-COS-2', 'Passivo', 'liability', None),
    ('COA-COS-2.1', 'Fornecedores', 'liability', 'COA-COS-2'),
    ('COA-COS-3', 'Patrimônio líquido', 'equity', None),
    ('COA-COS-4', 'Receitas', 'revenue', None),
    ('COA-COS-4.1', 'Receita de produtos cosméticos', 'revenue', 'COA-COS-4'),
    ('COA-COS-5', 'Despesas e custos', 'expense', None),
    ('COA-COS-5.1', 'Custo dos produtos vendidos', 'expense', 'COA-COS-5'),
    ('COA-COS-5.2', 'Controle da Qualidade', 'expense', 'COA-COS-5'),
    ('COA-COS-5.3', 'Garantia da Qualidade', 'expense', 'COA-COS-5'),
    ('COA-COS-5.4', 'Pesquisa e Desenvolvimento', 'expense', 'COA-COS-5'),
)

FINANCIAL_CATEGORIES = (
    ('FC-COS-COMP', 'Compras de materiais', 'payable', 'COA-COS-1.1'),
    ('FC-COS-TERC', 'Serviços de terceiros', 'payable', 'COA-COS-5'),
    ('FC-COS-CQ', 'Controle da Qualidade', 'payable', 'COA-COS-5.2'),
    ('FC-COS-GQ', 'Garantia da Qualidade', 'payable', 'COA-COS-5.3'),
    ('FC-COS-PD', 'Pesquisa e Desenvolvimento', 'payable', 'COA-COS-5.4'),
    ('FC-COS-VENDAS', 'Venda de produtos cosméticos', 'receivable', 'COA-COS-4.1'),
)

COMPETENCIES = (
    ('CPT-COS-BPF', 'Boas Práticas de Fabricação', 'gmp'),
    ('CPT-COS-ALCOA', 'Integridade de dados ALCOA+', 'gmp'),
    ('CPT-COS-HIG', 'Higiene e sanitização industrial', 'technical'),
    ('CPT-COS-PES', 'Pesagem e dispensação', 'technical'),
    ('CPT-COS-FAB', 'Fabricação de cosméticos', 'technical'),
    ('CPT-COS-ENV', 'Envase e embalagem', 'technical'),
    ('CPT-COS-CQ', 'Controle físico-químico', 'technical'),
    ('CPT-COS-MICRO', 'Controle microbiológico', 'technical'),
    ('CPT-COS-REG', 'Regularização de cosméticos', 'regulatory'),
    ('CPT-COS-COSVIG', 'Cosmetovigilância', 'regulatory'),
    ('CPT-COS-ERP', 'Utilização do RGN Farma System', 'system'),
)

# role, area, department and process. Titles always come from ORGANIZATIONAL_ROLES.
ROLE_RELATIONS = (
    ('ORG-COS-GGQ', 'BA-COS-GQ', 'DEP-COS-LIB', 'BPC-COS-LIB', True),
    ('ORG-COS-AGQ', 'BA-COS-GQ', 'DEP-COS-LIB', 'BPC-COS-DESV', True),
    ('ORG-COS-GCQ', 'BA-COS-CQ', 'DEP-COS-FQ', 'BPC-COS-FQ', True),
    ('ORG-COS-ACQ', 'BA-COS-CQ', 'DEP-COS-FQ', 'BPC-COS-FQ', True),
    ('ORG-COS-FORM', 'BA-COS-PD', 'DEP-COS-FORM', 'BPC-COS-DEV', True),
    ('ORG-COS-MICRO', 'BA-COS-CQ', 'DEP-COS-MICRO', 'BPC-COS-MICRO', True),
    ('ORG-COS-SPROD', 'BA-COS-PROD', 'DEP-COS-FAB', 'BPC-COS-FAB', True),
    ('ORG-COS-OFAB', 'BA-COS-PROD', 'DEP-COS-FAB', 'BPC-COS-FAB', True),
    ('ORG-COS-OENV', 'BA-COS-PROD', 'DEP-COS-ENV', 'BPC-COS-ENV', True),
    ('ORG-COS-IEMB', 'BA-COS-PROD', 'DEP-COS-EMB', 'BPC-COS-EMB', True),
    ('ORG-COS-REG', 'BA-COS-AR', 'DEP-COS-REG', 'BPC-COS-REG', True),
    ('ORG-COS-COMP', 'BA-COS-SUP', 'DEP-COS-COMP', 'BPC-COS-COMP', False),
    ('ORG-COS-ALMOX', 'BA-COS-LOG', 'DEP-COS-ALMOX', 'BPC-COS-ARM', True),
    ('ORG-COS-PCP', 'BA-COS-PROD', 'DEP-COS-FAB', 'BPC-COS-FAB', True),
    ('ORG-COS-MAN', 'BA-COS-ENG', 'DEP-COS-MAN', 'BPC-COS-MAN', True),
    ('ORG-COS-COSVIG', 'BA-COS-COM', 'DEP-COS-SAC', 'BPC-COS-COSVIG', True),
    ('ORG-COS-AUD', 'BA-COS-GQ', 'DEP-COS-AUD', 'BPC-COS-AUD', True),
)

_ROLE_NAMES = dict(ORGANIZATIONAL_ROLES)
JOB_POSITIONS = tuple(
    (
        role_code.replace('ORG-', 'JP-', 1),
        _ROLE_NAMES[role_code],
        area_code,
        department_code,
    )
    for role_code, area_code, department_code, _process_code, _critical in ROLE_RELATIONS
)
WORK_FUNCTIONS = tuple(
    (
        role_code.replace('ORG-', 'WF-', 1),
        _ROLE_NAMES[role_code],
        role_code.replace('ORG-', 'JP-', 1),
        area_code,
        process_code,
        critical,
    )
    for role_code, area_code, _department_code, process_code, critical in ROLE_RELATIONS
)

FISCAL_UNITS = (
    ('UN', 'Unidade'),
    ('KG', 'Kilograma'),
    ('G', 'Grama'),
    ('MG', 'Miligrama'),
    ('L', 'Litro'),
    ('ML', 'Mililitro'),
    ('CX', 'Caixa'),
    ('FR', 'Frasco'),
    ('TB', 'Bisnaga'),
    ('PT', 'Pote'),
    ('FD', 'Fardo'),
)

CFOPS = (
    ('1101', 'Compra para industrialização ou produção rural', 'inbound'),
    ('1102', 'Compra para comercialização', 'inbound'),
    ('1556', 'Compra de material para uso ou consumo', 'inbound'),
    ('2101', 'Compra para industrialização ou produção rural', 'inbound'),
    ('2102', 'Compra para comercialização', 'inbound'),
    ('2556', 'Compra de material para uso ou consumo', 'inbound'),
    ('5101', 'Venda de produção do estabelecimento', 'outbound'),
    ('5102', 'Venda de mercadoria adquirida ou recebida de terceiros', 'outbound'),
    ('5910', 'Remessa em bonificação, doação ou brinde', 'outbound'),
    ('6101', 'Venda de produção do estabelecimento', 'outbound'),
    ('6102', 'Venda de mercadoria adquirida ou recebida de terceiros', 'outbound'),
    ('6910', 'Remessa em bonificação, doação ou brinde', 'outbound'),
)

COSMETICS_CATALOG_PAYLOAD = {
    'masters.UnitOfMeasure': UNITS,
    'masters.MasterCategory': MASTER_CATEGORIES,
    'costing.CostElement': COST_ELEMENTS,
    'crm.CustomerGroup': CUSTOMER_GROUPS,
    'crm.SalesChannel': SALES_CHANNELS,
    'finance.ChartOfAccount': CHART_ACCOUNTS,
    'finance.FinancialCategory': FINANCIAL_CATEGORIES,
    'training.JobPosition': JOB_POSITIONS,
    'training.WorkFunction': WORK_FUNCTIONS,
    'training.Competency': COMPETENCIES,
    'fiscal.FiscalUnit': FISCAL_UNITS,
    'fiscal.FiscalOperationCode': CFOPS,
}

COSMETICS_CATALOG_MANIFEST = CatalogManifest(
    identifier='rgn-cosmetics-cross-app-catalogs',
    version='2026.1',
    source_date='2026-09-02',
    source_urls=(
        'https://www.gov.br/inmetro/pt-br/assuntos/metrologia-cientifica/documentos-tecnicos-em-metrologia/si_versao_final.pdf/view',
        'https://www.gov.br/receitafederal/pt-br/acesso-a-informacao/acoes-e-programas/facilitacao/anexo-ecf-cfop',
        'https://legislacao.fazenda.sp.gov.br/Paginas/art597.aspx',
    ),
    namespaces=(
        'UOM-',
        'CAT-COS-',
        'CE-COS-',
        'CG-COS-',
        'SC-COS-',
        'COA-COS-',
        'FC-COS-',
        'JP-COS-',
        'WF-COS-',
        'CPT-COS-',
        'FiscalUnit',
        'CFOP-SINIEF',
    ),
    expected_counts={
        'masters.UnitOfMeasure': 21,
        'masters.MasterCategory': 42,
        'costing.CostElement': 10,
        'crm.CustomerGroup': 5,
        'crm.SalesChannel': 5,
        'finance.ChartOfAccount': 12,
        'finance.FinancialCategory': 6,
        'training.JobPosition': 17,
        'training.WorkFunction': 17,
        'training.Competency': 11,
        'fiscal.FiscalUnit': 11,
        'fiscal.FiscalOperationCode': 12,
    },
    sha256='f57b994b72e311cd6ac5e477c596463cd35e8ab5401891c649bc7d914031a4f4',
    provenance=(
        'Unidades derivadas do Sistema Internacional de Unidades, tradução luso-brasileira Inmetro/IPQ, 2ª edição, 2025.',
        'Taxonomias cosméticas e organizacionais curadas no RGN Cosmetics Catalog 2026.1.',
        'CFOPs descritivos derivados do Anexo ECF/CFOP da Receita Federal e do Convênio SINIEF s/nº de 15 de dezembro de 1970; a seleção exige análise fiscal aplicável.',
    ),
    license_name='Fontes oficiais de acesso público e conteúdo interno proprietário; consultar proveniência',
    license_url='https://github.com/RuiGN/rgnfamarsystemv2',
)
