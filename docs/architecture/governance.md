# Administração, Parametrização e Governança

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

## Responsáveis técnicos

O cadastro `TechnicalResponsible` registra o profissional legalmente vinculado
à instituição usuária do sistema, com foco no Responsável Técnico farmacêutico
registrado no Conselho Regional de Farmácia (CRF). O cadastro fica em
Governança porque representa responsabilidade institucional, regularidade e
evidência auditável da operação.

Campos principais:

- Identificação: nome completo, CPF, e-mail, telefone e usuário vinculado
  opcional.
- Vínculo: instituição, empresa fiscal opcional e tipo de responsabilidade
  (principal, substituto ou assistente técnico).
- Registro profissional: profissão, conselho profissional, UF do conselho,
  número de inscrição, tipo e status da inscrição.
- Vigência: data de início, data de término opcional, carga horária semanal e
  grade de assistência farmacêutica em JSON.
- Regularidade: número da certidão, emissão, validade, referência do arquivo,
  URL de verificação e data/hora de verificação.

Regras:

- CPF deve ser válido.
- Para CRF, UF do conselho e número de inscrição são obrigatórios.
- Responsável técnico principal ativo exige inscrição ativa e data de início.
- Não pode existir mais de um responsável técnico principal ativo para a mesma
  instituição/empresa fiscal.
- Data de término não pode anteceder a data de início.
- Validade da certidão não pode anteceder a emissão.

UI operacional:

```text
/app/governance/technical-responsibles/
```

API REST:

```text
/api/governance/technical-responsibles/
```

## Verificação mínima

```bash
TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/python manage.py check

TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/pytest -q
```
