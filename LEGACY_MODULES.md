# Módulos Legados

Este documento rastreia os módulos legados do sistema que estão em processo de depreciação e remoção (transição da arquitetura multi-tenant para single-instance).

## 1. `tenants`

**Estado atual:**
- O projeto migrou de arquitetura multi-tenant para single-instance.
- O app existe em `INSTALLED_APPS` e seu código permanece em `tenants/` estritamente para preservar o histórico de migrações do Django.
- O código de produção (fora de migrations e apps.py) não faz mais nenhuma importação ou uso do módulo `tenants`.

**O que ainda depende dele:**
- **Testes de regressão e schema:** Existem testes (`tests/test_single_instance_schema.py`, `tests/test_foundation.py`, `tests/test_single_instance_runtime.py`, `tests/test_app_ui.py`) que validam a consistência da transição para single-instance.
- **Histórico do Django (Migrations):** O Django precisa de `tenants` no `INSTALLED_APPS` para que ambientes em versões anteriores do banco de dados consigam aplicar as migrações destrutivas (ex: `0006_delete_tenant.py`) de maneira segura.

**Plano de migração passo a passo:**
1. Assegurar que todos os ambientes de implantação apliquem todas as migrações que consolidam o single-instance.
2. Fazer o *squash* das migrações (`squashmigrations` ou limpar e refazer os arquivos de inicialização) no momento arquitetural adequado.
3. Excluir os testes e asserções relacionados à transição em `tests/`.
4. Remover `tenants` de `core/settings/base.py`.
5. Apagar completamente o diretório `tenants/`.

**Quando será seguro remover completamente:**
Após todos os bancos de dados não necessitarem mais do histórico incremental de migração antigo (via squashing de migrations) e os testes transitórios não forem mais necessários.

## 2. `control_plane`

**Estado atual:**
- O módulo gerenciava instâncias e metadados de tenants, sendo descontinuado após a mudança para single-instance.
- Restrito a `INSTALLED_APPS` e ao diretório `control_plane/` para garantir a resolução do histórico de migrações do banco.
- Nenhum uso em código de produção vivo foi detectado.

**O que ainda depende dele:**
- **Testes de regressão:** A validação da remoção e a preservação de dados associados é monitorada em testes (ex: `tests/test_control_plane_removal_migrations.py`, `tests/test_foundation.py`).
- **Histórico do Django (Migrations):** Necessário para que a migração de remoção e preservação dos dados aconteça adequadamente (ex: `0005_preserve_evidence_and_delete_runtime_models.py`).

**Plano de migração passo a passo:**
1. Certificar-se que a preservação de evidências e exclusão das tabelas do control plane foram executadas em todos os clientes e ambientes.
2. Realizar *squash* ou reset das migrações do projeto.
3. Deletar os testes em `tests/` que monitoram migrações específicas ou asserções do `control_plane`.
4. Remover `control_plane` de `core/settings/base.py`.
5. Excluir completamente a pasta `control_plane/`.

**Quando será seguro remover completamente:**
Juntamente com `tenants`, será seguro após um procedimento consolidado de consolidação das migrations, tornando as pastas legadas de migrações desnecessárias para as instâncias operacionais.
