# Modelo de inventário externo de segredos

Este arquivo define apenas o esquema. O inventário preenchido deve ficar no cofre corporativo e não pode ser commitado.

| Campo | Conteúdo permitido |
|---|---|
| Identificador | ID interno sem valor secreto |
| Classe | OAuth, banco, fila, SMTP, IA, túnel, backup ou criptografia |
| Sistema | Serviço que consome a credencial |
| Proprietário | Papel responsável |
| Escopo | Permissões concedidas |
| Ambiente | DEV, TEST/VALIDATION ou PROD |
| Introduzido em | Data/hora UTC |
| Revogado em | Data/hora UTC e ID da evidência |
| Novo key ID | Referência do secret manager, nunca o segredo |
| Validação | Resultado do teste pós-rotação |
| Aprovador | Segurança/DPO e, quando GxP, Qualidade |

O inventário externo deve incluir, sem valores: credencial do administrador
`Rui`, `SECRET_KEY`, PostgreSQL, RabbitMQ, SMTP, provedores de IA, chave de
criptografia, Google Drive e token do Cloudflare Tunnel. Arquivos temporários
usados para provisionar senha devem ser `0600` e destruídos após validação.

Critério G0: todos os itens encontrados devem possuir revogação confirmada, validação pós-rotação e aprovação.
