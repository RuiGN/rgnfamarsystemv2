"""Catálogos mestres curados para a operação cosmética single-instance."""

from auxiliary.cosmetics_seed import ORGANIZATIONAL_ROLES
from reference_data.manifest import CatalogManifest


UNITS = (
    ('1', 'KG', 'kg'),
    ('2', 'G', 'g'),
    ('3', 'MG', 'mg'),
    ('4', 'UG', 'µg'),
    ('5', 'L', 'L'),
    ('6', 'ML', 'mL'),
    ('7', 'UL', 'µL'),
    ('8', 'UN', 'un'),
    ('9', 'PCT', '%'),
    ('10', '°C', '°C'),
    ('11', 'K', 'K'),
    ('12', 'PA', 'Pa'),
    ('13', 'KPA', 'kPa'),
    ('14', 'BAR', 'bar'),
    ('15', 'S', 's'),
    ('16', 'MIN', 'min'),
    ('17', 'H', 'h'),
    ('18', 'M', 'm'),
    ('19', 'CM', 'cm'),
    ('20', 'MM', 'mm'),
    ('21', 'M²', 'm²'),
)

MASTER_CATEGORIES = (
    ('1', 'Higiene pessoal', 'family', None),
    ('2', 'Cuidados capilares', 'family', None),
    ('3', 'Cuidados faciais', 'family', None),
    ('4', 'Cuidados corporais', 'family', None),
    ('5', 'Perfumaria', 'family', None),
    ('6', 'Maquiagem', 'family', None),
    ('7', 'Proteção solar', 'family', None),
    ('8', 'Matérias-primas', 'group', None),
    ('9', 'Materiais de embalagem', 'group', None),
    ('10', 'Produtos semielaborados', 'group', None),
    ('11', 'Produtos acabados', 'group', None),
    ('12', 'Solução', 'cosmetic_form', None),
    ('13', 'Emulsão', 'cosmetic_form', None),
    ('14', 'Gel', 'cosmetic_form', None),
    ('15', 'Suspensão', 'cosmetic_form', None),
    ('16', 'Aerossol', 'cosmetic_form', None),
    ('17', 'Forma anidra', 'cosmetic_form', None),
    ('18', 'Pó', 'cosmetic_form', None),
    ('19', 'Barra', 'cosmetic_form', None),
    ('20', 'Bálsamo', 'cosmetic_form', None),
    ('21', 'Sérum', 'cosmetic_form', None),
    ('22', 'Frasco', 'presentation', None),
    ('23', 'Bisnaga', 'presentation', None),
    ('24', 'Pote', 'presentation', None),
    ('25', 'Sachê', 'presentation', None),
    ('26', 'Frasco com válvula', 'presentation', None),
    ('27', 'Frasco conta-gotas', 'presentation', None),
    ('28', 'Lata aerossol', 'presentation', None),
    ('29', 'Refil', 'presentation', None),
    ('30', 'Percentual massa/massa', 'concentration', None),
    ('31', 'Percentual massa/volume', 'concentration', None),
    ('32', 'Percentual volume/volume', 'concentration', None),
)

COST_ELEMENTS = (
    ('1', 'Materiais diretos', 'material'),
    ('2', 'Perdas de processo', 'loss'),
    ('3', 'Mão de obra direta', 'labor'),
    ('4', 'Hora máquina', 'machine'),
    ('5', 'Serviços de terceiros', 'third_party'),
    ('6', 'Análises laboratoriais', 'analysis'),
    ('7', 'Custos indiretos de fabricação', 'overhead'),
    ('8', 'Custos indiretos administrativos', 'indirect'),
    ('9', 'Tributos', 'tax'),
    ('10', 'Custo da não qualidade', 'non_quality'),
)

CUSTOMER_GROUPS = (
    ('1', 'Varejo especializado', 'Clientes do varejo especializado em cosméticos.'),
    ('2', 'Distribuidores', 'Distribuidores de produtos cosméticos.'),
    ('3', 'Farmácias e drogarias', 'Redes e lojas do canal farma.'),
    ('4', 'Varejo alimentar', 'Supermercados e atacarejos.'),
    ('5', 'Canal profissional', 'Salões, clínicas e profissionais habilitados.'),
)

SALES_CHANNELS = (
    ('1', 'Venda direta', 'direct'),
    ('2', 'Distribuidor', 'distributor'),
    ('3', 'E-commerce', 'ecommerce'),
    ('4', 'Representante comercial', 'representative'),
    ('5', 'Parceiro comercial', 'partner'),
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
    ('1', 'Compras de materiais', 'payable', 'COA-COS-1.1'),
    ('2', 'Serviços de terceiros', 'payable', 'COA-COS-5'),
    ('3', 'Controle da Qualidade', 'payable', 'COA-COS-5.2'),
    ('4', 'Garantia da Qualidade', 'payable', 'COA-COS-5.3'),
    ('5', 'Pesquisa e Desenvolvimento', 'payable', 'COA-COS-5.4'),
    ('6', 'Venda de produtos cosméticos', 'receivable', 'COA-COS-4.1'),
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
        'UOM-NUMERIC',
        'CAT-COS-NUMERIC',
        'CE-COS-NUMERIC',
        'CG-COS-NUMERIC',
        'SC-COS-NUMERIC',
        'COA-COS-',
        'FC-COS-NUMERIC',
        'JP-COS-',
        'WF-COS-',
        'CPT-COS-',
        'FiscalUnit',
        'CFOP-SINIEF',
    ),
    expected_counts={
        'masters.UnitOfMeasure': 21,
        'masters.MasterCategory': 32,
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
    sha256='fed9715c1c008c26a8190b445149e6591d541ce5149a1f708ed80d29a1d5a252',
    provenance=(
        'Unidades derivadas do Sistema Internacional de Unidades, tradução luso-brasileira Inmetro/IPQ, 2ª edição, 2025.',
        'Taxonomias cosméticas e organizacionais curadas no RGN Cosmetics Catalog 2026.1.',
        'CFOPs descritivos derivados do Anexo ECF/CFOP da Receita Federal e do Convênio SINIEF s/nº de 15 de dezembro de 1970; a seleção exige análise fiscal aplicável.',
    ),
    license_name='Fontes oficiais de acesso público e conteúdo interno proprietário; consultar proveniência',
    license_url='https://github.com/RuiGN/rgnfamarsystemv2',
)
