# Sprint 46 — Release v1 e operação assistida

## Objetivo

Criar um fluxo de release versionado e verificável para o RGN Farma System,
com gates automatizados, procedimento de rollback e evidência operacional,
sem publicar artefatos externos nem executar deploy real sem credenciais.

## Escopo

- Validar versão/tag de release a partir do commit.
- Criar workflow de release com testes, migrations, schema, segurança e
  readiness.
- Gerar artefato local reproduzível da imagem Docker.
- Documentar deploy, rollback, pós-deploy e critérios de go-live.
- Validar backup/restauração e healthchecks em ambiente isolado.
- Registrar evidências e a Sprint 46 no `PRD.md`.

## Fora de escopo

- Push para GHCR ou outro registry.
- Deploy em VPS, Swarm ou domínio público.
- Uso de tokens, certificados ou segredos reais.
- Alteração de modelos de negócio ou migrations de produto.

## Arquitetura

O workflow de release executará gates determinísticos e construirá a imagem
com uma tag derivada de `GITHUB_SHA` ou de uma tag semântica validada. Scripts
locais permitirão executar os mesmos gates sem GitHub Actions. O runbook
documentará promoção, rollback por tag anterior e verificação dos endpoints e
processos assíncronos.

## Segurança e rastreabilidade

- Tags de release devem ser imutáveis e seguir `vMAJOR.MINOR.PATCH`.
- O pipeline não imprimirá segredos nem fará login automático em registries.
- Artefatos e relatórios usarão caminhos locais temporários.
- Toda promoção exigirá gates verdes e registro de commit, versão e timestamp.

## Critérios de aceite

1. Workflow de release passa validação YAML e contém gates obrigatórios.
2. Tag inválida é rejeitada antes da construção.
3. A imagem pode ser construída localmente com tag determinística.
4. Rollback e pós-deploy estão documentados e verificáveis.
5. Backup/restauração e healthchecks possuem comandos reproduzíveis.
6. Não há publicação externa ou segredo versionado.
7. `PRD.md` registra a Sprint 46 apenas após os gates locais passarem.
