# Sprint 47 — Auditoria regulatória e validação CSV

## Objetivo

Criar uma matriz versionada e verificável de requisitos, controles e evidências
para apoiar validação computadorizada, sem declarar certificação regulatória.

## Entregas

- `docs/validation/requirements-matrix.yml` com requisitos, controles e
  evidências esperadas.
- `core/csv_validation.py` para validar a matriz e gerar relatório Markdown/JSON.
- Comando `check_csv_validation` para execução local e CI.
- Testes de rastreabilidade, hashes, ALCOA+ e dados incompletos.
- Runbook IQ/OQ/PQ, GAMP 5, ALCOA+ e limites da validação.

## Segurança

Evidências devem conter hash SHA-256, autor e timestamp. O sistema não aceita
segredos, tokens ou arquivos fora da raiz autorizada. O relatório é evidência
técnica auxiliar e não substitui validação formal qualificada.
