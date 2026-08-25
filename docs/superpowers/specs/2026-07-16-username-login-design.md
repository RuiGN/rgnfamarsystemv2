# Login por nome de usuário e banco PostgreSQL local

## Objetivo

Substituir a autenticação por e-mail pelo nome de usuário cadastrado no Django Admin e disponibilizar o banco PostgreSQL local com todas as migrations aplicadas.

## Decisões

- `accounts.User.username` será o identificador de autenticação (`USERNAME_FIELD`).
- O nome de usuário representará o nome completo de acesso, por exemplo `João Silva`.
- O e-mail continuará obrigatório e único, mas será usado apenas como contato e recuperação de acesso.
- O nome de usuário será obrigatório e único sem diferenciação entre maiúsculas e minúsculas. Espaços externos serão removidos e sequências internas de espaços serão normalizadas antes da persistência.
- ERP, Control Plane e Django Admin usarão o mesmo identificador.

## Modelo e migração de dados

O campo `username` deixará de aceitar valor vazio e terá unicidade no modelo. Uma restrição funcional no PostgreSQL impedirá duplicidade por caixa após normalização da aplicação.

A migration de dados preencherá usuários existentes nesta ordem:

1. `first_name + last_name`, quando disponível;
2. prefixo do e-mail, transformado em palavras, quando o nome estiver ausente;
3. sufixo numérico determinístico (`Nome 2`, `Nome 3`) quando houver colisão durante a transição.

Após a migração, novos usuários com nomes equivalentes serão rejeitados. A migration preservará os IDs, senhas, permissões, memberships e relações existentes.

## Autenticação e interfaces

O backend padrão do Django autenticará com `username` e senha. As telas do ERP e do Control Plane terão o rótulo “Nome do usuário”, autocomplete `username` e exemplos compatíveis com nomes completos. Mensagens de erro não revelarão se o usuário existe.

O Django Admin exibirá e exigirá o nome de usuário nos formulários de criação e edição. Gerenciadores, comandos, seeds e fixtures passarão o nome de usuário explicitamente.

## Banco local

O PostgreSQL definido pelo ambiente local será iniciado via Docker Compose. O banco e o usuário serão criados pelo container quando ausentes. A aplicação aguardará a verificação de saúde e executará `manage.py migrate` contra esse banco. A operação não apagará volumes ou dados existentes.

## Segurança e integridade

- A senha continuará processada exclusivamente pelos hashers do Django.
- A comparação do identificador será insensível a maiúsculas/minúsculas.
- A unicidade será validada na aplicação e protegida no banco.
- Nenhuma credencial será registrada em logs ou incluída na documentação.
- A alteração não modifica isolamento de tenant, MFA ou permissões.

## Testes e aceitação

- Login no ERP e Control Plane funciona com `João Silva` e a senha cadastrada.
- Login por e-mail deixa de funcionar.
- Cadastro de `João Silva` é rejeitado se `joão silva` já existir.
- Nome vazio é rejeitado.
- Usuários preexistentes recebem nomes determinísticos sem perda de relações.
- Django Admin cria e altera usuários com nome de acesso obrigatório.
- `makemigrations --check`, migrations, testes de autenticação e suíte relevante passam no PostgreSQL.
- O banco local responde e não possui migrations pendentes.

## Documentação afetada

Serão atualizados os documentos de arquitetura e operação que descrevem login por e-mail, além das instruções locais de acesso quando aplicáveis.
