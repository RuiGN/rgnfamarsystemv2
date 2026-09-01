# Cloudflared Metrics Port Isolation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tornar a porta local de métricas/readiness do Cloudflare Tunnel configurável e usar `20242` por padrão sem interferir em outros produtos da VPS.

**Architecture:** O dotenv fornece `TUNNEL_METRICS_PORT`; o Compose interpola a porta em `--metrics`, e o script de deploy lê e valida a mesma chave antes de montar a URL `/ready`. O avaliador operacional e os testes verificam que ambos permanecem alinhados e vinculados ao loopback.

**Tech Stack:** Docker Compose, Bash, cloudflared, Python 3.14, pytest, PyYAML.

## Global Constraints

- Preservar todos os containers, serviços e volumes de outros produtos.
- Manter o servidor de métricas em `127.0.0.1`.
- Usar `TUNNEL_METRICS_PORT=20242` como padrão.
- Nunca executar o `.env` com `source` nem imprimir seus valores.
- Não considerar o deploy concluído sem `/ready`, origem e domínio público em HTTP 200.

---

### Task 1: Contrato configurável de porta e readiness

**Files:**
- Modify: `tests/test_vps_compose_contract.py`
- Modify: `tests/test_operational_readiness.py`
- Modify: `tests/test_native_postgres_deployment.py`
- Modify: `docker-compose.vps.yml`
- Modify: `scripts/deploy-vps.sh`
- Modify: `core/operational_readiness.py`
- Modify: `.env.example`

**Interfaces:**
- Consumes: `read_env_value(key: str)` do script de deploy.
- Produces: `configure_tunnel_readiness()` e a variável exportada `TUNNEL_METRICS_PORT`.

- [x] **Step 1: Escrever testes falhando para o novo contrato**

Atualizar as asserções YAML para exigir:

```python
assert '127.0.0.1:${TUNNEL_METRICS_PORT:-20242}' in tunnel['command']
assert 'TUNNEL_METRICS_PORT=20242' in (ROOT / '.env.example').read_text(encoding='utf-8')
```

Adicionar um teste que carregue somente as funções do script e rejeite uma
porta fora do intervalo:

```python
def test_deploy_rejects_invalid_tunnel_metrics_port(tmp_path):
    env_file = tmp_path / '.env'
    env_file.write_text('TUNNEL_METRICS_PORT=70000\n', encoding='utf-8')
    result = subprocess.run(
        [
            'bash', '-c',
            'source <(sed \'$d\' "$1"); ENV_FILE="$2"; configure_tunnel_readiness',
            'bash', ROOT / 'scripts' / 'deploy-vps.sh', env_file,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert 'TUNNEL_METRICS_PORT invalida' in result.stderr
```

- [x] **Step 2: Executar os testes e comprovar a falha esperada**

Run:

```bash
bash scripts/test.sh tests/test_vps_compose_contract.py tests/test_operational_readiness.py tests/test_native_postgres_deployment.py -q
```

Expected: falhas por ainda existir `20241`, ausência da variável no exemplo e
ausência de `configure_tunnel_readiness`.

- [x] **Step 3: Implementar a configuração mínima**

No Compose:

```yaml
command:
  ["tunnel", "--no-autoupdate", "--metrics", "127.0.0.1:${TUNNEL_METRICS_PORT:-20242}", "run"]
```

No script:

```bash
configure_tunnel_readiness() {
  local configured_port
  configured_port="${TUNNEL_METRICS_PORT:-$(read_env_value TUNNEL_METRICS_PORT)}"
  configured_port="${configured_port:-20242}"
  [[ "$configured_port" =~ ^[0-9]+$ ]] &&
    (( configured_port >= 1 && configured_port <= 65535 )) ||
    fail "TUNNEL_METRICS_PORT invalida."
  TUNNEL_METRICS_PORT="$configured_port"
  TUNNEL_READY_URL="${TUNNEL_READY_URL:-http://127.0.0.1:${TUNNEL_METRICS_PORT}/ready}"
  export TUNNEL_METRICS_PORT
}
```

Chamar a função após `check_env_file`, atualizar o avaliador operacional e
declarar `TUNNEL_METRICS_PORT=20242` em `.env.example`.

- [x] **Step 4: Executar testes focais e validações estáticas**

Run:

```bash
bash scripts/test.sh tests/test_vps_compose_contract.py tests/test_operational_readiness.py tests/test_native_postgres_deployment.py -q
.venv/bin/python -m ruff check core/operational_readiness.py tests/test_vps_compose_contract.py tests/test_operational_readiness.py tests/test_native_postgres_deployment.py
bash -n scripts/deploy-vps.sh
git diff --check
```

Expected: todos os testes e checks com saída zero.

- [x] **Step 5: Documentar e commitar**

Atualizar `docs/architecture/operational-readiness.md` e `docs/DEPLOY_VPS.md`
com a variável e a porta padrão, depois executar:

```bash
git add .env.example docker-compose.vps.yml scripts/deploy-vps.sh core/operational_readiness.py tests/test_vps_compose_contract.py tests/test_operational_readiness.py tests/test_native_postgres_deployment.py docs/architecture/operational-readiness.md docs/DEPLOY_VPS.md docs/superpowers/plans/2026-09-01-cloudflared-metrics-port-isolation.md
git commit -m "fix: isolar porta de readiness do tunnel"
```

### Task 2: Publicação e instalação inicial na VPS

**Files:**
- Remote runtime: `/home/deploy/rgnfamarsystemv2/.env`
- Remote checkout: `/home/deploy/rgnfamarsystemv2`

**Interfaces:**
- Consumes: release aprovado em `origin/main` e `TUNNEL_METRICS_PORT=20242`.
- Produces: serviços Compose `rgnfarmasystem` e evidências de saúde.

- [ ] **Step 1: Enviar o release verificado**

```bash
git push origin main
git ls-remote --heads origin main
```

Expected: `origin/main` aponta para o commit de implementação.

- [ ] **Step 2: Preparar a instalação inicial sem tocar em outros projetos**

Na VPS, confirmar que `20242` está livre, adicionar ou atualizar apenas
`TUNNEL_METRICS_PORT=20242` no dotenv sem exibir segredos, validar o Compose e
registrar o SHA anterior.

- [ ] **Step 3: Promover e iniciar o Compose**

Como ainda não existe instância anterior do Compose `rgnfarmasystem`, atualizar
por fast-forward e executar:

```bash
COMPOSE_PROJECT_NAME=rgnfarmasystem VPS_ENV_FILE=.env \
  docker compose --env-file .env -f docker-compose.vps.yml \
  up -d --build --remove-orphans --wait --wait-timeout 900
```

- [ ] **Step 4: Validar o release real**

```bash
docker compose --env-file .env -f docker-compose.vps.yml ps
curl -fsS http://127.0.0.1:20242/ready >/dev/null
curl -fsS -H 'Host: rgnfarmasystem.rgnsystems.com.br' http://127.0.0.1:8081/health/ >/dev/null
curl -fsS https://rgnfarmasystem.rgnsystems.com.br/health/ >/dev/null
docker compose --env-file .env -f docker-compose.vps.yml exec -T app python manage.py check --deploy
```

Expected: nove serviços em execução, endpoints 200 e check de produção sem
erros.
