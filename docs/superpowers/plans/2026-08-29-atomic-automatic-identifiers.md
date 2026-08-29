# Atomic Automatic Identifiers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Gerar códigos e identificadores operacionais sem colisões concorrentes, preservando os formatos atuais e centralizando seus metadados nos modelos.

**Architecture:** Criar um contador persistente `IdentifierSequence` e um alocador transacional bloqueado por namespace. Manter `generate_code()` e `sequence_code()` como fachadas compatíveis, declarar identificadores por `IdentifierSpec` nos modelos e consumir essa declaração nas camadas de apresentação.

**Tech Stack:** Python 3.14, Django 6, PostgreSQL, SQLite para testes locais, pytest-django.

## Global Constraints

- Preservar os formatos `PREFIX-NNNN` e `PREFIX-AAAAMMDD-NNNN`.
- Toda mensagem apresentada ao usuário ou operador deve estar em português do Brasil com acentuação.
- Não reutilizar números após exclusões normais.
- Aceitar lacunas; não prometer sequência fiscal estritamente sem lacunas.
- Preservar alterações locais preexistentes.
- Não adicionar suporte implícito a `bulk_create()`.

---

## File Structure

- Modify: `base/models.py` — modelo persistente do contador.
- Modify: `base/sequences.py` — especificação, validação, bootstrap e alocação atômica.
- Modify: `base/automatic_fields.py` — descoberta dos campos declarados nos modelos.
- Modify: `training/models.py` — declaração dos identificadores e unicidade do certificado.
- Modify: modelos operacionais listados em `base/automatic_fields.py` — declaração local dos identificadores.
- Create: `base/migrations/0001_initial.py` — tabela de contadores.
- Create: `training/migrations/0002_*.py` — verificação e constraint condicional do certificado.
- Modify: `tests/test_codegen.py` — regressões do algoritmo e do mixin.
- Modify: `tests/test_automatic_fields.py` — contrato declarativo.
- Create: `tests/test_identifier_sequence_concurrency.py` — contrato PostgreSQL concorrente.
- Modify: `docs/architecture/foundation.md` — comportamento operacional e limitações.

### Task 1: Contrato do alocador

**Files:**
- Modify: `tests/test_codegen.py`
- Create: `tests/test_identifier_sequence_concurrency.py`
- Modify: `base/models.py`
- Modify: `base/sequences.py`

**Interfaces:**
- Produces: `IdentifierSpec`, `allocate_identifier_number()`, `generate_identifier()`, `IdentifierSequence`.
- Preserves: `generate_code()` e `sequence_code()`.

- [ ] Escrever testes que demonstrem bootstrap, continuidade após exclusão, validação de comprimento e `update_fields`.
- [ ] Executar os testes e confirmar falhas causadas pela ausência do novo contrato.
- [ ] Implementar `IdentifierSequence` e o menor alocador transacional que satisfaça os testes.
- [ ] Adaptar as duas fachadas existentes ao alocador sem alterar seus formatos.
- [ ] Executar novamente os testes direcionados e confirmar sucesso.

### Task 2: Metadados declarativos

**Files:**
- Modify: `tests/test_automatic_fields.py`
- Modify: `base/automatic_fields.py`
- Modify: modelos que hoje aparecem em `AUTOMATIC_IDENTIFIER_FIELDS`.

**Interfaces:**
- Consumes: `IdentifierSpec`.
- Produces: atributo de classe `AUTOMATIC_IDENTIFIERS: tuple[IdentifierSpec, ...]`.

- [ ] Escrever testes que exijam a declaração no próprio modelo e eliminem a dependência do mapa central.
- [ ] Executar os testes e confirmar a falha esperada.
- [ ] Adicionar `AUTOMATIC_IDENTIFIERS` aos modelos, incluindo gatilho `approval` no certificado.
- [ ] Fazer `automatic_generated_fields()` derivar os nomes dessas declarações.
- [ ] Executar os testes de formulários, serializers e admin.

### Task 3: Integridade do certificado e migrations

**Files:**
- Modify: `training/models.py`
- Create: `base/migrations/0001_initial.py`
- Create: `training/migrations/0002_*.py`
- Modify: `tests/test_codegen.py`

**Interfaces:**
- Produces: constraint `unique_nonempty_training_certificate_number`.

- [ ] Escrever teste que permita certificados vazios e rejeite número preenchido duplicado.
- [ ] Executar o teste e confirmar a duplicidade atualmente aceita.
- [ ] Adicionar a constraint condicional ao modelo.
- [ ] Gerar migrations e inserir verificação de duplicidades antes da criação da constraint.
- [ ] Executar `makemigrations --check --dry-run` e os testes direcionados.

### Task 4: Documentação e verificação

**Files:**
- Modify: `docs/architecture/foundation.md`

**Interfaces:**
- Documents: formatos, atomicidade, bootstrap, lacunas e restrição de `bulk_create()`.

- [ ] Atualizar a documentação técnica em português.
- [ ] Executar testes direcionados, suíte completa, `manage.py check` e compilação Python.
- [ ] Revisar `git diff --check`, migrations e o diff final sem alterar mudanças preexistentes.
