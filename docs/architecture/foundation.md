# Fundação Arquitetural

## Arquitetura single-instance

Este módulo opera em escopo global da instalação local. O acesso é controlado
por autenticação Django e permissões nativas `view`, `add`, `change` e
`delete`, administradas no Django Admin por usuário ou grupo.

O identificador de autenticação é o nome de usuário único cadastrado no Django
Admin. O e-mail permanece obrigatório e único para contato, sem autenticar.

As APIs e telas operacionais não exigem cabeçalho de escopo, seleção de empresa
ou vínculo de contrato por cliente. Listagens, formulários, detalhes e ações
usam o mesmo conjunto global de dados da instância.

## Regras de implementação

- Preservar as regras de negócio da indústria de cosméticos do módulo.
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

## Campos gerados pelo servidor

`base.automatic_fields.automatic_generated_fields()` centraliza a política de
identificadores automáticos consumida pelos formulários operacionais, pelos
serializers DRF e pelo Django Admin. Códigos são reconhecidos pelo contrato do
model (`AutoCodeMixin` com `CODE_PREFIX` ativo); identificadores operacionais
com outros nomes são declarados no próprio model por meio de
`AUTOMATIC_IDENTIFIERS`, usando objetos imutáveis `IdentifierSpec`.

Na criação, esses campos ficam visíveis, desabilitados e opcionais. Na edição,
o valor persistido fica visível e imutável. Valores forjados no POST são
ignorados pelo `ModelForm`, e a API e o Admin expõem os mesmos campos somente
para leitura. Códigos manuais, como o ISO da moeda, não participam da política.

`base.models.IdentifierSequence` guarda o último número alocado por namespace.
O namespace separa model, campo e período diário ou global. A alocação ocorre
em transação com bloqueio de linha; quando um namespace ainda não existe, o
maior sufixo persistido é usado como ponto inicial. Depois do bootstrap, não há
varredura da tabela de negócio e a exclusão de um registro não reduz o contador.

Lacunas são válidas e números emitidos não devem ser reaproveitados. Modelos
com identificadores automáticos não podem depender de `bulk_create()`, pois
essa operação não executa `save()`. Importações em lote devem alocar os números
explicitamente pelo serviço de sequências antes da persistência.

## Verificação mínima

```bash
TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/python manage.py check

TEST_DATABASE_URL=postgresql://rgn_test:rgn_test@127.0.0.1:5433/rgn_test DJANGO_SETTINGS_MODULE=core.settings.test .venv/bin/pytest -q
```
