# Local Test PostgreSQL Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Disponibilizar um comando único e reproduzível que execute a suíte Django local contra um PostgreSQL 15 isolado.

**Architecture:** Um Compose dedicado publicará apenas um PostgreSQL de testes em `127.0.0.1:5433`, com volume e projeto isolados. Um script Bash defensivo controlará o serviço, aguardará o healthcheck, definirá as URLs do banco somente para o processo de pytest e preservará seu código de saída.

**Tech Stack:** Docker Compose, PostgreSQL 15, Bash, Django 5.2, pytest, pytest-django, PyYAML.

## Global Constraints

- Manter PostgreSQL obrigatório; nenhum fallback para SQLite.
- Não carregar `.env` no executor de testes.
- Não reutilizar banco, porta padrão, serviço ou volume do ambiente de desenvolvimento.
- Publicar o banco somente em `127.0.0.1`.
- Usar porta `5433` por padrão e aceitar `TEST_POSTGRES_PORT`.
- Preservar `pytest --reuse-db` mantendo o container e o volume após a execução.
- Não modificar a alteração preexistente em `base/ui/forms.py`.
- Não corrigir Ruff ou Bandit nesta implementação.

---

### Task 1: Contrato do ambiente de testes

**Files:**
- Create: `tests/test_local_test_environment.py`
- Create: `docker-compose.test.yml`
- Create: `scripts/test.sh`

**Interfaces:**
- Consumes: Docker Compose v2 e `.venv/bin/python`.
- Produces: serviço Compose `postgres_test`; volume `postgres_test_data`; comando `bash scripts/test.sh [pytest args...]`.

- [ ] **Step 1: Escrever o teste de contrato inicialmente falho**

Criar `tests/test_local_test_environment.py`:

```python
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
COMPOSE_PATH = ROOT / "docker-compose.test.yml"
SCRIPT_PATH = ROOT / "scripts" / "test.sh"


def test_test_compose_isolates_postgresql_on_loopback():
    compose = yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))
    service = compose["services"]["postgres_test"]

    assert compose["name"] == "rgnfarmasystem-test"
    assert service["image"] == "postgres:15-alpine"
    assert service["ports"] == ["127.0.0.1:${TEST_POSTGRES_PORT:-5433}:5432"]
    assert service["environment"] == {
        "POSTGRES_DB": "rgn_test",
        "POSTGRES_USER": "rgn_test",
        "POSTGRES_PASSWORD": "rgn_test",
    }
    assert service["volumes"] == ["postgres_test_data:/var/lib/postgresql/data"]
    assert service["healthcheck"]["test"] == [
        "CMD-SHELL",
        "pg_isready -U rgn_test -d rgn_test",
    ]
    assert "postgres_test_data" in compose["volumes"]


def test_test_script_starts_waits_and_runs_pytest_safely():
    source = SCRIPT_PATH.read_text(encoding="utf-8")

    assert "set -Eeuo pipefail" in source
    assert 'COMPOSE_FILE="$ROOT_DIR/docker-compose.test.yml"' in source
    assert 'docker compose -f "$COMPOSE_FILE" up -d --wait postgres_test' in source
    assert "postgresql://rgn_test:rgn_test@127.0.0.1:${TEST_POSTGRES_PORT}/rgn_test" in source
    assert 'export TEST_DATABASE_URL="$TEST_DATABASE_URL"' in source
    assert 'export DATABASE_URL="$TEST_DATABASE_URL"' in source
    assert 'exec "$PYTHON" -m pytest "$@"' in source
    assert "source .env" not in source
    assert SCRIPT_PATH.stat().st_mode & 0o111
```

- [ ] **Step 2: Executar o teste e confirmar RED**

Run: `.venv/bin/python -m pytest tests/test_local_test_environment.py -q`

Expected: FAIL porque `docker-compose.test.yml` e `scripts/test.sh` não existem.

- [ ] **Step 3: Criar o Compose mínimo**

Criar `docker-compose.test.yml`:

```yaml
name: rgnfarmasystem-test

services:
  postgres_test:
    image: postgres:15-alpine
    restart: unless-stopped
    ports:
      - "127.0.0.1:${TEST_POSTGRES_PORT:-5433}:5432"
    environment:
      POSTGRES_DB: rgn_test
      POSTGRES_USER: rgn_test
      POSTGRES_PASSWORD: rgn_test
    volumes:
      - postgres_test_data:/var/lib/postgresql/data
    healthcheck:
      test: [CMD-SHELL, pg_isready -U rgn_test -d rgn_test]
      interval: 2s
      timeout: 5s
      retries: 30

volumes:
  postgres_test_data:
```

- [ ] **Step 4: Criar o executor mínimo**

Criar `scripts/test.sh` e marcá-lo como executável:

```bash
#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
COMPOSE_FILE="$ROOT_DIR/docker-compose.test.yml"
PYTHON="$ROOT_DIR/.venv/bin/python"
TEST_POSTGRES_PORT=${TEST_POSTGRES_PORT:-5433}
TEST_DATABASE_URL="postgresql://rgn_test:rgn_test@127.0.0.1:${TEST_POSTGRES_PORT}/rgn_test"

command -v docker >/dev/null 2>&1 || {
  echo "Erro: Docker não encontrado." >&2
  exit 127
}
docker compose version >/dev/null 2>&1 || {
  echo "Erro: Docker Compose v2 não está disponível." >&2
  exit 127
}
[[ -x "$PYTHON" ]] || {
  echo "Erro: virtualenv não encontrada em $PYTHON." >&2
  exit 127
}

export TEST_POSTGRES_PORT
docker compose -f "$COMPOSE_FILE" up -d --wait postgres_test

export TEST_DATABASE_URL="$TEST_DATABASE_URL"
export DATABASE_URL="$TEST_DATABASE_URL"
cd "$ROOT_DIR"
exec "$PYTHON" -m pytest "$@"
```

Run: `chmod +x scripts/test.sh`

- [ ] **Step 5: Executar o teste e confirmar GREEN**

Run: `.venv/bin/python -m pytest tests/test_local_test_environment.py -q`

Expected: `2 passed`.

- [ ] **Step 6: Validar sintaxe e configuração renderizada**

Run: `bash -n scripts/test.sh`

Expected: exit `0`, sem saída.

Run: `TEST_POSTGRES_PORT=55433 docker compose -f docker-compose.test.yml config`

Expected: configuração válida com bind `127.0.0.1:55433` e serviço `postgres_test`.

- [ ] **Step 7: Commit do contrato e implementação**

```bash
git add tests/test_local_test_environment.py docker-compose.test.yml scripts/test.sh
git commit -m "test: add isolated local PostgreSQL runner"
```

---

### Task 2: Documentação operacional

**Files:**
- Modify: `tests/test_local_test_environment.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: `bash scripts/test.sh [pytest args...]` e `docker-compose.test.yml` da Task 1.
- Produces: instruções oficiais para suíte integral, teste seletivo e limpeza explícita.

- [ ] **Step 1: Escrever o teste documental inicialmente falho**

Adicionar a `tests/test_local_test_environment.py`:

```python
def test_readme_documents_isolated_test_workflow():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "## Testes automatizados" in readme
    assert "bash scripts/test.sh" in readme
    assert "bash scripts/test.sh tests/test_foundation.py -q" in readme
    assert "docker compose -f docker-compose.test.yml down -v" in readme
    assert "TEST_POSTGRES_PORT=55433 bash scripts/test.sh" in readme
```

- [ ] **Step 2: Executar o teste e confirmar RED**

Run: `.venv/bin/python -m pytest tests/test_local_test_environment.py::test_readme_documents_isolated_test_workflow -q`

Expected: FAIL porque a seção `Testes automatizados` ainda não contém o contrato.

- [ ] **Step 3: Adicionar a documentação mínima ao README**

Adicionar após “Ambiente local” em `README.md`:

````markdown
## Testes automatizados

A suíte usa um PostgreSQL 15 isolado em `127.0.0.1:5433`. Docker, Docker
Compose v2 e a virtualenv `.venv` devem estar disponíveis.

```bash
bash scripts/test.sh
```

Para executar somente parte da suíte, passe os argumentos diretamente ao
pytest:

```bash
bash scripts/test.sh tests/test_foundation.py -q
```

Se a porta `5433` estiver ocupada, escolha outra porta:

```bash
TEST_POSTGRES_PORT=55433 bash scripts/test.sh
```

O banco permanece ativo para acelerar execuções posteriores com `--reuse-db`.
Para removê-lo, incluindo o volume isolado:

```bash
docker compose -f docker-compose.test.yml down -v
```
````

- [ ] **Step 4: Executar os testes de contrato**

Run: `.venv/bin/python -m pytest tests/test_local_test_environment.py -q`

Expected: `3 passed`.

- [ ] **Step 5: Commit da documentação**

```bash
git add README.md tests/test_local_test_environment.py
git commit -m "docs: document isolated local test workflow"
```

---

### Task 3: Validação operacional e quality gate

**Files:**
- Verify: `docker-compose.test.yml`
- Verify: `scripts/test.sh`
- Verify: `tests/`
- Produces: `coverage.xml` (artefato ignorado pelo Git, se configurado assim).

**Interfaces:**
- Consumes: executor local completo das Tasks 1 e 2.
- Produces: evidência dos testes, migrations, cobertura e eventuais falhas reais.

- [ ] **Step 1: Confirmar isolamento da configuração Django**

Run: `bash scripts/test.sh tests/test_settings_profiles.py tests/test_foundation.py -q`

Expected: todos os testes selecionados passam usando vendor PostgreSQL.

- [ ] **Step 2: Verificar integridade Django e migrations no banco isolado**

Run:

```bash
TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test \
DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test \
DJANGO_SETTINGS_MODULE=core.settings.test \
.venv/bin/python manage.py check
```

Expected: `System check identified no issues`.

Run:

```bash
TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test \
DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test \
DJANGO_SETTINGS_MODULE=core.settings.test \
.venv/bin/python manage.py makemigrations --check --dry-run
```

Expected: `No changes detected`.

- [ ] **Step 3: Executar a suíte integral**

Run: `bash scripts/test.sh -q`

Expected: `456 passed` ou nova contagem superior, zero falhas e exit `0`.

- [ ] **Step 4: Executar a cobertura equivalente ao CI**

Run: `bash scripts/test.sh --cov=. --cov-report=term-missing --cov-report=xml --cov-fail-under=80`

Expected: zero falhas, cobertura total mínima de 80% e `coverage.xml` gerado.

- [ ] **Step 5: Executar validações finais do artefato**

Run: `.venv/bin/ruff check tests/test_local_test_environment.py`

Expected: `All checks passed!`.

Run: `git diff --check -- docker-compose.test.yml scripts/test.sh tests/test_local_test_environment.py README.md`

Expected: exit `0`, sem saída.

Run: `git status --short`

Expected: nenhuma alteração inesperada; `base/ui/forms.py` pode continuar modificado pelo usuário.

- [ ] **Step 6: Registrar falhas reais sem mascará-las**

Se qualquer teste funcional ou o limite de cobertura falhar, não alterar o
executor para contornar o resultado. Registrar o nome do teste, traceback e
percentual obtido; correções funcionais devem receber planos TDD separados.

- [ ] **Step 7: Commit apenas se a validação gerar ajuste necessário**

Se nenhum arquivo versionado mudar, não criar commit vazio. Se houver ajuste no
executor ou documentação, repetir os testes de contrato e então executar:

```bash
git add docker-compose.test.yml scripts/test.sh tests/test_local_test_environment.py README.md
git commit -m "fix: complete local test database validation"
```
