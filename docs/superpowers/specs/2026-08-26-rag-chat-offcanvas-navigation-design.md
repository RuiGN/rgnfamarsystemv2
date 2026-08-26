# Chat RAG em painel lateral e navegação simplificada

## Objetivo

Remover o módulo **Conhecimento RAG** dos pontos de navegação destinados aos usuários e apresentar o assistente RAG global no mesmo formato visual adotado pelo projeto `sistema_assorrp_v2`: botão flutuante que abre um painel lateral Bootstrap pela direita.

## Escopo

### Incluído

- Ocultar **Conhecimento RAG** do menu lateral.
- Ocultar **Conhecimento RAG** da grade da página **Aplicativos**.
- Manter o módulo registrado internamente para que suas rotas, permissões, modelos, APIs e telas administrativas continuem disponíveis.
- Substituir o painel flutuante compacto do chat por um `offcanvas offcanvas-end` do Bootstrap 5.
- Preservar o endpoint `/api/knowledge/chat/` e o comportamento atual de sessão, envio, repetição, nova conversa e apresentação de citações.
- Preservar a exigência da permissão `knowledge.view_ragchatsession` para exibir e utilizar o chat.
- Garantir adaptação para desktop, tablet e celular.

### Não incluído

- Importar o fluxo de geração de relatórios do `sistema_assorrp_v2`.
- Alterar os modelos, serviços, índice ou corpus do RAG.
- Excluir o aplicativo Django `knowledge` ou suas rotas.
- Alterar o chat dedicado dos perfis de agentes de IA, exceto pelos ajustes estritamente necessários para que o JavaScript compartilhado continue compatível.

## Arquitetura

### Visibilidade do módulo

`ModuleConfig` receberá uma propriedade declarativa que indica se o módulo deve aparecer na navegação. O módulo `knowledge` continuará em `MODULES`, mas será marcado como oculto. `get_visible_modules()` excluirá módulos ocultos antes de montar o contexto usado pelo menu lateral e pela página de aplicativos.

Essa decisão preserva `get_module('knowledge')`, `get_resource()` e os recursos internos, ao mesmo tempo que elimina os dois pontos de entrada solicitados.

### Estrutura visual do chat

O partial `templates/includes/rag_chat.html` manterá o elemento raiz e o atributo `data-rag-chat-endpoint`. Dentro dele haverá:

- um botão flutuante circular com `data-bs-toggle="offcanvas"`;
- um painel `offcanvas offcanvas-end` com largura de `560px` e limite de `96vw`;
- cabeçalho com título, descrição e botão Bootstrap de fechamento;
- região rolável de mensagens;
- rodapé fixo do painel com estado, repetição, textarea, nova conversa e envio.

O botão continuará posicionado acima do footer da aplicação. O painel lateral será controlado pelo componente Bootstrap, inclusive animação, backdrop, fechamento por `Esc` e restauração de foco.

### Comportamento JavaScript

`static/js/rag-chat.js` continuará controlando:

- identificação da sessão em `sessionStorage`;
- proteção CSRF;
- envio ao endpoint RAG;
- renderização segura com `textContent`;
- citações e links externos seguros;
- estados de carregamento e erro;
- repetição e início de nova conversa.

O controle manual baseado no atributo `hidden` será removido somente do chat global. O script identificará o painel `offcanvas` e usará os eventos Bootstrap para focar o campo ao abrir. O chat dedicado, que não possui botão flutuante, continuará sendo inicializado normalmente pelo mesmo script.

## Direção visual

A interface seguirá o design system já utilizado pelo RGN Farma:

- botão primário circular de 56 px;
- painel branco com cabeçalho discreto, bordas do tema e hierarquia tipográfica existente;
- mensagens do usuário em azul primário;
- respostas e fontes em superfícies neutras;
- compositor separado por borda, sempre acessível na parte inferior;
- largura quase total em telas pequenas, limitada a `96vw`.

O diferencial visual será o painel lateral contínuo, alinhado ao padrão já aprovado no `sistema_assorrp_v2`, sem introduzir nova paleta ou tipografia.

## Segurança e acessibilidade

- O partial continuará condicionado à autenticação e à permissão `knowledge.view_ragchatsession`.
- Conteúdo retornado pela API continuará inserido como texto, sem HTML remoto.
- Links de fontes continuarão usando `target="_blank"` com `rel="noopener noreferrer"`.
- O `offcanvas` terá título acessível, botão de fechamento, foco coerente e fechamento por teclado fornecidos pelo Bootstrap.
- A região de mensagens continuará com `role="log"` e `aria-live="polite"`.
- Estados de consulta continuarão anunciados por `role="status"`.

## Tratamento de erros

As mensagens atuais para falta de permissão, excesso de solicitações, falha no servidor e validação serão mantidas. O painel permanecerá aberto após erros para permitir repetição. A indisponibilidade de `sessionStorage` continuará sem bloquear o uso do chat.

## Estratégia de testes

O desenvolvimento seguirá TDD com testes para:

1. comprovar que um módulo marcado como oculto permanece no registry, mas não aparece em `get_visible_modules()`;
2. comprovar que **Conhecimento RAG** não aparece no menu nem na página **Aplicativos**, mesmo para um usuário autorizado;
3. comprovar que o chat autorizado renderiza o botão e o painel `offcanvas-end` com o endpoint atual;
4. comprovar que usuários sem permissão continuam sem receber o chat;
5. validar o contrato estrutural do partial e do JavaScript, incluindo ausência do controle global baseado em `hidden` e preservação da renderização segura;
6. validar o posicionamento responsivo do botão acima do footer;
7. executar os testes direcionados de UI, chat, registry e API afetados.

## Critérios de aceitação

- Nenhuma ocorrência visível de **Conhecimento RAG** aparece no menu lateral ou na grade **Aplicativos**.
- O registry e as APIs do módulo `knowledge` continuam funcionais.
- Usuário autenticado com `knowledge.view_ragchatsession` vê o botão flutuante.
- O clique abre um painel lateral pela direita, visualmente equivalente ao padrão do projeto de referência.
- O painel mede até 560 px no desktop e no máximo 96% da largura da tela.
- Envio, nova conversa, repetição, respostas e citações mantêm o comportamento atual.
- Usuário sem permissão não recebe markup nem JavaScript do chat.
- Os testes relevantes passam sem erros e o diff não contém problemas de formatação.

