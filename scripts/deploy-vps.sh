#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# Deploy automatizado do RGN Farma System na VPS
# Publica:
#   https://rgnfarmasystem.rgnsystems.com.br
#   https://control.rgnfarmasystem.rgnsystems.com.br
# VPS: 13.140.139.122
# ---------------------------------------------------------------------------

EXPECTED_VPS_IP="13.140.139.122"
PROJECT_DIR="/opt/rgnfarmasystem"
STACK_NAME="rgnfarmasystem"
COMPOSE_FILE="docker-stack.yml"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# ---------------------------------------------------------------------------
# Verifica IP da VPS
# ---------------------------------------------------------------------------
check_vps_ip() {
    local current_ip
    current_ip=$(curl -fsS https://ipinfo.io/ip 2>/dev/null || echo "")
    if [[ -z "$current_ip" ]]; then
        log_error "Nao foi possivel detectar o IP publico desta maquina."
        exit 1
    fi

    if [[ "$current_ip" != "$EXPECTED_VPS_IP" ]]; then
        log_warn "IP detectado ($current_ip) difere do IP esperado ($EXPECTED_VPS_IP)."
        read -r -p "Deseja continuar mesmo assim? [s/N] " confirm
        if [[ ! "$confirm" =~ ^[Ss]$ ]]; then
            log_info "Deploy cancelado."
            exit 0
        fi
    else
        log_info "IP da VPS confirmado: $current_ip"
    fi
}

# ---------------------------------------------------------------------------
# Verifica Docker
# ---------------------------------------------------------------------------
check_docker() {
    if ! command -v docker &>/dev/null; then
        log_error "Docker nao esta instalado."
        exit 1
    fi
}

# ---------------------------------------------------------------------------
# Verifica, sem alterar o host, se o Swarm esta ativo e este no e manager
# ---------------------------------------------------------------------------
check_docker_swarm() {
    if ! docker info --format '{{.Swarm.ControlAvailable}}' 2>/dev/null | grep -q "true"; then
        log_error "Docker Swarm nao esta ativo ou este no nao e manager."
        log_error "Ative-o manualmente neste host manager antes do deploy: docker swarm init"
        exit 1
    fi

    log_info "Docker Swarm ativo e este no e manager."
}

# ---------------------------------------------------------------------------
# Cria redes externas se necessario
# ---------------------------------------------------------------------------
ensure_networks() {
    local networks=("traefik_public" "rgnfarmasystem_egress")
    for net in "${networks[@]}"; do
        if docker network inspect "$net" &>/dev/null; then
            log_info "Rede '$net' ja existe."
        else
            log_info "Criando rede overlay '$net'..."
            docker network create --driver overlay --attachable "$net"
        fi
    done
}

# ---------------------------------------------------------------------------
# Verifica secrets obrigatorios
# ---------------------------------------------------------------------------
check_secrets() {
    local secrets=("CLOUDFLARE_DNS_API_TOKEN" "GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON")
    local missing=()

    for secret in "${secrets[@]}"; do
        if ! docker secret inspect "$secret" &>/dev/null; then
            missing+=("$secret")
        fi
    done

    if [[ ${#missing[@]} -gt 0 ]]; then
        log_error "Secrets nao encontrados: ${missing[*]}"
        echo ""
        echo "Crie os secrets antes de continuar:"
        echo ""
        echo "  printf 'SEU_TOKEN' | docker secret create CLOUDFLARE_DNS_API_TOKEN -"
        echo "  docker secret create GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON /caminho/service-account.json"
        echo ""
        exit 1
    fi

    log_info "Secrets obrigatorios encontrados."
}

# ---------------------------------------------------------------------------
# Verifica arquivo .env
# ---------------------------------------------------------------------------
check_env_file() {
    if [[ ! -f ".env" ]]; then
        log_error "Arquivo .env nao encontrado."
        echo "Copie .env.example para .env e preencha as variaveis antes de continuar."
        exit 1
    fi

    # Verifica variaveis criticas
    local required_vars=(
        "SECRET_KEY"
        "POSTGRES_PASSWORD"
        "TRAEFIK_ACME_EMAIL"
        "DATABASE_URL"
        "CELERY_BROKER_URL"
    )

    local missing=()
    for var in "${required_vars[@]}"; do
        if ! grep -qE "^${var}=" .env || grep -qE "^${var}=$" .env || grep -qE "^${var}=change-me" .env; then
            missing+=("$var")
        fi
    done

    if [[ ${#missing[@]} -gt 0 ]]; then
        log_warn "Variaveis nao preenchidas ou com valores de exemplo: ${missing[*]}"
        read -r -p "Deseja continuar mesmo assim? [s/N] " confirm
        if [[ ! "$confirm" =~ ^[Ss]$ ]]; then
            log_info "Deploy cancelado."
            exit 0
        fi
    else
        log_info "Arquivo .env presente e preenchido."
    fi
}

# Le exatamente uma chave do .env sem executar seu conteudo no shell.
read_env_value() {
    local key="$1"
    awk -v key="$key" '
        index($0, key "=") == 1 {
            value = substr($0, length(key) + 2)
            sub(/\r$/, "", value)
            matches++
        }
        END {
            if (matches > 1) {
                print "Arquivo .env contem chave duplicada: " key > "/dev/stderr"
                exit 1
            }
            if (matches == 1) {
                print value
            }
        }
    ' .env
}

# ---------------------------------------------------------------------------
# Valida a topologia e a conectividade com o PostgreSQL nativo
# ---------------------------------------------------------------------------
check_native_postgres() {
    local db_deployment db_host db_port postgres_db postgres_user postgres_password image_tag
    db_deployment=$(read_env_value DB_DEPLOYMENT)
    db_host=$(read_env_value DB_HOST)
    db_port=$(read_env_value DB_PORT)
    postgres_db=$(read_env_value POSTGRES_DB)
    postgres_user=$(read_env_value POSTGRES_USER)
    postgres_password=$(read_env_value POSTGRES_PASSWORD)
    image_tag=$(read_env_value IMAGE_TAG)

    [[ "$db_deployment" == "external" ]] || {
        log_error "DB_DEPLOYMENT deve ser external na VPS."
        exit 1
    }
    [[ "$db_host" == "host.docker.internal" ]] || {
        log_error "DB_HOST deve ser host.docker.internal na VPS."
        exit 1
    }
    [[ -n "$db_port" ]] || {
        log_error "DB_PORT deve estar preenchido na VPS."
        exit 1
    }
    [[ -n "$postgres_db" ]] || {
        log_error "POSTGRES_DB deve estar preenchido na VPS."
        exit 1
    }
    [[ -n "$postgres_user" ]] || {
        log_error "POSTGRES_USER deve estar preenchido na VPS."
        exit 1
    }
    [[ -n "$postgres_password" ]] || {
        log_error "POSTGRES_PASSWORD deve estar preenchido na VPS."
        exit 1
    }

    log_info "Validando PostgreSQL nativo em ${db_host}:${db_port} com senha <redacted>..."
    docker run --rm --add-host host.docker.internal:host-gateway \
        -e PGPASSWORD="$postgres_password" \
        --entrypoint pg_isready \
        "ghcr.io/ruign/rgnfarmasystem:${image_tag:-latest}" \
        -h "$db_host" -p "$db_port" -U "$postgres_user" -d "$postgres_db" || {
            log_error "PostgreSQL nativo indisponivel para a stack."
            exit 1
        }

    docker run --rm --add-host host.docker.internal:host-gateway \
        -e PGPASSWORD="$postgres_password" \
        --entrypoint psql \
        "ghcr.io/ruign/rgnfarmasystem:${image_tag:-latest}" \
        -h "$db_host" -p "$db_port" -U "$postgres_user" -d "$postgres_db" \
        -v ON_ERROR_STOP=1 -c "SELECT 1" >/dev/null || {
            log_error "Falha ao autenticar no PostgreSQL nativo."
            exit 1
        }
}

# ---------------------------------------------------------------------------
# Faz o deploy da stack
# ---------------------------------------------------------------------------
deploy_stack() {
    log_info "Fazendo deploy da stack '$STACK_NAME'..."

    # Carrega apenas as variaveis necessarias para interpolacao do docker-stack.yml.
    # O .env e lido pelo Docker como env_file dos containers, entao nao precisamos
    # exportar tudo no shell (evita problemas com caracteres especiais).
    local image_tag traefik_acme_email
    image_tag=$(python3 -c "import re; print(next((m.group(2) for m in (re.match(r'^IMAGE_TAG=(.*)$', line) for line in open('.env')) if m), 'latest'))")
    traefik_acme_email=$(python3 -c "import re; print(next((m.group(2) for m in (re.match(r'^TRAEFIK_ACME_EMAIL=(.*)$', line) for line in open('.env')) if m), ''))")

    IMAGE_TAG="${image_tag:-latest}" TRAEFIK_ACME_EMAIL="$traefik_acme_email" docker stack deploy \
        --with-registry-auth \
        -c "$COMPOSE_FILE" \
        "$STACK_NAME"

    log_info "Deploy enviado. Aguardando convergencia..."
}

# ---------------------------------------------------------------------------
# Aguarda e verifica status dos servicos
# ---------------------------------------------------------------------------
wait_for_services() {
    local attempts=0
    local max_attempts=30
    local wait_seconds=10

    while [[ $attempts -lt $max_attempts ]]; do
        local status
        status=$(docker service ls --filter "name=${STACK_NAME}_" --format '{{.Name}} {{.Replicas}}')

        local not_ready
        not_ready=$(echo "$status" | awk '$2 !~ /\/$/ {print}' | wc -l)

        if [[ "$not_ready" -eq 0 ]]; then
            log_info "Todos os servicos estao prontos:"
            docker service ls --filter "name=${STACK_NAME}_"
            return 0
        fi

        attempts=$((attempts + 1))
        log_warn "Aguardando servicos ficarem prontos (tentativa $attempts/$max_attempts)..."
        echo "$status"
        sleep "$wait_seconds"
    done

    log_error "Timeout aguardando servicos ficarem prontos."
    docker service ls --filter "name=${STACK_NAME}_"
    return 1
}

# ---------------------------------------------------------------------------
# Testa endpoint de health localmente
# ---------------------------------------------------------------------------
health_check() {
    log_info "Verificando endpoints de health..."
    local ok=true
    if curl -fsS -k -H "Host: rgnfarmasystem.rgnsystems.com.br" https://127.0.0.1:8443/health/ >/dev/null 2>&1; then
        log_info "Health check OK via Traefik (HTTPS) - rgnfarmasystem."
    else
        log_warn "Health check via Traefik falhou para rgnfarmasystem."
        ok=false
    fi

    if curl -fsS -k -H "Host: control.rgnfarmasystem.rgnsystems.com.br" https://127.0.0.1:8443/health/ >/dev/null 2>&1; then
        log_info "Health check OK via Traefik (HTTPS) - control."
    else
        log_warn "Health check via Traefik falhou para control."
        ok=false
    fi

    if [[ "$ok" != true ]]; then
        echo "Verifique os logs:"
        echo "  docker service logs ${STACK_NAME}_traefik --tail 50"
        echo "  docker service logs ${STACK_NAME}_app --tail 50"
    fi
}

# ---------------------------------------------------------------------------
# Instrucoes finais
# ---------------------------------------------------------------------------
print_final_instructions() {
    echo ""
    echo "============================================================"
    echo " Deploy concluido na VPS $EXPECTED_VPS_IP"
    echo "============================================================"
    echo ""
    log_info "DNS ja configurado:"
    echo ""
    echo "  rgnfarmasystem.rgnsystems.com.br  ->  A -> $EXPECTED_VPS_IP"
    echo "  control.rgnfarmasystem.rgnsystems.com.br -> A -> $EXPECTED_VPS_IP"
    echo ""
    echo "Apos a propagacao DNS (geralmente 1-5 minutos), valide com:"
    echo ""
    echo "  curl -fsS https://rgnfarmasystem.rgnsystems.com.br/health/"
    echo "  curl -fsS https://control.rgnfarmasystem.rgnsystems.com.br/health/"
    echo ""
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    log_info "Iniciando deploy do RGN Farma System..."

    check_vps_ip
    check_docker
    check_env_file
    check_native_postgres
    check_docker_swarm
    check_secrets
    ensure_networks
    deploy_stack
    wait_for_services
    health_check
    print_final_instructions
}

main "$@"
