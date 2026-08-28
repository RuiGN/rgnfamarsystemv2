# Consolidação da navegação de workspaces no sidebar

## Contexto

Os workspaces de operação, qualidade e workflow passaram a usar um registro
imutável (`WORKSPACES`) e um template compartilhado. O sidebar e os atalhos do
cabeçalho, contudo, ainda repetem títulos, ícones e rotas diretamente nos
templates. Como esses links não são filtrados por permissão, um usuário pode
visualizar um destino que a `WorkspaceView` corretamente responde com HTTP 403.

## Objetivo

Transformar `WorkspaceConfig` na fonte única de metadados de navegação dos
workspaces e entregar ao sidebar e ao cabeçalho apenas destinos autorizados.
A alteração deve preservar as rotas existentes, a aparência Duralux, o menu
responsivo e a navegação dinâmica de módulos e recursos.

## Abordagens consideradas

### 1. Registro central de workspaces — selecionada

Adicionar metadados de navegação a `WorkspaceConfig` e construir no context
processor a coleção de workspaces visíveis. Sidebar e cabeçalho consomem essa
coleção. É a opção com menor risco de divergência futura e aplica autorização
antes da renderização.

### 2. Mapa de navegação separado no context processor

Manter títulos, ícones e nomes de rota em uma nova constante exclusiva do menu.
Exige menos alterações no registro, mas cria uma segunda fonte de verdade que
pode divergir do conteúdo e das permissões do workspace.

### 3. Condições hardcoded nos templates

Adicionar flags individuais como `can_view_quality_workspace`. É uma correção
local, porém aumenta a lógica de autorização na apresentação e exige editar
vários templates para cada novo workspace.

## Arquitetura aprovada

### Configuração

`WorkspaceConfig` receberá:

- `route_name`: nome estável da rota Django;
- `navigation_label`: texto compacto do menu;
- `icon`: classe Feather usada no sidebar e nos atalhos;
- `order`: ordenação explícita da navegação.

O título completo, a descrição, o módulo exigido e o builder continuam no
mesmo objeto imutável. A rota será resolvida no servidor, sem concatenação de
URLs nos templates.

### Context processor

`sidebar_menu` buscará os módulos visíveis uma única vez e derivará:

- `sidebar_workspaces`: workspaces cujo `module_slug` esteja autorizado;
- `dashboard_navigation`: painéis já filtrados por módulo;
- `show_dashboard_navigation`: verdadeiro apenas quando houver painel visível;
- `can_view_workflow_workspace`: usado pelo sino de notificações.

Cada `WorkspaceConfig` exporá sua URL de navegação por uma propriedade que usa
`reverse()`, permitindo que o context processor entregue diretamente uma tupla
de configurações autorizadas, sem dicionários intermediários. Para usuários
anônimos, as coleções permanecem vazias e as flags, falsas. A consulta de
notificações só será executada quando o workspace de workflow estiver
autorizado; nos demais casos, o contador será zero.

### Sidebar

O menu será dividido semanticamente em duas áreas:

1. **Visão geral**: Painéis, Aplicativos e workspaces autorizados;
2. **Módulos**: grupos dinâmicos e seus recursos autorizados.

“Painéis” não será renderizado quando seu submenu estiver vazio. Os workspaces
serão produzidos por um único loop, com ícone, rota e rótulo vindos do registro.
O item da página atual terá as classes visuais existentes e
`aria-current="page"`.

### Cabeçalho

Os atalhos Operação, Qualidade e Fluxo usarão `sidebar_workspaces`; itens sem
permissão não serão renderizados. O sino de workflow será exibido apenas quando
o usuário puder abrir o workspace correspondente, evitando um link que termina
em HTTP 403 e a exposição de um contador inacessível.

## Fluxo de dados

1. Django autentica o usuário e resolve a rota atual.
2. O context processor obtém módulos e recursos visíveis pelo registro atual.
3. O context processor cruza `WORKSPACES` com os módulos autorizados, ordena os
   itens e resolve suas rotas.
4. Sidebar e cabeçalho iteram somente sobre os itens recebidos.
5. A `WorkspaceView` mantém a validação defensiva do módulo ao receber acesso
   direto por URL.

Assim, ocultar um link melhora a experiência, enquanto a view continua sendo a
fronteira efetiva de segurança.

## Tratamento de erros e compatibilidade

- Uma configuração com `route_name` inválido deve falhar durante renderização e
  testes, em vez de produzir um link silenciosamente quebrado.
- Um `module_slug` inexistente torna o workspace invisível e o acesso direto
  permanece protegido pela `WorkspaceView`.
- Os nomes e caminhos de `operations_workspace`, `quality_workspace` e
  `workflow_workspace` não mudam.
- Nenhuma migration ou alteração de banco é necessária.

## Testes e critérios de aceitação

- Usuário sem permissão não vê links de workspaces no sidebar nem no cabeçalho.
- Usuário com permissão de produção vê somente o workspace operacional.
- Superusuário vê os três workspaces na ordem configurada.
- O workspace atual recebe `aria-current="page"` e estado visual ativo.
- O menu Painéis não aparece quando não há dashboards autorizados.
- O sino e a consulta de notificações ficam condicionados ao workflow visível.
- Módulos e recursos dinâmicos continuam filtrados por permissões Django.
- Rotas existentes, responsividade, menu recolhível e scroll permanecem
  cobertos pela suíte atual.

## Fora de escopo

- Redesenhar cores, tipografia ou comportamento do tema Duralux.
- Alterar permissões Django ou regras de acesso dos módulos.
- Reorganizar a ordem interna dos recursos de cada módulo.
- Criar novos workspaces ou dashboards.
