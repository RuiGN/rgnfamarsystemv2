# Release v1 e operação assistida

Uma release usa uma tag `vMAJOR.MINOR.PATCH`. Antes da promoção, execute
`GITHUB_SHA=$(git rev-parse HEAD) bash scripts/release_gate.sh v1.0.0`.
O workflow `.github/workflows/release.yml` repete testes, migrations, OpenAPI,
segurança e readiness e constrói uma imagem local com tag do commit, sem push.

Os workflows usam actions com runtime Node.js 24 (`checkout@v6`,
`setup-python@v6`, `gitleaks-action@v3` e `upload-artifact@v6`). Runners
self-hosted devem executar GitHub Actions Runner `v2.327.1` ou superior antes
de processar esses workflows; os runners hospedados atuais já atendem ao
requisito.

Após iniciar os serviços, valide `/health/`, `/`, `/api/schema/` e `/api/docs/`,
além dos healthchecks de PostgreSQL, Redis, RabbitMQ, worker e beat. Registre
versão, commit, timestamp, resultado dos gates e digest da imagem.

Para rollback, interrompa a promoção, preserve logs e volte à imagem da última
tag aprovada. Repita migrations compatíveis, healthchecks e smoke tests. O
workflow não publica no GHCR nem executa deploy externo.
