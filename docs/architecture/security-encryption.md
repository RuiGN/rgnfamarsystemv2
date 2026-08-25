# Criptografia AES-256

O sistema possui uma camada de criptografia em repouso baseada em AES-256-GCM
para conteúdo sensível de arquivos protegidos.

## Algoritmo

- Algoritmo: AES-256-GCM.
- Chave: 32 bytes, informada por variável de ambiente em base64 URL-safe.
- Nonce: 12 bytes aleatórios por operação.
- Envelope: `aes256gcm:v1:<key_id>:<nonce>:<ciphertext>`.
- Dados associados: identidade do arquivo protegido, vinculando o criptograma ao
  registro e número do arquivo.

## Configuração

Gere uma chave:

```bash
python manage.py generate_data_encryption_key --key-id primary
```

Configure:

```env
DATA_ENCRYPTION_KEY_ID=primary
DATA_ENCRYPTION_KEYS=primary:<chave-gerada>
```

Para rotação, adicione a nova chave ao `DATA_ENCRYPTION_KEYS`, altere
`DATA_ENCRYPTION_KEY_ID` para o novo identificador e recriptografe os conteúdos
que precisarem ser migrados.

## Arquivos Protegidos

`ProtectedFile.store_encrypted_content()` grava o conteúdo criptografado no
storage padrão do Django e atualiza:

- `file_reference`
- `content_hash` do plaintext
- `file_size` do plaintext
- `encrypted_size`
- `encryption_algorithm`
- `encryption_key_id`
- `encrypted_at`

`ProtectedFile.read_encrypted_content()` valida disponibilidade, permissão e
descriptografa o conteúdo apenas quando o usuário tem acesso ao arquivo.

Registros antigos permanecem compatíveis com `encryption_algorithm=none`.

Os artefatos enviados pelo fluxo de backup off-site também usam AES-256-GCM e
sidecar SHA-256. A identidade usada como dado associado é funcional (arquivo,
registro ou tipo de backup) e não depende de escopo SaaS.

## Verificação single-instance

Em 18/07/2026, os módulos `ai_agents`, `knowledge`, `files`, `integrations`,
`auxiliary` e `core.crypto`, junto aos templates operacionais, foram
inventariados sem encontrar campos, filtros, headers ou contexto funcional de
tenant. O ciclo local de backup foi restaurado em banco PostgreSQL temporário e
reconstruiu 173 registros de migration antes da remoção do banco de validação.

```bash
.venv/bin/pytest tests/test_ai_agents.py tests/test_knowledge.py \
  tests/test_files.py tests/test_backup_encryption.py tests/test_encryption.py -q
```

## Limites

A criptografia cobre o conteúdo gravado por `store_encrypted_content()`. Ela não
criptografa automaticamente campos históricos já existentes, backups do banco,
volumes Docker ou arquivos previamente gravados fora desse fluxo.
