# Cadastros auxiliares

## Arquitetura single-instance

Este módulo opera em escopo global da instalação local. O acesso é controlado
por autenticação Django e permissões nativas `view`, `add`, `change` e
`delete`, administradas no Django Admin por usuário ou grupo.

As APIs e telas operacionais não exigem cabeçalho de escopo, seleção de empresa
ou vínculo de contrato por cliente. Listagens, formulários, detalhes e ações
usam o mesmo conjunto global de dados da instância.

## Regras de implementação

- Preservar as regras de negócio farmacêuticas do módulo.
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

O comando abaixo carrega, de forma transacional e idempotente, os catálogos
geográficos do IBGE e a lista vigente de moedas ISO 4217 mantida pela SIX:

```bash
python manage.py load_official_reference_data
```

A carga valida a cardinalidade mínima esperada antes de gravar e não remove
cadastros adicionados pelo usuário. Registros preexistentes são reconciliados
pelos identificadores oficiais (`ISO alfa-2/alfa-3`, sigla da UF, código IBGE
do município e código alfabético/numérico da moeda), preservando códigos
internos legados e chaves estrangeiras. Toda a gravação ocorre em uma única
transação; erro de fonte, relacionamento ou validação provoca rollback.

Fontes oficiais:

- IBGE API de Localidades: países, UFs e municípios brasileiros;
- SIX ISO 4217 List One: moedas e fundos correntes.

`--timeout` configura o limite de cada requisição HTTPS entre 1 e 300 segundos.
`--allow-partial` desativa somente a verificação de cardinalidade e deve ser
usado exclusivamente em testes automatizados ou cargas controladas.

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
