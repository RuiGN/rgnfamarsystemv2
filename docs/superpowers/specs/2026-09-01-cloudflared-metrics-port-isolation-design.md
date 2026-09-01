# Isolamento da porta de readiness do Cloudflare Tunnel

## Contexto

A VPS hospeda outros produtos em containers independentes. O container
`michele-tunnel`, executado com rede do host, já ocupa a porta `20241`. O novo
Compose do RGN Farma também reservava essa porta para o servidor de métricas e
readiness do `cloudflared`, impedindo a coexistência dos conectores.

## Decisão

O RGN Farma usará `TUNNEL_METRICS_PORT`, com padrão `20242`, como única
configuração da porta local do conector. O endereço continuará restrito a
`127.0.0.1`.

- `docker-compose.vps.yml` interpolará a variável no argumento `--metrics`.
- `.env.example` documentará o valor de produção esperado.
- `scripts/deploy-vps.sh` lerá a mesma variável do dotenv sem executar
  `source` e consultará `/ready` nessa porta.
- O preflight rejeitará valores que não sejam portas TCP válidas.
- Testes de contrato comprovarão a interpolação e o alinhamento entre Compose e
  script.

## Alternativas rejeitadas

1. Parar ou alterar o `michele-tunnel`: afetaria outro produto fora do escopo.
2. Criar override Compose somente na VPS: produziria configuração não
   versionada e um próximo deploy poderia reintroduzir a colisão.
3. Manter outra porta fixa: resolveria esta VPS, mas repetiria o acoplamento que
   causou o incidente.

## Fluxo operacional

O operador mantém `TUNNEL_METRICS_PORT=20242` no `.env`. O Compose entrega
`127.0.0.1:20242` ao `cloudflared`; após os containers ficarem saudáveis, o
script exige HTTP 200 de `http://127.0.0.1:20242/ready`, além da origem Nginx e
do domínio público.

## Falhas e rollback

Configuração ausente usa `20242`. Porta inválida interrompe o preflight. Porta
ocupada impede o conector de ficar pronto e, em promoção normal, aciona o
rollback de código já previsto. A instalação inicial não remove containers,
volumes nem túneis de outros projetos.

## Verificação

- Teste em vermelho para o antigo valor fixo e para o novo contrato.
- Testes focais de Compose, prontidão operacional e script de deploy.
- `docker compose config --quiet` com o dotenv de produção, sem imprimir seus
  valores.
- Na VPS: comprovar `20242` livre antes do start, `/ready` 200 após o start e
  manter o processo que ocupa `20241` inalterado.
