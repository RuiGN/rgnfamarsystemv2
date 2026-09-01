# Catálogos de Referência de Produção — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Multi-agent execution is not authorized for this task.

**Goal:** Carregar catálogos oficiais e mestres pt-BR da indústria cosmética de forma offline, versionada, atômica e idempotente.

**Architecture:** Normalizar as chaves oficiais de localização, separar a atualização online dos snapshots da carga de produção e centralizar os catálogos curados em manifestos imutáveis. Um serviço cross-app validará todos os itens antes de aplicar upserts apenas nos models explicitamente autorizados.

**Tech Stack:** Python 3.14, Django 6, PostgreSQL, JSON, SHA-256, pytest-django, APIs oficiais IBGE, ISO 4217/SIX e publicação SI Inmetro 2025.

## Global Constraints

- Criar somente referências e cadastros mestres; nunca dados operacionais ou de demonstração.
- Atualizar registros do namespace reservado e preservar integralmente registros externos ao namespace.
- Não consultar a internet durante o deploy.
- Executar `full_clean()` antes de persistir cada registro gerenciado.
- Aplicar todo o lote relacional em uma única transação atômica.
- Usar nomes e descrições visíveis em português do Brasil com acentuação.
- Não criar registros de backup, produtos, parceiros, plantas, fórmulas, lotes, documentos ou transações.
- Não executar commit, push ou deploy sem autorização explícita do usuário.

## File Map

- `auxiliary/models.py`: chaves oficiais estáveis de país, UF e município.
- `auxiliary/migrations/0003_official_location_codes.py`: evolução relacional das chaves oficiais.
- `reference_data/manifest.py`: manifesto canônico e cálculo de hash.
- `reference_data/snapshots/*.json`: snapshots oficiais usados no deploy.
- `reference_data/cosmetics_catalogs.py`: catálogos curados cross-app.
- `reference_data/loaders.py`: validação e upsert cross-app.
- `auxiliary/reference_snapshots.py`: parsing e aplicação dos snapshots oficiais.
- `auxiliary/management/commands/refresh_official_reference_snapshots.py`: atualização online explícita.
- `auxiliary/management/commands/load_official_reference_data.py`: carga offline de produção.
- `auxiliary/cosmetics_seed.py`: compatibilidade do seeder existente com o serviço unificado.
- `tests/test_official_reference_snapshots.py`: snapshots, hashes e atomicidade.
- `tests/test_production_reference_catalogs.py`: conteúdo, escopo e idempotência cross-app.

---

### Task 1: Persistir chaves oficiais de localização

**Files:**
- Modify: `auxiliary/models.py`
- Create: `auxiliary/migrations/0003_official_location_codes.py`
- Modify: `tests/test_auxiliary_reference_data.py`
- Modify: `auxiliary/admin.py`

**Interfaces:**
- Produces: `Country.iso_alpha2`, `Country.iso_alpha3`, `Country.numeric_code`, `StateProvince.abbreviation`, `StateProvince.ibge_code` e `City.ibge_code`.
- Consumes: os identificadores já presentes nas respostas oficiais do IBGE.

- [ ] **Step 1: Escrever o teste falho das chaves oficiais**

Adicionar ao teste de carga existente:

```python
assert brazil.iso_alpha2 == 'BR'
assert brazil.iso_alpha3 == 'BRA'
assert brazil.numeric_code == '076'
assert pernambuco.abbreviation == 'PE'
assert pernambuco.ibge_code == '26'
assert recife.ibge_code == '2611606'
```

Adicionar um teste de unicidade:

```python
def test_official_location_codes_are_unique_when_present():
    Country.objects.create(
        name='Brasil', iso_alpha2='BR', iso_alpha3='BRA', numeric_code='076'
    )
    with pytest.raises(IntegrityError):
        Country.objects.create(name='Brasil duplicado', iso_alpha2='BR')
```

- [ ] **Step 2: Executar RED**

Run: `TEST_DATABASE_URL="$TEST_DATABASE_URL" .venv/bin/python -m pytest tests/test_auxiliary_reference_data.py -q`

Expected: FAIL com `AttributeError`/`TypeError` porque os campos oficiais ainda não existem.

- [ ] **Step 3: Adicionar os campos e constraints condicionais**

Adicionar aos models:

```python
class Country(models.Model):
    name = models.CharField('nome', max_length=180, unique=True)
    iso_alpha2 = models.CharField('ISO alfa-2', max_length=2, blank=True)
    iso_alpha3 = models.CharField('ISO alfa-3', max_length=3, blank=True)
    numeric_code = models.CharField('código numérico', max_length=3, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['iso_alpha2'],
                condition=~models.Q(iso_alpha2=''),
                name='unique_country_iso_alpha2',
            ),
            models.UniqueConstraint(
                fields=['iso_alpha3'],
                condition=~models.Q(iso_alpha3=''),
                name='unique_country_iso_alpha3',
            ),
            models.UniqueConstraint(
                fields=['numeric_code'],
                condition=~models.Q(numeric_code=''),
                name='unique_country_numeric_code',
            ),
        ]


class StateProvince(models.Model):
    name = models.CharField('nome', max_length=180)
    abbreviation = models.CharField('sigla', max_length=2, blank=True)
    ibge_code = models.CharField('código IBGE', max_length=2, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['country', 'abbreviation'],
                condition=~models.Q(abbreviation=''),
                name='unique_state_country_abbreviation',
            ),
            models.UniqueConstraint(
                fields=['ibge_code'],
                condition=~models.Q(ibge_code=''),
                name='unique_state_ibge_code',
            ),
        ]


class City(models.Model):
    name = models.CharField('nome', max_length=180)
    ibge_code = models.CharField('código IBGE', max_length=7, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['ibge_code'],
                condition=~models.Q(ibge_code=''),
                name='unique_city_ibge_code',
            ),
        ]
```

Preservar os `ordering`, índices e verbose names existentes. Exibir as novas chaves em `CountryAdmin`, `StateProvinceAdmin` e `CityAdmin`.

- [ ] **Step 4: Gerar e revisar a migration**

Run: `.venv/bin/python manage.py makemigrations auxiliary --name official_location_codes`

Expected: uma migration com seis `AddField` e seis `AddConstraint`, sem operações em outros apps.

- [ ] **Step 5: Atualizar o parser/upsert existente**

Em `_parse_countries`, produzir:

```python
identifier = item.get('id') or {}
alpha2 = str(identifier.get('ISO-ALPHA-2') or '').strip().upper()
alpha3 = str(identifier.get('ISO-ALPHA-3') or '').strip().upper()
numeric = str(identifier.get('M49') or '').strip()
countries[name] = {
    'name': name,
    'iso_alpha2': alpha2,
    'iso_alpha3': alpha3,
    'numeric_code': numeric.zfill(3) if numeric else '',
}
```

Nos parsers de UF e município, manter `numeric_code`/`ibge_code` e usar essas chaves no upsert. Registros legados sem código serão reaproveitados por nome e terão a chave oficial preenchida.

- [ ] **Step 6: Executar GREEN e checks de migration**

Run: `TEST_DATABASE_URL="$TEST_DATABASE_URL" .venv/bin/python -m pytest tests/test_auxiliary_reference_data.py tests/test_normalized_locations.py -q`

Run: `.venv/bin/python manage.py makemigrations --check --dry-run`

Expected: testes PASS e `No changes detected`.

- [ ] **Step 7: Checkpoint de revisão**

Revisar `git diff -- auxiliary/models.py auxiliary/admin.py auxiliary/migrations/0002_official_location_codes.py tests/test_auxiliary_reference_data.py`. Não criar commit sem autorização.

### Task 2: Separar atualização online da carga offline

**Files:**
- Create: `reference_data/__init__.py`
- Create: `reference_data/manifest.py`
- Create: `reference_data/snapshots/official_references.json`
- Create: `reference_data/snapshots/official_references.manifest.json`
- Create: `auxiliary/reference_snapshots.py`
- Create: `auxiliary/management/commands/refresh_official_reference_snapshots.py`
- Modify: `auxiliary/management/commands/load_official_reference_data.py`
- Create: `tests/test_official_reference_snapshots.py`

**Interfaces:**
- Produces: `load_official_snapshot(path: Path | None = None) -> OfficialReferenceSnapshot` e `apply_official_snapshot(snapshot) -> dict[str, int]`.
- Produces: `CatalogManifest.canonical_hash() -> str`.
- Consumes: JSON determinístico gerado a partir do IBGE e ISO 4217/SIX.

- [ ] **Step 1: Escrever testes falhos para hash e carga offline**

Criar testes que montem um snapshot temporário e bloqueiem rede:

```python
def test_official_loader_uses_committed_snapshot_without_network(tmp_path, monkeypatch):
    snapshot_path, manifest_path = write_minimal_snapshot(tmp_path)
    monkeypatch.setattr(requests, 'get', Mock(side_effect=AssertionError('rede proibida')))

    result = load_official_snapshot(snapshot_path, manifest_path)
    counts = apply_official_snapshot(result)

    assert counts == {'countries': 1, 'states': 1, 'cities': 2, 'currencies': 2}
    assert City.objects.get(ibge_code='2611606').name == 'Recife'


def test_snapshot_rejects_manifest_hash_mismatch(tmp_path):
    snapshot_path, manifest_path = write_minimal_snapshot(tmp_path)
    snapshot_path.write_text('{}', encoding='utf-8')

    with pytest.raises(CommandError, match='SHA-256'):
        load_official_snapshot(snapshot_path, manifest_path)
```

- [ ] **Step 2: Executar RED**

Run: `TEST_DATABASE_URL="$TEST_DATABASE_URL" .venv/bin/python -m pytest tests/test_official_reference_snapshots.py -q`

Expected: ERROR de importação porque `reference_data.manifest` e `auxiliary.reference_snapshots` não existem.

- [ ] **Step 3: Implementar manifesto canônico**

Criar:

```python
from dataclasses import dataclass
import hashlib
import json


def canonical_json(payload) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(',', ':'),
    )


def payload_hash(payload) -> str:
    return hashlib.sha256(canonical_json(payload).encode('utf-8')).hexdigest()


@dataclass(frozen=True)
class CatalogManifest:
    identifier: str
    version: str
    source_date: str
    source_urls: tuple[str, ...]
    namespaces: tuple[str, ...]
    expected_counts: dict[str, int]
    sha256: str

    def validate_payload(self, payload) -> None:
        if payload_hash(payload) != self.sha256:
            raise ValueError('O SHA-256 do snapshot oficial não corresponde ao manifesto.')
```

- [ ] **Step 4: Implementar leitura e aplicação offline**

Definir `OfficialReferenceSnapshot` com `manifest` e `payload`. A leitura deve validar:

```python
required_sections = {'countries', 'states', 'cities', 'currencies'}
if set(payload) != required_sections:
    raise CommandError('Snapshot oficial possui seções ausentes ou inesperadas.')
manifest.validate_payload(payload)
for section, expected in manifest.expected_counts.items():
    if len(payload[section]) != expected:
        raise CommandError(f'Contagem divergente no snapshot: {section}.')
```

Aplicar em `transaction.atomic()` usando códigos oficiais como lookup e fallback por nome apenas para reaproveitar registros legados.

- [ ] **Step 5: Transformar o comando atual em atualizador explícito**

Mover download/parsing HTTP para `refresh_official_reference_snapshots`. O comando deve:

```python
payload = command.fetch_and_parse(timeout=options['timeout'])
manifest = build_manifest(
    identifier='official-references-br',
    version=options['version'],
    source_date=options['source_date'],
    source_urls=(IBGE_COUNTRIES_URL, IBGE_STATES_URL, IBGE_CITIES_URL, ISO_CURRENCIES_URL),
    namespaces=('ISO-3166', 'IBGE-LOCALIDADES', 'ISO-4217'),
    payload=payload,
)
write_snapshot(snapshot_path, manifest_path, payload, manifest)
```

Exigir `--version`, `--source-date`, `--output-dir` e timeout entre 1 e 300 segundos. Gravar JSON com UTF-8, chaves ordenadas e newline final.

- [ ] **Step 6: Fazer `load_official_reference_data` consumir somente o snapshot**

O `handle()` passa a executar:

```python
snapshot = load_official_snapshot()
counts = apply_official_snapshot(snapshot)
self.stdout.write(
    self.style.SUCCESS(
        'Carga oficial versionada concluída: '
        + ', '.join(f'{key}={value}' for key, value in counts.items())
        + f'; versão={snapshot.manifest.version}; sha256={snapshot.manifest.sha256}.'
    )
)
```

Remover opções de download do comando de produção. Manter download apenas no comando `refresh_*`.

- [ ] **Step 7: Gerar o snapshot oficial inicial**

Run: `.venv/bin/python manage.py refresh_official_reference_snapshots --version 2026.08.31 --source-date 2026-08-31 --output-dir reference_data/snapshots`

Expected: snapshot com pelo menos 190 países, exatamente 27 UFs, pelo menos 5.500 municípios e pelo menos 150 moedas; manifesto com SHA-256 válido.

- [ ] **Step 8: Executar GREEN**

Run: `TEST_DATABASE_URL="$TEST_DATABASE_URL" .venv/bin/python -m pytest tests/test_official_reference_snapshots.py tests/test_auxiliary_reference_data.py -q`

Expected: PASS sem chamadas de rede durante `load_official_reference_data`.

- [ ] **Step 9: Checkpoint de revisão**

Revisar tamanhos, fontes, hash e diff gerado. Confirmar que o snapshot não contém dados pessoais nem campos além dos quatro catálogos aprovados.

### Task 3: Criar os catálogos mestres cross-app

**Files:**
- Create: `reference_data/cosmetics_catalogs.py`
- Create: `reference_data/loaders.py`
- Create: `tests/test_production_reference_catalogs.py`

**Interfaces:**
- Produces: `COSMETICS_CATALOG_MANIFEST: CatalogManifest`.
- Produces: `validate_catalogs() -> None` e `apply_catalogs() -> dict[str, dict[str, int]]`.
- Consumes: códigos `BA-COS-*`, `BPC-COS-*` e `DEP-COS-*` já criados pelo seeder auxiliar.

- [ ] **Step 1: Escrever os testes falhos do escopo e conteúdo**

```python
@pytest.mark.django_db
def test_catalogs_create_real_pt_br_reference_data_without_transactions():
    seed_cosmetics_auxiliary_data()
    result = apply_catalogs()

    assert UnitOfMeasure.objects.get(code='UOM-KG').name == 'Kilograma'
    assert UnitOfMeasure.objects.get(code='UOM-ML').symbol == 'mL'
    assert MasterCategory.objects.get(code='CAT-COS-FORM-EMULSAO').name == 'Emulsão'
    assert CostElement.objects.get(code='CE-COS-NQ').name == 'Custo da não qualidade'
    assert SalesChannel.objects.get(code='SC-COS-ECOM').name == 'E-commerce'
    assert FinancialCategory.objects.get(code='FC-COS-CQ').name == 'Controle da Qualidade'
    assert Competency.objects.get(code='CPT-COS-BPF').name == 'Boas Práticas de Fabricação'
    assert FiscalUnit.objects.get(code='KG').description == 'Kilograma'
    assert FiscalOperationCode.objects.get(code='5101').direction == 'outbound'
    assert result['masters.UnitOfMeasure']['managed'] >= 20
    assert Product.objects.count() == 0
    assert BusinessPartner.objects.count() == 0
    assert StockLot.objects.count() == 0


@pytest.mark.django_db
def test_catalogs_overwrite_managed_and_preserve_local_records():
    UnitOfMeasure.objects.create(code='UOM-KG', name='Nome incorreto', symbol='x')
    UnitOfMeasure.objects.create(code='LOCAL-BOMBONA', name='Bombona local', symbol='bb')

    apply_catalogs()
    first_counts = catalog_model_counts()
    apply_catalogs()

    assert UnitOfMeasure.objects.get(code='UOM-KG').name == 'Kilograma'
    assert UnitOfMeasure.objects.get(code='LOCAL-BOMBONA').name == 'Bombona local'
    assert catalog_model_counts() == first_counts
```

- [ ] **Step 2: Executar RED**

Run: `TEST_DATABASE_URL="$TEST_DATABASE_URL" .venv/bin/python -m pytest tests/test_production_reference_catalogs.py -q`

Expected: ERROR de importação porque os catálogos cross-app ainda não existem.

- [ ] **Step 3: Declarar unidades e taxonomia mestre**

Usar estes dados canônicos:

```python
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
```

O manifesto deve citar `Sistema Internacional de Unidades (SI), Inmetro/IPQ, 2ª edição da tradução luso-brasileira, 2025` para unidades e `RGN Cosmetics Catalog 2026.1` para a taxonomia curada.

- [ ] **Step 4: Declarar catálogos dos demais domínios**

```python
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
```

Adicionar cargos/funções ligados aos códigos auxiliares e competências:

```python
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
```

Os `JOB_POSITIONS` e `WORK_FUNCTIONS` devem reutilizar exatamente os 17 cargos/funções já declarados em `ORGANIZATIONAL_ROLES`, resolvendo `area_ref`, `department_ref` e `process_ref` pelos códigos `BA-COS-*`, `DEP-COS-*` e `BPC-COS-*` correspondentes.

Adicionar referências fiscais sem inferir tributação do produto:

```python
FISCAL_UNITS = (
    ('UN', 'Unidade'), ('KG', 'Kilograma'), ('G', 'Grama'),
    ('MG', 'Miligrama'), ('L', 'Litro'), ('ML', 'Mililitro'),
    ('CX', 'Caixa'), ('FR', 'Frasco'), ('TB', 'Bisnaga'),
    ('PT', 'Pote'), ('FD', 'Fardo'),
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
```

O manifesto fiscal deve registrar o Convênio SINIEF e as páginas oficiais de
referência da Receita Federal/SEFAZ usadas para revisar o snapshot. A descrição
canônica é igual em pares como 1101/2101 e 5101/6101; a origem/destino da
operação é expressa pelo primeiro dígito do código, não por texto acrescentado.
Advertir que a seleção do código de uma operação continua dependendo da análise
fiscal aplicável.

- [ ] **Step 5: Implementar loader explícito por model**

Criar um `upsert_validated(model, lookup, values)` que:

```python
instance = model.objects.filter(**lookup).first()
created = instance is None
instance = instance or model(**lookup)
changed = created
for name, value in values.items():
    if getattr(instance, name) != value:
        setattr(instance, name, value)
        changed = True
if hasattr(instance, 'is_active') and not instance.is_active:
    instance.is_active = True
    changed = True
instance.full_clean()
if changed:
    instance.save()
return 'created' if created else ('updated' if changed else 'unchanged')
```

Resolver pais antes de filhos e relações por código; falhar com `ValidationError` se uma dependência não existir.

- [ ] **Step 6: Validar todos os itens antes da primeira escrita**

`validate_catalogs()` deve conferir códigos duplicados, values fora dos `TextChoices`, parents inexistentes, relações auxiliares inexistentes e prefixos reservados. Em `apply_catalogs()`, chamar validação primeiro e executar todos os loaders sob `transaction.atomic()`.

- [ ] **Step 7: Executar GREEN**

Run: `TEST_DATABASE_URL="$TEST_DATABASE_URL" .venv/bin/python -m pytest tests/test_production_reference_catalogs.py tests/test_cosmetics_auxiliary_data.py -q`

Expected: PASS com idempotência e ausência de registros transacionais.

- [ ] **Step 8: Checkpoint de revisão**

Revisar códigos, rótulos pt-BR, choices, relações e fontes. Confirmar que nenhum NCM, CST/CSOSN ou regra tributária foi criado sem definição fiscal específica.

### Task 4: Unificar a carga e provar atomicidade do lote

**Files:**
- Modify: `auxiliary/cosmetics_seed.py`
- Modify: `auxiliary/management/commands/load_cosmetics_auxiliary_data.py`
- Create: `reference_data/services.py`
- Modify: `tests/test_production_reference_catalogs.py`
- Modify: `docs/architecture/auxiliary.md`
- Modify: `docs/architecture/master-data.md`
- Modify: `docs/deployment.md`

**Interfaces:**
- Produces: `seed_production_reference_data() -> ReferenceDataResult`.
- `ReferenceDataResult` contém `manifest_hashes: dict[str, str]` e `counts: dict[str, dict[str, int]]`.

- [ ] **Step 1: Escrever teste falho da transação global**

```python
@pytest.mark.django_db(transaction=True)
def test_global_reference_load_rolls_back_every_domain(monkeypatch):
    monkeypatch.setattr(
        reference_data.loaders,
        'FISCAL_UNITS',
        (*FISCAL_UNITS, ('CODIGO-MAIOR-QUE-VINTE', 'Inválida')),
    )

    with pytest.raises(ValidationError):
        seed_production_reference_data()

    assert BusinessArea.objects.count() == 0
    assert UnitOfMeasure.objects.count() == 0
    assert CostElement.objects.count() == 0
    assert FiscalUnit.objects.count() == 0
```

- [ ] **Step 2: Executar RED**

Run: `TEST_DATABASE_URL="$TEST_DATABASE_URL" .venv/bin/python -m pytest tests/test_production_reference_catalogs.py::test_global_reference_load_rolls_back_every_domain -q`

Expected: FAIL porque o serviço unificado não existe.

- [ ] **Step 3: Implementar serviço transacional**

```python
@dataclass(frozen=True)
class ReferenceDataResult:
    manifest_hashes: dict[str, str]
    counts: dict[str, dict[str, int]]


@transaction.atomic
def seed_production_reference_data() -> ReferenceDataResult:
    official = load_official_snapshot()
    validate_catalogs()
    official_counts = apply_official_snapshot(official, use_current_transaction=True)
    auxiliary_counts = seed_cosmetics_auxiliary_data()
    domain_counts = apply_catalogs(use_current_transaction=True)
    return ReferenceDataResult(
        manifest_hashes={
            official.manifest.identifier: official.manifest.sha256,
            COSMETICS_CATALOG_MANIFEST.identifier: COSMETICS_CATALOG_MANIFEST.sha256,
        },
        counts={
            'official': normalize_counts(official_counts),
            'auxiliary': normalize_counts(auxiliary_counts),
            **domain_counts,
        },
    )
```

Os métodos internos não devem abrir `durable=True`; nested `atomic()` comuns são permitidos.

- [ ] **Step 4: Atualizar o comando compatível**

`load_cosmetics_auxiliary_data` passa a aceitar `--production-catalogs`. Sem a flag, preserva a carga auxiliar atual; com a flag, chama `seed_production_reference_data()` e imprime somente versões, hashes abreviados e contagens, nunca valores de ambiente.

- [ ] **Step 5: Atualizar documentação**

Documentar:

```text
python manage.py load_cosmetics_auxiliary_data --production-catalogs
```

Explicar namespace gerenciado, atualização de snapshots fora do deploy, fontes e exclusões operacionais.

- [ ] **Step 6: Executar o gate focado**

Run: `TEST_DATABASE_URL="$TEST_DATABASE_URL" .venv/bin/python -m pytest tests/test_official_reference_snapshots.py tests/test_auxiliary_reference_data.py tests/test_cosmetics_auxiliary_data.py tests/test_production_reference_catalogs.py tests/test_master_data.py tests/test_costing_migrations.py tests/test_crm.py tests/test_finance.py tests/test_fiscal.py tests/test_training.py -q`

Run: `.venv/bin/python -m ruff check reference_data auxiliary tests/test_official_reference_snapshots.py tests/test_production_reference_catalogs.py`

Run: `.venv/bin/python manage.py check`

Run: `.venv/bin/python manage.py makemigrations --check --dry-run`

Expected: todos os comandos terminam com código 0.

- [ ] **Step 7: Checkpoint de revisão do plano A**

Conferir o diff restrito aos arquivos listados neste plano, registrar resultados frescos e não fazer commit sem autorização explícita.
