# Cadastros auxiliares

## Arquitetura single-instance

Este módulo opera em escopo global da instalação local. O acesso é controlado
por autenticação Django e permissões nativas `view`, `add`, `change` e
`delete`, administradas no Django Admin por usuário ou grupo.

As APIs e telas operacionais não exigem cabeçalho de escopo, seleção de empresa
ou vínculo de contrato por cliente. Listagens, formulários, detalhes e ações
usam o mesmo conjunto global de dados da instância.

## Regras de implementação

- Preservar as regras de negócio da indústria de cosméticos do módulo.
- Validar relacionamentos pelo contexto funcional do domínio, não por escopo
  SaaS herdado.
- Manter trilha de auditoria, logs e justificativas quando aplicável.
- Expor menus e botões somente conforme permissões Django reais.
- Criar migrations consistentes para qualquer alteração de modelo.
- Cobrir novas regras com testes automatizados.

## APIs e UI

Endpoints REST devem usar `IsAuthenticated` e permissões Django de modelo. A UI
operacional em `/app/` deve usar o shell, cards, tabelas, formulários, badges,
modais, paginação e estados do design system.

## Dados oficiais de referência

O comando de produção abaixo carrega, de forma transacional e idempotente, o
snapshot versionado incluído no repositório. Ele não acessa a rede:

```bash
.venv/bin/python manage.py load_official_reference_data
```

O loader valida o SHA-256 canônico, as quatro seções permitidas e as contagens
do manifesto antes de gravar. Os nomes das moedas são localizados para
português do Brasil com o catálogo CLDR fornecido por Babel. Códigos
alfabéticos e numéricos, casas decimais, símbolos conhecidos e a referência à
fonte ISO permanecem preservados.

A carga não remove cadastros adicionados pelo usuário. Localidades legadas são
reconciliadas somente por nome exato e hierarquia exata; apenas códigos
oficiais vazios são preenchidos. Código divergente, código já pertencente a
outro cadastro ou correspondência ambígua aborta sem sobrescrever dados. Toda
a gravação ocorre em uma única transação; erro de integridade, relacionamento
ou validação provoca rollback.

Fontes oficiais:

- IBGE API de Localidades: países, UFs e municípios brasileiros;
- SIX ISO 4217 List One: moedas e fundos correntes.

A atualização das fontes é uma operação online explícita, separada da carga:

```bash
.venv/bin/python manage.py refresh_official_reference_snapshots \
  --version 2026.08.31 \
  --source-date 2026-08-31 \
  --output-dir reference_data/snapshots
```

Somente esse comando possui `--timeout` (entre 1 e 300 segundos). Ele exige
versão, data de corte e diretório de saída, rejeita fontes abaixo das
cardinalidades esperadas e grava JSON UTF-8 determinístico com manifesto e
SHA-256 para revisão antes do commit.

## Referências para indústria cosmética

O catálogo curado em pt-BR preenche áreas, processos, departamentos, funções,
condições comerciais, níveis de impacto, módulos, models e classificações
auxiliares típicas de uma indústria cosmética:

```bash
.venv/bin/python manage.py load_cosmetics_auxiliary_data
```

Para obter primeiro as referências oficiais e em seguida aplicar o catálogo
cosmético, execute:

```bash
.venv/bin/python manage.py load_cosmetics_auxiliary_data --with-official-references
```

A carga é idempotente e identifica o conjunto gerenciado por códigos estáveis.
Ela não apaga registros locais nem grava em outros apps. A carga oficial e a
cosmética possuem transações próprias; qualquer erro de leitura, integridade ou
validação do snapshot oficial interrompe a execução antes do catálogo
cosmético.

## UF e município normalizados

`StateProvince` e `City` são a fonte da verdade para UF e cidade nos cadastros
e registros operacionais. A UI e APIs expõem os campos normalizados com os
labels `UF` e `Cidade`; campos textuais legados de cidade/UF foram removidos
dos recursos operacionais. Integrações fiscais derivam os textos exigidos em
payloads externos a partir de `state_ref` e `city_ref`.

## Verificação mínima

```bash
TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/python manage.py check

TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/pytest -q
```
