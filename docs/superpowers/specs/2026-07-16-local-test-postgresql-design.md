# Ambiente PostgreSQL reproduzível para testes locais

## Contexto

A suíte automatizada usa `core.settings.test` e exige um PostgreSQL isolado por
meio de `TEST_DATABASE_URL`. O ambiente atual pode apontar para
`host.docker.internal`, endereço que não é resolvido de forma uniforme em hosts
Linux. Isso impede a criação do banco de testes antes que as asserções sejam
executadas.

O CI já valida o sistema com PostgreSQL 15. O ambiente local deve reproduzir
esse contrato sem reutilizar o banco de desenvolvimento e sem permitir fallback
para SQLite.

## Objetivo

Disponibilizar um único comando local que:

1. suba um PostgreSQL 15 exclusivo para testes;
2. aguarde o banco aceitar conexões;
3. configure `TEST_DATABASE_URL` e `DATABASE_URL` para o processo de teste;
4. encaminhe argumentos adicionais ao pytest;
5. preserve o banco de desenvolvimento e os demais serviços locais.

## Arquitetura

Será criado um arquivo `docker-compose.test.yml` com um único serviço
PostgreSQL. O serviço será publicado apenas em `127.0.0.1`, na porta `5433` por
padrão, para evitar exposição na rede e conflito com a porta padrão `5432`.

O banco utilizará credenciais locais fixas e não sensíveis, exclusivas para
testes. Um volume Docker nomeado permitirá o uso de `pytest --reuse-db` sem
misturar dados com os volumes das topologias de desenvolvimento ou produção.

Um script `scripts/test.sh` será a interface oficial. Ele usará Docker Compose
para iniciar somente o PostgreSQL, aguardará o healthcheck e executará a suíte
com a virtualenv do projeto. O script não encerrará ou removerá automaticamente
o banco após cada execução, preservando o benefício de `--reuse-db`. A remoção
continuará disponível explicitamente por Docker Compose.

## Configuração e fluxo

Valores padrão:

- host: `127.0.0.1`;
- porta: `5433`, substituível por `TEST_POSTGRES_PORT`;
- banco: `rgn_test`;
- usuário: `rgn_test`;
- senha: `rgn_test`;
- URL: `postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test`.

Fluxo de execução:

```text
scripts/test.sh [argumentos pytest]
  -> valida Docker, Compose e virtualenv
  -> sobe o serviço postgres_test
  -> aguarda healthcheck com limite de tempo
  -> exporta URLs do banco somente para o subprocesso
  -> executa python -m pytest [argumentos]
  -> retorna exatamente o status do pytest
```

O script não carregará `.env`, evitando que valores de desenvolvimento ou
produção sobrescrevam o banco isolado. Variáveis necessárias para os settings
base que já possuam defaults seguros continuarão usando esses defaults.

## Tratamento de erros

O comando deve falhar com mensagem clara quando:

- Docker ou Docker Compose não estiver disponível;
- `.venv/bin/python` não existir;
- o container não iniciar;
- o PostgreSQL não ficar saudável dentro do limite;
- pytest retornar erro ou falha.

Mensagens e comandos não devem revelar credenciais provenientes de `.env`. As
credenciais locais fixas do banco descartável não são segredos.

## Testes

Um teste de contrato, independente de banco, verificará que:

- o Compose usa PostgreSQL 15, healthcheck e bind em `127.0.0.1`;
- serviço e volume possuem nomes isolados da topologia local;
- a porta pode ser configurada sem alterar arquivos;
- o script usa modo Bash defensivo;
- o script sobe e aguarda o serviço antes do pytest;
- `TEST_DATABASE_URL` e `DATABASE_URL` apontam para o banco isolado;
- argumentos são encaminhados sem reinterpretação;
- o status final do pytest é preservado;
- a documentação apresenta execução, execução seletiva e limpeza explícita.

Após os testes de contrato, a validação operacional executará os 453 testes
coletados contra o PostgreSQL isolado. A cobertura será medida pelo mesmo
comando empregado no quality gate do CI.

## Documentação

O README ganhará uma seção curta com:

```bash
bash scripts/test.sh
bash scripts/test.sh tests/test_foundation.py -q
docker compose -f docker-compose.test.yml down -v
```

## Fora de escopo

- alterar `core.settings.test` para aceitar SQLite;
- executar Redis ou RabbitMQ localmente para a suíte, pois os settings de teste
  usam cache em memória e Celery eager;
- corrigir os achados existentes do Ruff ou Bandit;
- modificar o banco ou a topologia de desenvolvimento;
- alterar o quality gate do GitHub Actions, que já possui PostgreSQL isolado.

## Critérios de aceitação

- Um desenvolvedor com Docker e a virtualenv instalada executa a suíte usando um
  único comando.
- O banco de testes não compartilha serviço, porta padrão, nome de banco ou
  volume com o ambiente local.
- A suíte permanece estritamente PostgreSQL.
- O teste de contrato do ambiente passa.
- A documentação descreve uso e limpeza.
- O resultado integral da suíte e da cobertura é registrado sem ocultar falhas.
